"""会话管理服务

封装会话相关的数据库操作，供 WebSocket handler 调用
"""
import json
import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.models.paper import Paper
from app.models.paper_analysis import PaperAnalysisCache
from app.repositories import session_repository, message_repository, paper_repository
from app.services.core.event_bus import event_bus, Event, EventTypes
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def get_or_create_session(
    db: AsyncSession, session_id: int, user_id: int, paper_id: int = None
) -> ChatSession:
    """获取或创建会话"""
    if session_id:
        session = await session_repository.get_session_by_id(db, session_id, user_id=user_id)
        if session:
            return session

    return await session_repository.create_session(db, user_id=user_id, paper_id=paper_id, title="新对话")


async def auto_title(db: AsyncSession, session: ChatSession, message: str):
    """自动更新会话标题（如果是前几条消息且标题仍为默认值）"""
    message_count = await message_repository.count_messages(db, session.id)
    if message_count <= 2 and session.title == "新对话":
        session.title = message[:30] + "..." if len(message) > 30 else message
        await db.commit()


async def get_paper_by_id(db: AsyncSession, paper_id: int):
    """获取论文对象"""
    return await paper_repository.get_paper_by_id(db, paper_id)


async def save_paper_section_analysis(paper_id: int, section_analysis: str):
    """保存章节概述缓存（创建独立数据库会话）"""
    try:
        async with AsyncSessionLocal() as cache_db:
            result = await cache_db.execute(
                select(PaperAnalysisCache).where(PaperAnalysisCache.paper_id == paper_id)
            )
            cache = result.scalar_one_or_none()
            if cache:
                cache.section_analysis = section_analysis
                cache.last_analyzed_at = datetime.now()
                cache.analysis_status = "completed"
            else:
                cache = PaperAnalysisCache(
                    paper_id=paper_id,
                    section_analysis=section_analysis,
                    analysis_status="completed",
                    last_analyzed_at=datetime.now()
                )
                cache_db.add(cache)
            await cache_db.commit()

        # 发布分析完成事件（fire-and-forget，不阻塞主流程）
        asyncio.create_task(event_bus.publish(Event(
            type=EventTypes.ANALYSIS_COMPLETED,
            data={"paper_id": paper_id, "analysis_type": "section"}
        )))
    except Exception as e:
        logger.warning(f"保存章节概述缓存失败: {e}")


async def save_paper_deep_analysis(paper_id: int, deep_analysis: str):
    """保存深度分析缓存（创建独立数据库会话）"""
    try:
        async with AsyncSessionLocal() as cache_db:
            result = await cache_db.execute(
                select(PaperAnalysisCache).where(PaperAnalysisCache.paper_id == paper_id)
            )
            cache = result.scalar_one_or_none()
            if cache:
                cache.deep_analysis = deep_analysis
                cache.last_analyzed_at = datetime.now()
                cache.analysis_status = "completed"
            else:
                cache = PaperAnalysisCache(
                    paper_id=paper_id,
                    deep_analysis=deep_analysis,
                    analysis_status="completed",
                    last_analyzed_at=datetime.now()
                )
                cache_db.add(cache)
            await cache_db.commit()

        # 发布分析完成事件（fire-and-forget，不阻塞主流程）
        asyncio.create_task(event_bus.publish(Event(
            type=EventTypes.ANALYSIS_COMPLETED,
            data={"paper_id": paper_id, "analysis_type": "deep"}
        )))
    except Exception as e:
        logger.warning(f"保存深度分析缓存失败: {e}")


async def extract_and_save_keywords(paper_id: int, text: str, websocket=None):
    """异步提取关键词并更新论文标签（创建独立数据库会话，不阻塞主流程）"""
    from app.services.llm_service import llm_service

    try:
        async with AsyncSessionLocal() as kw_db:
            paper_obj = await paper_repository.get_paper_by_id(kw_db, paper_id)
            if paper_obj and not paper_obj.tags:
                keywords = await asyncio.wait_for(
                    llm_service.extract_keywords(
                        text=text[:3000],
                        title=paper_obj.title or "",
                        max_keywords=5
                    ),
                    timeout=15.0
                )
                if keywords:
                    paper_obj.tags = json.dumps(keywords, ensure_ascii=False)
                    await kw_db.commit()
                    if websocket:
                        try:
                            await websocket.send_text(json.dumps({
                                "type": "keywords_result",
                                "keywords": keywords,
                                "paper_id": paper_id
                            }))
                        except:
                            pass
            elif paper_obj and paper_obj.tags:
                try:
                    existing_keywords = json.loads(paper_obj.tags)
                    if websocket:
                        await websocket.send_text(json.dumps({
                            "type": "keywords_result",
                            "keywords": existing_keywords,
                            "paper_id": paper_id
                        }))
                except:
                    pass
    except asyncio.TimeoutError:
        logger.warning(f"论文 {paper_id} 关键词提取超时")
    except Exception as e:
        logger.warning(f"论文 {paper_id} 关键词提取失败: {e}")
