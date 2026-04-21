"""分析工具集 — 摘要、翻译、术语解释、内容对比、质量评估

工具列表：
- SummarizeTool: 调用 llm_service.summarize_text 生成摘要（流式，约 1 次 LLM 调用）
- TranslateTool: 调用 llm_service.translate_text 翻译文本（流式，约 1 次 LLM 调用）
- ExplainTermTool: 调用 llm_service.explain_term 解释术语（流式，约 1 次 LLM 调用）
- CompareContentTool: 调用 llm_service.compare_papers 对比多篇论文（流式，约 1 次 LLM 调用）
- AssessQualityTool: 使用 LLM 评估论文质量（非流式 JSON，约 1 次 LLM 调用）
"""
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.tools.base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class SummarizeTool(Tool):
    """文本摘要"""
    name = "summarize"
    description = "对指定文本进行摘要，保留核心论点和关键数据"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要摘要的文本内容"},
            "max_length": {"type": "integer", "default": 500, "description": "摘要最大长度"}
        },
        "required": ["text"]
    }

    async def execute(self, ctx: ToolContext, text: str, max_length: int = 500) -> ToolResult:
        """调用 llm_service 的 summarize_text 方法（非流式版本）"""
        # 收集流式结果
        full_summary = ""
        async for chunk in llm_service.summarize_text(text):
            full_summary += chunk

        return ToolResult(data={
            "summary": full_summary[:max_length] if max_length else full_summary,
            "full_summary": full_summary
        })


class TranslateTool(Tool):
    """翻译"""
    name = "translate"
    description = "翻译学术文本，保留专业术语准确性"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要翻译的文本内容"},
            "target_lang": {"type": "string", "default": "zh", "description": "目标语言代码"}
        },
        "required": ["text"]
    }

    async def execute(self, ctx: ToolContext, text: str, target_lang: str = "zh") -> ToolResult:
        """调用 llm_service 的 translate_text 方法"""
        full_translation = ""
        async for chunk in llm_service.translate_text(text, target_lang):
            full_translation += chunk

        return ToolResult(data={
            "translation": full_translation,
            "source_lang": "auto",
            "target_lang": target_lang
        })


class ExplainTermTool(Tool):
    """术语解释"""
    name = "explain_term"
    description = "解释学术术语，结合上下文提供准确解释"
    parameters = {
        "type": "object",
        "properties": {
            "term": {"type": "string", "description": "要解释的术语"},
            "context": {"type": "string", "description": "术语出现的上下文（可选）"}
        },
        "required": ["term"]
    }

    async def execute(self, ctx: ToolContext, term: str, context: str = "") -> ToolResult:
        """调用 llm_service 的 explain_term 方法"""
        full_explanation = ""
        async for chunk in llm_service.explain_term(term, context):
            full_explanation += chunk

        return ToolResult(data={
            "term": term,
            "explanation": full_explanation
        })


class CompareContentTool(Tool):
    """对比内容"""
    name = "compare_content"
    description = "对比多篇论文的特定内容维度"
    parameters = {
        "type": "object",
        "properties": {
            "paper_contents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "text": {"type": "string"}
                    }
                },
                "description": "论文内容列表，每项包含title和text"
            },
            "dimension": {"type": "string", "default": "general", "description": "对比维度"}
        },
        "required": ["paper_contents"]
    }

    async def execute(self, ctx: ToolContext, paper_contents: list[dict], dimension: str = "general") -> ToolResult:
        """
        paper_contents: [{"title": "论文1", "text": "内容"}, ...]
        dimension: 对比维度 (methodology/results/contributions/general)
        """
        # 构建论文文本列表
        papers_text = []
        for p in paper_contents:
            papers_text.append({
                "title": p.get("title", "未知论文"),
                "text": p.get("text", "")[:5000]  # 限制长度
            })

        # 收集流式结果
        full_comparison = ""
        async for chunk in llm_service.compare_papers(papers_text):
            full_comparison += chunk

        return ToolResult(data={
            "dimension": dimension,
            "comparison": full_comparison,
            "paper_count": len(paper_contents)
        })


class AssessQualityTool(Tool):
    """评估质量"""
    name = "assess_quality"
    description = "评估论文的研究质量和方法论严谨性"
    parameters = {
        "type": "object",
        "properties": {
            "paper_text": {"type": "string", "description": "论文文本内容"},
            "paper_title": {"type": "string", "description": "论文标题（可选）"}
        },
        "required": ["paper_text"]
    }

    async def execute(self, ctx: ToolContext, paper_text: str, paper_title: str = "") -> ToolResult:
        """使用 LLM 评估论文质量"""
        prompt = f"""请对以下学术论文进行质量评估：

{f"论文标题：{paper_title}" if paper_title else ""}

论文内容：
{paper_text[:8000]}

请从以下维度进行评估（1-5分）：
1. 研究创新性
2. 方法论严谨性
3. 实验设计合理性
4. 数据分析充分性
5. 结论可信度
6. 写作规范性

请返回 JSON 格式：
{{
    "scores": {{
        "innovation": 分数,
        "methodology": 分数,
        "experimental_design": 分数,
        "data_analysis": 分数,
        "conclusion_validity": 分数,
        "writing_quality": 分数
    }},
    "total_score": 总分,
    "assessment": "总体评价",
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": "改进建议"
}}"""

        messages = [
            SystemMessage(content="你是学术论文评审专家，擅长评估研究质量和方法论。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        try:
            content = response.content
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            assessment = json.loads(content.strip())
            return ToolResult(data=assessment)
        except Exception as e:
            return ToolResult(success=False, error=str(e), data={
                "raw_response": response.content,
                "scores": {},
                "assessment": "评估解析失败"
            })
