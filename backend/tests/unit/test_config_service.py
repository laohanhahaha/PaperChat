# -*- coding: utf-8 -*-
"""配置服务单元测试

覆盖：
- ConfigService 四层优先级覆盖链（user_db > yaml > .env > default）
- get() 按正确优先级返回值
- set() 写入 user 层并触发回调
- on_change() 注册回调，值变更时触发
- 回调异常不影响主流程
- ProjectConfig._flatten() 嵌套 dict 展开
"""
import pytest
from unittest.mock import MagicMock, patch

from app.config import ConfigService, ProjectConfig, Settings


# ─────────────────────────────────────────────────────────────────────────────
# Helpers：创建干净的 ConfigService 实例
# ─────────────────────────────────────────────────────────────────────────────

def _make_service(
    settings_overrides: dict | None = None,
    yaml_data: dict | None = None,
) -> ConfigService:
    """构造一个隔离的 ConfigService，不依赖真实文件系统"""
    # 构造 Settings mock
    settings = MagicMock(spec=Settings)
    # 为已知属性配置默认返回值
    settings.APP_NAME = "TestApp"
    settings.DEBUG = False
    settings.DEFAULT_USER_ID = 1
    if settings_overrides:
        for k, v in settings_overrides.items():
            setattr(settings, k, v)

    # 构造 ProjectConfig mock
    project_cfg = MagicMock(spec=ProjectConfig)
    project_cfg.get.return_value = None  # 默认 yaml 层无值
    if yaml_data:
        def yaml_get(key, default=None):
            return yaml_data.get(key, default)
        project_cfg.get.side_effect = yaml_get

    return ConfigService(base_settings=settings, project_cfg=project_cfg)


# ─────────────────────────────────────────────────────────────────────────────
# 四层优先级覆盖链
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigServicePriority:
    def test_user_layer_overrides_all(self):
        """Layer 4（user）优先级最高"""
        svc = _make_service(
            settings_overrides={"APP_NAME": "FromSettings"},
            yaml_data={"APP_NAME": "FromYaml"},
        )
        svc.set("APP_NAME", "FromUser")
        assert svc.get("APP_NAME") == "FromUser"

    def test_yaml_layer_overrides_settings(self):
        """Layer 3（yaml）优先于 Layer 2（.env/Settings）"""
        svc = _make_service(
            settings_overrides={"MY_KEY": "from_settings"},
            yaml_data={"MY_KEY": "from_yaml"},
        )
        assert svc.get("MY_KEY") == "from_yaml"

    def test_settings_layer_used_when_no_yaml(self):
        """无 yaml 配置时回退到 Settings 层"""
        svc = _make_service(settings_overrides={"APP_NAME": "FromSettings"})
        assert svc.get("APP_NAME") == "FromSettings"

    def test_default_returned_when_no_layer_has_value(self):
        """所有层均无值时返回 default"""
        svc = _make_service()
        # "NONEXISTENT_KEY" 在所有层都不存在
        assert svc.get("NONEXISTENT_KEY", "fallback") == "fallback"

    def test_default_is_none_when_not_provided(self):
        svc = _make_service()
        assert svc.get("NONEXISTENT_KEY") is None

    def test_user_layer_set_then_get(self):
        svc = _make_service()
        svc.set("custom.feature", True)
        assert svc.get("custom.feature") is True

    def test_multiple_set_overwrite(self):
        svc = _make_service()
        svc.set("debug_level", 1)
        svc.set("debug_level", 3)
        assert svc.get("debug_level") == 3


# ─────────────────────────────────────────────────────────────────────────────
# on_change 回调
# ─────────────────────────────────────────────────────────────────────────────

class TestOnChange:
    def test_callback_triggered_on_value_change(self):
        svc = _make_service()
        received = []

        svc.on_change("my_key", lambda k, v: received.append((k, v)))
        svc.set("my_key", "initial")
        svc.set("my_key", "updated")

        # 两次 set 均触发（第一次是从无到有的变化）
        assert len(received) >= 1
        assert received[-1] == ("my_key", "updated")

    def test_callback_not_triggered_when_value_unchanged(self):
        svc = _make_service()
        count = [0]

        svc.set("my_key", "same_value")  # 初始写入
        svc.on_change("my_key", lambda k, v: count.__setitem__(0, count[0] + 1))
        svc.set("my_key", "same_value")  # 值不变，不应触发

        assert count[0] == 0

    def test_multiple_callbacks_all_triggered(self):
        svc = _make_service()
        hits = []

        svc.on_change("k", lambda key, val: hits.append("cb1"))
        svc.on_change("k", lambda key, val: hits.append("cb2"))
        svc.set("k", "new_val")

        assert "cb1" in hits
        assert "cb2" in hits

    def test_callback_exception_does_not_raise(self):
        """回调抛出异常时不影响 set() 正常完成"""
        svc = _make_service()

        def bad_callback(k, v):
            raise RuntimeError("回调炸了")

        svc.on_change("crash_key", bad_callback)
        # 不应抛出
        svc.set("crash_key", "value")
        assert svc.get("crash_key") == "value"

    def test_callback_receives_correct_key_and_value(self):
        svc = _make_service()
        results = {}

        svc.on_change("target", lambda k, v: results.update({k: v}))
        svc.set("target", 42)

        assert results == {"target": 42}


# ─────────────────────────────────────────────────────────────────────────────
# ProjectConfig._flatten
# ─────────────────────────────────────────────────────────────────────────────

class TestProjectConfigFlatten:
    def test_flat_dict_unchanged(self):
        result = ProjectConfig._flatten({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_nested_dict_flattened_with_dot(self):
        result = ProjectConfig._flatten({"rag": {"chunk_size": 512, "top_k": 5}})
        assert result == {"rag.chunk_size": 512, "rag.top_k": 5}

    def test_deeply_nested(self):
        result = ProjectConfig._flatten({"a": {"b": {"c": 99}}})
        assert result == {"a.b.c": 99}

    def test_mixed_nested_and_flat(self):
        result = ProjectConfig._flatten({"x": 1, "y": {"z": 2}})
        assert "x" in result
        assert "y.z" in result
        assert result["x"] == 1
        assert result["y.z"] == 2
