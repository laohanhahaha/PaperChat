"""模型配置管理路由

提供模型配置的 CRUD API，支持用户添加/删除/切换多个自定义 LLM 模型
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models.model_config import ModelConfig
from app.models.user import User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/models", tags=["models"])


# ---------------------------------------------------------------------------
# Pydantic 请求/响应模型
# ---------------------------------------------------------------------------

class ModelConfigCreate(BaseModel):
    """创建模型配置请求体"""
    display_name: str = ""
    model_name: str
    api_key: str
    api_base_url: str


class ModelConfigUpdate(BaseModel):
    """更新模型配置请求体"""
    display_name: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _mask_api_key(api_key: str) -> str:
    """脱敏 API Key，只显示最后4位

    Args:
        api_key: 原始 API Key

    Returns:
        脱敏后的 API Key
    """
    if not api_key or len(api_key) <= 4:
        return "****" if api_key else ""
    return "****" + api_key[-4:]


def _is_masked_api_key(api_key: str) -> bool:
    """检查是否为脱敏后的 API Key

    Args:
        api_key: 待检查的 API Key

    Returns:
        是否为脱敏值
    """
    if not api_key or not isinstance(api_key, str):
        return False
    if not api_key.startswith("****"):
        return False
    suffix = api_key[4:]
    return len(suffix) <= 4


def _model_to_dict(m: ModelConfig) -> dict:
    """将 ModelConfig ORM 对象转换为 API 返回格式（API Key 脱敏）

    Args:
        m: ModelConfig 实例

    Returns:
        API 响应字典
    """
    return {
        "id": m.id,
        "display_name": m.display_name,
        "model_name": m.model_name,
        "api_key_masked": _mask_api_key(m.api_key),
        "api_base_url": m.api_base_url,
        "is_active": m.is_active,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("")
async def list_model_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有模型配置

    Returns:
        {"models": [ModelConfig...]}
    """
    result = await db.execute(
        select(ModelConfig)
        .where(ModelConfig.user_id == current_user.id)
        .order_by(ModelConfig.created_at.desc())
    )
    configs = result.scalars().all()
    return {"models": [_model_to_dict(m) for m in configs]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_model_config(
    body: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的模型配置

    如果用户没有激活模型，新建的第一个自动激活。
    """
    config = ModelConfig(
        user_id=current_user.id,
        display_name=body.display_name or body.model_name,
        model_name=body.model_name,
        api_key=body.api_key,
        api_base_url=body.api_base_url,
        is_active=False,
    )

    # 检查是否已有激活模型，如果没有则自动激活
    active_result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.user_id == current_user.id,
            ModelConfig.is_active == True,
        )
    )
    has_active = active_result.scalar_one_or_none()
    if not has_active:
        config.is_active = True

    db.add(config)
    await db.commit()
    await db.refresh(config)

    logger.info(
        f"用户 {current_user.id} 创建模型配置: id={config.id}, "
        f"model_name={config.model_name}, is_active={config.is_active}"
    )

    return _model_to_dict(config)


@router.put("/{model_id}")
async def update_model_config(
    model_id: int,
    body: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模型配置

    如果 api_key 是脱敏值则不更新 key，保留原值。
    """
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == model_id,
            ModelConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    # 更新字段
    if body.display_name is not None:
        config.display_name = body.display_name
    if body.model_name is not None:
        config.model_name = body.model_name
    if body.api_key is not None:
        # 脱敏值不更新 key
        if not _is_masked_api_key(body.api_key):
            config.api_key = body.api_key
    if body.api_base_url is not None:
        config.api_base_url = body.api_base_url

    await db.commit()
    await db.refresh(config)

    # 如果更新的是当前激活模型，同步更新运行时
    if config.is_active:
        try:
            from app.services.llm_service import llm_service
            await llm_service.update_config(
                model=config.model_name,
                api_key=config.api_key,
                api_base_url=config.api_base_url,
            )
            logger.info(f"激活模型配置已更新，同步到运行时: model={config.model_name}")
        except Exception as e:
            logger.warning(f"同步运行时模型配置失败: {e}")

    logger.info(f"用户 {current_user.id} 更新模型配置: id={config.id}")
    return _model_to_dict(config)


@router.delete("/{model_id}")
async def delete_model_config(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模型配置

    如果删除的是激活模型，则取消激活（不自动切换到其他模型）。
    """
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == model_id,
            ModelConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    was_active = config.is_active
    await db.delete(config)
    await db.commit()

    logger.info(
        f"用户 {current_user.id} 删除模型配置: id={model_id}, was_active={was_active}"
    )

    return {"success": True}


@router.put("/{model_id}/activate")
async def activate_model_config(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """激活指定模型配置

    将该模型设为激活（先取消其他模型的 is_active），
    然后调用 llm_service.update_config 切换运行时模型。
    """
    # 查找目标模型
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.id == model_id,
            ModelConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    # 取消当前用户所有模型的激活状态
    await db.execute(
        update(ModelConfig)
        .where(ModelConfig.user_id == current_user.id)
        .values(is_active=False)
    )

    # 激活目标模型
    config.is_active = True
    await db.commit()
    await db.refresh(config)

    # 切换运行时 LLM 模型
    try:
        from app.services.llm_service import llm_service
        await llm_service.update_config(
            model=config.model_name,
            api_key=config.api_key,
            api_base_url=config.api_base_url,
        )
        logger.info(
            f"运行时模型已切换: model={config.model_name}, "
            f"api_base_url={config.api_base_url}"
        )
    except Exception as e:
        logger.error(f"切换运行时模型失败: {e}")
        # 仍然返回配置，但记录错误

    logger.info(
        f"用户 {current_user.id} 激活模型配置: id={config.id}, "
        f"model_name={config.model_name}"
    )

    return _model_to_dict(config)
