"""兼容层 — 将旧导入路径代理到 app.prompts

原有导入方式（如 `from app.services.llm.prompts import ANALYZE_SYSTEM_PROMPT`）
仍然完全可用，所有符号均从 app.prompts 透传过来。
"""

from app.prompts.analyze import (
    ANALYZE_SYSTEM_PROMPT,
    DEEP_ANALYZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
)

from app.prompts.chat import (
    CHAT_SYSTEM_PROMPT,
)

from app.prompts.rag import (
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT,
    CROSS_DOC_CHAT_SYSTEM_PROMPT,
)

from app.prompts.reading import (
    EXPLAIN_TERM_PROMPT,
    SUMMARIZE_PROMPT,
    TRANSLATE_PROMPT,
)

from app.prompts.writing import (
    GENERATE_REVIEW_PROMPT,
    GENERATE_OUTLINE_PROMPT,
    GENERATE_DRAFT_PROMPT,
    POLISH_TEXT_PROMPT,
    CITATION_FORMAT_TEMPLATES,
    CITATION_SYSTEM_PROMPT,
)

__all__ = [
    # analyze
    "ANALYZE_SYSTEM_PROMPT",
    "DEEP_ANALYZE_PROMPT",
    "COMPARE_PAPERS_PROMPT",
    # chat
    "CHAT_SYSTEM_PROMPT",
    # rag
    "RAG_CHAT_SYSTEM_PROMPT",
    "RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT",
    "CROSS_DOC_CHAT_SYSTEM_PROMPT",
    # reading
    "EXPLAIN_TERM_PROMPT",
    "SUMMARIZE_PROMPT",
    "TRANSLATE_PROMPT",
    # writing
    "GENERATE_REVIEW_PROMPT",
    "GENERATE_OUTLINE_PROMPT",
    "GENERATE_DRAFT_PROMPT",
    "POLISH_TEXT_PROMPT",
    "CITATION_FORMAT_TEMPLATES",
    "CITATION_SYSTEM_PROMPT",
]
