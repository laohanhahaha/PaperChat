"""跨文档问答处理器

处理跨文档 RAG 问答请求。

继承 ChatHandlerBase，遵循 Template Method 模式：
- handle() 负责会话管理、消息持久化（基类实现）
- _process() 实现跨文档检索 + LLM 问答业务逻辑
"""
import json
from typing import Any

from app.services.llm_service import llm_service
from app.services.rag.rag_service import rag_service
from app.handlers.base import ChatHandlerBase
from app.handlers.ws_utils import ChunkBuffer


class CrossDocChatHandler(ChatHandlerBase):
    """跨文档问答处理器

    跨多篇论文进行 RAG 检索和综合问答。
    """

    channel: str = "cross_doc_chat"
    chunk_type: str = "cross_doc_chunk"

    def _user_message_meta(self, **kwargs) -> Any:
        """附加 paper_ids 到用户消息元数据"""
        paper_ids = kwargs.get("paper_ids", [])
        return {"paper_ids": paper_ids} if paper_ids else None

    async def _process(
        self,
        websocket,
        db,
        message: str,
        history,
        session,
        paper_id: Any,
        user_id: int,
        **kwargs
    ):
        """跨文档 RAG 检索 + LLM 问答

        Returns:
            Tuple[str, list]: (full_response, sources)
        """
        paper_ids: list = kwargs.get("paper_ids", [])

        # 4. 跨文档 RAG 检索
        results = await rag_service.search_multiple_papers(paper_ids, message, top_k=8)

        if not results:
            no_content_msg = "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。"
            await websocket.send_text(json.dumps({
                "type": "cross_doc_chunk",
                "content": no_content_msg
            }))
            return no_content_msg, []

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
            await chunk_buffer.flush("cross_doc_chunk")
        finally:
            chunk_buffer.close()

        return full_response, sources


# 向后兼容：保留函数接口
_cross_doc_handler = CrossDocChatHandler()


async def handle_cross_doc_chat(websocket, db, state, message, paper_ids, session_id, user_id, task_key="cross_doc_chat"):
    """异步处理跨文档 RAG 问答（向后兼容函数接口）"""
    await _cross_doc_handler.handle(
        websocket=websocket,
        db=db,
        state=state,
        message=message,
        user_id=user_id,
        session_id=session_id,
        paper_id=None,
        task_key=task_key,
        paper_ids=paper_ids,
    )
