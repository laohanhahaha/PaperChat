"""智能路由引擎单元测试（适配提取后的 ModelRouter）"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestModelRouter:
    """ModelRouter 测试"""

    @pytest.fixture
    def router(self):
        from app.services.routing.route_engine import ModelRouter
        return ModelRouter()

    def test_task_complexity_mapping(self, router):
        """任务复杂度映射完整性"""
        assert router.TASK_COMPLEXITY.get("simple_qa") == "simple"
        assert router.TASK_COMPLEXITY.get("deep_analysis") == "complex"
        assert router.TASK_COMPLEXITY.get("translate") == "simple"
        assert router.TASK_COMPLEXITY.get("summarize") == "medium"

    @pytest.mark.asyncio
    async def test_route_local_only_mode(self, router):
        """本地模式使用默认模型（当前环境无真实本地模型）"""
        mock_settings = {
            "routing": {
                "model_mode": "local_only",
                "budget_limit": 10.0,
                "confirm_threshold": 0.5,
            }
        }
        mock_db = MagicMock()

        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value=mock_settings)

            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 0}
                )

                result = await router.route(
                    "test query", "deep_analysis", user_id=1, db=mock_db
                )
                assert result["tier"] == "cloud_standard"
                assert result["estimated_cost"] == 0
                assert "本地" in result["reason"]

    @pytest.mark.asyncio
    async def test_route_cloud_only_mode(self, router):
        """云端模式使用 cloud 模型"""
        mock_settings = {
            "routing": {
                "model_mode": "cloud_only",
                "budget_limit": 10.0,
                "confirm_threshold": 0.5,
            }
        }
        mock_db = MagicMock()

        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value=mock_settings)

            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 0}
                )

                result = await router.route(
                    "complex task", "deep_analysis", user_id=1, db=mock_db
                )
                assert result["tier"] in ("cloud_standard", "cloud_premium")

    @pytest.mark.asyncio
    async def test_route_budget_exceeded_fallback(self, router):
        """预算超限时使用默认模型"""
        mock_settings = {
            "routing": {
                "model_mode": "smart_route",
                "budget_limit": 10.0,
                "confirm_threshold": 0.5,
            }
        }
        mock_db = MagicMock()

        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value=mock_settings)

            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 15.0}
                )

                result = await router.route(
                    "complex query", "deep_analysis", user_id=1, db=mock_db
                )
                assert result["tier"] == "cloud_standard"
                assert "预算" in result["reason"]

    @pytest.mark.asyncio
    async def test_route_complex_task_uses_premium(self, router):
        """复杂任务使用高级模型"""
        mock_settings = {
            "routing": {
                "model_mode": "cloud_only",
                "budget_limit": 100.0,
                "confirm_threshold": 0.5,
            }
        }
        mock_db = MagicMock()

        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value=mock_settings)

            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 0}
                )

                result = await router.route(
                    "写一篇综述", "literature_review", user_id=1, db=mock_db
                )
                assert result["tier"] == "cloud_premium"

    @pytest.mark.asyncio
    async def test_route_returns_required_fields(self, router):
        """路由结果包含所有必需字段"""
        required_fields = [
            "model",
            "tier",
            "estimated_cost",
            "needs_confirmation",
            "reason",
        ]
        mock_db = MagicMock()
        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value={"routing": {}})
            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 0}
                )
                result = await router.route(
                    "hello", "simple_qa", user_id=1, db=mock_db
                )
                for field in required_fields:
                    assert field in result, f"缺少字段: {field}"

    @pytest.mark.asyncio
    async def test_route_simple_task_no_confirmation(self, router):
        """简单任务不需要费用确认"""
        mock_settings = {
            "routing": {
                "model_mode": "smart_route",
                "budget_limit": 10.0,
                "confirm_threshold": 0.01,
            }
        }
        mock_db = MagicMock()
        with patch("app.services.settings_service.SettingsService") as MockSettings:
            instance = MockSettings.return_value
            instance.get_setting_values = AsyncMock(return_value=mock_settings)
            with patch("app.services.cost.cost_service.CostService") as MockCost:
                cost_instance = MockCost.return_value
                cost_instance.get_budget_status_by_user_id = AsyncMock(
                    return_value={"used": 0}
                )
                result = await router.route(
                    "1+1=?", "simple_qa", user_id=1, db=mock_db
                )
                assert result["needs_confirmation"] is False
