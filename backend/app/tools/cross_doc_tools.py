"""跨文档推理工具集 — 从 cross_paper_tools.py 迁移

提供5个跨论文分析工具，用于矛盾检测、演进追踪、一致性验证、
研究空白发现和跨论文假设推理。

性能影响：
- 每个工具需对多篇论文分别进行 RAG 检索（并行执行），约 500-1500ms
- 加上 LLM 分析调用，总体约 3-10s（取决于论文数量和 LLM 响应速度）

注意：cross_paper_tools.py 仍保留原内容以维持向后兼容，
      本模块通过直接导入实现职责归并，避免代码重复。
"""
# 直接从原模块导入，避免代码重复
from app.services.agent.cross_paper_tools import (
    DetectContradictionTool,
    TraceEvolutionTool,
    VerifyConsistencyTool,
    FindResearchGapsTool,
    CrossPaperReasonTool,
    # 辅助函数也一并导出，供测试或外部使用
    _fetch_paper_evidence,
    _fetch_paper_metadata,
    _build_evidence_text,
)

__all__ = [
    "DetectContradictionTool",
    "TraceEvolutionTool",
    "VerifyConsistencyTool",
    "FindResearchGapsTool",
    "CrossPaperReasonTool",
    "_fetch_paper_evidence",
    "_fetch_paper_metadata",
    "_build_evidence_text",
]
