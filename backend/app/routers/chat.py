"""聊天会话管理路由

提供会话的创建、查询、更新、删除等接口
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.chat import ChatSession, ChatMessage
from app.models.user import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/sessions")
async def get_sessions(
    paper_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有会话列表
    
    Args:
        paper_id: 可选，筛选特定论文的会话
    """
    query = select(ChatSession).where(ChatSession.user_id == current_user.id).options(
        selectinload(ChatSession.messages)
    )
    
    if paper_id is not None:
        # 筛选包含该论文的会话（单论文或多论文）
        from sqlalchemy import or_
        query = query.where(
            or_(
                ChatSession.paper_id == paper_id,
                ChatSession.paper_ids.contains([paper_id])
            )
        )
    
    query = query.order_by(desc(ChatSession.updated_at))
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "paper_id": s.paper_id,
                "paper_ids": s.paper_ids,
                "is_cross_doc": s.is_cross_doc_session(),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": len(s.messages) if s.messages else 0
            }
            for s in sessions
        ]
    }


@router.post("/sessions")
async def create_session(
    paper_id: Optional[int] = None,
    paper_ids: Optional[list] = None,
    title: str = "新对话",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新会话
    
    Args:
        paper_id: 可选，关联的单论文ID
        paper_ids: 可选，关联的多论文ID列表（跨文档会话）
        title: 会话标题
    """
    session = ChatSession(
        user_id=current_user.id,
        paper_id=paper_id,
        paper_ids=paper_ids,
        title=title
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "title": session.title,
        "paper_id": session.paper_id,
        "paper_ids": session.paper_ids,
        "is_cross_doc": session.is_cross_doc_session(),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取会话详情（含消息历史）"""
    result = await db.execute(
        select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 加载消息
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()
    
    return {
        "id": session.id,
        "title": session.title,
        "paper_id": session.paper_id,
        "paper_ids": session.paper_ids,
        "is_cross_doc": session.is_cross_doc_session(),
        "related_paper_ids": session.get_related_paper_ids(),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取会话消息列表（分页）"""
    # 验证会话归属
    result = await db.execute(
        select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 查询消息
    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    messages = messages_result.scalars().all()
    
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ],
        "total": len(messages),
        "limit": limit,
        "offset": offset
    }


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: int,
    title: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新会话标题"""
    result = await db.execute(
        select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    session.title = title
    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "title": session.title,
        "paper_id": session.paper_id,
        "paper_ids": session.paper_ids,
        "is_cross_doc": session.is_cross_doc_session(),
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除会话（级联删除所有消息）"""
    result = await db.execute(
        select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    await db.delete(session)
    await db.commit()
    
    return {"message": "会话已删除"}


@router.get("/sessions/by-paper/{paper_id}")
async def get_or_create_session_by_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取或创建指定论文的默认会话
    
    用于切换论文时自动查找或创建会话
    """
    # 查找该论文的现有会话
    result = await db.execute(
        select(ChatSession)
        .where(
            and_(
                ChatSession.user_id == current_user.id,
                ChatSession.paper_id == paper_id
            )
        )
        .order_by(desc(ChatSession.updated_at))
        .limit(1)
    )
    session = result.scalar_one_or_none()
    
    if session:
        return {
            "id": session.id,
            "title": session.title,
            "paper_id": session.paper_id,
            "paper_ids": session.paper_ids,
            "is_cross_doc": session.is_cross_doc_session(),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "is_new": False
        }
    
    # 创建新会话
    new_session = ChatSession(
        user_id=current_user.id,
        paper_id=paper_id,
        title="新对话"
    )
    
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    
    return {
        "id": new_session.id,
        "title": new_session.title,
        "paper_id": new_session.paper_id,
        "paper_ids": new_session.paper_ids,
        "is_cross_doc": new_session.is_cross_doc_session(),
        "created_at": new_session.created_at.isoformat() if new_session.created_at else None,
        "updated_at": new_session.updated_at.isoformat() if new_session.updated_at else None,
        "is_new": True
    }


@router.post("/sessions/cross-doc")
async def create_cross_doc_session(
    paper_ids: list,
    title: str = "跨文档对话",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建跨文档会话
    
    Args:
        paper_ids: 关联的论文ID列表
        title: 会话标题
    """
    if not paper_ids or len(paper_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="跨文档会话需要提供至少一个论文ID"
        )
    
    session = ChatSession(
        user_id=current_user.id,
        paper_id=None,  # 跨文档会话不设置单论文ID
        paper_ids=paper_ids,
        title=title
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "title": session.title,
        "paper_id": session.paper_id,
        "paper_ids": session.paper_ids,
        "is_cross_doc": session.is_cross_doc_session(),
        "related_paper_ids": session.get_related_paper_ids(),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }
