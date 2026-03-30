"""高亮标注路由

提供高亮标注的创建、查询、更新、删除等接口
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models.highlight import Highlight
from app.models.paper import Paper
from app.models.user import User
from app.schemas.highlight import HighlightCreate, HighlightUpdate, HighlightResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/highlights", tags=["高亮标注"])


@router.get("/paper/{paper_id}", response_model=List[HighlightResponse])
async def get_paper_highlights(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文的所有高亮标注
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 高亮标注列表
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在或无权限访问"
        )
    
    # 查询该论文的所有高亮
    result = await db.execute(
        select(Highlight).where(
            and_(Highlight.paper_id == paper_id, Highlight.user_id == current_user.id)
        ).order_by(Highlight.page, Highlight.created_at)
    )
    highlights = result.scalars().all()
    
    return highlights


@router.post("", response_model=HighlightResponse, status_code=status.HTTP_201_CREATED)
async def create_highlight(
    data: HighlightCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建高亮标注
    
    请求体:
        - paper_id: 论文 ID
        - page: 页码
        - rects: 标注区域数组（JSON 格式）
        - color: 颜色（可选，默认 #FFEB3B）
        - highlight_type: 标注类型（可选，默认 highlight）
        - selected_text: 选中的文本内容
    
    返回:
        - 创建的高亮标注信息
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == data.paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在或无权限访问"
        )
    
    # 创建高亮
    highlight = Highlight(
        paper_id=data.paper_id,
        user_id=current_user.id,
        page=data.page,
        rects=data.rects,
        color=data.color,
        highlight_type=data.highlight_type,
        selected_text=data.selected_text
    )
    
    db.add(highlight)
    await db.commit()
    await db.refresh(highlight)
    
    return highlight


@router.put("/{highlight_id}", response_model=HighlightResponse)
async def update_highlight(
    highlight_id: int,
    data: HighlightUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新高亮标注
    
    路径参数:
        - highlight_id: 高亮标注 ID
    
    请求体:
        - color: 颜色（可选）
        - highlight_type: 标注类型（可选）
    
    返回:
        - 更新后的高亮标注信息
    """
    # 查询高亮
    result = await db.execute(
        select(Highlight).where(
            and_(Highlight.id == highlight_id, Highlight.user_id == current_user.id)
        )
    )
    highlight = result.scalar_one_or_none()
    
    if not highlight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="高亮标注不存在或无权限"
        )
    
    # 更新字段
    if data.color is not None:
        highlight.color = data.color
    if data.highlight_type is not None:
        highlight.highlight_type = data.highlight_type
    
    await db.commit()
    await db.refresh(highlight)
    
    return highlight


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除高亮标注
    
    路径参数:
        - highlight_id: 高亮标注 ID
    
    返回:
        - 无内容（204）
    """
    # 查询高亮
    result = await db.execute(
        select(Highlight).where(
            and_(Highlight.id == highlight_id, Highlight.user_id == current_user.id)
        )
    )
    highlight = result.scalar_one_or_none()
    
    if not highlight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="高亮标注不存在或无权限"
        )
    
    await db.delete(highlight)
    await db.commit()
    
    return None


