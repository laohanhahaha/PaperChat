# -*- coding: utf-8 -*-
"""应用异常类体系

AppError 为所有业务异常的基类，包含结构化错误码、HTTP 状态码及可选详情。
子类按语义分组，便于异常处理器精确捕获。
"""
from typing import Optional

from app.errors.codes import ErrorCode


class AppError(Exception):
    """应用异常基类

    Args:
        code: 结构化错误码（ERR-xxxx）
        message: 面向用户的错误描述
        status_code: HTTP 响应状态码，默认 500
        details: 附加调试信息字典（可选）
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details: dict = details or {}


class NotFoundError(AppError):
    """资源不存在（404）"""

    def __init__(
        self,
        message: str = "资源不存在",
        code: str = ErrorCode.NOT_FOUND,
        details: Optional[dict] = None,
    ):
        super().__init__(code=code, message=message, status_code=404, details=details)


class ValidationError(AppError):
    """请求参数验证失败（422）"""

    def __init__(
        self,
        message: str = "请求参数验证失败",
        code: str = ErrorCode.VALIDATION_ERROR,
        details: Optional[dict] = None,
    ):
        super().__init__(code=code, message=message, status_code=422, details=details)


class AuthError(AppError):
    """认证/鉴权失败（401）"""

    def __init__(
        self,
        message: str = "认证失败",
        code: str = ErrorCode.AUTH_INVALID_TOKEN,
        details: Optional[dict] = None,
    ):
        super().__init__(code=code, message=message, status_code=401, details=details)


class LLMError(AppError):
    """LLM/RAG 调用失败（502）"""

    def __init__(
        self,
        message: str = "AI 服务调用失败",
        code: str = ErrorCode.LLM_API_ERROR,
        details: Optional[dict] = None,
    ):
        super().__init__(code=code, message=message, status_code=502, details=details)


class AgentError(AppError):
    """Agent/工具执行失败（500）"""

    def __init__(
        self,
        message: str = "Agent 执行失败",
        code: str = ErrorCode.TOOL_EXECUTION_ERROR,
        details: Optional[dict] = None,
    ):
        super().__init__(code=code, message=message, status_code=500, details=details)
