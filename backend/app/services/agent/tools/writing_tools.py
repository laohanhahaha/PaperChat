"""写作辅助工具集 — 文献综述、引用格式化、文本润色

工具列表：
- LiteratureReviewTool: 用 LLM 生成结构化文献综述（非流式，约 1 次 LLM 调用）
- CitePaperTool: 格式化引用（APA/MLA/Chicago），优先无 LLM；若需补全则调用 llm_service
- PolishTextTool: 调用 llm_service.polish_text 润色文本（流式，约 1 次 LLM 调用）
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.core.tool_base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class LiteratureReviewTool(Tool):
    """文献综述生成"""
    name = "literature_review"
    description = "根据主题生成结构化文献综述"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "文献综述主题"},
            "paper_text": {"type": "string", "description": "参考论文文本（可选）"}
        },
        "required": ["topic"]
    }

    async def execute(self, ctx: ToolContext, topic: str, paper_text: str = "", **kwargs) -> ToolResult:
        """使用 LLM 生成文献综述"""
        context_section = ""
        if paper_text:
            context_section = f"\n参考论文内容：\n{paper_text[:8000]}"

        prompt = f"""请根据以下主题生成一份结构化的文献综述。

主题：{topic}
{context_section}

要求：
1. 综述结构应包含：引言、主体（按主题或时间线组织）、总结与展望
2. 引用相关研究成果时请标注作者和年份
3. 对不同研究观点进行对比和评价
4. 指出研究空白和未来方向
5. 语言学术、严谨、客观

请直接输出文献综述内容："""

        messages = [
            SystemMessage(content="你是学术文献综述撰写专家，擅长系统性地梳理和总结研究领域的进展。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "topic": topic,
            "review": response.content,
            "type": "writing"
        })


class CitePaperTool(Tool):
    """引用格式化"""
    name = "cite_paper"
    description = "将论文引用格式化为指定格式（APA/MLA/Chicago）"
    parameters = {
        "type": "object",
        "properties": {
            "paper_info": {"type": "object", "description": "论文信息对象（可选）"},
            "format": {"type": "string", "default": "apa", "description": "引用格式（apa/mla/chicago）"}
        },
        "required": []
    }

    async def execute(self, ctx: ToolContext, paper_info: dict = None, format: str = "apa", **kwargs) -> ToolResult:
        """根据论文元数据和请求格式生成引用，不需要 LLM 调用"""
        # 尝试从 ctx.db 获取论文信息
        if not paper_info:
            paper_info = kwargs.get("paper_info", {})

        # 如果仍无 paper_info，尝试从数据库查询
        if not paper_info and ctx.paper_id and ctx.db:
            from sqlalchemy import select
            from app.models.paper import Paper
            result = await ctx.db.execute(select(Paper).where(Paper.id == ctx.paper_id))
            paper = result.scalar_one_or_none()
            if paper:
                paper_info = {
                    "title": paper.title,
                    "authors": paper.authors or "未知作者",
                    "year": paper.created_at.year if paper.created_at else "n.d.",
                    "journal": "",
                }

        if not paper_info:
            return ToolResult(success=False, error="需要提供论文信息(paper_info)或paper_id")

        # 使用 llm_service 的 generate_citation 方法
        citation = await llm_service.generate_citation(paper_info, format)

        return ToolResult(data={
            "citation": citation,
            "format": format,
            "type": "citation"
        })


class PolishTextTool(Tool):
    """文本润色"""
    name = "polish_text"
    description = "润色和优化学术文本"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要润色的文本内容"},
            "polish_type": {"type": "string", "default": "academic", "description": "润色类型"}
        },
        "required": ["text"]
    }

    async def execute(self, ctx: ToolContext, text: str, polish_type: str = "academic", **kwargs) -> ToolResult:
        """使用 LLM 润色文本"""
        full_polished = ""
        async for chunk in llm_service.polish_text(text, polish_type):
            full_polished += chunk

        return ToolResult(data={
            "original_text": text,
            "polished_text": full_polished,
            "polish_type": polish_type,
            "type": "writing"
        })
