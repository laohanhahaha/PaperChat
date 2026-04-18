"""消息服务测试

验证 message_repository 的保存与分页查询
"""
import pytest

from app.models.user import User
from app.repositories import session_repository, message_repository


@pytest.fixture(autouse=True)
async def seed_data(test_db):
    """插入用户和会话，供消息测试使用"""
    user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        hashed_password="fake",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()

    session = await session_repository.create_session(
        test_db, user_id=1, title="消息测试会话"
    )
    return session


@pytest.mark.asyncio
async def test_save_and_get_messages(test_db, seed_data):
    """保存消息后应能通过 get_messages_by_session 查到"""
    session = seed_data

    msg = await message_repository.save_message(
        test_db, session_id=session.id, role="user", content="你好"
    )
    assert msg is not None
    assert msg.id is not None
    assert msg.role == "user"
    assert msg.content == "你好"

    messages = await message_repository.get_messages_by_session(test_db, session.id)
    assert len(messages) == 1
    assert messages[0].content == "你好"


@pytest.mark.asyncio
async def test_message_pagination(test_db, seed_data):
    """分页查询应正确返回对应偏移量的消息"""
    session = seed_data

    # 插入 5 条消息
    for i in range(5):
        await message_repository.save_message(
            test_db,
            session_id=session.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息{i}",
        )

    # 第一页 limit=2 offset=0
    page1 = await message_repository.get_messages_by_session(
        test_db, session.id, limit=2, offset=0
    )
    assert len(page1) == 2

    # 第二页 limit=2 offset=2
    page2 = await message_repository.get_messages_by_session(
        test_db, session.id, limit=2, offset=2
    )
    assert len(page2) == 2

    # 最后一页 offset=4
    page3 = await message_repository.get_messages_by_session(
        test_db, session.id, limit=2, offset=4
    )
    assert len(page3) == 1
