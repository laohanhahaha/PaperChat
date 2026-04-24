"""兼容层 — 从 app.prompts.analyze 导入论文分析提示词"""

from app.prompts.analyze import (  # noqa: F401
    ANALYZE_SYSTEM_PROMPT,
    DEEP_ANALYZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
)

__all__ = [
    "ANALYZE_SYSTEM_PROMPT",
    "DEEP_ANALYZE_PROMPT",
    "COMPARE_PAPERS_PROMPT",
]
