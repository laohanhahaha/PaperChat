"""跨论文推理工具集

提供5个跨论文分析工具，用于矛盾检测、演进追踪、一致性验证、
研究空白发现和跨论文假设推理。

性能影响：
- 每个工具需对多篇论文分别进行 RAG 检索（并行执行），约 500-1500ms
- 加上 LLM 分析调用，总体约 3-10s（取决于论文数量和 LLM 响应速度）
"""
import asyncio
import logging
from typing import List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.core.tool_base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


# ============ 辅助函数 ============

async def _fetch_paper_evidence(
    paper_ids: List[int],
    query: str,
    top_k: int = 3,
) -> Dict[int, List[Dict[str, Any]]]:
    """从多篇论文并行检索与 query 相关的段落

    Returns:
        {paper_id: [rag_result, ...]}
    """
    from app.services.rag_service import rag_service

    tasks = [rag_service.search(pid, query, top_k=top_k) for pid in paper_ids]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    evidence = {}
    for paper_id, result in zip(paper_ids, results_list):
        if isinstance(result, Exception):
            logger.warning(f"RAG 检索论文 {paper_id} 失败: {result}")
            evidence[paper_id] = []
        else:
            evidence[paper_id] = result
    return evidence


async def _fetch_paper_metadata(
    db,
    paper_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    """从数据库获取论文元数据（标题、作者、上传时间等）

    Returns:
        {paper_id: {"title": ..., "authors": ..., "created_at": ...}}
    """
    from sqlalchemy import select
    from app.models.paper import Paper

    metadata = {}
    for pid in paper_ids:
        result = await db.execute(select(Paper).where(Paper.id == pid))
        paper = result.scalar_one_or_none()
        if paper:
            metadata[pid] = {
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors or "未知作者",
                "created_at": paper.created_at.isoformat() if paper.created_at else None,
            }
        else:
            metadata[pid] = {"id": pid, "title": f"论文#{pid}", "authors": "未知", "created_at": None}
    return metadata


def _build_evidence_text(
    evidence: Dict[int, List[Dict[str, Any]]],
    metadata: Dict[int, Dict[str, Any]],
) -> str:
    """将检索结果格式化为 LLM 可读的文本"""
    sections = []
    for paper_id, passages in evidence.items():
        meta = metadata.get(paper_id, {})
        title = meta.get("title", f"论文#{paper_id}")
        authors = meta.get("authors", "")
        created = meta.get("created_at", "")

        header = f"### {title}"
        if authors:
            header += f" (作者: {authors})"
        if created:
            header += f" [上传时间: {created}]"

        section_lines = [header]
        if not passages:
            section_lines.append("（未检索到相关段落）")
        else:
            for i, p in enumerate(passages, 1):
                text = p.get("text", "")
                pages = p.get("pages", [])
                page_info = f" (第{pages}页)" if pages else ""
                section_lines.append(f"[段落{i}{page_info}] {text[:500]}")
        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


# ============ 工具1: 矛盾检测 ============

class DetectContradictionTool(Tool):
    """检测多篇论文间的矛盾主张"""
    name = "detect_contradiction"
    description = "检测多篇论文之间在特定主题上是否存在矛盾或冲突的主张"
    parameters = {
        "type": "object",
        "properties": {
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "论文ID列表"
            },
            "topic": {"type": "string", "description": "要检测矛盾的主题"}
        },
        "required": ["paper_ids", "topic"]
    }

    async def execute(self, ctx: ToolContext, paper_ids: list[int], topic: str, **kwargs) -> ToolResult:
        if not paper_ids:
            # 从 ctx 回退
            paper_ids = ctx.paper_ids
        if not paper_ids:
            return ToolResult(success=False, error="需要提供 paper_ids")

        # 1. 并行 RAG 检索
        evidence = await _fetch_paper_evidence(paper_ids, topic, top_k=5)

        # 2. 获取元数据
        metadata = {}
        if ctx.db:
            metadata = await _fetch_paper_metadata(ctx.db, paper_ids)

        # 3. 构造 LLM prompt
        evidence_text = _build_evidence_text(evidence, metadata)

        prompt = f"""请分析以下多篇论文中关于「{topic}」的主张，检测是否存在矛盾或冲突。

检索到的相关段落：
{evidence_text}

请按以下格式分析：
1. 列出每篇论文中关于该主题的核心主张
2. 逐对比较，指出是否存在矛盾
3. 如果存在矛盾，分析可能的原因（方法论差异、数据集不同、实验条件不同等）
4. 给出矛盾严重程度评估（轻微分歧/显著矛盾/根本性冲突）

请直接输出分析结果："""

        messages = [
            SystemMessage(content="你是学术研究分析专家，擅长识别不同研究之间的矛盾和冲突。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "topic": topic,
            "analysis": response.content,
            "paper_count": len(paper_ids),
            "type": "cross_paper"
        })


