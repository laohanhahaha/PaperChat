"""预缓存管理路由

提供预缓存主题订阅的 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from app.services.auth_service import get_current_user
from app.models.user import User
from app.services.precache_service import precache_service


class TopicsRequest(BaseModel):
    """更新主题请求体"""
    topics: List[str]


router = APIRouter(prefix="/api/v1/precache", tags=["precache"])


@router.get("/topics")
async def get_precache_topics(
    current_user: User = Depends(get_current_user)
):
    """获取当前预缓存订阅主题

    返回:
        - topics: 当前订阅的 arXiv 分类列表
    """
    return {"topics": precache_service.get_topics()}


@router.put("/topics")
async def update_precache_topics(
    request: TopicsRequest,
    current_user: User = Depends(get_current_user)
):
    """更新预缓存订阅主题

    请求体:
        - topics: arXiv 分类代码列表，如 ["cs.AI", "cs.CV"]

    返回:
        - topics: 更新后的主题列表
        - message: 结果消息
    """
    if not request.topics:
        raise HTTPException(status_code=400, detail="主题列表不能为空")

    # 基础校验：确保主题非空字符串
    cleaned = [t.strip() for t in request.topics if t and t.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="主题列表不能为空")

    precache_service.update_topics(cleaned)
    return {
        "topics": precache_service.get_topics(),
        "message": "预缓存主题已更新"
    }
