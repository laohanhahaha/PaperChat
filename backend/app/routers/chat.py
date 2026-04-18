"""聊天会话管理路由

提供会话的创建、查询、更新、删除等接口
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.repositories import session_repository, message_repository, paper_repository
from app.rate_limiter import limiter

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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
    sessions = await session_repository.get_sessions_by_user(db, current_user.id, paper_id=paper_id)
    
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
@limiter.limit("30/minute")
async def create_session(
    request: Request,
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
    # 如果提供了 paper_id，验证论文是否存在且属于当前用户
    if paper_id is not None:
        paper = await paper_repository.get_paper_by_id_and_user(db, paper_id, current_user.id)
        if paper is None:
            # 论文不存在或不属于当前用户，创建无关联论文的会话
            paper_id = None
    
    session = await session_repository.create_session(
        db, user_id=current_user.id, paper_id=paper_id, paper_ids=paper_ids, title=title
    )
    
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
    session = await session_repository.get_session_by_id(db, session_id, user_id=current_user.id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 加载消息
    messages = await message_repository.get_messages_by_session(db, session_id)
    
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
    """获取会话消息列表（分页）
    
    消息按时间倒序返回（最新的在前），前端需要 reverse 后展示
    """
    # 验证会话归属
    session = await session_repository.get_session_by_id(db, session_id, user_id=current_user.id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 查询消息
    messages = await message_repository.get_messages_by_session(db, session_id, limit=limit, offset=offset)
    
    # 获取消息总数
    total = await message_repository.count_messages(db, session_id)
    
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
        "total": total,
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
    session = await session_repository.get_session_by_id(db, session_id, user_id=current_user.id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    await session_repository.update_title(db, session, title)
    
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
    deleted = await session_repository.delete_session(db, session_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
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
    session = await session_repository.get_session_by_paper(db, current_user.id, paper_id)
    
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
    new_session = await session_repository.create_session(
        db, user_id=current_user.id, paper_id=paper_id, title="新对话"
    )
    
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
@limiter.limit("30/minute")
async def create_cross_doc_session(
    request: Request,
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
    
    # 验证所有论文 ID 是否有效且属于当前用户（批量验证，替代逐条查询）
    valid_paper_ids = await paper_repository.validate_papers(db, paper_ids, current_user.id)
    
    # 如果没有有效的论文 ID，返回错误
    if len(valid_paper_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有有效的论文ID，请重新选择"
        )
    
    session = await session_repository.create_session(
        db, user_id=current_user.id, paper_id=None, paper_ids=valid_paper_ids, title=title
    )
    
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
