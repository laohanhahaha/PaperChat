"""数据库连接管理"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 调试模式下输出 SQL 语句
    future=True
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncSession:
    """
    获取数据库会话的依赖注入函数
    
    用法:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库，创建所有表
    应在应用启动时调用
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 确保默认用户存在
    async with AsyncSessionLocal() as db:
        from app.models.user import User
        from sqlalchemy import select, text
        result = await db.execute(select(User).where(User.id == 1))
        if not result.scalar_one_or_none():
            user = User(
                id=1,
                username="default",
                email="default@local.dev",
                hashed_password="not-used",
                is_active=True
            )
            db.add(user)
            await db.commit()
    
    # 添加分析缓存字段迁移（兼容已有数据库）
    from sqlalchemy import text
    alter_statements = [
        "ALTER TABLE papers ADD COLUMN section_analysis TEXT",
        "ALTER TABLE papers ADD COLUMN deep_analysis TEXT",
        "ALTER TABLE papers ADD COLUMN analysis_status VARCHAR(20) DEFAULT 'not_generated'",
        "ALTER TABLE papers ADD COLUMN last_analyzed_at DATETIME",
        "ALTER TABLE papers ADD COLUMN last_read_at DATETIME",
    ]
    for stmt in alter_statements:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text(stmt))
                await db.commit()
        except Exception:
            # 列已存在，忽略错误
            pass


async def close_db():
    """
    关闭数据库连接
    应在应用关闭时调用
    """
    await engine.dispose()
