# backend/app/services/llm_service.py（兼容层）
"""兼容入口 - 保持现有导入路径不变"""
from app.services.llm.llm_service import LLMService, llm_service
from app.services.llm.prompts import (
    # analyze
    ANALYZE_SYSTEM_PROMPT,
    DEEP_ANALYZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
    # chat
    CHAT_SYSTEM_PROMPT,
    # rag
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT,
    CROSS_DOC_CHAT_SYSTEM_PROMPT,
    # reading
    EXPLAIN_TERM_PROMPT,
    SUMMARIZE_PROMPT,
    TRANSLATE_PROMPT,
    # writing
    GENERATE_REVIEW_PROMPT,
    GENERATE_OUTLINE_PROMPT,
    GENERATE_DRAFT_PROMPT,
    POLISH_TEXT_PROMPT,
    CITATION_FORMAT_TEMPLATES,
    CITATION_SYSTEM_PROMPT,
)

__all__ = [
    'LLMService',
    'llm_service',
    # analyze
    'ANALYZE_SYSTEM_PROMPT',
    'DEEP_ANALYZE_PROMPT',
    'COMPARE_PAPERS_PROMPT',
    # chat
    'CHAT_SYSTEM_PROMPT',
    # rag
    'RAG_CHAT_SYSTEM_PROMPT',
    'RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT',
    'CROSS_DOC_CHAT_SYSTEM_PROMPT',
    # reading
    'EXPLAIN_TERM_PROMPT',
    'SUMMARIZE_PROMPT',
    'TRANSLATE_PROMPT',
    # writing
    'GENERATE_REVIEW_PROMPT',
    'GENERATE_OUTLINE_PROMPT',
    'GENERATE_DRAFT_PROMPT',
    'POLISH_TEXT_PROMPT',
    'CITATION_FORMAT_TEMPLATES',
    'CITATION_SYSTEM_PROMPT',
]
