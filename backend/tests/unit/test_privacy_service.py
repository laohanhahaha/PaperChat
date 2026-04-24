# -*- coding: utf-8 -*-
"""隐私服务单元测试

覆盖：
- DataMinimizer.minimize() 白名单字段过滤
- DataMinimizer.anonymize() 敏感字段脱敏
- ApiKeyAuditor.log_access() 记录写入
- ApiKeyAuditor.get_audit_log() 查询与 limit 控制
- AnonymousMode.strip_identity() 身份字段剥离
- AnonymousMode.is_anonymous_query() 匿名请求检测
"""
import pytest

from app.services.privacy.privacy_service import (
    AnonymousMode,
    ApiKeyAuditor,
    DataMinimizer,
    _IDENTITY_FIELDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# DataMinimizer
# ─────────────────────────────────────────────────────────────────────────────

class TestDataMinimizer:
    def setup_method(self):
        self.dm = DataMinimizer()

    def test_minimize_keeps_allowed_fields(self):
        data = {"name": "Alice", "email": "a@b.com", "score": 99}
        result = self.dm.minimize(data, ["name", "score"])
        assert result == {"name": "Alice", "score": 99}
        assert "email" not in result

    def test_minimize_empty_data_returns_empty(self):
        assert self.dm.minimize({}, ["name"]) == {}

    def test_minimize_empty_allowed_fields_returns_empty(self):
        assert self.dm.minimize({"name": "Alice"}, []) == {}

    def test_minimize_all_fields_allowed(self):
        data = {"a": 1, "b": 2}
        result = self.dm.minimize(data, ["a", "b"])
        assert result == data

    def test_minimize_nonexistent_allowed_fields_returns_empty(self):
        data = {"a": 1}
        result = self.dm.minimize(data, ["z"])
        assert result == {}

    def test_anonymize_masks_string_field(self):
        data = {"api_key": "sk-abcdefghijklmn"}
        result = self.dm.anonymize(data, ["api_key"])
        masked = result["api_key"]
        assert "***" in masked
        # 原始字符串不应完整出现
        assert masked != "sk-abcdefghijklmn"

    def test_anonymize_short_string_replaced_with_stars(self):
        """长度 <= 4 的字符串直接替换为 '***'"""
        data = {"pin": "1234"}
        result = self.dm.anonymize(data, ["pin"])
        assert result["pin"] == "***"

    def test_anonymize_non_string_replaced_with_stars(self):
        data = {"user_id": 12345}
        result = self.dm.anonymize(data, ["user_id"])
        assert result["user_id"] == "***"

    def test_anonymize_does_not_modify_original(self):
        data = {"email": "test@example.com", "role": "user"}
        result = self.dm.anonymize(data, ["email"])
        # 原始 dict 不变
        assert data["email"] == "test@example.com"
        assert "role" in result

    def test_anonymize_only_masks_listed_fields(self):
        data = {"email": "test@example.com", "name": "Bob"}
        result = self.dm.anonymize(data, ["email"])
        assert "***" in result["email"]
        assert result["name"] == "Bob"

    def test_anonymize_empty_data_returns_empty(self):
        assert self.dm.anonymize({}, ["field"]) == {}


# ─────────────────────────────────────────────────────────────────────────────
# ApiKeyAuditor
# ─────────────────────────────────────────────────────────────────────────────

class TestApiKeyAuditor:
    def setup_method(self):
        self.auditor = ApiKeyAuditor()

    def test_log_access_and_retrieve(self):
        self.auditor.log_access("key-001", "query_paper", "192.168.1.1")
        log = self.auditor.get_audit_log("key-001")
        assert len(log) == 1
        entry = log[0]
        assert entry["key_id"] == "key-001"
        assert entry["action"] == "query_paper"
        assert entry["source"] == "192.168.1.1"
        assert "timestamp" in entry

    def test_unknown_key_returns_empty_list(self):
        result = self.auditor.get_audit_log("nonexistent-key")
        assert result == []

    def test_multiple_entries_preserved(self):
        for i in range(5):
            self.auditor.log_access("key-multi", f"action-{i}", "127.0.0.1")
        log = self.auditor.get_audit_log("key-multi")
        assert len(log) == 5

    def test_limit_respected(self):
        for i in range(10):
            self.auditor.log_access("key-limit", f"action-{i}", "127.0.0.1")
        log = self.auditor.get_audit_log("key-limit", limit=3)
        assert len(log) == 3

    def test_limit_returns_most_recent(self):
        """get_audit_log(limit=n) 应返回最新的 n 条"""
        for i in range(5):
            self.auditor.log_access("key-order", f"action-{i}", "127.0.0.1")
        log = self.auditor.get_audit_log("key-order", limit=2)
        # 最后两条 action 为 action-3, action-4
        actions = [e["action"] for e in log]
        assert "action-3" in actions
        assert "action-4" in actions

    def test_multiple_keys_isolated(self):
        self.auditor.log_access("key-A", "upload", "10.0.0.1")
        self.auditor.log_access("key-B", "download", "10.0.0.2")
        assert len(self.auditor.get_audit_log("key-A")) == 1
        assert len(self.auditor.get_audit_log("key-B")) == 1

    def test_max_per_key_respected(self):
        """超过 max_per_key 上限时旧记录被丢弃"""
        auditor = ApiKeyAuditor(max_per_key=5)
        for i in range(10):
            auditor.log_access("bounded-key", f"action-{i}", "127.0.0.1")
        log = auditor.get_audit_log("bounded-key", limit=100)
        assert len(log) == 5


# ─────────────────────────────────────────────────────────────────────────────
# AnonymousMode
# ─────────────────────────────────────────────────────────────────────────────

class TestAnonymousMode:
    def setup_method(self):
        self.anon = AnonymousMode()

    # strip_identity
    def test_strip_removes_identity_fields(self):
        data = {
            "user_id": 42,
            "email": "test@example.com",
            "query": "什么是深度学习",
            "role": "user",
        }
        result = self.anon.strip_identity(data)
        assert "user_id" not in result
        assert "email" not in result
        assert result["query"] == "什么是深度学习"
        assert result["role"] == "user"

    def test_strip_empty_data_returns_empty(self):
        assert self.anon.strip_identity({}) == {}

    def test_strip_no_identity_fields_unchanged(self):
        data = {"title": "Paper A", "score": 0.95}
        result = self.anon.strip_identity(data)
        assert result == data

    def test_strip_case_insensitive(self):
        """字段名匹配应不区分大小写"""
        data = {"User_Id": 10, "content": "hello"}
        result = self.anon.strip_identity(data)
        # user_id 的大小写变体 User_Id 应被移除
        assert "User_Id" not in result

    def test_all_identity_fields_are_stripped(self):
        """所有已知 _IDENTITY_FIELDS 均被剥离"""
        data = {field: "sensitive" for field in _IDENTITY_FIELDS}
        data["safe_field"] = "keep_me"
        result = self.anon.strip_identity(data)
        for field in _IDENTITY_FIELDS:
            assert field not in result
        assert result["safe_field"] == "keep_me"

    # is_anonymous_query — 使用 mock request 对象
    def test_is_anonymous_via_header(self):
        req = _MockRequest(headers={"X-Anonymous-Query": "true"})
        assert self.anon.is_anonymous_query(req) is True

    def test_is_anonymous_via_query_param(self):
        req = _MockRequest(query_params={"anonymous": "1"})
        assert self.anon.is_anonymous_query(req) is True

    def test_non_anonymous_request(self):
        req = _MockRequest()
        assert self.anon.is_anonymous_query(req) is False

    def test_anonymous_header_case_insensitive_value(self):
        req = _MockRequest(headers={"X-Anonymous-Query": "TRUE"})
        assert self.anon.is_anonymous_query(req) is True


# ─────────────────────────────────────────────────────────────────────────────
# 辅助 mock request 对象
# ─────────────────────────────────────────────────────────────────────────────

class _MockRequest:
    """模拟 FastAPI Request，提供 headers 和 query_params 属性"""

    def __init__(self, headers: dict | None = None, query_params: dict | None = None):
        self.headers = _CaseInsensitiveDict(headers or {})
        self.query_params = query_params or {}


class _CaseInsensitiveDict(dict):
    def get(self, key, default=""):
        # 转小写查找
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default
