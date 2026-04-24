"""WebSocket 认证模块

提供 WebSocket 连接的 token 验证功能，支持无 token 降级到默认用户（个人使用模式）
"""
from jose import jwt, JWTError
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import get_current_user


async def verify_websocket_token(token: str = None):
    """验证 WebSocket token，无 token 时降级为默认用户"""
    if not token:
        # 向后兼容：无 token 时使用默认用户（个人使用模式）
        async with AsyncSessionLocal() as db:
            return await get_current_user(db)

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = int(payload.get("sub"))
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
        return None
    except Exception:
        return None


async def get_db_session():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
