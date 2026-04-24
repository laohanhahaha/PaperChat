"""消息管理服务

封装消息相关的数据库操作，供 WebSocket handler 调用
"""
import time
from collections import OrderedDict
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_community.chat_message_histories import ChatMessageHistory

from app.models.paper import PaperTextBlock
from app.repositories import message_repository, paper_repository


# ---------------------------------------------------------------------------
# 全文 LRU 缓存（max_size=200, TTL=30 分钟）
# 缓存结构: {paper_id: (text, timestamp)}
# ---------------------------------------------------------------------------
_CACHE_MAX_SIZE: int = 200
_CACHE_TTL: float = 30 * 60  # 30 分钟（秒）
_full_text_cache: OrderedDict[int, Tuple[str, float]] = OrderedDict()


def _cache_get(paper_id: int) -> Optional[str]:
    """查询缓存，请求时检查 TTL，命中则将条目移至队尾（LRU）"""
    entry = _full_text_cache.get(paper_id)
    if entry is None:
        return None
    text, ts = entry
    if time.monotonic() - ts > _CACHE_TTL:
        # TTL 过期移除
        _full_text_cache.pop(paper_id, None)
        return None
    # 移到队尾表示最近使用
    _full_text_cache.move_to_end(paper_id)
    return text


def _cache_set(paper_id: int, text: str) -> None:
    """写入缓存，超容量时递出最久未使用条目（LRU 递出）"""
    if paper_id in _full_text_cache:
        _full_text_cache.move_to_end(paper_id)
    _full_text_cache[paper_id] = (text, time.monotonic())
    while len(_full_text_cache) > _CACHE_MAX_SIZE:
        _full_text_cache.popitem(last=False)


async def get_paper_full_text(db: AsyncSession, paper_id: int) -> str:
    """从 PaperTextBlock 表获取论文完整文本"""
    # 先查 LRU 缓存（含 TTL 检查）
    cached = _cache_get(paper_id)
    if cached is not None:
        return cached

    result = await db.execute(
        select(PaperTextBlock.text).where(PaperTextBlock.paper_id == paper_id)
        .order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    )
    texts = result.scalars().all()
    full_text = "\n".join(texts) if texts else ""

    # 写入缓存
    if full_text:
        _cache_set(paper_id, full_text)

    return full_text


def invalidate_full_text_cache(paper_id: int = None):
    """清除全文缓存（保持原有接口）"""
    if paper_id is None:
        _full_text_cache.clear()
    else:
        _full_text_cache.pop(paper_id, None)


async def get_paper_text_preview(db: AsyncSession, paper_id: int, max_chars: int = 15000) -> str:
    """获取论文文本预览（截取前 max_chars 字符），用于分析场景"""
    full_text = await get_paper_full_text(db, paper_id)
    if len(full_text) <= max_chars:
        return full_text
    return full_text[:max_chars]


async def load_chat_history(db: AsyncSession, session_id: int, limit: int = 10) -> ChatMessageHistory:
    """从数据库加载会话历史"""
    history = ChatMessageHistory()

    messages = await message_repository.get_recent_messages(db, session_id, limit=limit)

    for msg in reversed(messages):
        if msg.role == "user":
            history.add_user_message(msg.content)
        else:
            history.add_ai_message(msg.content)

    return history


async def save_message(db: AsyncSession, session_id: int, role: str, content: str, sources: list = None):
    """保存消息到数据库"""
    return await message_repository.save_message(db, session_id, role, content, sources=sources)


async def has_paper_text_blocks(db: AsyncSession, paper_id: int) -> bool:
    """检查论文是否有文本块"""
    return await paper_repository.has_paper_text_blocks(db, paper_id)


async def get_paper_text_blocks(db: AsyncSession, paper_id: int) -> list:
    """获取论文所有文本块（按页码和位置排序）"""
    return await paper_repository.get_paper_text_blocks(db, paper_id)
