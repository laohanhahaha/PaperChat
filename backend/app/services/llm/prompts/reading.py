"""兼容层 — 从 app.prompts.reading 导入阅读辅助提示词"""

from app.prompts.reading import (  # noqa: F401
    EXPLAIN_TERM_PROMPT,
    SUMMARIZE_PROMPT,
    TRANSLATE_PROMPT,
)

__all__ = [
    "EXPLAIN_TERM_PROMPT",
    "SUMMARIZE_PROMPT",
    "TRANSLATE_PROMPT",
]
