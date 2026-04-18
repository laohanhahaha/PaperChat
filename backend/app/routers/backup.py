"""数据备份导出路由

提供用户全量数据的 JSON 导出接口
"""
import json
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.chat import ChatSession, ChatMessage
from app.models.paper import Paper
from app.models.knowledge import KnowledgeCard, KnowledgeRelation
from app.models.note import Note
from app.models.highlight import Highlight
from app.models.feedback import MessageFeedback
from app.models.memory import UserMemory
from app.models.settings import UserSettings
from app.models.user import User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


def _serialize_datetime(val):
    """将 datetime 转为 ISO 格式字符串"""
    if val is None:
        return None
    return val.isoformat()


@router.get("/export")
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出用户所有数据为 JSON 文件

    包含：会话及消息、论文、知识卡片及关联、笔记、高亮、反馈、记忆、设置
    """
    try:
        data = {
            "export_info": {
                "user_id": current_user.id,
                "app_version": "3.1.0",
            },
            "sessions": [],
            "papers": [],
            "knowledge_cards": [],
            "knowledge_relations": [],
            "notes": [],
            "highlights": [],
            "feedbacks": [],
            "memories": [],
            "settings": None,
        }

        # ---- 会话 + 消息 ----
        user_id = current_user.id
        stmt_session = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .options(selectinload(ChatSession.messages))
        )
        result_s = await db.execute(stmt_session)
        sessions = result_s.scalars().all()
        for s in sessions:
            session_data = {
                "id": s.id,
                "title": s.title,
                "paper_id": s.paper_id,
                "paper_ids": s.paper_ids,
                "created_at": _serialize_datetime(s.created_at),
                "updated_at": _serialize_datetime(s.updated_at),
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "sources": m.sources,
                        "created_at": _serialize_datetime(m.created_at),
                    }
                    for m in s.messages
                ],
            }
            data["sessions"].append(session_data)

        # ---- 论文 ----
        stmt_paper = select(Paper).where(Paper.user_id == user_id)
        result_p = await db.execute(stmt_paper)
        papers = result_p.scalars().all()
        for p in papers:
            data["papers"].append({
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "doi": p.doi,
                "file_size": p.file_size,
                "page_count": p.page_count,
                "tags": p.tags,
                "category": p.category,
                "reading_status": p.reading_status,
                "last_read_page": p.last_read_page,
                "last_read_at": _serialize_datetime(p.last_read_at),
                "created_at": _serialize_datetime(p.created_at),
                "updated_at": _serialize_datetime(p.updated_at),
            })

        # ---- 知识卡片 ----
        stmt_kc = select(KnowledgeCard).where(KnowledgeCard.user_id == user_id)
        result_kc = await db.execute(stmt_kc)
        knowledge_cards = result_kc.scalars().all()
        kc_ids = []
        for kc in knowledge_cards:
            kc_ids.append(kc.id)
            data["knowledge_cards"].append({
                "id": kc.id,
                "title": kc.title,
                "content": kc.content,
                "summary": kc.summary,
                "source_type": kc.source_type,
                "source_id": kc.source_id,
                "paper_id": kc.paper_id,
                "tags": kc.tags,
                "category": kc.category,
                "importance": kc.importance,
                "created_at": _serialize_datetime(kc.created_at),
                "updated_at": _serialize_datetime(kc.updated_at),
            })

        # ---- 知识关联（仅导出用户拥有的卡片之间的关联）----
        if kc_ids:
            stmt_kr = select(KnowledgeRelation).where(
                KnowledgeRelation.source_card_id.in_(kc_ids)
            )
            result_kr = await db.execute(stmt_kr)
            knowledge_relations = result_kr.scalars().all()
            for kr in knowledge_relations:
                data["knowledge_relations"].append({
                    "id": kr.id,
                    "source_card_id": kr.source_card_id,
                    "target_card_id": kr.target_card_id,
                    "relation_type": kr.relation_type,
                    "description": kr.description,
                    "confidence": kr.confidence,
                    "created_at": _serialize_datetime(kr.created_at),
                })

        # ---- 笔记 ----
        stmt_note = select(Note).where(Note.user_id == user_id)
        result_n = await db.execute(stmt_note)
        notes = result_n.scalars().all()
        for n in notes:
            data["notes"].append({
                "id": n.id,
                "paper_id": n.paper_id,
                "highlight_id": n.highlight_id,
                "content": n.content,
                "created_at": _serialize_datetime(n.created_at),
                "updated_at": _serialize_datetime(n.updated_at),
            })

        # ---- 高亮 ----
        stmt_hl = select(Highlight).where(Highlight.user_id == user_id)
        result_h = await db.execute(stmt_hl)
        highlights = result_h.scalars().all()
        for h in highlights:
            data["highlights"].append({
                "id": h.id,
                "paper_id": h.paper_id,
                "page": h.page,
                "rects": h.rects,
                "color": h.color,
                "highlight_type": h.highlight_type,
                "selected_text": h.selected_text,
                "created_at": _serialize_datetime(h.created_at),
                "updated_at": _serialize_datetime(h.updated_at),
            })

        # ---- 反馈 ----
        stmt_fb = select(MessageFeedback).where(MessageFeedback.user_id == user_id)
        result_fb = await db.execute(stmt_fb)
        feedbacks = result_fb.scalars().all()
        for fb in feedbacks:
            data["feedbacks"].append({
                "id": fb.id,
                "message_id": fb.message_id,
                "rating": fb.rating,
                "comment": fb.comment,
                "created_at": _serialize_datetime(fb.created_at),
            })

        # ---- 记忆 ----
        stmt_mem = select(UserMemory).where(UserMemory.user_id == user_id)
        result_mem = await db.execute(stmt_mem)
        memories = result_mem.scalars().all()
        for mem in memories:
            data["memories"].append({
                "id": mem.id,
                "memory_type": mem.memory_type,
                "content": mem.content,
                "importance": mem.importance,
                "access_count": mem.access_count,
                "last_accessed": _serialize_datetime(mem.last_accessed),
                "created_at": _serialize_datetime(mem.created_at),
            })

        # ---- 用户设置 ----
        stmt_us = select(UserSettings).where(UserSettings.user_id == user_id)
        result_us = await db.execute(stmt_us)
        user_settings = result_us.scalar_one_or_none()
        if user_settings:
            data["settings"] = {
                "user_id": user_settings.user_id,
                "settings_json": user_settings.settings_json,
                "updated_at": _serialize_datetime(user_settings.updated_at),
            }

        content = json.dumps(data, ensure_ascii=False, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=paperchat_backup.json"
            },
        )

    except Exception as e:
        logger.error(f"导出用户数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出数据失败: {str(e)}")
