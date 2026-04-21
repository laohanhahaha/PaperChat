"""论文查询与提纲工具集 — 查询最近论文、搜索论文、生成提纲

工具列表：
- RecentPapersTool: 按上传时间倒序查询论文列表（无 LLM，快速）
- SearchPapersTool: 按标题/摘要关键词模糊搜索论文（无 LLM，快速）
- GenerateOutlineTool: 用 LLM 生成研究报告或文献综述提纲（约 1 次 LLM 调用）
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.core.tool_base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class RecentPapersTool(Tool):
    """查询最近论文"""
    name = "recent_papers"
    description = "查询最近上传的论文列表"
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10, "description": "返回论文数量"}
        },
        "required": []
    }

    async def execute(self, ctx: ToolContext, limit: int = 10, **kwargs) -> ToolResult:
        """查询 Paper 表，按上传时间倒序"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        from sqlalchemy import select
        from app.models.paper import Paper

        query = select(Paper)
        if ctx.user_id:
            query = query.where(Paper.user_id == ctx.user_id)
        query = query.order_by(Paper.created_at.desc()).limit(limit)

        result = await db.execute(query)
        papers = result.scalars().all()

        paper_list = []
        for p in papers:
            paper_list.append({
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "category": p.category,
                "reading_status": p.reading_status,
                "page_count": p.page_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return ToolResult(data={
            "papers": paper_list,
            "count": len(paper_list),
            "type": "papers"
        })


class SearchPapersTool(Tool):
    """搜索论文"""
    name = "search_papers"
    description = "按关键词搜索论文"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"}
        },
        "required": ["query"]
    }

    async def execute(self, ctx: ToolContext, query: str, top_k: int = 10, **kwargs) -> ToolResult:
        """按标题和摘要模糊匹配搜索 Paper 表"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        if not query:
            return ToolResult(success=False, error="需要提供搜索关键词")

        from sqlalchemy import select, or_
        from app.models.paper import Paper

        keyword_pattern = f"%{query}%"
        sql_query = select(Paper).where(
            or_(
                Paper.title.ilike(keyword_pattern),
                Paper.abstract.ilike(keyword_pattern),
            )
        )
        if ctx.user_id:
            sql_query = sql_query.where(Paper.user_id == ctx.user_id)
        sql_query = sql_query.order_by(Paper.created_at.desc()).limit(top_k)

        result = await db.execute(sql_query)
        papers = result.scalars().all()

        paper_list = []
        for p in papers:
            paper_list.append({
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract[:200] + "..." if p.abstract and len(p.abstract) > 200 else p.abstract,
                "category": p.category,
                "reading_status": p.reading_status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return ToolResult(data={
            "papers": paper_list,
            "count": len(paper_list),
            "query": query,
            "type": "papers"
        })


class GenerateOutlineTool(Tool):
    """生成提纲"""
    name = "generate_outline"
    description = "基于论文内容生成研究报告或文献综述的提纲"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "报告主题"},
            "context": {"type": "string", "description": "相关上下文内容（可选）"},
            "paper_ids": {"type": "array", "items": {"type": "integer"}, "description": "相关论文ID列表（可选）"}
        },
        "required": ["topic"]
    }

    async def execute(self, ctx: ToolContext, topic: str, context: str = "", paper_ids: list[int] = None) -> ToolResult:
        """使用 LLM 生成提纲"""
        # 优先使用传入的paper_ids，否则从ctx获取
        pids = paper_ids if paper_ids is not None else ctx.paper_ids

        prompt = f"""请为以下主题生成一份详细的研究报告提纲：

主题：{topic}

{f"相关论文内容：\n{context[:5000]}" if context else ""}

要求：
1. 提纲结构清晰，层级分明
2. 包含引言、主体章节、结论
3. 每个章节提供简要说明
4. 适合作为研究报告或文献综述的框架

请直接输出提纲内容。"""

        messages = [
            SystemMessage(content="你是学术研究专家，擅长构建清晰的研究报告结构。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "topic": topic,
            "outline": response.content,
            "paper_count": len(pids) if pids else 0
        })
