"""知识库工具集 — 保存和搜索知识卡片

工具列表：
- SaveCardTool: 保存知识卡片到数据库，并尝试建立向量索引（无 LLM）
- SearchCardsTool: 调用 knowledge_service.search 语义搜索知识卡片（无 LLM）
"""
import logging

from app.services.core.tool_base import Tool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class SaveCardTool(Tool):
    """保存知识卡片"""
    name = "save_card"
    description = "保存知识卡片到知识库"
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "卡片标题（可选）"},
            "content": {"type": "string", "description": "卡片内容"},
            "summary": {"type": "string", "description": "内容摘要（可选）"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表（可选）"}
        },
        "required": ["content"]
    }

    async def execute(self, ctx: ToolContext, title: str = "", content: str = "", summary: str = "", tags: list = None, **kwargs) -> ToolResult:
        """保存知识卡片到数据库"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        if not content:
            return ToolResult(success=False, error="需要提供知识卡片内容")

        if not title:
            title = content[:30] + "..." if len(content) > 30 else content

        from app.models.knowledge import KnowledgeCard

        card = KnowledgeCard(
            user_id=ctx.user_id,
            title=title,
            content=content,
            summary=summary or content[:100] + "..." if len(content) > 100 else content,
            source_type="chat",
            paper_id=ctx.paper_id,
            tags=tags or [],
            importance=1.0
        )

        db.add(card)
        await db.commit()
        await db.refresh(card)

        # 向量化索引
        try:
            from app.services.knowledge.knowledge_service import knowledge_service
            await knowledge_service.index_card(card)
        except Exception:
            pass  # 索引失败不影响保存

        return ToolResult(data={
            "card_id": card.id,
            "title": card.title,
            "message": "知识卡片已保存",
            "type": "knowledge"
        })


class SearchCardsTool(Tool):
    """搜索知识卡片"""
    name = "search_cards"
    description = "搜索知识库中的知识卡片"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询文本"},
            "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"}
        },
        "required": ["query"]
    }

    async def execute(self, ctx: ToolContext, query: str, top_k: int = 10, **kwargs) -> ToolResult:
        """搜索知识库"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        if not query:
            return ToolResult(success=False, error="需要提供搜索关键词")

        if ctx.user_id is None:
            return ToolResult(success=False, error="需要提供用户ID")

        from app.services.knowledge.knowledge_service import knowledge_service

        results = await knowledge_service.search(ctx.user_id, query, db, top_k)

        return ToolResult(data={
            "cards": results,
            "count": len(results),
            "query": query,
            "type": "knowledge"
        })
