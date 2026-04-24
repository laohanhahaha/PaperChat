"""费用与预算管理路由"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.cost.cost_service import cost_service, MODEL_PRICING, get_current_model, set_current_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cost", tags=["cost"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class BudgetSetRequest(BaseModel):
    monthly_limit: float = Field(..., gt=0, description="月预算上限（美元）")


class ModelSwitchRequest(BaseModel):
    model: str = Field(..., description="模型名称")


# ─── 路由 ─────────────────────────────────────────────────────────────────────

@router.get("/models")
async def get_models():
    """获取可用模型列表及单价信息"""
    models = []
    for name, info in MODEL_PRICING.items():
        models.append({
            "name": name,
            "description": info["description"],
            "input_price_per_1k": info["input"],
            "output_price_per_1k": info["output"],
            "input_price_per_1m": round(info["input"] * 1000, 4),
            "output_price_per_1m": round(info["output"] * 1000, 4),
        })
    return {"models": models}


@router.get("/session/{session_id}")
async def get_session_cost(session_id: str, db: AsyncSession = Depends(get_db)):
    """查询指定会话的费用汇总"""
    return await cost_service.get_session_cost(db, session_id)


@router.get("/daily")
async def get_daily_cost(
    date: Optional[str] = Query(None, description="日期（YYYY-MM-DD），默认今天"),
    db: AsyncSession = Depends(get_db),
):
    """查询日费用"""
    return await cost_service.get_daily_cost(db, date)


@router.get("/monthly")
async def get_monthly_cost(
    year: Optional[int] = Query(None, description="年份，默认当前年"),
    month: Optional[int] = Query(None, description="月份，默认当前月"),
    db: AsyncSession = Depends(get_db),
):
    """查询月费用"""
    from datetime import datetime
    now = datetime.now()
    return await cost_service.get_monthly_cost(db, year or now.year, month or now.month)


@router.get("/budget")
async def get_budget_status(db: AsyncSession = Depends(get_db)):
    """查询预算使用状态"""
    return await cost_service.get_budget_status(db)


@router.put("/budget")
async def set_budget(req: BudgetSetRequest, db: AsyncSession = Depends(get_db)):
    """设置月度预算"""
    return await cost_service.set_budget(db, req.monthly_limit)


@router.get("/current-model")
async def get_current_model_endpoint():
    """获取当前使用的模型"""
    model = get_current_model()
    info = MODEL_PRICING.get(model, {})
    return {
        "model": model,
        "description": info.get("description", ""),
        "input_price_per_1k": info.get("input", 0),
        "output_price_per_1k": info.get("output", 0),
    }


@router.put("/current-model")
async def switch_model(req: ModelSwitchRequest):
    """切换当前模型"""
    try:
        set_current_model(req.model)
        # 同步更新 llm_service
        from app.services.llm.llm_service import llm_service
        await llm_service.update_config(model=req.model)
        info = MODEL_PRICING.get(req.model, {})
        return {
            "model": req.model,
            "description": info.get("description", ""),
            "message": f"已切换到 {req.model}",
        }
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
