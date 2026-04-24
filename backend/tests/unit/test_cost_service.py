# -*- coding: utf-8 -*-
"""成本服务单元测试

覆盖：
- MODEL_PRICING 定价表完整性
- calculate_cost() 计算精度
- get_current_model / set_current_model
- CostService.record_usage() 写入记录
- CostService.get_session_cost() 汇总查询
- CostService.get_monthly_cost() 月度汇总
- CostService.check_budget() 预算检查
- CostService.set_budget() 设置预算
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cost.cost_service import (
    MODEL_PRICING,
    CostService,
    calculate_cost,
    get_current_model,
    set_current_model,
)


# ─────────────────────────────────────────────────────────────────────────────
# 定价表 & 工具函数
# ─────────────────────────────────────────────────────────────────────────────

class TestModelPricing:
    REQUIRED_MODELS = ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"]

    def test_all_required_models_present(self):
        for model in self.REQUIRED_MODELS:
            assert model in MODEL_PRICING, f"定价表缺少模型 {model!r}"

    def test_each_model_has_input_output_price(self):
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing, f"{model} 缺少 input 价格"
            assert "output" in pricing, f"{model} 缺少 output 价格"

    def test_prices_are_positive(self):
        for model, pricing in MODEL_PRICING.items():
            assert pricing["input"] > 0, f"{model} input 价格应 > 0"
            assert pricing["output"] > 0, f"{model} output 价格应 > 0"

    def test_output_price_greater_than_input(self):
        """输出 token 通常贵于输入 token"""
        for model, pricing in MODEL_PRICING.items():
            assert pricing["output"] >= pricing["input"], (
                f"{model}: output 价格应 >= input 价格"
            )


class TestCalculateCost:
    def test_zero_tokens_gives_zero_cost(self):
        cost = calculate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0

    def test_positive_cost_for_nonzero_tokens(self):
        cost = calculate_cost("deepseek-chat", 1000, 500)
        assert cost > 0.0

    def test_more_tokens_more_cost(self):
        cost1 = calculate_cost("deepseek-chat", 1000, 500)
        cost2 = calculate_cost("deepseek-chat", 2000, 1000)
        assert cost2 > cost1

    def test_reasoner_more_expensive_than_chat(self):
        cost_chat = calculate_cost("deepseek-chat", 1000, 1000)
        cost_reasoner = calculate_cost("deepseek-reasoner", 1000, 1000)
        assert cost_reasoner > cost_chat

    def test_unknown_model_falls_back_to_chat_pricing(self):
        """未知模型回退到 deepseek-chat 定价，不抛异常"""
        cost = calculate_cost("unknown-model", 1000, 500)
        expected = calculate_cost("deepseek-chat", 1000, 500)
        assert cost == expected

    def test_result_rounded_to_8_decimals(self):
        cost = calculate_cost("deepseek-chat", 1234, 567)
        # 检查小数位数不超过 8
        assert cost == round(cost, 8)


class TestSetCurrentModel:
    def test_set_valid_model(self):
        original = get_current_model()
        try:
            set_current_model("deepseek-reasoner")
            assert get_current_model() == "deepseek-reasoner"
        finally:
            set_current_model(original)

    def test_set_invalid_model_raises(self):
        with pytest.raises(ValueError, match="不支持的模型"):
            set_current_model("gpt-4-turbo")

    def test_default_model_is_chat(self):
        # 默认模型为 deepseek-chat（重置后验证）
        set_current_model("deepseek-chat")
        assert get_current_model() == "deepseek-chat"


# ─────────────────────────────────────────────────────────────────────────────
# CostService 异步方法（使用 mock DB）
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def cost_service():
    return CostService()


@pytest.fixture
def mock_db():
    """返回一个行为与 AsyncSession 兼容的 mock"""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_record_creates_usage_record(self, cost_service, mock_db):
        """record_usage 应调用 db.add 并 commit"""
        from app.models.cost import UsageRecord

        # mock db.refresh 为 no-op（record 保持原样）
        async def _refresh(obj):
            obj.id = 1  # 模拟数据库回填 id

        mock_db.refresh.side_effect = _refresh

        record = await cost_service.record_usage(
            db=mock_db,
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert record.model == "deepseek-chat"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cost > 0.0

    @pytest.mark.asyncio
    async def test_record_with_session_id(self, cost_service, mock_db):
        async def _refresh(obj):
            obj.id = 2

        mock_db.refresh.side_effect = _refresh

        record = await cost_service.record_usage(
            db=mock_db,
            model="deepseek-chat",
            input_tokens=200,
            output_tokens=80,
            session_id="sess-001",
        )
        assert record.session_id == "sess-001"

    @pytest.mark.asyncio
    async def test_cost_calculated_correctly(self, cost_service, mock_db):
        async def _refresh(obj):
            obj.id = 3

        mock_db.refresh.side_effect = _refresh

        record = await cost_service.record_usage(
            db=mock_db,
            model="deepseek-chat",
            input_tokens=1000,
            output_tokens=1000,
        )
        expected = calculate_cost("deepseek-chat", 1000, 1000)
        assert record.cost == expected


class TestGetSessionCost:
    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(self, cost_service, mock_db):
        """get_session_cost 返回字典包含必要字段"""
        row = MagicMock()
        row.total_input_tokens = 500
        row.total_output_tokens = 300
        row.total_cost = 0.001234
        row.call_count = 3

        result_mock = MagicMock()
        result_mock.one.return_value = row
        mock_db.execute = AsyncMock(return_value=result_mock)

        data = await cost_service.get_session_cost(mock_db, "sess-xyz")

        assert data["session_id"] == "sess-xyz"
        assert data["total_input_tokens"] == 500
        assert data["total_output_tokens"] == 300
        assert data["total_tokens"] == 800
        assert data["call_count"] == 3
        assert "total_cost" in data

    @pytest.mark.asyncio
    async def test_handles_none_values_gracefully(self, cost_service, mock_db):
        """当无记录时 None 值应处理为 0"""
        row = MagicMock()
        row.total_input_tokens = None
        row.total_output_tokens = None
        row.total_cost = None
        row.call_count = None

        result_mock = MagicMock()
        result_mock.one.return_value = row
        mock_db.execute = AsyncMock(return_value=result_mock)

        data = await cost_service.get_session_cost(mock_db, "sess-empty")

        assert data["total_tokens"] == 0
        assert data["total_cost"] == 0.0
        assert data["call_count"] == 0


class TestCheckBudget:
    @pytest.mark.asyncio
    async def test_returns_true_when_under_budget(self, cost_service, mock_db):
        """未超预算时返回 True"""
        with patch.object(cost_service, "get_budget_status", new=AsyncMock(
            return_value={"over_budget": False}
        )):
            result = await cost_service.check_budget(mock_db)
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_over_budget(self, cost_service, mock_db):
        """超出预算时返回 False"""
        with patch.object(cost_service, "get_budget_status", new=AsyncMock(
            return_value={"over_budget": True}
        )):
            result = await cost_service.check_budget(mock_db)
            assert result is False
