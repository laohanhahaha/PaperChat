"""兼容层 — 从 app.prompts.graph 导入知识图谱提示词"""

from app.prompts.graph import EXTRACT_ENTITIES_PROMPT, BUILD_RELATIONS_PROMPT  # noqa: F401

__all__ = [
    "EXTRACT_ENTITIES_PROMPT",
    "BUILD_RELATIONS_PROMPT",
]
