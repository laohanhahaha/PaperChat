"""WebSocket 路由

提供论文分析和问答的实时 WebSocket 通信
支持会话持久化和溯源引用

仅负责：WebSocket 连接生命周期管理、消息类型路由分发、调用对应 handler
"""
import json
import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from langchain_community.chat_message_histories import ChatMessageHistory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)
from app.services.auth_service import get_current_user
from app.services.session_service import get_paper_by_id
from app.services.message_service import get_paper_full_text, get_paper_text_preview
from app.handlers.analyze_handler import handle_analyze, handle_deep_analyze
from app.handlers.chat_handler import handle_chat
from app.handlers.rag_handler import handle_rag_chat
from app.handlers.agent_handler import handle_agent_chat
from app.handlers.cross_doc_handler import handle_cross_doc_chat

router = APIRouter(tags=["WebSocket"])


class ChunkBuffer:
    """合并高频 WebSocket chunk 消息，减少发送次数

    性能影响说明：
    - 默认 50ms 的合并间隔对用户体验影响极小（人眼感知延迟约 100ms）
    - 可显著减少 WebSocket 消息数量（通常减少 80-90%）
    - 降低前端 React 重渲染频率，提升整体流畅度
    """
    def __init__(self, websocket, interval_ms=50):
        self.websocket = websocket
        self.interval = interval_ms / 1000  # 转换为秒
        self.buffer = ""
        self.last_flush = time.time()
        self._lock = asyncio.Lock()
        self._closed = False

    async def add(self, chunk: str, msg_type: str = "stream"):
        """添加 chunk 到缓冲区，如果达到间隔时间则自动 flush

        Args:
            chunk: 要发送的文本内容
            msg_type: 消息类型，默认 "stream"，也可用于 "chat_chunk", "rag_chat_chunk" 等
        """
        if self._closed:
            return

        async with self._lock:
            self.buffer += chunk
            now = time.time()
            if now - self.last_flush >= self.interval:
                await self._flush(msg_type)

    async def flush(self, msg_type: str = "stream"):
        """强制刷新缓冲区，发送所有累积的内容"""
        if self._closed:
            return

        async with self._lock:
            await self._flush(msg_type)

    async def _flush(self, msg_type: str):
        """内部刷新方法（需在持有锁的情况下调用）"""
        if self.buffer:
            await self.websocket.send_text(json.dumps({
                "type": msg_type,
                "content": self.buffer
            }))
            self.buffer = ""
            self.last_flush = time.time()

    def close(self):
        """关闭 buffer，不再接受新内容"""
        self._closed = True


async def send_chunk_with_buffer(websocket, chunk_buffer, chunk: str, msg_type: str = "stream"):
    """使用 buffer 发送 chunk 的辅助函数

    如果 chunk_buffer 为 None，则直接发送；否则使用 buffer。
    这样允许 handler 选择是否使用缓冲功能。
    """
    if chunk_buffer is not None:
        await chunk_buffer.add(chunk, msg_type)
    else:
        await websocket.send_text(json.dumps({
            "type": msg_type,
            "content": chunk
        }))


async def verify_websocket_token(token: str = None):
    """验证 WebSocket token，无 token 时降级为默认用户"""
    if not token:
        # 向后兼容：无 token 时使用默认用户（个人使用模式）
        async with AsyncSessionLocal() as db:
            return await get_current_user(db)

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = int(payload.get("sub"))
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
        return None
    except Exception:
        return None


class ConnectionState:
    """WebSocket 连接状态，在各 handler 间共享"""
    def __init__(self):
        self.paper_context = ""
        self.current_paper_id = None
        self.current_session_id = None
        self.current_user_id = None
        self.chat_history = ChatMessageHistory()
        self.running_tasks = {}


