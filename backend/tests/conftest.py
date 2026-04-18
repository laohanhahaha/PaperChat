"""全局测试 fixtures

提供内存 SQLite 测试数据库和异步会话等基础 fixture，
确保每个测试用例之间完全隔离。
"""
import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models import *  # noqa: F401,F403 — 确保所有模型注册到 Base.metadata


def _deduplicate_indexes(metadata):
    """移除与列自动生成索引同名的显式 Index，避免 create_all 冲突。

    部分模型（如 PaperAnalysisCache）的 paper_id 列同时设置了
    unique=True/index=True 并在 __table_args__ 里声明了同名 Index，
    导致 create_all 时报 "index already exists"。
    """
    for table in metadata.sorted_tables:
        # 收集列级自动生成的索引名
        auto_index_names = set()
        for col in table.columns:
            if col.index:
                auto_index_names.add(f"ix_{table.name}_{col.name}")
            if col.unique:
                auto_index_names.add(f"ix_{table.name}_{col.name}")

        # 移除同名的显式 Index
        to_remove = [
            idx for idx in table.indexes
            if idx.name in auto_index_names
        ]
        for idx in to_remove:
            table.indexes.discard(idx)


# 清理重复索引（在模块加载时执行一次）
_deduplicate_indexes(Base.metadata)


# ── 内存 SQLite 引擎 ──────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── 数据库 fixtures ───────────────────────────────────────────
@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """每个测试函数独立的内存数据库会话"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    # 测试结束后删除所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── 事件循环 ──────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """为整个测试会话提供统一事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
