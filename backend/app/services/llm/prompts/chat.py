"""兼容层 — 从 app.prompts.chat 导入论文问答提示词"""

from app.prompts.chat import (  # noqa: F401
    CHAT_SYSTEM_PROMPT,
    GENERAL_CHAT_SYSTEM_PROMPT,
    THINKING_PROMPT,
)

__all__ = [
    "CHAT_SYSTEM_PROMPT",
    "GENERAL_CHAT_SYSTEM_PROMPT",
    "THINKING_PROMPT",
]
