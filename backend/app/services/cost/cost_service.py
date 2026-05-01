"""费用追踪与预算管理服务"""
import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import UsageRecord, BudgetConfig

logger = logging.getLogger(__name__)

# ─── 模型定价表（美元 / 1000 tokens）──────────────────────────────────────────
# 来源：DeepSeek 官方定价（2025年）
MODEL_PRICING: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {
        "input": 0.00027,   # $0.27 / 1M tokens (cache miss)
        "output": 0.00110,  # $1.10 / 1M tokens
        "description": "DeepSeek-V3（通用对话）",
    },
    "deepseek-v4-pro": {
        "input": 0.00055,   # $0.55 / 1M tokens (cache miss)
        "output": 0.00219,  # $2.19 / 1M tokens
        "description": "DeepSeek-V4-Pro（深度推理）",
    },
}

# 当前使用的模型（全局状态，持久化在内存中）
_current_model: str = "deepseek-v4-flash"


def get_current_model() -> str:
    return _current_model


def set_current_model(model: str) -> None:
    global _current_model
    if model not in MODEL_PRICING:
        raise ValueError(f"不支持的模型: {model}，可选: {list(MODEL_PRICING.keys())}")
    _current_model = model


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """计算单次调用费用（美元）"""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["deepseek-v4-flash"])
    # 定价单位：美元/1000 tokens
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
    return round(cost, 8)


class CostService:
    """费用追踪与预算管理服务"""

    async def record_usage(
        self,
        db: AsyncSession,
        model: str,
        input_tokens: int,
        output_tokens: int,
        session_id: Optional[str] = None,
    ) -> UsageRecord:
        """记录一次 LLM 调用的 token 使用量与费用"""
        cost = calculate_cost(model, input_tokens, output_tokens)
        record = UsageRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            session_id=session_id,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.debug(
            "费用记录",
            extra={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
                "session_id": session_id,
            },
        )
        return record

    async def get_session_cost(self, db: AsyncSession, session_id: str) -> dict:
        """查询指定会话的费用汇总"""
        result = await db.execute(
            select(
                func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
                func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count(UsageRecord.id).label("call_count"),
            ).where(UsageRecord.session_id == session_id)
        )
        row = result.one()
        return {
            "session_id": session_id,
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_tokens": (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
            "total_cost": round(row.total_cost or 0.0, 6),
            "call_count": row.call_count or 0,
        }

    async def get_daily_cost(self, db: AsyncSession, target_date: Optional[str] = None) -> dict:
        """查询指定日期（默认今天）的费用汇总"""
        if target_date:
            try:
                d = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                d = date.today()
        else:
            d = date.today()

        result = await db.execute(
            select(
                func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
                func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count(UsageRecord.id).label("call_count"),
            ).where(
                func.date(UsageRecord.created_at) == d.isoformat()
            )
        )
        row = result.one()
        return {
            "date": d.isoformat(),
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_tokens": (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
            "total_cost": round(row.total_cost or 0.0, 6),
            "call_count": row.call_count or 0,
        }

    async def get_monthly_cost(self, db: AsyncSession, year: int, month: int) -> dict:
        """查询指定年月的费用汇总及每日明细"""
        # 总计
        result = await db.execute(
            select(
                func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
                func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
                func.sum(UsageRecord.cost).label("total_cost"),
                func.count(UsageRecord.id).label("call_count"),
            ).where(
                extract("year", UsageRecord.created_at) == year,
                extract("month", UsageRecord.created_at) == month,
            )
        )
        row = result.one()

        # 每日明细
        daily_result = await db.execute(
            select(
                func.date(UsageRecord.created_at).label("day"),
                func.sum(UsageRecord.cost).label("day_cost"),
                func.count(UsageRecord.id).label("day_calls"),
            ).where(
                extract("year", UsageRecord.created_at) == year,
                extract("month", UsageRecord.created_at) == month,
            ).group_by(func.date(UsageRecord.created_at))
            .order_by(func.date(UsageRecord.created_at))
        )
        daily_rows = daily_result.all()
        daily_breakdown = [
            {
                "date": str(r.day),
                "cost": round(r.day_cost or 0.0, 6),
                "calls": r.day_calls or 0,
            }
            for r in daily_rows
        ]

        return {
            "year": year,
            "month": month,
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_tokens": (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
            "total_cost": round(row.total_cost or 0.0, 6),
            "call_count": row.call_count or 0,
            "daily_breakdown": daily_breakdown,
        }

    async def get_budget_status(self, db: AsyncSession) -> dict:
        """查询当前月预算使用状态"""
        budget = await self._get_or_create_budget(db)
        now = datetime.now()
        monthly = await self.get_monthly_cost(db, now.year, now.month)
        used = monthly["total_cost"]
        limit = budget.monthly_limit
        remaining = max(0.0, limit - used)
        percent = round((used / limit * 100) if limit > 0 else 0, 1)
        return {
            "monthly_limit": limit,
            "used": round(used, 6),
            "remaining": round(remaining, 6),
            "percent": percent,
            "over_budget": used >= limit,
        }

    async def set_budget(self, db: AsyncSession, monthly_limit: float) -> dict:
        """设置月度预算上限"""
        budget = await self._get_or_create_budget(db)
        budget.monthly_limit = monthly_limit
        await db.commit()
        await db.refresh(budget)
        return {"monthly_limit": budget.monthly_limit, "updated_at": budget.updated_at.isoformat()}

    async def check_budget(self, db: AsyncSession) -> bool:
        """检查是否已超出本月预算，True 表示未超出（可继续使用）"""
        status = await self.get_budget_status(db)
        return not status["over_budget"]

    async def get_budget_status_by_user_id(self, db: AsyncSession, user_id: int) -> dict:
        """按用户查询当前月预算使用状态（当前系统为单用户模式，user_id 预留扩展）"""
        return await self.get_budget_status(db)

    async def check_budget_exceeded(self, db: AsyncSession, user_id: int, budget_limit: float) -> bool:
        """检查用户月度预算是否超限"""
        status = await self.get_budget_status_by_user_id(db, user_id)
        return status.get("used", 0) >= budget_limit

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    async def _get_or_create_budget(self, db: AsyncSession) -> BudgetConfig:
        result = await db.execute(select(BudgetConfig).limit(1))
        budget = result.scalar_one_or_none()
        if budget is None:
            budget = BudgetConfig(monthly_limit=10.0)
            db.add(budget)
            await db.commit()
            await db.refresh(budget)
        return budget


# 全局单例
cost_service = CostService()
