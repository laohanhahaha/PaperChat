"""RAG 问答处理器

处理基于检索增强生成的问答请求
"""
import json
import asyncio

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_service import llm_service, RAG_CHAT_SYSTEM_PROMPT, RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT
from app.services.search_service import search_service
from app.services.rag_service import rag_service
from app.services.session_service import get_or_create_session, auto_title
from app.services.event_bus import event_bus, Event, EventTypes
from app.services.message_service import (
    save_message, load_chat_history,
    has_paper_text_blocks, get_paper_text_blocks
)
from app.routers.ws import ChunkBuffer


async def extract_keywords_async(paper_id, text, ws):
    """异步提取关键词，不阻塞主分析流程

    委托 session_service 处理数据库操作和 LLM 调用
    """
    from app.services.session_service import extract_and_save_keywords
    await extract_and_save_keywords(paper_id, text, ws)


async def handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search=False, task_key="rag_chat"):
    """异步处理RAG问答（使用检索上下文，支持会话持久化和联网搜索）"""
    state.current_paper_id = paper_id
    state.current_user_id = user_id

    try:
        # 1. 获取或创建会话
        session = await get_or_create_session(db, session_id, user_id, paper_id)
        state.current_session_id = session.id

        # 2. 保存用户消息
        await save_message(db, session.id, "user", message)

        # 3. 加载会话历史（最近10条）
        history = await load_chat_history(db, session.id, limit=10)

        # 4. RAG 检索
        relevant_chunks = await rag_service.search(paper_id, message, top_k=5)

        # 如果没有检索到内容，尝试检查并重建索引
        if not relevant_chunks:
            has_blocks = await has_paper_text_blocks(db, paper_id)

            if has_blocks:
                if not rag_service.try_start_indexing(paper_id):
                    # 已在索引中
                    await websocket.send_text(json.dumps({
                        "type": "index_status", "status": "rebuilding",
                        "message": "论文索引正在构建中，将使用论文原文为您回答..."
                    }))
                else:
                    # 成功标记，启动后台任务
                    all_blocks = await get_paper_text_blocks(db, paper_id)
                    blocks_data = [{"text": b.text, "page_number": b.page_number, "metadata": {"y0": b.y0}} for b in all_blocks]

                    # 发布索引重建开始事件
                    asyncio.create_task(event_bus.publish(Event(
                        type=EventTypes.INDEX_REBUILD_STARTED,
                        data={"paper_id": paper_id}
                    )))

                    async def _rebuild_and_notify():
                        try:
                            await rag_service.reindex_paper(paper_id, blocks_data)

                            # 发布索引重建完成事件
                            asyncio.create_task(event_bus.publish(Event(
                                type=EventTypes.INDEX_REBUILD_COMPLETED,
                                data={"paper_id": paper_id}
                            )))

                            await websocket.send_text(json.dumps({
                                "type": "index_status", "status": "ready",
                                "message": "论文索引构建完成"
                            }))
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error(f"索引重建失败: {e}")
                        finally:
                            rag_service.finish_indexing(paper_id)

                    asyncio.create_task(_rebuild_and_notify())
                    await websocket.send_text(json.dumps({
                        "type": "index_status", "status": "rebuilding",
                        "message": "正在后台构建索引，将使用论文原文为您回答..."
                    }))

                # 降级方案：使用论文文本预览作为上下文
                from app.services.message_service import get_paper_text_preview
                paper_preview = await get_paper_text_preview(db, paper_id)
                # 将预览文本作为伪检索结果
                if paper_preview:
                    relevant_chunks = [{
                        "text": paper_preview,
                        "score": 1.0,
                        "pages": [],
                        "chunk_index": 0
                    }]
            else:
                # 论文没有文本块，可能还没解析完成
                error_msg = "论文尚未解析完成或内容为空，请稍后再试。如果问题持续，请尝试重新上传论文。"
                await websocket.send_text(json.dumps({
                    "type": "rag_chat_chunk",
                    "content": error_msg
                }))
                await save_message(db, session.id, "assistant", error_msg, [])
                await websocket.send_text(json.dumps({
                    "type": "done",
                    "channel": "rag_chat",
                    "session_id": session.id
                }))
                return

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

        # 9. 流式获取回复（使用 ChunkBuffer 合并高频消息）
        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            async for chunk in llm_service.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    await chunk_buffer.add(chunk.content, "rag_chat_chunk")
            # 确保发送所有剩余的 chunk
            await chunk_buffer.flush("rag_chat_chunk")
        finally:
            chunk_buffer.close()

        # 10. 发送引用来源
        await websocket.send_text(json.dumps({
            "type": "rag_sources",
            "sources": sources
        }))

        # 11. 保存 assistant 消息到数据库
        await save_message(db, session.id, "assistant", full_response, sources)

        # 12. 更新会话标题
        await auto_title(db, session, message)

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
        state.running_tasks.pop(task_key, None)
