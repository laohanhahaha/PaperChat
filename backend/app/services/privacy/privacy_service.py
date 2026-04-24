# -*- coding: utf-8 -*-
"""隐私合规服务

提供三个核心能力:
  DataMinimizer  — 数据最小化与脱敏
  ApiKeyAuditor  — API Key 访问审计日志
  AnonymousMode  — 匿名查询判断与身份信息剥离
"""
import re
import time
import logging
from collections import deque
from typing import Any, Callable, Deque

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DataMinimizer
# ---------------------------------------------------------------------------

class DataMinimizer:
    """数据最小化与字段脱敏工具

    不持有任何状态，所有方法均为纯函数风格（可安全复用单例）。
    """

    def minimize(self, data: dict, allowed_fields: list) -> dict:
        """只保留白名单字段，其余字段一律剔除。

        Args:
            data: 原始数据字典
            allowed_fields: 允许保留的字段名列表（顶层 key）

        Returns:
            仅包含白名单字段的新字典
        """
        if not data or not allowed_fields:
            return {}
        allowed_set = set(allowed_fields)
        result = {k: v for k, v in data.items() if k in allowed_set}
        logger.debug(
            "DataMinimizer.minimize: 保留 %d/%d 字段",
            len(result),
            len(data),
        )
        return result

    def anonymize(self, data: dict, sensitive_fields: list) -> dict:
        """对指定敏感字段进行部分掩码脱敏。

        脱敏规则:
          - 字符串: 保留首尾各 1/4 字符，中间替换为 ***
          - 非字符串: 直接替换为 "***"

        Args:
            data: 原始数据字典
            sensitive_fields: 需要脱敏的字段名列表

        Returns:
            脱敏后的新字典（不修改原始 data）
        """
        if not data:
            return {}
        result = dict(data)
        sensitive_set = set(sensitive_fields)
        for key in sensitive_set:
            if key not in result:
                continue
            value = result[key]
            if isinstance(value, str) and len(value) > 4:
                keep = max(1, len(value) // 4)
                result[key] = value[:keep] + "***" + value[-keep:]
            else:
                result[key] = "***"
        logger.debug(
            "DataMinimizer.anonymize: 脱敏字段 %s",
            list(sensitive_set & set(result)),
        )
        return result


# ---------------------------------------------------------------------------
# ApiKeyAuditor
# ---------------------------------------------------------------------------

_AuditEntry = dict  # {"key_id", "action", "source", "timestamp"}


class ApiKeyAuditor:
    """API Key 使用审计记录器（内存实现，生产环境建议持久化到 DB）

    每个 key_id 独立维护一个有限长度的双端队列，避免无限增长。
    """

    DEFAULT_MAX_LOG = 1000  # 每个 key 最多保留的审计条目数

    def __init__(self, max_per_key: int = DEFAULT_MAX_LOG):
        self._logs: dict[str, Deque[_AuditEntry]] = {}
        self._max_per_key = max_per_key

    def log_access(self, key_id: str, action: str, source: str) -> None:
        """记录 API Key 访问事件（同步、无阻塞）。

        Args:
            key_id: API Key 标识符（脱敏存储建议仅传末4位）
            action: 操作描述，如 "query_paper"、"upload"
            source: 请求来源，如 IP 地址或服务名
        """
        if key_id not in self._logs:
            self._logs[key_id] = deque(maxlen=self._max_per_key)
        entry: _AuditEntry = {
            "key_id": key_id,
            "action": action,
            "source": source,
            "timestamp": time.time(),
        }
        self._logs[key_id].append(entry)
        logger.debug("ApiKeyAuditor: key=%s action=%s source=%s", key_id, action, source)

    def get_audit_log(self, key_id: str, limit: int = 50) -> list:
        """查询指定 key 的最近审计日志。

        Args:
            key_id: API Key 标识符
            limit: 返回的最大条目数

        Returns:
            按时间升序排列的审计条目列表
        """
        if key_id not in self._logs:
            return []
        entries = list(self._logs[key_id])
        # 返回最新的 limit 条（队列末尾为最新）
        return entries[-limit:] if limit > 0 else entries


# ---------------------------------------------------------------------------
# AnonymousMode
# ---------------------------------------------------------------------------

# 身份信息字段白名单（用于 strip_identity）
_IDENTITY_FIELDS = {
    "user_id", "user_name", "username", "email", "phone",
    "ip_address", "ip", "device_id", "session_id",
    "real_name", "id_card", "address",
}

# 请求头或参数中表示匿名访问的标志
_ANONYMOUS_HEADER = "X-Anonymous-Query"
_ANONYMOUS_PARAM = "anonymous"


class AnonymousMode:
    """匿名查询检测与身份信息剥离工具"""

    def is_anonymous_query(self, request: Any) -> bool:
        """判断当前请求是否为匿名查询。

        检测规则（任一满足即为匿名）:
          1. 请求头 X-Anonymous-Query: true
          2. 查询参数 anonymous=1 / anonymous=true

        Args:
            request: FastAPI Request 对象

        Returns:
            True 表示匿名查询
        """
        try:
            # FastAPI/Starlette Request
            header_val = request.headers.get(_ANONYMOUS_HEADER, "").lower()
            if header_val in ("true", "1", "yes"):
                return True
            param_val = request.query_params.get(_ANONYMOUS_PARAM, "").lower()
            if param_val in ("true", "1", "yes"):
                return True
        except AttributeError:
            # 非标准请求对象，回退到字典访问
            headers = getattr(request, "headers", {}) or {}
            if str(headers.get(_ANONYMOUS_HEADER, "")).lower() in ("true", "1"):
                return True
        return False

    def strip_identity(self, data: dict) -> dict:
        """从数据字典中移除所有已知身份信息字段。

        Args:
            data: 原始数据字典

        Returns:
            移除身份字段后的新字典
        """
        if not data:
            return {}
        result = {k: v for k, v in data.items() if k.lower() not in _IDENTITY_FIELDS}
        removed = set(data) - set(result)
        if removed:
            logger.debug("AnonymousMode.strip_identity: 移除字段 %s", removed)
        return result


# ---------------------------------------------------------------------------
# 全局单例（便于直接 import 使用，也支持通过 DI 注入）
# ---------------------------------------------------------------------------
data_minimizer = DataMinimizer()
api_key_auditor = ApiKeyAuditor()
anonymous_mode = AnonymousMode()
