"""Agent 指标监控路由

提供 Agent 运行指标的查询接口，支持仪表盘展示和工具使用分析
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.user.auth_service import get_current_user
from app.services.metrics.metrics_service import metrics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class DashboardStatsResponse(BaseModel):
    """仪表盘统计响应模型"""
    total_runs: int = Field(..., description="总运行次数")
    success_rate: float = Field(..., description="成功率（%）")
    avg_duration_ms: float = Field(..., description="平均耗时（毫秒）")
    total_tool_calls: int = Field(..., description="总工具调用次数")
    cache_hit_rate: float = Field(..., description="缓存命中率（%）")
    tool_usage_ranking: list = Field(..., description="工具使用排名")
    period_days: int = Field(..., description="统计周期（天）")


class ToolStatItem(BaseModel):
    """工具统计项"""
    tool_name: str = Field(..., description="工具名称")
    call_count: int = Field(..., description="调用次数")
    success_count: int = Field(..., description="成功次数")
    success_rate: float = Field(..., description="成功率（%）")
    avg_duration_ms: float = Field(..., description="平均耗时（毫秒）")
    cache_hit_count: int = Field(..., description="缓存命中次数")
    cache_hit_rate: float = Field(..., description="缓存命中率（%）")


class ToolStatsResponse(BaseModel):
    """工具统计响应模型"""
    tools: list[ToolStatItem] = Field(..., description="工具统计列表")
    period_days: int = Field(..., description="统计周期（天）")


class RecentRunsResponse(BaseModel):
    """最近运行记录响应模型"""
    runs: list[dict] = Field(..., description="运行记录列表")
    total: int = Field(..., description="总记录数")
    limit: int = Field(..., description="每页数量")
    offset: int = Field(..., description="偏移量")


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard(
    days: int = Query(default=7, ge=1, le=90, description="统计天数（1-90）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取仪表盘统计数据
    
    返回指定时间范围内的聚合统计：
    - 总运行次数
    - 成功率
    - 平均耗时
    - 总工具调用次数
    - 缓存命中率
    - 工具使用排名
    """
    stats = await metrics_service.get_dashboard_stats(db, days=days)
    return DashboardStatsResponse(**stats)


@router.get("/runs", response_model=RecentRunsResponse)
async def get_runs(
    limit: int = Query(default=50, ge=1, le=100, description="每页数量（1-100）"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取最近运行记录
    
    分页查询 Agent 运行记录，按时间倒序排列
    """
    result = await metrics_service.get_recent_runs(db, limit=limit, offset=offset)
    return RecentRunsResponse(**result)


@router.get("/tools", response_model=ToolStatsResponse)
async def get_tools(
    days: int = Query(default=7, ge=1, le=90, description="统计天数（1-90）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取工具使用统计
    
    返回每个工具的详细统计：
    - 调用次数
    - 成功率
    - 平均耗时
    - 缓存命中率
    """
    tools = await metrics_service.get_tool_stats(db, days=days)
    return ToolStatsResponse(
        tools=[ToolStatItem(**tool) for tool in tools],
        period_days=days
    )