# ============ 工具2: 方法演进追踪 ============

class TraceEvolutionTool(Tool):
    """追踪方法演进时间线"""
    name = "trace_evolution"
    description = "追踪某一方法在多篇论文中的演进变化时间线"
    parameters = {
        "type": "object",
        "properties": {
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "论文ID列表"
            },
            "method_name": {"type": "string", "description": "要追踪的方法名称"}
        },
        "required": ["paper_ids", "method_name"]
    }

    async def execute(self, ctx: ToolContext, paper_ids: list[int], method_name: str, **kwargs) -> ToolResult:
        if not paper_ids:
            paper_ids = ctx.paper_ids
        if not paper_ids:
            return ToolResult(success=False, error="需要提供 paper_ids")

        # 1. 获取元数据（含上传时间，用于排序）
        metadata = {}
        if ctx.db:
            metadata = await _fetch_paper_metadata(ctx.db, paper_ids)

        # 按上传时间排序论文
        sorted_pids = sorted(
            paper_ids,
            key=lambda pid: metadata.get(pid, {}).get("created_at") or ""
        )

        # 2. 并行 RAG 检索
        evidence = await _fetch_paper_evidence(sorted_pids, method_name, top_k=5)

        # 3. 按时间顺序组织证据
        evidence_text = _build_evidence_text(
            {pid: evidence.get(pid, []) for pid in sorted_pids},
            metadata
        )

        # 4. 构造 LLM prompt
        prompt = f"""请追踪方法「{method_name}」在以下论文中的演进变化。

论文已按上传时间排序（从早到晚）：

{evidence_text}

请分析：
1. 该方法在各论文中的具体形态和特征
2. 方法随时间的变化趋势（改进、变体、替代方案）
3. 每次重大变化的驱动因素
4. 当前方法的最新状态和未来可能的演进方向

请以时间线形式输出分析结果："""

        messages = [
            SystemMessage(content="你是学术研究分析专家，擅长梳理方法论的演进脉络。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "method_name": method_name,
            "analysis": response.content,
            "paper_count": len(paper_ids),
            "type": "cross_paper"
        })


# ============ 工具3: 一致性验证 ============

class VerifyConsistencyTool(Tool):
    """验证多篇论文结论一致性"""
    name = "verify_consistency"
    description = "验证多篇论文对于某一主张的结论是否一致，判断各论文的支持/反对/无关立场"
    parameters = {
        "type": "object",
        "properties": {
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "论文ID列表"
            },
            "claim": {"type": "string", "description": "要验证的主张或结论"}
        },
        "required": ["paper_ids", "claim"]
    }

    async def execute(self, ctx: ToolContext, paper_ids: list[int], claim: str, **kwargs) -> ToolResult:
        if not paper_ids:
            paper_ids = ctx.paper_ids
        if not paper_ids:
            return ToolResult(success=False, error="需要提供 paper_ids")

        # 1. 并行 RAG 检索
        evidence = await _fetch_paper_evidence(paper_ids, claim, top_k=5)

        # 2. 获取元数据
        metadata = {}
        if ctx.db:
            metadata = await _fetch_paper_metadata(ctx.db, paper_ids)

        # 3. 构造 LLM prompt
        evidence_text = _build_evidence_text(evidence, metadata)

        prompt = f"""请验证以下多篇论文对于该主张的立场一致性。

主张：「{claim}」

各论文中检索到的相关段落：
{evidence_text}

请逐篇分析：
1. 该论文是否涉及此主张
2. 如果涉及，其立场是：支持 / 反对 / 中立（无关）
3. 支持或反对的证据和推理

最后给出整体一致性评估：
- 一致性等级：完全一致 / 基本一致 / 存在分歧 / 严重分歧
- 支持论文数 vs 反对论文数
- 分歧焦点（如有）

请直接输出分析结果："""

        messages = [
            SystemMessage(content="你是学术研究验证专家，擅长评估不同研究结论的一致性。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "claim": claim,
            "analysis": response.content,
            "paper_count": len(paper_ids),
            "type": "cross_paper"
        })


