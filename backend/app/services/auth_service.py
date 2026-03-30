"""认证服务

提供用户认证、默认用户获取功能（个人使用模式，无需登录）
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """
    获取默认用户（个人使用模式，无需认证）
    
    Args:
        db: 数据库会话
        
    Returns:
        默认用户对象（id=1）
    """
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    
    if not user:
        # 自动创建默认用户
        user = User(
            id=1,
            username="default",
            email="default@local.dev",
            hashed_password="not-used",
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user
