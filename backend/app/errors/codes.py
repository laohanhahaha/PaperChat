# -*- coding: utf-8 -*-
"""结构化错误码定义

所有错误码遵循 ERR-XXXX 格式:
  1xxx: 通用错误
  2xxx: 论文相关
  3xxx: RAG/LLM 相关
  4xxx: Agent/MCP 相关
  5xxx: 认证相关
"""


class ErrorCode:
    # ---- 通用 1xxx ----
    INTERNAL_ERROR = "ERR-1001"
    VALIDATION_ERROR = "ERR-1002"
    NOT_FOUND = "ERR-1003"
    RATE_LIMITED = "ERR-1004"

    # ---- 论文 2xxx ----
    PAPER_NOT_FOUND = "ERR-2001"
    PAPER_PARSE_FAILED = "ERR-2002"
    PAPER_TOO_LARGE = "ERR-2003"

    # ---- RAG/LLM 3xxx ----
    LLM_API_ERROR = "ERR-3001"
    RAG_INDEX_ERROR = "ERR-3002"
    EMBEDDING_ERROR = "ERR-3003"
    CONTEXT_TOO_LONG = "ERR-3004"

    # ---- Agent/MCP 4xxx ----
    AGENT_TIMEOUT = "ERR-4001"
    TOOL_NOT_FOUND = "ERR-4002"
    MCP_CONNECTION_ERROR = "ERR-4003"
    TOOL_EXECUTION_ERROR = "ERR-4004"

    # ---- 认证 5xxx ----
    AUTH_INVALID_TOKEN = "ERR-5001"
    AUTH_EXPIRED = "ERR-5002"
    AUTH_INSUFFICIENT = "ERR-5003"
