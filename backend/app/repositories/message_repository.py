"""消息数据仓库

封装 ChatMessage 的纯 CRUD 数据库操作
"""
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatMessage


async def get_messages_by_session(db: AsyncSession, session_id: int, limit: int = 100, offset: int = 0):
    """获取会话消息（按时间倒序，分页）
    
    返回的消息按时间倒序排列（最新的在前），前端需要 reverse 后展示
    """
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_recent_messages(db: AsyncSession, session_id: int, limit: int = 10):
    """获取会话最近的消息（按时间倒序，用于加载聊天历史）"""
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def count_messages(db: AsyncSession, session_id: int) -> int:
    """获取会话消息数量"""
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    )
    return result.scalar() or 0


async def save_message(db: AsyncSession, session_id: int, role: str, content: str, sources=None):
    """保存消息"""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources=sources
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
