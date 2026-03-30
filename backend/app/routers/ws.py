"""WebSocket 路由

提供论文分析和问答的实时 WebSocket 通信
支持会话持久化和溯源引用
"""
import json
import asyncio
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.services.llm_service import llm_service, RAG_CHAT_SYSTEM_PROMPT, RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT
from app.services.agent_service import agent_service
from app.services.search_service import search_service
from app.database import AsyncSessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.models.paper import Paper

router = APIRouter(tags=["WebSocket"])


async def get_db_session():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_or_create_session(db: AsyncSession, session_id: int, user_id: int, paper_id: int = None) -> ChatSession:
    """获取或创建会话"""
    if session_id:
        # 查找现有会话
        result = await db.execute(
            select(ChatSession).where(
                and_(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id
                )
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session
    
    # 创建新会话
    new_session = ChatSession(
        user_id=user_id,
        paper_id=paper_id,
        title="新对话"
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session


async def load_chat_history(db: AsyncSession, session_id: int, limit: int = 10) -> ChatMessageHistory:
    """从数据库加载会话历史"""
    history = ChatMessageHistory()
    
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()
    
    # 按时间正序排列
    for msg in reversed(messages):
        if msg.role == "user":
            history.add_user_message(msg.content)
        else:
            history.add_ai_message(msg.content)
    
    return history


async def save_message(db: AsyncSession, session_id: int, role: str, content: str, sources: list = None):
    """保存消息到数据库"""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources=sources
    )
    db.add(message)
    await db.commit()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点 - 论文分析与问答
    
    消息格式:
        - 分析论文: {"type": "analyze", "text": "论文文本内容"}
        - 问答: {"type": "chat", "message": "用户问题"}
        - RAG问答: {"type": "rag_chat", "message": "用户问题", "paper_id": 123, "session_id": 456, "user_id": 789, "enable_search": false}
        - 跨文档问答: {"type": "cross_doc_chat", "message": "用户问题", "paper_ids": [1, 2, 3], "session_id": 456, "user_id": 789}
        - 深度分析: {"type": "deep_analyze", "text": "论文文本内容"}
        - Agent问答: {"type": "agent_chat", "message": "用户问题", "paper_id": 123, "paper_ids": [1, 2, 3]}
    
    响应格式:
        - 分析片段: {"type": "analyze_chunk", "data": "..."}
        - 问答片段: {"type": "chat_chunk", "data": "..."}
        - RAG问答片段: {"type": "rag_chat_chunk", "content": "..."}
        - 跨文档问答片段: {"type": "cross_doc_chunk", "content": "..."}
        - 跨文档引用来源: {"type": "cross_doc_sources", "sources": [{"text": "...", "pages": [1], "paper_id": 1, "score": 0.9}]}
        - 引用来源: {"type": "rag_sources", "sources": [...]}
        - 搜索状态: {"type": "search_status", "status": "searching|completed", "results_count": N}
        - 完成: {"type": "done", "channel": "analyze|chat|rag_chat|cross_doc_chat", "session_id": 456}
        - 错误: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    # 每个连接维护独立状态
    paper_context = ""
    current_paper_id = None
    current_session_id = None
    current_user_id = None
    chat_history = ChatMessageHistory()
    # 跟踪正在运行的任务
    running_tasks = {}
    
    async def _extract_keywords_async(paper_id, text, ws):
        """异步提取关键词，不阻塞主分析流程"""
        try:
            async with AsyncSessionLocal() as kw_db:
                result = await kw_db.execute(select(Paper).where(Paper.id == paper_id))
                paper_obj = result.scalar_one_or_none()
                if paper_obj and not paper_obj.tags:
                    keywords = await asyncio.wait_for(
                        llm_service.extract_keywords(
                            text=text[:3000],
                            title=paper_obj.title or "",
                            max_keywords=5
                        ),
                        timeout=15.0  # 15秒超时
                    )
                    if keywords:
                        paper_obj.tags = json.dumps(keywords, ensure_ascii=False)
                        await kw_db.commit()
                        try:
                            await ws.send_text(json.dumps({
                                "type": "keywords_result",
                                "keywords": keywords,
                                "paper_id": paper_id
                            }))
                        except:
                            pass  # WebSocket 可能已关闭
                elif paper_obj and paper_obj.tags:
                    # 已有关键词，直接发送
                    try:
                        existing_keywords = json.loads(paper_obj.tags)
                        await ws.send_text(json.dumps({
                            "type": "keywords_result",
                            "keywords": existing_keywords,
                            "paper_id": paper_id
                        }))
                    except:
                        pass
        except asyncio.TimeoutError:
            print(f"[WARN] 论文 {paper_id} 关键词提取超时")
        except Exception as e:
            print(f"[WARN] 论文 {paper_id} 关键词提取失败: {e}")
    
    async def handle_analyze(text, paper_id=None):
        """异步处理论文分析"""
        nonlocal paper_context
        paper_context = text
        chat_history.clear()
        
        full_response = ""
        try:
            async for chunk in llm_service.analyze_paper(text):
                full_response += chunk
                await websocket.send_text(json.dumps({
                    "type": "analyze_chunk",
                    "data": chunk
                }))
            
            # 保存章节概述缓存
            if paper_id:
                try:
                    async with AsyncSessionLocal() as cache_db:
                        result = await cache_db.execute(select(Paper).where(Paper.id == paper_id))
                        paper = result.scalar_one_or_none()
                        if paper:
                            paper.section_analysis = full_response
                            paper.last_analyzed_at = datetime.now()
                            await cache_db.commit()
                except Exception as e:
                    print(f"[WARN] 保存章节概述缓存失败: {e}")
            
            # 先发送 done 消息，确保前端立即结束加载状态
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "analyze"
            }))
            
            # 异步提取关键词（不阻塞主流程）
            if paper_id:
                asyncio.create_task(_extract_keywords_async(paper_id, text, websocket))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"分析失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("analyze", None)
    
    async def handle_chat(message):
        """异步处理问答（使用全文上下文）"""
        try:
            async for chunk in llm_service.chat(message, paper_context, chat_history):
                await websocket.send_text(json.dumps({
                    "type": "chat_chunk",
                    "data": chunk
                }))
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "chat"
            }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"问答失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("chat", None)
    
    async def handle_rag_chat(message, paper_id, session_id, user_id, enable_search=False):
        """异步处理RAG问答（使用检索上下文，支持会话持久化和联网搜索）"""
        nonlocal current_session_id, current_paper_id, current_user_id
        
        current_paper_id = paper_id
        current_user_id = user_id
        
        # 创建数据库会话
        async with AsyncSessionLocal() as db:
            try:
                # 1. 获取或创建会话
                session = await get_or_create_session(db, session_id, user_id, paper_id)
                current_session_id = session.id
                
                # 2. 保存用户消息
                await save_message(db, session.id, "user", message)
                
                # 3. 加载会话历史（最近10条）
                history = await load_chat_history(db, session.id, limit=10)
                
                # 4. RAG 检索
                from app.services.rag_service import rag_service
                relevant_chunks = await rag_service.search(paper_id, message, top_k=5)
                
                # 5. 网络搜索（如果启用）
                web_results = []
                if enable_search:
                    # 推送搜索状态
                    await websocket.send_text(json.dumps({
                        "type": "search_status",
                        "status": "searching"
                    }))
                    # 执行搜索
                    web_results = await search_service.search(message, max_results=5)
                    # 推送搜索完成
                    await websocket.send_text(json.dumps({
                        "type": "search_status",
                        "status": "completed",
                        "results_count": len(web_results)
                    }))
                
                if not relevant_chunks and not web_results:
                    # 如果没有检索到内容也没有搜索结果
                    no_content_msg = "抱歉，未能从论文中检索到相关内容，网络搜索也未返回结果。请尝试重新表述问题。"
                    await websocket.send_text(json.dumps({
                        "type": "rag_chat_chunk",
                        "content": no_content_msg
                    }))
                    await save_message(db, session.id, "assistant", no_content_msg, [])
                    await websocket.send_text(json.dumps({
                        "type": "done",
                        "channel": "rag_chat",
                        "session_id": session.id
                    }))
                    return
                
                # 6. 组装引用来源
                sources = [
                    {
                        "type": "paper",
                        "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                        "pages": chunk["pages"],
                        "score": chunk["score"]
                    }
                    for chunk in relevant_chunks
                ]
                
                # 添加网络来源
                for wr in web_results:
                    sources.append({
                        "type": "web",
                        "title": wr.get("title", ""),
                        "href": wr.get("href", ""),
                        "text": wr.get("body", "")[:200] + "..." if len(wr.get("body", "")) > 200 else wr.get("body", "")
                    })
                
                # 7. 组装上下文
                from langchain_core.messages import SystemMessage
                
                if enable_search and web_results:
                    # 有网络搜索结果，使用合并提示词
                    # 组装论文上下文
                    paper_context_parts = []
                    for chunk in relevant_chunks:
                        pages_str = ",".join(map(str, chunk['pages'])) if chunk['pages'] else "未知"
                        paper_context_parts.append(f"[来源: 第{pages_str}页]\n{chunk['text']}")
                    paper_context = "\n\n---\n\n".join(paper_context_parts) if paper_context_parts else "无相关论文内容"
                    
                    # 组装网络上下文
                    web_context_parts = []
                    for i, wr in enumerate(web_results, 1):
                        web_context_parts.append(f"[{i}] {wr.get('title', '未知标题')}\n{wr.get('body', '')}\n来源: {wr.get('href', '')}")
                    web_context = "\n\n---\n\n".join(web_context_parts)
                    
                    # 使用带搜索的系统提示词
                    system_content = RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT.format(
                        paper_context=paper_context,
                        web_context=web_context
                    )
                else:
                    # 仅使用论文内容
                    context_parts = []
                    for chunk in relevant_chunks:
                        pages_str = ",".join(map(str, chunk['pages'])) if chunk['pages'] else "未知"
                        context_parts.append(f"[来源: 第{pages_str}页]\n{chunk['text']}")
                    context = "\n\n---\n\n".join(context_parts)
                    
                    system_content = RAG_CHAT_SYSTEM_PROMPT.format(context=context)
                
                # 8. 构建消息
                messages = [SystemMessage(content=system_content)]
                messages.extend(history.messages)
                messages.append(HumanMessage(content=message))
                
                # 9. 流式获取回复
                full_response = ""
                async for chunk in llm_service.llm.astream(messages):
                    if chunk.content:
                        full_response += chunk.content
                        await websocket.send_text(json.dumps({
                            "type": "rag_chat_chunk",
                            "content": chunk.content
                        }))
                
                # 10. 发送引用来源
                await websocket.send_text(json.dumps({
                    "type": "rag_sources",
                    "sources": sources
                }))
                
                # 11. 保存 assistant 消息到数据库
                await save_message(db, session.id, "assistant", full_response, sources)
                
                # 12. 更新会话标题（如果是第一条消息）
                result = await db.execute(
                    select(ChatMessage).where(ChatMessage.session_id == session.id)
                )
                all_messages = result.scalars().all()
                if len(all_messages) <= 2 and session.title == "新对话":
                    # 使用用户问题的前20字作为标题
                    session.title = message[:30] + "..." if len(message) > 30 else message
                    await db.commit()
                
                # 13. 发送完成信号
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "channel": "rag_chat",
                    "session_id": session.id
                }))
                
            except asyncio.CancelledError:
                pass
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"RAG问答失败: {str(e)}"
                }))
            finally:
                running_tasks.pop("rag_chat", None)
    
    async def handle_deep_analyze(text, paper_id=None):
        """异步处理深度分析"""
        nonlocal paper_context
        paper_context = text
        chat_history.clear()
        
        full_response = ""
        try:
            async for chunk in llm_service.deep_analyze_paper(text):
                full_response += chunk
                await websocket.send_text(json.dumps({
                    "type": "deep_analyze_chunk",
                    "data": chunk
                }))
            
            # 保存深度分析缓存
            if paper_id:
                try:
                    async with AsyncSessionLocal() as cache_db:
                        result = await cache_db.execute(select(Paper).where(Paper.id == paper_id))
                        paper = result.scalar_one_or_none()
                        if paper:
                            paper.deep_analysis = full_response
                            paper.last_analyzed_at = datetime.now()
                            await cache_db.commit()
                except Exception as e:
                    print(f"[WARN] 保存深度分析缓存失败: {e}")
            
            # 先发送 done 消息，确保前端立即结束加载状态
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "deep_analyze"
            }))
            
            # 异步提取关键词（不阻塞主流程）
            if paper_id:
                asyncio.create_task(_extract_keywords_async(paper_id, text, websocket))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"深度分析失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("deep_analyze", None)
    
    async def handle_agent_chat(message, paper_id, paper_ids):
        """异步处理 Agent 智能问答
        
        Agent 模式：意图识别 -> 任务规划 -> 逐步执行 -> 结果聚合
        """
        db = None
        try:
            # 创建数据库会话
            db = AsyncSessionLocal()
            
            # 1. 意图识别
            intent = await agent_service.classify_intent(message)
            await websocket.send_text(json.dumps({
                "type": "agent_intent",
                "intent": intent
            }))
            
            # 2. 任务规划
            context = {"paper_id": paper_id, "paper_ids": paper_ids}
            plan = await agent_service.plan_tasks(message, intent, context)
            await websocket.send_text(json.dumps({
                "type": "agent_plan",
                "plan": plan
            }))
            
            # 3. 逐步执行
            context["db"] = db
            context["original_question"] = message
            
            async for progress in agent_service.execute_plan(plan, context):
                if progress["type"] == "step_start":
                    await websocket.send_text(json.dumps({
                        "type": "agent_step",
                        **progress
                    }))
                elif progress["type"] == "step_result":
                    await websocket.send_text(json.dumps({
                        "type": "agent_step_result",
                        **progress
                    }))
                elif progress["type"] == "final_answer_chunk":
                    await websocket.send_text(json.dumps({
                        "type": "agent_answer_chunk",
                        "content": progress["content"]
                    }))
            
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": "agent_chat"
            }))
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Agent 问答失败: {str(e)}"
            }))
        finally:
            running_tasks.pop("agent_chat", None)
            if db:
                await db.close()

    async def handle_cross_doc_chat(message, paper_ids, session_id, user_id):
        """异步处理跨文档 RAG 问答"""
        nonlocal current_session_id, current_paper_id, current_user_id
        
        current_user_id = user_id
        
        # 创建数据库会话
        async with AsyncSessionLocal() as db:
            try:
                # 1. 获取或创建会话
                session = await get_or_create_session(db, session_id, user_id, paper_id=None)
                current_session_id = session.id
                
                # 2. 保存用户消息（附带 paper_ids 信息）
                await save_message(db, session.id, "user", message, {"paper_ids": paper_ids})
                
                # 3. 加载会话历史（最近10条）
                history = await load_chat_history(db, session.id, limit=10)
                
                # 4. 跨文档 RAG 检索
                from app.services.rag_service import rag_service
                results = await rag_service.search_multiple_papers(paper_ids, message, top_k=8)
                
                if not results:
                    # 如果没有检索到内容
                    no_content_msg = "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。"
                    await websocket.send_text(json.dumps({
                        "type": "cross_doc_chunk",
                        "content": no_content_msg
                    }))
                    await save_message(db, session.id, "assistant", no_content_msg, [])
                    await websocket.send_text(json.dumps({
                        "type": "done",
                        "channel": "cross_doc_chat",
                        "session_id": session.id
                    }))
                    return
                
                # 5. 组装引用来源（附带 paper_id）
                sources = [
                    {
                        "text": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                        "pages": r["pages"],
                        "paper_id": r["paper_id"],
                        "score": r["score"]
                    }
                    for r in results
                ]
                
                # 6. 发送引用来源
                await websocket.send_text(json.dumps({
                    "type": "cross_doc_sources",
                    "sources": sources
                }))
                
                # 7. 流式获取回复
                full_response = ""
                async for chunk in llm_service.chat_cross_doc(message, paper_ids, history, top_k=8):
                    full_response += chunk
                    await websocket.send_text(json.dumps({
                        "type": "cross_doc_chunk",
                        "content": chunk
                    }))
                
                # 8. 保存 assistant 消息到数据库
                await save_message(db, session.id, "assistant", full_response, sources)
                
                # 9. 更新会话标题（如果是第一条消息）
                result = await db.execute(
                    select(ChatMessage).where(ChatMessage.session_id == session.id)
                )
                all_messages = result.scalars().all()
                if len(all_messages) <= 2 and session.title == "新对话":
                    # 使用用户问题的前30字作为标题
                    session.title = message[:30] + "..." if len(message) > 30 else message
                    await db.commit()
                
                # 10. 发送完成信号
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "channel": "cross_doc_chat",
                    "session_id": session.id
                }))
                
            except asyncio.CancelledError:
                pass
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"跨文档问答失败: {str(e)}"
                }))
            finally:
                running_tasks.pop("cross_doc_chat", None)
    
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            
            if msg_type == "analyze":
                text = data.get("text", "")
                paper_id = data.get("paper_id")  # 获取 paper_id
                if not text or len(text.strip()) < 50:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "论文内容过短，请提供完整的论文文本"
                    }))
                    continue
            
                # 取消之前正在进行的分析
                if "analyze" in running_tasks:
                    running_tasks["analyze"].cancel()
            
                # 启动新的异步分析任务
                running_tasks["analyze"] = asyncio.create_task(handle_analyze(text, paper_id))
            
            elif msg_type == "chat":
                message = data.get("message", "")
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue
                
                # 取消之前正在进行的问答
                if "chat" in running_tasks:
                    running_tasks["chat"].cancel()
                
                # 启动新的异步问答任务
                running_tasks["chat"] = asyncio.create_task(handle_chat(message))
            
            elif msg_type == "rag_chat":
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                session_id = data.get("session_id")  # 可选
                user_id = 1  # 使用默认用户（个人使用模式）
                enable_search = data.get("enable_search", False)  # 是否启用联网搜索
                
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue
                
                if not paper_id:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "RAG问答需要提供 paper_id"
                    }))
                    continue
                
                # 更新当前论文ID
                current_paper_id = paper_id
                
                # 取消之前正在进行的RAG问答
                if "rag_chat" in running_tasks:
                    running_tasks["rag_chat"].cancel()
                
                # 启动新的异步RAG问答任务
                running_tasks["rag_chat"] = asyncio.create_task(
                    handle_rag_chat(message, paper_id, session_id, user_id, enable_search)
                )
            
            elif msg_type == "deep_analyze":
                text = data.get("text", "")
                paper_id = data.get("paper_id")  # 获取 paper_id
                if not text or len(text.strip()) < 50:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "论文内容过短，请提供完整的论文文本"
                    }))
                    continue
            
                # 取消之前正在进行的深度分析
                if "deep_analyze" in running_tasks:
                    running_tasks["deep_analyze"].cancel()
            
                # 启动新的异步深度分析任务
                running_tasks["deep_analyze"] = asyncio.create_task(handle_deep_analyze(text, paper_id))
            
            elif msg_type == "agent_chat":
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                paper_ids = data.get("paper_ids", [])  # 多论文场景
                
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue
                
                # 取消之前正在进行的 Agent 问答
                if "agent_chat" in running_tasks:
                    running_tasks["agent_chat"].cancel()
                
                # 启动新的异步 Agent 问答任务
                running_tasks["agent_chat"] = asyncio.create_task(
                    handle_agent_chat(message, paper_id, paper_ids)
                )
            
            elif msg_type == "cross_doc_chat":
                message = data.get("message", "")
                paper_ids = data.get("paper_ids", [])
                session_id = data.get("session_id")
                user_id = 1  # 使用默认用户（个人使用模式）
                
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue
                
                if not paper_ids or len(paper_ids) == 0:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "跨文档问答需要提供 paper_ids"
                    }))
                    continue
                
                # 取消之前正在进行的跨文档问答
                if "cross_doc_chat" in running_tasks:
                    running_tasks["cross_doc_chat"].cancel()
                
                # 启动新的异步跨文档问答任务
                running_tasks["cross_doc_chat"] = asyncio.create_task(
                    handle_cross_doc_chat(message, paper_ids, session_id, user_id)
                )
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}"
                }))
    
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # 清理所有运行中的任务
        for task in running_tasks.values():
            task.cancel()
        try:
            await websocket.close()
        except:
            pass
