"""基础问答处理器

处理基于全文上下文的简单问答请求
"""
import json
import asyncio

from app.services.llm_service import llm_service
from app.handlers.ws_utils import ChunkBuffer


async def handle_chat(websocket, state, message, task_key="chat"):
    """异步处理问答（使用全文上下文）"""
    chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
    try:
        async for chunk in llm_service.chat(message, state.paper_context, state.chat_history):
            await chunk_buffer.add(chunk, "chat_chunk")
        # 确保发送所有剩余的 chunk
        await chunk_buffer.flush("chat_chunk")
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
        chunk_buffer.close()
        state.running_tasks.pop(task_key, None)
