"""跨文档问答处理器

处理跨文档 RAG 问答请求
"""
import json
import asyncio

from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.services.session_service import get_or_create_session, auto_title
from app.services.message_service import save_message, load_chat_history
from app.routers.ws import ChunkBuffer


async def handle_cross_doc_chat(websocket, db, state, message, paper_ids, session_id, user_id, task_key="cross_doc_chat"):
    """异步处理跨文档 RAG 问答"""
    state.current_user_id = user_id

    try:
        # 1. 获取或创建会话
        session = await get_or_create_session(db, session_id, user_id, paper_id=None)
        state.current_session_id = session.id

        # 2. 保存用户消息（附带 paper_ids 信息）
        await save_message(db, session.id, "user", message, {"paper_ids": paper_ids})

        # 3. 加载会话历史（最近10条）
        history = await load_chat_history(db, session.id, limit=10)

        # 4. 跨文档 RAG 检索
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

        # 7. 流式获取回复（使用 ChunkBuffer 合并高频消息）
        chunk_buffer = ChunkBuffer(websocket, interval_ms=50)
        full_response = ""
        try:
            async for chunk in llm_service.chat_cross_doc(message, results, history):
                full_response += chunk
                await chunk_buffer.add(chunk, "cross_doc_chunk")
            # 确保发送所有剩余的 chunk
            await chunk_buffer.flush("cross_doc_chunk")
        finally:
            chunk_buffer.close()

        # 8. 保存 assistant 消息到数据库
        await save_message(db, session.id, "assistant", full_response, sources)

        # 9. 更新会话标题
        await auto_title(db, session, message)

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
        state.running_tasks.pop(task_key, None)
