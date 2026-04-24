# -*- coding: utf-8 -*-
"""errors 包公共导出

使用方式:
    from app.errors import ErrorCode, AppError, NotFoundError, ValidationError
    from app.errors import AuthError, LLMError, AgentError
"""
from app.errors.codes import ErrorCode
from app.errors.exceptions import (
    AppError,
    NotFoundError,
    ValidationError,
    AuthError,
    LLMError,
    AgentError,
)

__all__ = [
    "ErrorCode",
    "AppError",
    "NotFoundError",
    "ValidationError",
    "AuthError",
    "LLMError",
    "AgentError",
]
