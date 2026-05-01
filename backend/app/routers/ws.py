"""WebSocket 路由

提供论文分析和问答的实时 WebSocket 通信
支持会话持久化和溯源引用

仅负责：WebSocket 连接生命周期管理、消息类型路由分发、调用对应 handler
"""
import json
import asyncio
import logging
import os
import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.database import AsyncSessionLocal
from app.routers.ws_state import ConnectionState
from app.routers.ws_auth import verify_websocket_token
from app.handlers.analyze_handler import handle_analyze, handle_deep_analyze
from app.handlers.chat_handler import handle_chat
from app.handlers.rag_handler import handle_rag_chat
from app.handlers.agent_handler import handle_agent_chat
from app.handlers.cross_doc_handler import handle_cross_doc_chat
from app.handlers.unified_handler import handle_unified_chat, handle_cost_confirmation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _load_uploaded_images(images_meta: list) -> list[dict]:
    """从 uploads 目录加载图片数据
    
    性能: 单张 < 10ms（本地文件读取）
    """
    loaded = []
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for img in images_meta:
        image_id = img.get("image_id", "")
        # 优先读取压缩版，其次原图
        for suffix in [".jpg", "_original.jpg", "_original.png"]:
            path = os.path.join(base_dir, "uploads", "images", f"{image_id}{suffix}")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                loaded.append({
                    "image_id": image_id,
                    "data": data,
                    "type": img.get("type", "image/jpeg"),
                    "name": img.get("name", ""),
                })
                break
    return loaded


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

    # WS permessage-deflate 压缩已在 uvicorn 层启用（run.py: ws_per_message_deflate=True）
    # Starlette 不支持在 accept() 级别直接配置压缩，压缩协商由 uvicorn ASGI 服务器处理
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

            elif msg_type == "cost_confirmed":
                """费用确认响应 — 用户点击确认或取消"""
                confirmed = data.get("confirmed", False)

                if "unified" in state.running_tasks:
                    state.running_tasks["unified"].cancel()
                    del state.running_tasks["unified"]

                state.running_tasks["unified"] = asyncio.create_task(
                    handle_cost_confirmation(websocket, confirmed, state)
                )

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

                # 加载用户上传的图片
                images_meta = data.get("images", [])
                loaded_images = _load_uploaded_images(images_meta)

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
                        images=loaded_images,
                    )
                )

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
