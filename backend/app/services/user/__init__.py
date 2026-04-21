"""用户服务模块"""
from app.services.user.auth_service import get_current_user
from app.services.user.memory_service import MemoryService, memory_service
from app.services.user.memory_middleware import (
    enrich_context_with_memory,
    post_chat_memory_extraction,
    build_memory_aware_prompt,
)
from app.services.user.profile_service import ProfileService, profile_service
from app.services.user.settings_service import SettingsService, settings_service

__all__ = [
    "get_current_user",
    "MemoryService", "memory_service",
    "enrich_context_with_memory", "post_chat_memory_extraction", "build_memory_aware_prompt",
    "ProfileService", "profile_service",
    "SettingsService", "settings_service",
]