async def get_db_session():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default=None)):
    """
    WebSocket 端点 - 论文分析与问答

    参数:
        token: JWT 认证 token（可选，无 token 时降级为默认用户）

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
    user = await verify_websocket_token(token)
    if not user:
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    state = ConnectionState()
    state.current_user_id = user.id

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "analyze":
                text = data.get("text", "")
                paper_id = data.get("paper_id")
                if not text or len(text.strip()) < 50:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "论文内容过短，请提供完整的论文文本"
                    }))
                    continue

                if "analyze" in state.running_tasks:
                    state.running_tasks["analyze"].cancel()

                state.running_tasks["analyze"] = asyncio.create_task(
                    handle_analyze(websocket, state, text, paper_id)
                )

            elif msg_type == "chat":
                message = data.get("message", "")
                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue

                if "chat" in state.running_tasks:
                    state.running_tasks["chat"].cancel()

                state.running_tasks["chat"] = asyncio.create_task(
                    handle_chat(websocket, state, message)
                )

            elif msg_type == "rag_chat":
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                session_id = data.get("session_id")
                user_id = state.current_user_id
                enable_search = data.get("enable_search", False)

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

                state.current_paper_id = paper_id

                if "rag_chat" in state.running_tasks:
                    state.running_tasks["rag_chat"].cancel()

                async def _run_rag_chat():
                    async with AsyncSessionLocal() as db:
                        await handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search)

                state.running_tasks["rag_chat"] = asyncio.create_task(_run_rag_chat())

            elif msg_type == "deep_analyze":
                text = data.get("text", "")
                paper_id = data.get("paper_id")
                if not text or len(text.strip()) < 50:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "论文内容过短，请提供完整的论文文本"
                    }))
                    continue

                if "deep_analyze" in state.running_tasks:
                    state.running_tasks["deep_analyze"].cancel()

                state.running_tasks["deep_analyze"] = asyncio.create_task(
                    handle_deep_analyze(websocket, state, text, paper_id)
                )

            elif msg_type == "agent_chat":
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                paper_ids = data.get("paper_ids", [])

                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue

                if "agent_chat" in state.running_tasks:
                    state.running_tasks["agent_chat"].cancel()

                async def _run_agent_chat():
                    async with AsyncSessionLocal() as db:
                        await handle_agent_chat(websocket, db, state, message, paper_id, paper_ids)

                state.running_tasks["agent_chat"] = asyncio.create_task(_run_agent_chat())

            elif msg_type == "cross_doc_chat":
                message = data.get("message", "")
                paper_ids = data.get("paper_ids", [])
                session_id = data.get("session_id")
                user_id = state.current_user_id

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

                if "cross_doc_chat" in state.running_tasks:
                    state.running_tasks["cross_doc_chat"].cancel()

                async def _run_cross_doc_chat():
                    async with AsyncSessionLocal() as db:
                        await handle_cross_doc_chat(websocket, db, state, message, paper_ids, session_id, user_id)

                state.running_tasks["cross_doc_chat"] = asyncio.create_task(_run_cross_doc_chat())

            elif msg_type == "cancel":
                for key in list(state.running_tasks.keys()):
                    state.running_tasks[key].cancel()
                    del state.running_tasks[key]
                await websocket.send_text(json.dumps({
                    "type": "cancelled",
                    "message": "已取消当前任务"
                }))
                continue

            elif msg_type == "unified_chat":
                """统一聊天入口 - 根据关键词自动路由到不同功能"""
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                paper_ids = data.get("paper_ids", [])
                session_id = data.get("session_id")
                user_id = state.current_user_id
                enable_search = data.get("enable_search", False)

                if "unified" in state.running_tasks:
                    state.running_tasks["unified"].cancel()
                    del state.running_tasks["unified"]

                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue

                # 使用关键词进行意图识别
                from app.services.agent_service import classify_by_keywords
                intent_result = classify_by_keywords(message)

                # 发送意图识别结果给前端
                await websocket.send_text(json.dumps({
                    "type": "intent_detected",
                    "intent": intent_result.get("intent", "simple_qa") if intent_result.get("matched") else "simple_qa",
                    "tool": intent_result.get("tool", "rag_chat") if intent_result.get("matched") else "rag_chat",
                    "confidence": intent_result.get("confidence", "low"),
                    "matched": intent_result.get("matched", False)
                }))

                # 根据意图路由到不同的处理函数
                if intent_result.get("matched"):
                    tool = intent_result.get("tool")

                    if tool == "analyze_paper":
                        # 章节概述
                        if paper_id:
                            async with AsyncSessionLocal() as db:
                                paper = await get_paper_by_id(db, paper_id)
                                if paper:
                                    paper_text = await get_paper_text_preview(db, paper_id)
                                    if paper_text:
                                        state.running_tasks["unified"] = asyncio.create_task(
                                            handle_analyze(websocket, state, paper_text, paper_id, task_key="unified")
                                        )
                                    else:
                                        await websocket.send_text(json.dumps({
                                            "type": "error",
                                            "message": "论文内容不存在，请先上传并解析论文"
                                        }))
                                else:
                                    await websocket.send_text(json.dumps({
                                        "type": "error",
                                        "message": "论文不存在"
                                    }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "需要提供 paper_id"
                            }))

                    elif tool == "deep_analyze_paper":
                        # 深度分析
                        if paper_id:
                            async with AsyncSessionLocal() as db:
                                paper = await get_paper_by_id(db, paper_id)
                                if paper:
                                    paper_text = await get_paper_text_preview(db, paper_id)
                                    if paper_text:
                                        state.running_tasks["unified"] = asyncio.create_task(
                                            handle_deep_analyze(websocket, state, paper_text, paper_id, task_key="unified")
                                        )
                                    else:
                                        await websocket.send_text(json.dumps({
                                            "type": "error",
                                            "message": "论文内容不存在，请先上传并解析论文"
                                        }))
                                else:
                                    await websocket.send_text(json.dumps({
                                        "type": "error",
                                        "message": "论文不存在"
                                    }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "需要提供 paper_id"
                            }))

                    elif tool == "cross_doc_chat":
                        # 跨文档问答
                        if not paper_ids or len(paper_ids) == 0:
                            if paper_id:
                                paper_ids = [paper_id]
                            else:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "跨文档问答需要提供论文列表"
                                }))
                                continue

                        async def _run_unified_cross_doc():
                            async with AsyncSessionLocal() as db:
                                await handle_cross_doc_chat(websocket, db, state, message, paper_ids, session_id, user_id, task_key="unified")

                        state.running_tasks["unified"] = asyncio.create_task(_run_unified_cross_doc())

                    elif tool == "rag_chat" or tool == "search_text":
                        # RAG 问答
                        if not paper_id:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "RAG 问答需要提供 paper_id"
                            }))
                            continue

                        async def _run_unified_rag():
                            async with AsyncSessionLocal() as db:
                                await handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search, task_key="unified")

                        state.running_tasks["unified"] = asyncio.create_task(_run_unified_rag())
                    else:
                        # 其他工具，暂不支持直接调用，使用 RAG 问答
                        if not paper_id:
                            paper_id = paper_ids[0] if paper_ids else None

                        if paper_id:
                            async def _run_unified_rag_fallback():
                                async with AsyncSessionLocal() as db:
                                    await handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search, task_key="unified")

                            state.running_tasks["unified"] = asyncio.create_task(_run_unified_rag_fallback())
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "无法确定论文，请提供 paper_id"
                            }))
                else:
                    # 没有匹配到特定意图，使用 RAG 问答
                    if not paper_id:
                        paper_id = paper_ids[0] if paper_ids else None

                    if paper_id:
                        async def _run_unified_rag_default():
                            async with AsyncSessionLocal() as db:
                                await handle_rag_chat(websocket, db, state, message, paper_id, session_id, user_id, enable_search, task_key="unified")

                        state.running_tasks["unified"] = asyncio.create_task(_run_unified_rag_default())
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "请先选择一篇论文再进行问答"
                        }))

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}"
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理所有运行中的任务
        for task in state.running_tasks.values():
            task.cancel()
        try:
            await websocket.close()
        except:
            pass
