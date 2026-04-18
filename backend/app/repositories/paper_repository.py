"""论文数据仓库

封装 Paper 和 PaperTextBlock 的纯 CRUD 数据库操作
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.paper import Paper, PaperTextBlock


async def get_paper_by_id(db: AsyncSession, paper_id: int):
    """获取论文（仅按 ID）"""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    return result.scalar_one_or_none()


async def get_paper_by_id_and_user(db: AsyncSession, paper_id: int, user_id: int):
    """获取论文并验证归属"""
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def validate_papers(db: AsyncSession, paper_ids: list, user_id: int) -> list:
    """批量验证论文是否存在且属于该用户，返回有效的 paper_id 列表"""
    result = await db.execute(
        select(Paper.id).where(Paper.id.in_(paper_ids), Paper.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def has_paper_text_blocks(db: AsyncSession, paper_id: int) -> bool:
    """检查论文是否有文本块"""
    result = await db.execute(
        select(PaperTextBlock).where(PaperTextBlock.paper_id == paper_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_paper_text_blocks(db: AsyncSession, paper_id: int):
    """获取论文文本块（按页码和位置排序）"""
    result = await db.execute(
        select(PaperTextBlock)
        .where(PaperTextBlock.paper_id == paper_id)
        .order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    )
    return result.scalars().all()
