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
from app.handlers.unified_handler import handle_unified_chat

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
                """统一聊天入口 - 路由到 unified_handler（21种意图 + ReAct + 安全检测）"""
                message = data.get("message", "")
                paper_id = data.get("paper_id")
                paper_ids = data.get("paper_ids", [])
                session_id = data.get("session_id")
                user_id = state.current_user_id
                enable_search = data.get("enable_search", False)
                forced_tool = data.get("forced_tool")        # 可选：强制指定工具
                thinking_mode = data.get("thinking_mode", "quick")  # "quick" 或 "deep"

                if "unified" in state.running_tasks:
                    state.running_tasks["unified"].cancel()
                    del state.running_tasks["unified"]

                if not message:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "消息不能为空"
                    }))
                    continue

                # === 新版：路由到 unified_handler（21种意图、ReAct循环、安全检测）===
                state.running_tasks["unified"] = asyncio.create_task(
                    handle_unified_chat(
                        websocket=websocket,
                        state=state,
                        message=message,
                        paper_id=paper_id,
                        paper_ids=paper_ids,
                        session_id=session_id,
                        user_id=user_id,
                        enable_search=enable_search,
                        forced_tool=forced_tool,
                        thinking_mode=thinking_mode,
                        task_key="unified",
                        message_data=data,
                    )
                )

                # [DEPRECATED] 旧版内联路由，已被 unified_handler 替代
                # 旧版只支持 13 种意图、5 个 handler，无 ReAct 循环和安全检测
                # 如需回滚，注释掉上方新版代码块，取消注释以下代码:
                #
                # from app.services.agent_service import classify_by_keywords
                # intent_result = classify_by_keywords(message)
                # await websocket.send_text(json.dumps({
                #     "type": "intent_detected",
                #     "intent": intent_result.get("intent", "simple_qa") if intent_result.get("matched") else "simple_qa",
                #     "tool": intent_result.get("tool", "rag_chat") if intent_result.get("matched") else "rag_chat",
                #     "confidence": intent_result.get("confidence", "low"),
                #     "matched": intent_result.get("matched", False)
                # }))
                # if intent_result.get("matched"):
                #     tool = intent_result.get("tool")
                #     if tool == "analyze_paper":
                #         # ... 旧版 analyze_paper 路由逻辑 ...
                #         pass
                #     elif tool == "deep_analyze_paper":
                #         pass  # ... 旧版 deep_analyze_paper 路由逻辑 ...
                #     elif tool == "cross_doc_chat":
                #         pass  # ... 旧版 cross_doc_chat 路由逻辑 ...
                #     elif tool == "rag_chat" or tool == "search_text":
                #         pass  # ... 旧版 RAG 路由逻辑 ...
                #     else:
                #         pass  # ... 旧版 fallback 到 RAG ...
                # else:
                #     pass  # ... 旧版默认 RAG 路由 ...

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
