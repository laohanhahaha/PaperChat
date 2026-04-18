"""功能开关管理路由

提供功能开关的查询和更新接口
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.feature_flag_service import feature_flag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/features", tags=["feature-flags"])


class FeatureFlagUpdate(BaseModel):
    """更新功能开关的请求体"""
    enabled: bool = Field(..., description="是否启用")
    description: Optional[str] = Field(default="", description="功能描述")


class FeatureFlagCreate(BaseModel):
    """创建功能开关的请求体"""
    name: str = Field(..., min_length=1, max_length=100, description="开关名称")
    enabled: bool = Field(default=False, description="是否启用")
    description: str = Field(default="", description="功能描述")


@router.get("")
async def list_feature_flags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """列出所有功能开关"""
    flags = await feature_flag_service.list_flags(db)
    return [flag.to_dict() for flag in flags]


@router.get("/{name}")
async def get_feature_flag(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """查询单个功能开关状态"""
    enabled = await feature_flag_service.get_flag(db, name)
    return {"name": name, "enabled": enabled}


@router.put("/{name}")
async def update_feature_flag(
    name: str,
    body: FeatureFlagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新功能开关状态

    如果开关不存在则自动创建
    """
    flag = await feature_flag_service.set_flag(
        db,
        name=name,
        enabled=body.enabled,
        description=body.description,
    )
    return flag.to_dict()


@router.post("")
async def create_feature_flag(
    body: FeatureFlagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建功能开关"""
    flag = await feature_flag_service.set_flag(
        db,
        name=body.name,
        enabled=body.enabled,
        description=body.description,
    )
    return flag.to_dict()


@router.delete("/{name}")
async def delete_feature_flag(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除功能开关"""
    deleted = await feature_flag_service.delete_flag(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Feature flag '{name}' not found")
    return {"detail": f"Feature flag '{name}' deleted"}
