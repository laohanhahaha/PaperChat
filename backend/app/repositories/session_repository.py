"""会话数据仓库

封装 ChatSession 的纯 CRUD 数据库操作
"""
from datetime import datetime

from sqlalchemy import select, desc, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatSession, ChatMessage
from app.repositories.message_repository import get_messages_by_session


async def get_sessions_by_user(db: AsyncSession, user_id: int, paper_id: int = None):
    """获取用户的会话列表（含消息预加载）"""
    query = select(ChatSession).where(ChatSession.user_id == user_id).options(
        selectinload(ChatSession.messages)
    )

    if paper_id is not None:
        # 筛选包含该论文的会话（单论文或多论文）
        query = query.where(
            or_(
                ChatSession.paper_id == paper_id,
                ChatSession.paper_ids.contains([paper_id])
            )
        )

    query = query.order_by(desc(ChatSession.updated_at))
    result = await db.execute(query)
    return result.scalars().all()


async def get_session_by_id(db: AsyncSession, session_id: int, user_id: int = None):
    """获取单个会话（可选验证用户归属）"""
    query = select(ChatSession).where(ChatSession.id == session_id)
    if user_id is not None:
        query = query.where(ChatSession.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_session_with_messages(db: AsyncSession, session_id: int, user_id: int = None):
    """获取会话及其消息"""
    session = await get_session_by_id(db, session_id, user_id)
    if not session:
        return None, []
    messages = await get_messages_by_session(db, session_id)
    return session, messages


async def get_session_by_paper(db: AsyncSession, user_id: int, paper_id: int):
    """获取指定论文的最新会话（按更新时间倒序取第一条）"""
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.user_id == user_id,
            ChatSession.paper_id == paper_id
        )
        .order_by(desc(ChatSession.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_session(db: AsyncSession, user_id: int, paper_id: int = None, title: str = "新对话", paper_ids: list = None):
    """创建新会话"""
    session = ChatSession(
        user_id=user_id,
        paper_id=paper_id,
        paper_ids=paper_ids,
        title=title
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: int, user_id: int):
    """删除会话及其消息"""
    session = await get_session_by_id(db, session_id, user_id)
    if not session:
        return False
    # 显式删除消息，确保数据一致性
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    await db.delete(session)
    await db.commit()
    return True


async def update_title(db: AsyncSession, session: ChatSession, title: str):
    """更新会话标题"""
    session.title = title
    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)
