"""研究画像路由

用户研究画像 API 端点，包括画像摘要、推荐论文、盲区状态管理
"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.services.user.auth_service import get_current_user
from app.services.user.profile_service import profile_service
from app.models.user import User

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


class BlindspotUpdateRequest(BaseModel):
    """盲区状态更新请求"""
    status: str  # blind/improving/mastered


@router.get("/{user_id}")
async def get_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户画像摘要
    
    路径参数:
        - user_id: 用户 ID
    
    返回:
        - domains: 研究领域列表（含类型和频次）
        - preferences: 阅读偏好统计
        - blindspots: 知识盲区列表
        - stage: 当前研究阶段及置信度
    """
    # 校验用户权限
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他用户的画像"
        )
    
    try:
        profile_data = await profile_service.get_profile_summary(user_id, db)
        return profile_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取画像失败: {str(e)}"
        )


@router.get("/{user_id}/recommendations")
async def get_recommendations(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取基于画像的推荐论文
    
    路径参数:
        - user_id: 用户 ID
    
    返回:
        - 推荐论文列表，包含推荐理由和来源标签
    """
    # 校验用户权限
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他用户的推荐"
        )
    
    try:
        recommendations = await profile_service.get_recommendations(user_id, db)
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取推荐失败: {str(e)}"
        )


@router.put("/{user_id}/blindspots/{blindspot_id}")
async def update_blindspot(
    user_id: int,
    blindspot_id: int,
    request: BlindspotUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新知识盲区状态（用户标记为已掌握等）
    
    路径参数:
        - user_id: 用户 ID
        - blindspot_id: 盲区记录 ID
    
    请求体:
        - status: 新状态 (blind/improving/mastered)
    
    返回:
        - 更新后的盲区信息
    """
    # 校验用户权限
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改其他用户的盲区状态"
        )
    
    # 校验状态值
    valid_statuses = ["blind", "improving", "mastered"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态值，必须是: {', '.join(valid_statuses)}"
        )
    
    try:
        from sqlalchemy import select
        from app.models.research_profile import KnowledgeBlindspot
        
        # 查询盲区记录
        result = await db.execute(
            select(KnowledgeBlindspot).where(
                KnowledgeBlindspot.id == blindspot_id,
                KnowledgeBlindspot.user_id == user_id
            )
        )
        blindspot = result.scalar_one_or_none()
        
        if not blindspot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="盲区记录不存在"
            )
        
        # 更新状态
        blindspot.status = request.status
        await db.commit()
        await db.refresh(blindspot)
        
        return {
            "id": blindspot.id,
            "concept": blindspot.concept,
            "status": blindspot.status,
            "query_count": blindspot.query_count,
            "message": "状态更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新盲区状态失败: {str(e)}"
        )
