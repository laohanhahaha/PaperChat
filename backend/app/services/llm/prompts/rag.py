"""兼容层 — 从 app.prompts.rag 导入 RAG 检索增强问答提示词"""

from app.prompts.rag import (  # noqa: F401
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT,
    CROSS_DOC_CHAT_SYSTEM_PROMPT,
)

__all__ = [
    "RAG_CHAT_SYSTEM_PROMPT",
    "RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT",
    "CROSS_DOC_CHAT_SYSTEM_PROMPT",
]