# ============ 工具4: 发现研究空白 ============

class FindResearchGapsTool(Tool):
    """发现研究空白"""
    name = "find_research_gaps"
    description = "分析多篇论文的局限性和未来工作，发现尚未解决的研究空白"
    parameters = {
        "type": "object",
        "properties": {
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "论文ID列表"
            },
            "field": {"type": "string", "description": "研究领域或方向"}
        },
        "required": ["paper_ids", "field"]
    }

    async def execute(self, ctx: ToolContext, paper_ids: list[int], field: str, **kwargs) -> ToolResult:
        if not paper_ids:
            paper_ids = ctx.paper_ids
        if not paper_ids:
            return ToolResult(success=False, error="需要提供 paper_ids")

        # 1. 并行 RAG 检索 — 同时检索 limitation 和 future work 两个维度
        limitation_evidence = await _fetch_paper_evidence(paper_ids, f"{field} limitations", top_k=3)
        future_evidence = await _fetch_paper_evidence(paper_ids, f"{field} future work directions", top_k=3)

        # 2. 获取元数据
        metadata = {}
        if ctx.db:
            metadata = await _fetch_paper_metadata(ctx.db, paper_ids)

        # 3. 组装两部分的证据文本
        limitation_text = _build_evidence_text(limitation_evidence, metadata)
        future_text = _build_evidence_text(future_evidence, metadata)

        # 4. 构造 LLM prompt
        prompt = f"""请分析以下多篇论文在领域「{field}」中的局限性和未来工作方向，发现尚未解决的研究空白。

=== 各论文的局限性相关段落 ===
{limitation_text}

=== 各论文的未来工作方向相关段落 ===
{future_text}

请分析：
1. 列出每篇论文提到的局限性
2. 列出每篇论文提到的未来工作方向
3. 识别哪些局限性在所有论文中均未解决（即研究空白）
4. 识别哪些未来方向尚无论文实际探索
5. 给出最有价值的研究空白（按重要性排序，前3个）

请直接输出分析结果："""

        messages = [
            SystemMessage(content="你是学术研究分析专家，擅长发现研究领域中的空白和未解决问题。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "field": field,
            "analysis": response.content,
            "paper_count": len(paper_ids),
            "type": "cross_paper"
        })


# ============ 工具5: 跨论文假设推理 ============

class CrossPaperReasonTool(Tool):
    """跨论文假设生成与推理"""
    name = "cross_paper_reason"
    description = "综合多篇论文的证据，对给定假设进行推理验证"
    parameters = {
        "type": "object",
        "properties": {
            "paper_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "论文ID列表"
            },
            "hypothesis": {"type": "string", "description": "要进行推理验证的假设"}
        },
        "required": ["paper_ids", "hypothesis"]
    }

    async def execute(self, ctx: ToolContext, paper_ids: list[int], hypothesis: str, **kwargs) -> ToolResult:
        if not paper_ids:
            paper_ids = ctx.paper_ids
        if not paper_ids:
            return ToolResult(success=False, error="需要提供 paper_ids")

        # 1. 并行 RAG 检索 — 从假设中提取关键词检索
        evidence = await _fetch_paper_evidence(paper_ids, hypothesis, top_k=5)

        # 2. 获取元数据
        metadata = {}
        if ctx.db:
            metadata = await _fetch_paper_metadata(ctx.db, paper_ids)

        # 3. 构造 LLM prompt
        evidence_text = _build_evidence_text(evidence, metadata)

        prompt = f"""请综合以下多篇论文的证据，对给定假设进行推理验证。

假设：「{hypothesis}」

各论文中检索到的相关证据：
{evidence_text}

请推理分析：
1. 支持该假设的证据有哪些（来自哪些论文）
2. 反对该假设的证据有哪些（来自哪些论文）
3. 间接相关但可提供启发的证据
4. 基于现有证据的逻辑推理链
5. 假设的可行性评估（很可能成立 / 有可能成立 / 存在较大争议 / 不太可能成立）
6. 需要进一步验证的关键问题

请直接输出推理过程和结论："""

        messages = [
            SystemMessage(content="你是学术推理专家，擅长基于多篇论文的证据进行逻辑推理和假设验证。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "hypothesis": hypothesis,
            "analysis": response.content,
            "paper_count": len(paper_ids),
            "type": "cross_paper"
        })
