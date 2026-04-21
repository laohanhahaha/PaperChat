"""论文核心工具 — 搜索、提取、获取元数据

工具列表：
- SearchTextTool: 在论文中语义搜索文本段落（RAG 检索）
- ExtractKeyPointsTool: 用 LLM 提取核心知识点（约 1 次 LLM 调用）
- GetPaperInfoTool: 从数据库查询论文元数据（无 LLM，快速）
"""
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.core.tool_base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class SearchTextTool(Tool):
    """搜索论文文本"""
    name = "search_text"
    description = "在论文中搜索与查询相关的文本段落，返回最相关的文本块及其页码"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询文本"},
            "top_k": {"type": "integer", "default": 5, "description": "返回结果数量"},
            "paper_id": {"type": "integer", "description": "论文ID（可选，默认使用当前论文）"}
        },
        "required": ["query"]
    }

    async def execute(self, ctx: ToolContext, query: str, top_k: int = 5, paper_id: int = None) -> ToolResult:
        from app.services.rag.rag_service import rag_service
        # 优先使用传入的paper_id，否则从ctx获取
        pid = paper_id if paper_id is not None else ctx.paper_id
        if pid is None:
            return ToolResult(success=False, error="需要提供paper_id")
        results = await rag_service.search(pid, query, top_k)
        return ToolResult(data={
            "results": results,
            "count": len(results)
        })


class ExtractKeyPointsTool(Tool):
    """提取核心知识点"""
    name = "extract_key_points"
    description = "从论文文本中提取核心知识点、关键概念和重要发现"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要提取知识点的文本内容"},
            "max_points": {"type": "integer", "default": 5, "description": "最多提取的知识点数量"}
        },
        "required": ["text"]
    }

    async def execute(self, ctx: ToolContext, text: str, max_points: int = 5) -> ToolResult:
        """使用 LLM 提取关键知识点"""
        prompt = f"""请从以下学术文本中提取 {max_points} 个核心知识点或关键概念。

要求：
1. 每个知识点包含：概念名称、简要解释、在文本中的重要性
2. 优先提取专业术语、方法论、核心发现
3. 以 JSON 数组格式返回

文本内容：
{text[:8000]}

请返回 JSON 格式：
[{{"concept": "概念名称", "explanation": "解释", "importance": "重要性说明"}}, ...]
"""
        messages = [
            SystemMessage(content="你是学术知识提取专家，擅长从论文中提取核心概念。"),
            HumanMessage(content=prompt)
        ]

        # 使用非流式调用获取完整结果
        response = await llm_service.llm.ainvoke(messages)

        # 尝试解析 JSON
        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            points = json.loads(content.strip())
            return ToolResult(data={"points": points, "count": len(points)})
        except Exception as e:
            return ToolResult(success=False, error=str(e), data={
                "points": [{"concept": "提取失败", "explanation": str(e), "importance": "N/A"}],
                "count": 0,
                "raw_response": response.content
            })


class GetPaperInfoTool(Tool):
    """获取论文信息"""
    name = "get_paper_info"
    description = "获取论文的元数据信息（标题、作者、摘要等）"
    parameters = {
        "type": "object",
        "properties": {
            "paper_id": {"type": "integer", "description": "论文ID（可选，默认使用当前论文）"}
        },
        "required": []
    }

    async def execute(self, ctx: ToolContext, paper_id: int = None) -> ToolResult:
        """从数据库查询论文信息"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        # 优先使用传入的paper_id，否则从ctx获取
        pid = paper_id if paper_id is not None else ctx.paper_id
        if pid is None:
            return ToolResult(success=False, error="需要提供paper_id")

        from sqlalchemy import select
        from app.models.paper import Paper

        result = await db.execute(select(Paper).where(Paper.id == pid))
        paper = result.scalar_one_or_none()

        if not paper:
            return ToolResult(success=False, error=f"未找到论文 ID: {pid}")

        return ToolResult(data={
            "id": paper.id,
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "doi": paper.doi,
            "page_count": paper.page_count,
            "category": paper.category,
            "reading_status": paper.reading_status
        })
