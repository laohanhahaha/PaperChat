"""论文分析处理器

处理论文章节概述和深度分析请求
"""
import json
import asyncio

from app.services.llm_service import llm_service
from app.services.session_service import save_paper_section_analysis, save_paper_deep_analysis
from app.handlers.rag_handler import extract_keywords_async
from app.routers.ws import ChunkBuffer


async def handle_analyze(websocket, state, text, paper_id=None, task_key="analyze"):
    """异步处理论文分析"""
    state.paper_context = text
    state.chat_history.clear()

    chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
    full_response = ""
    try:
        async for chunk in llm_service.analyze_paper(text):
            full_response += chunk
            await chunk_buffer.add(chunk, "analyze_chunk")

        # 保存章节概述缓存
        if paper_id:
            await save_paper_section_analysis(paper_id, full_response)

        # 确保发送所有剩余的 chunk
        await chunk_buffer.flush("analyze_chunk")

        # 先发送 done 消息，确保前端立即结束加载状态
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "analyze"
        }))

        # 异步提取关键词（不阻塞主流程）
        if paper_id:
            asyncio.create_task(extract_keywords_async(paper_id, text, websocket))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"分析失败: {str(e)}"
        }))
    finally:
        chunk_buffer.close()
        state.running_tasks.pop(task_key, None)


async def handle_deep_analyze(websocket, state, text, paper_id=None, task_key="deep_analyze"):
    """异步处理深度分析"""
    state.paper_context = text
    state.chat_history.clear()

    chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
    full_response = ""
    try:
        async for chunk in llm_service.deep_analyze_paper(text):
            full_response += chunk
            await chunk_buffer.add(chunk, "deep_analyze_chunk")

        # 保存深度分析缓存
        if paper_id:
            await save_paper_deep_analysis(paper_id, full_response)

        # 确保发送所有剩余的 chunk
        await chunk_buffer.flush("deep_analyze_chunk")

        # 先发送 done 消息，确保前端立即结束加载状态
        await websocket.send_text(json.dumps({
            "type": "done",
            "channel": "deep_analyze"
        }))

        # 异步提取关键词（不阻塞主流程）
        if paper_id:
            asyncio.create_task(extract_keywords_async(paper_id, text, websocket))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"深度分析失败: {str(e)}"
        }))
    finally:
        chunk_buffer.close()
        state.running_tasks.pop(task_key, None)
