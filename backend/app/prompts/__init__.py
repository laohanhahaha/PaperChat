"""app/prompts — 提示词统一归集模块

所有散落在各服务中的提示词均集中于此，按功能分类存放。
原有导入路径（app.services.llm.prompts.*）通过兼容层保持可用。

子模块：
- analyze.py   — 论文分析相关提示词
- chat.py      — 论文问答相关提示词
- rag.py       — RAG 检索增强问答提示词
- reading.py   — 阅读辅助提示词（摘要、翻译、术语解释）
- writing.py   — 学术写作辅助提示词
- graph.py     — 知识图谱提示词
- agent.py     — ReAct Agent + 任务规划提示词
- intent.py    — 意图识别提示词
- service.py   — 服务层提示词（记忆、知识库）
- tools.py     — 工具类提示词模板
- manager.py   — PromptManager 类（Jinja2 模板渲染 + 版本管理）
"""

# ── analyze ──────────────────────────────────────────────────────────────────
from app.prompts.analyze import (
    ANALYZE_SYSTEM_PROMPT,
    DEEP_ANALYZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
)

# ── chat ─────────────────────────────────────────────────────────────────────
from app.prompts.chat import (
    CHAT_SYSTEM_PROMPT,
    GENERAL_CHAT_SYSTEM_PROMPT,
    THINKING_PROMPT,
)

# ── rag ──────────────────────────────────────────────────────────────────────
from app.prompts.rag import (
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT,
    CROSS_DOC_CHAT_SYSTEM_PROMPT,
)

# ── reading ───────────────────────────────────────────────────────────────────
from app.prompts.reading import (
    EXPLAIN_TERM_PROMPT,
    SUMMARIZE_PROMPT,
    TRANSLATE_PROMPT,
)

# ── writing ───────────────────────────────────────────────────────────────────
from app.prompts.writing import (
    GENERATE_REVIEW_PROMPT,
    GENERATE_OUTLINE_PROMPT,
    GENERATE_DRAFT_PROMPT,
    POLISH_TEXT_PROMPT,
    CITATION_FORMAT_TEMPLATES,
    CITATION_SYSTEM_PROMPT,
)

# ── graph ─────────────────────────────────────────────────────────────────────
from app.prompts.graph import (
    EXTRACT_ENTITIES_PROMPT,
    BUILD_RELATIONS_PROMPT,
)

# ── agent ─────────────────────────────────────────────────────────────────────
from app.prompts.agent import (
    REACT_SYSTEM_PROMPT,
    DEEP_RESEARCH_SYSTEM_PROMPT,
    TASK_PLANNING_PROMPT,
)

# ── intent ────────────────────────────────────────────────────────────────────
from app.prompts.intent import (
    INTENT_CLASSIFICATION_PROMPT,
    LLM_CLASSIFY_PROMPT,
    _LLM_CLASSIFY_PROMPT,
    _LLM_TOOL_DESCRIPTIONS,
)

# ── service ───────────────────────────────────────────────────────────────────
from app.prompts.service import (
    MEMORY_EXTRACTION_PROMPT,
    AUTO_TAG_PROMPT,
    FIND_RELATIONS_PROMPT,
    EXTRACT_FROM_HIGHLIGHT_PROMPT,
    EXTRACT_FROM_CHAT_PROMPT,
)

# ── tools ─────────────────────────────────────────────────────────────────────
from app.prompts.tools import (
    LITERATURE_REVIEW_SYSTEM_PROMPT,
    LITERATURE_REVIEW_USER_TEMPLATE,
    ASSESS_QUALITY_SYSTEM_PROMPT,
    ASSESS_QUALITY_USER_TEMPLATE,
)

# ── manager ───────────────────────────────────────────────────────────────────
from app.prompts.manager import PromptManager, prompt_manager

__all__ = [
    # analyze
    "ANALYZE_SYSTEM_PROMPT",
    "DEEP_ANALYZE_PROMPT",
    "COMPARE_PAPERS_PROMPT",
    # chat
    "CHAT_SYSTEM_PROMPT",
    "GENERAL_CHAT_SYSTEM_PROMPT",
    "THINKING_PROMPT",
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
    # graph
    "EXTRACT_ENTITIES_PROMPT",
    "BUILD_RELATIONS_PROMPT",
    # agent
    "REACT_SYSTEM_PROMPT",
    "DEEP_RESEARCH_SYSTEM_PROMPT",
    "TASK_PLANNING_PROMPT",
    # intent
    "INTENT_CLASSIFICATION_PROMPT",
    "LLM_CLASSIFY_PROMPT",
    "_LLM_CLASSIFY_PROMPT",
    "_LLM_TOOL_DESCRIPTIONS",
    # service
    "MEMORY_EXTRACTION_PROMPT",
    "AUTO_TAG_PROMPT",
    "FIND_RELATIONS_PROMPT",
    "EXTRACT_FROM_HIGHLIGHT_PROMPT",
    "EXTRACT_FROM_CHAT_PROMPT",
    # tools
    "LITERATURE_REVIEW_SYSTEM_PROMPT",
    "LITERATURE_REVIEW_USER_TEMPLATE",
    "ASSESS_QUALITY_SYSTEM_PROMPT",
    "ASSESS_QUALITY_USER_TEMPLATE",
    # manager
    "PromptManager",
    "prompt_manager",
]
