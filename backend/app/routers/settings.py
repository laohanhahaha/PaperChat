"""设置管理路由

提供用户个性化配置的 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.services.settings_service import settings_service
from app.services.security.key_rotation import get_key_rotation_service


class RotateKeyRequest(BaseModel):
    """密钥轮换请求体"""
    service_name: str
    new_key: str


class ValidateKeyRequest(BaseModel):
    """密钥验证请求体"""
    service_name: str
    key: str

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


@router.post("/rotate-key")
async def rotate_api_key(
    request: RotateKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """轮换 API Key
    
    请求体:
        - service_name: 服务名称（deepseek/bing/tavily/brave/zotero/semantic_scholar）
        - new_key: 新的 API Key
    
    返回:
        - success: 是否成功
        - message: 结果消息
        - service: 服务名称
    """
    result = await settings_service.rotate_api_key(
        user_id=current_user.id,
        service_name=request.service_name,
        new_key=request.new_key,
        db=db,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/validate-key")
async def validate_api_key(
    request: ValidateKeyRequest,
    current_user: User = Depends(get_current_user)
):
    """验证 API Key 有效性
    
    请求体:
        - service_name: 服务名称
        - key: 待验证的 API Key
    
    返回:
        - valid: 是否有效
        - message: 验证消息
        - latency_ms: 验证延迟（毫秒）
    """
    return await settings_service.validate_api_key(
        service_name=request.service_name,
        key=request.key,
    )


@router.get("/key-status")
async def get_key_status(
    current_user: User = Depends(get_current_user)
):
    """获取所有 API Key 的轮换状态
    
    返回:
        - keys: 所有 Key 的状态列表
            - service: 服务名称
            - status: valid / expiring_soon / expired
            - days_until_expiry: 距过期天数
            - created_at: Key 创建时间
            - expires_at: Key 过期时间
            - last_rotated_at: 上次轮换时间
    """
    rotation_svc = get_key_rotation_service()
    keys = rotation_svc.check_all_keys()
    return {"keys": keys}


@router.post("/key-rotation/check")
async def trigger_key_rotation_check(
    current_user: User = Depends(get_current_user)
):
    """触发立即检查所有 Key 的轮换状态
    
    性能影响：仅遍历内存中的 Key 元数据（通常 < 10 个），
    CPU 开销可忽略。如有到期 Key，通过 WebSocket 广播警告。
    
    返回:
        - warnings: 到期警告列表
        - checked_count: 检查的 Key 数量
    """
    rotation_svc = get_key_rotation_service()
    await rotation_svc._perform_check()
    all_status = rotation_svc.check_all_keys()
    warnings = [s for s in all_status if s["status"] != "valid"]
    return {
        "warnings": warnings,
        "checked_count": len(all_status),
    }
