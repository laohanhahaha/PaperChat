"""智能路由配置管理 API"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import get_current_user
from app.services.routing.route_engine import model_router
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


class RoutingConfigUpdate(BaseModel):
    model_mode: str = Field("smart_route", pattern="^(local_only|smart_route|cloud_only)$")
    budget_limit: float = Field(10.0, ge=0)
    confirm_threshold: float = Field(0.5, ge=0)


class RouteRequest(BaseModel):
    query: str = Field(..., min_length=1)
    task_type: str = Field("simple_qa")
    paper_id: int = Field(None)


@router.get("/config")
async def get_routing_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前路由配置"""
    from app.services.settings_service import SettingsService

    svc = SettingsService()
    settings = await svc.get_setting_values(current_user.id, db)
    routing = settings.get("routing", {})
    # 补充默认值
    return {
        "model_mode": routing.get("model_mode", "smart_route"),
        "budget_limit": routing.get("budget_limit", 10.0),
        "confirm_threshold": routing.get("confirm_threshold", 0.5),
    }


@router.put("/config")
async def update_routing_config(
    req: RoutingConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新路由配置"""
    from app.services.settings_service import SettingsService

    svc = SettingsService()
    await svc.update_setting_values(
        current_user.id,
        db,
        values={
            "routing": {
                "model_mode": req.model_mode,
                "budget_limit": req.budget_limit,
                "confirm_threshold": req.confirm_threshold,
            }
        },
    )
    return {"message": "路由配置已更新", "config": req.model_dump()}


@router.post("/route")
async def get_route_decision(
    req: RouteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取路由决策（不实际调用 LLM，仅查询路由结果）"""
    decision = await model_router.route(
        query=req.query,
        task_type=req.task_type,
        user_id=current_user.id,
        db=db,
        paper_id=req.paper_id or None,
    )
    return decision
