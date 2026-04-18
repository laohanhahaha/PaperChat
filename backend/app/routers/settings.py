"""设置管理路由

提供用户个性化配置的 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.services.settings_service import settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有配置（含元数据，供前端渲染表单）
    
    返回:
        - 完整配置字典，包含每个配置项的 value, type, label, description 等
        - API Key 已脱敏，只显示最后4位
    """
    return await settings_service.get_settings(current_user.id, db)


@router.put("")
async def update_settings(
    settings: Dict[str, Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新配置
    
    请求体示例（只传需要更新的值）:
    {
        "llm": {
            "temperature": 0.7,
            "max_tokens": 8192
        },
        "search": {
            "max_results": 10
        }
    }
    
    返回:
        - 更新后的完整配置
    """
    try:
        result = await settings_service.update_settings(current_user.id, settings, db)
        
        # 应用配置到运行时
        values = await settings_service.get_setting_values(current_user.id, db)
        await settings_service.apply_settings(values)
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset")
async def reset_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重置为默认值
    
    返回:
        - 默认配置
    """
    result = await settings_service.reset_settings(current_user.id, db)
    
    # 应用默认配置到运行时
    await settings_service.apply_settings(settings_service.get_default_values())
    
    return result


@router.get("/values")
async def get_setting_values(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取纯值配置（不含元数据，供前端快速读取）
    
    返回:
        - 纯值配置字典，只包含 value
    """
    return await settings_service.get_setting_values(current_user.id, db)
