"""笔记路由

提供笔记的创建、查询、更新、删除等接口
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.database import get_db
from app.models.note import Note
from app.models.highlight import Highlight
from app.models.paper import Paper
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate, NoteResponse, NoteWithHighlightResponse
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/notes", tags=["笔记"])


@router.get("", response_model=List[NoteWithHighlightResponse])
async def get_notes(
    paper_id: int = Query(..., description="论文 ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文的所有笔记
    
    查询参数:
        - paper_id: 论文 ID
    
    返回:
        - 笔记列表（包含关联的高亮文本信息）
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
    
    # 查询该论文的所有笔记
    result = await db.execute(
        select(Note, Highlight).outerjoin(
            Highlight, Note.highlight_id == Highlight.id
        ).where(
            and_(Note.paper_id == paper_id, Note.user_id == current_user.id)
        ).order_by(Note.created_at.desc())
    )
    
    notes_with_highlight = result.all()
    
    # 构造响应数据
    response_data = []
    for note, highlight in notes_with_highlight:
        note_dict = {
            "id": note.id,
            "paper_id": note.paper_id,
            "user_id": note.user_id,
            "highlight_id": note.highlight_id,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "highlight_text": highlight.selected_text if highlight else None
        }
        response_data.append(note_dict)
    
    return response_data


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建笔记
    
    请求体:
        - paper_id: 论文 ID
        - highlight_id: 高亮 ID（可选）
        - content: 笔记内容
    
    返回:
        - 创建的笔记信息
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
    
    # 如果提供了 highlight_id，验证高亮存在且属于当前用户
    if data.highlight_id:
        result = await db.execute(
            select(Highlight).where(
                and_(
                    Highlight.id == data.highlight_id,
                    Highlight.user_id == current_user.id,
                    Highlight.paper_id == data.paper_id
                )
            )
        )
        highlight = result.scalar_one_or_none()
        
        if not highlight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="高亮标注不存在或无权限访问"
            )
    
    # 创建笔记
    note = Note(
        paper_id=data.paper_id,
        user_id=current_user.id,
        highlight_id=data.highlight_id,
        content=data.content
    )
    
    db.add(note)
    await db.commit()
    await db.refresh(note)
    
    return note


@router.get("/{note_id}", response_model=NoteWithHighlightResponse)
async def get_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取单个笔记详情
    
    路径参数:
        - note_id: 笔记 ID
    
    返回:
        - 笔记详情（包含关联的高亮文本信息）
    """
    result = await db.execute(
        select(Note, Highlight).outerjoin(
            Highlight, Note.highlight_id == Highlight.id
        ).where(
            and_(Note.id == note_id, Note.user_id == current_user.id)
        )
    )
    
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在或无权限"
        )
    
    note, highlight = row
    
    return {
        "id": note.id,
        "paper_id": note.paper_id,
        "user_id": note.user_id,
        "highlight_id": note.highlight_id,
        "content": note.content,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "highlight_text": highlight.selected_text if highlight else None
    }


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新笔记
    
    路径参数:
        - note_id: 笔记 ID
    
    请求体:
        - content: 笔记内容（可选）
        - highlight_id: 高亮 ID（可选）
    
    返回:
        - 更新后的笔记信息
    """
    # 查询笔记
    result = await db.execute(
        select(Note).where(
            and_(Note.id == note_id, Note.user_id == current_user.id)
        )
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在或无权限"
        )
    
    # 如果更新 highlight_id，验证新高亮存在
    if data.highlight_id is not None and data.highlight_id != note.highlight_id:
        result = await db.execute(
            select(Highlight).where(
                and_(
                    Highlight.id == data.highlight_id,
                    Highlight.user_id == current_user.id,
                    Highlight.paper_id == note.paper_id
                )
            )
        )
        highlight = result.scalar_one_or_none()
        
        if not highlight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="高亮标注不存在或无权限访问"
            )
        
        note.highlight_id = data.highlight_id
    
    # 更新内容
    if data.content is not None:
        note.content = data.content
    
    await db.commit()
    await db.refresh(note)
    
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除笔记
    
    路径参数:
        - note_id: 笔记 ID
    
    返回:
        - 无内容（204）
    """
    # 查询笔记
    result = await db.execute(
        select(Note).where(
            and_(Note.id == note_id, Note.user_id == current_user.id)
        )
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="笔记不存在或无权限"
        )
    
    await db.delete(note)
    await db.commit()
    
    return None


@router.get("/search", response_model=List[NoteWithHighlightResponse])
async def search_notes(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    paper_id: Optional[int] = Query(None, description="论文 ID（可选，不提供则搜索所有笔记）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    搜索笔记（模糊匹配内容）
    
    查询参数:
        - q: 搜索关键词
        - paper_id: 论文 ID（可选）
    
    返回:
        - 匹配的笔记列表
    """
    # 构建查询条件
    conditions = [
        Note.user_id == current_user.id,
        Note.content.ilike(f"%{q}%")
    ]
    
    if paper_id:
        # 验证论文权限
        result = await db.execute(
            select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
        )
        paper = result.scalar_one_or_none()
        
        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="论文不存在或无权限访问"
            )
        
        conditions.append(Note.paper_id == paper_id)
    
    # 执行搜索
    result = await db.execute(
        select(Note, Highlight).outerjoin(
            Highlight, Note.highlight_id == Highlight.id
        ).where(
            and_(*conditions)
        ).order_by(Note.updated_at.desc())
    )
    
    notes_with_highlight = result.all()
    
    # 构造响应数据
    response_data = []
    for note, highlight in notes_with_highlight:
        note_dict = {
            "id": note.id,
            "paper_id": note.paper_id,
            "user_id": note.user_id,
            "highlight_id": note.highlight_id,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "highlight_text": highlight.selected_text if highlight else None
        }
        response_data.append(note_dict)
    
    return response_data
