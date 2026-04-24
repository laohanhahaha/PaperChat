"""论文推荐路由

提供相似论文推荐和个性化推荐接口
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.recommendation_service import recommendation_service

router = APIRouter(prefix="/api/v1", tags=["推荐"])


# ========== Pydantic 模型 ==========

class FeedbackRequest(BaseModel):
    """推荐反馈请求体"""
    paper_id: int = Field(..., description="被推荐的论文 ID")
    feedback_type: str = Field(..., pattern="^(useful|not_useful)$", description="反馈类型: useful | not_useful")
    source: Optional[str] = Field(None, description="推荐来源: similar | personal | graph | comprehensive")
    comment: Optional[str] = Field(None, max_length=500, description="可选备注")


@router.get("/papers/{paper_id}/recommendations")
async def get_similar_papers(
    paper_id: int,
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取相似论文推荐
    
    基于内容相似性，推荐与用户当前阅读论文相似的其他论文。
    使用余弦相似度计算论文嵌入向量之间的相似性。
    
    路径参数:
        - paper_id: 当前论文 ID
        
    查询参数:
        - top_k: 返回结果数量（默认 5，最大 20）
    
    返回:
        - recommendations: 推荐论文列表
        - total: 推荐数量
        - source_paper_id: 源论文 ID
    
    性能说明:
        - 首次计算嵌入约 100-200ms/篇
        - 结果会被缓存，后续查询更快
        - 100篇论文的相似度计算约 200ms
    """
    # 验证论文存在且属于当前用户
    from sqlalchemy import select, and_
    from app.models.paper import Paper
    
    result = await db.execute(
        select(Paper).where(
            and_(Paper.id == paper_id, Paper.user_id == current_user.id)
        )
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 获取相似论文推荐
    recommendations = await recommendation_service.get_similar_papers(
        paper_id=paper_id,
        user_id=current_user.id,
        db=db,
        top_k=top_k
    )
    
    return {
        "source_paper_id": paper_id,
        "total": len(recommendations),
        "recommendations": recommendations
    }


@router.get("/recommendations")
async def get_personalized_recommendations(
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取个性化论文推荐
    
    基于用户画像（研究兴趣、阅读历史等）推荐最匹配的论文。
    优先推荐未读或阅读中的论文。
    
    查询参数:
        - top_k: 返回结果数量（默认 5，最大 20）
    
    返回:
        - recommendations: 推荐论文列表
        - total: 推荐数量
        - has_profile: 是否有用户画像数据
    
    性能说明:
        - 依赖用户画像构建（约 300ms）
        - 嵌入计算约 100-200ms/篇
        - 无画像时返回最近上传的论文
    """
    # 获取个性化推荐
    recommendations = await recommendation_service.get_personalized_recommendations(
        user_id=current_user.id,
        db=db,
        top_k=top_k
    )
    
    # 检查是否有用户画像
    from app.services.memory_service import memory_service
    profile = await memory_service.build_user_profile(current_user.id, db)
    has_profile = profile.get("total_memories", 0) > 0
    
    return {
        "total": len(recommendations),
        "has_profile": has_profile,
        "recommendations": recommendations
    }


@router.post("/papers/{paper_id}/recommendations/refresh")
async def refresh_paper_recommendations(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """刷新论文推荐缓存
    
    清除指定论文的嵌入缓存并重新计算。
    适用于论文内容更新后需要重新生成推荐的情况。
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - success: 是否成功
        - message: 状态信息
    """
    # 验证论文存在且属于当前用户
    from sqlalchemy import select, and_
    from app.models.paper import Paper
    
    result = await db.execute(
        select(Paper).where(
            and_(Paper.id == paper_id, Paper.user_id == current_user.id)
        )
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 清除缓存
    recommendation_service.clear_cache(paper_id)
    
    # 重新计算嵌入
    embedding = await recommendation_service.compute_paper_embedding(
        paper_id=paper_id,
        db=db,
        use_cache=False
    )
    
    if embedding:
        return {
            "success": True,
            "message": "推荐缓存已刷新",
            "paper_id": paper_id
        }
    else:
        return {
            "success": False,
            "message": "嵌入计算失败，论文内容可能不足",
            "paper_id": paper_id
        }


@router.get("/papers/{paper_id}/web-recommendations")
async def get_web_recommendations(
    paper_id: int,
    max_results: int = Query(8, ge=1, le=20, description="返回结果数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从网络搜索相关学术文献
    
    基于当前论文标题，从互联网学术资源（arXiv、Google Scholar等）
    搜索相关学术文献，提供可点击的外部链接。
    
    路径参数:
        - paper_id: 当前论文 ID
        
    查询参数:
        - max_results: 返回结果数量（默认 8，最大 20）
    
    返回:
        - results: 网络学术文献列表
        - total: 结果数量
    
    性能说明:
        - 网络搜索约 3-5 秒延迟
        - 结果被缓存以优化重复查询
    """
    # 验证论文存在且属于当前用户
    from sqlalchemy import select, and_
    from app.models.paper import Paper
    
    result = await db.execute(
        select(Paper).where(
            and_(Paper.id == paper_id, Paper.user_id == current_user.id)
        )
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 执行网络学术搜索
    results = await recommendation_service.search_web_recommendations(
        paper_id=paper_id,
        db=db,
        max_results=max_results
    )
    
    return {
        "results": results,
        "total": len(results)
    }


@router.get("/recommendations/comprehensive")
async def get_comprehensive_recommendations(
    paper_id: Optional[int] = Query(None, description="当前论文 ID，用于内容相似推荐"),
    top_k: int = Query(8, ge=1, le=20, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """综合推荐

    融合内容相似推荐、个性化推荐和知识图谱推荐，按权重混合排序。
    每篇推荐附带 reason 字段说明推荐理由。

    查询参数:
        - paper_id: 当前正在查看的论文 ID（可选）
        - top_k: 返回数量（默认 8，最大 20）

    返回:
        - recommendations: 综合推荐论文列表（含 reason 字段）
        - total: 推荐数量

    性能说明:
        - 并行计算三路推荐，总耗时约 200-500ms
        - 首次计算嵌入向量可能耗时 1-2s
    """
    recommendations = await recommendation_service.get_comprehensive_recommendations(
        user_id=current_user.id,
        db=db,
        paper_id=paper_id,
        top_k=top_k
    )

    return {
        "total": len(recommendations),
        "source_paper_id": paper_id,
        "recommendations": recommendations
    }


@router.post("/recommendations/feedback")
async def submit_recommendation_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交推荐反馈

    记录用户对推荐结果的使用反馈，用于后续推荐优化。
    目前将反馈记录到日志，后续可按需入库。

    请求体:
        - paper_id: 被推荐的论文 ID
        - feedback_type: useful | not_useful
        - source: 推荐来源（similar / personal / graph / comprehensive）
        - comment: 可选备注

    返回:
        - success: 是否成功
        - message: 状态信息
    """
    from sqlalchemy import select, and_
    from app.models.paper import Paper
    import logging

    logger = logging.getLogger(__name__)

    # 验证被推荐论文属于当前用户
    result = await db.execute(
        select(Paper).where(
            and_(Paper.id == body.paper_id, Paper.user_id == current_user.id)
        )
    )
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )

    # 记录反馈（当前记录到日志，可后续扩展入库）
    logger.info(
        f"[recommendation_feedback] user={current_user.id} paper={body.paper_id} "
        f"type={body.feedback_type} source={body.source} comment={body.comment!r}"
    )

    return {
        "success": True,
        "message": "反馈已记录，感谢您的建议",
        "paper_id": body.paper_id,
        "feedback_type": body.feedback_type
    }
