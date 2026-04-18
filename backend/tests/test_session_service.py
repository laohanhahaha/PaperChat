"""会话服务测试

验证 session_repository 的核心 CRUD 操作
"""
import pytest

from app.models.user import User
from app.repositories import session_repository


@pytest.fixture(autouse=True)
async def seed_user(test_db):
    """在每个测试前插入默认用户（外键约束需要）"""
    user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        hashed_password="fake",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()


@pytest.mark.asyncio
async def test_create_session(test_db):
    """创建会话应返回包含正确字段的 ChatSession 对象"""
    session = await session_repository.create_session(
        test_db, user_id=1, title="测试会话"
    )
    assert session is not None
    assert session.id is not None
    assert session.user_id == 1
    assert session.title == "测试会话"
    assert session.paper_id is None


@pytest.mark.asyncio
async def test_get_sessions_by_user(test_db):
    """获取用户会话列表应只返回该用户的会话"""
    # 创建两个会话
    await session_repository.create_session(test_db, user_id=1, title="会话A")
    await session_repository.create_session(test_db, user_id=1, title="会话B")

    sessions = await session_repository.get_sessions_by_user(test_db, user_id=1)
    assert len(sessions) == 2
    titles = {s.title for s in sessions}
    assert titles == {"会话A", "会话B"}


@pytest.mark.asyncio
async def test_delete_session(test_db):
    """删除会话后应无法再查到该会话"""
    session = await session_repository.create_session(
        test_db, user_id=1, title="待删除"
    )
    session_id = session.id

    deleted = await session_repository.delete_session(test_db, session_id, user_id=1)
    assert deleted is True

    # 再次查询应返回 None
    found = await session_repository.get_session_by_id(test_db, session_id)
    assert found is None
