# -*- coding: utf-8 -*-
"""错误码体系单元测试

覆盖：
- ErrorCode 常量完整性
- AppError 基类属性
- 各子类默认实例化与自定义参数
- 继承关系正确性
"""
import pytest

from app.errors.codes import ErrorCode
from app.errors.exceptions import (
    AgentError,
    AppError,
    AuthError,
    LLMError,
    NotFoundError,
    ValidationError,
)


# ─────────────────────────────────────────────────────────────────────────────
# ErrorCode 常量
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorCode:
    """验证 ErrorCode 常量存在且格式正确"""

    def _assert_errcode(self, code: str) -> None:
        assert isinstance(code, str)
        assert code.startswith("ERR-"), f"错误码 {code!r} 应以 'ERR-' 开头"

    def test_general_codes_exist(self):
        """1xxx 通用错误码均已定义"""
        codes = [
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.VALIDATION_ERROR,
            ErrorCode.NOT_FOUND,
            ErrorCode.RATE_LIMITED,
        ]
        for c in codes:
            self._assert_errcode(c)

    def test_paper_codes_exist(self):
        """2xxx 论文相关错误码均已定义"""
        codes = [
            ErrorCode.PAPER_NOT_FOUND,
            ErrorCode.PAPER_PARSE_FAILED,
            ErrorCode.PAPER_TOO_LARGE,
        ]
        for c in codes:
            self._assert_errcode(c)

    def test_llm_rag_codes_exist(self):
        """3xxx RAG/LLM 错误码均已定义"""
        codes = [
            ErrorCode.LLM_API_ERROR,
            ErrorCode.RAG_INDEX_ERROR,
            ErrorCode.EMBEDDING_ERROR,
            ErrorCode.CONTEXT_TOO_LONG,
        ]
        for c in codes:
            self._assert_errcode(c)

    def test_agent_mcp_codes_exist(self):
        """4xxx Agent/MCP 错误码均已定义"""
        codes = [
            ErrorCode.AGENT_TIMEOUT,
            ErrorCode.TOOL_NOT_FOUND,
            ErrorCode.MCP_CONNECTION_ERROR,
            ErrorCode.TOOL_EXECUTION_ERROR,
        ]
        for c in codes:
            self._assert_errcode(c)

    def test_auth_codes_exist(self):
        """5xxx 认证错误码均已定义"""
        codes = [
            ErrorCode.AUTH_INVALID_TOKEN,
            ErrorCode.AUTH_EXPIRED,
            ErrorCode.AUTH_INSUFFICIENT,
        ]
        for c in codes:
            self._assert_errcode(c)

    def test_all_codes_unique(self):
        """所有错误码值唯一"""
        all_codes = [
            getattr(ErrorCode, attr)
            for attr in dir(ErrorCode)
            if not attr.startswith("_")
        ]
        assert len(all_codes) == len(set(all_codes)), "存在重复的错误码值"


# ─────────────────────────────────────────────────────────────────────────────
# AppError 基类
# ─────────────────────────────────────────────────────────────────────────────

class TestAppError:
    """AppError 基类属性与行为"""

    def test_basic_instantiation(self):
        err = AppError(code="ERR-9999", message="测试错误", status_code=400)
        assert err.code == "ERR-9999"
        assert err.message == "测试错误"
        assert err.status_code == 400
        assert err.details == {}

    def test_default_status_code_is_500(self):
        err = AppError(code="ERR-0001", message="服务器错误")
        assert err.status_code == 500

    def test_details_stored(self):
        details = {"field": "title", "reason": "空值"}
        err = AppError(code="ERR-1002", message="校验失败", details=details)
        assert err.details == details

    def test_is_exception(self):
        err = AppError(code="ERR-0001", message="测试")
        assert isinstance(err, Exception)

    def test_str_representation_contains_message(self):
        err = AppError(code="ERR-0001", message="某错误信息")
        assert "某错误信息" in str(err)


# ─────────────────────────────────────────────────────────────────────────────
# 各子类
# ─────────────────────────────────────────────────────────────────────────────

class TestNotFoundError:
    def test_default_status_code(self):
        err = NotFoundError()
        assert err.status_code == 404

    def test_default_code(self):
        err = NotFoundError()
        assert err.code == ErrorCode.NOT_FOUND

    def test_custom_message(self):
        err = NotFoundError(message="论文不存在")
        assert err.message == "论文不存在"

    def test_is_app_error(self):
        assert isinstance(NotFoundError(), AppError)


class TestValidationError:
    def test_default_status_code(self):
        err = ValidationError()
        assert err.status_code == 422

    def test_default_code(self):
        err = ValidationError()
        assert err.code == ErrorCode.VALIDATION_ERROR

    def test_is_app_error(self):
        assert isinstance(ValidationError(), AppError)


class TestAuthError:
    def test_default_status_code(self):
        err = AuthError()
        assert err.status_code == 401

    def test_default_code(self):
        err = AuthError()
        assert err.code == ErrorCode.AUTH_INVALID_TOKEN

    def test_custom_code(self):
        err = AuthError(code=ErrorCode.AUTH_EXPIRED)
        assert err.code == ErrorCode.AUTH_EXPIRED

    def test_is_app_error(self):
        assert isinstance(AuthError(), AppError)


class TestLLMError:
    def test_default_status_code(self):
        err = LLMError()
        assert err.status_code == 502

    def test_default_code(self):
        err = LLMError()
        assert err.code == ErrorCode.LLM_API_ERROR

    def test_is_app_error(self):
        assert isinstance(LLMError(), AppError)


class TestAgentError:
    def test_default_status_code(self):
        err = AgentError()
        assert err.status_code == 500

    def test_default_code(self):
        err = AgentError()
        assert err.code == ErrorCode.TOOL_EXECUTION_ERROR

    def test_details_propagation(self):
        details = {"tool": "summarize", "reason": "超时"}
        err = AgentError(details=details)
        assert err.details == details

    def test_is_app_error(self):
        assert isinstance(AgentError(), AppError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AppError):
            raise AgentError(message="Agent 执行超时")
