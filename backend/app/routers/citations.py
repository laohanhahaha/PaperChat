"""引用管理路由

提供引用导出、外部工具同步（Zotero/Mendeley）和格式查询。
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.models.paper import Paper
from app.services.citation import CitationFormatter, ZoteroClient
from app.services.settings_service import settings_service

router = APIRouter(prefix="/api/v1/citations", tags=["citations"])

formatter = CitationFormatter()


class ExportRequest(BaseModel):
    paper_ids: List[int]
    format: str = "bibtex"


class SyncZoteroRequest(BaseModel):
    paper_ids: List[int]


@router.post("/export")
async def export_citations(
    req: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出选中论文的引用

    Args:
        req: 包含 paper_ids 和 format 的请求体
    """
    paper_ids = req.paper_ids
    format = req.format.lower().strip()
    supported = ["bibtex", "ris", "apa", "mla", "chicago", "gbt7714", "gbt"]
    if format not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的引用格式: {format}。支持: {supported}",
        )

    if not paper_ids:
        return {"content": "", "format": format, "count": 0}

    result = await db.execute(
        select(Paper).where(Paper.id.in_(paper_ids), Paper.user_id == current_user.id)
    )
    papers = result.scalars().all()

    citations = []
    for paper in papers:
        paper_info = {
            "title": paper.title,
            "authors": paper.authors or "未知作者",
            "year": paper.created_at.year if paper.created_at else "n.d.",
            "journal": "",
            "doi": paper.doi or "",
        }
        citations.append(formatter.format(paper_info, format))

    # 不同格式的分隔方式
    if format in ("bibtex", "ris"):
        content = "\n\n".join(citations)
    else:
        content = "\n".join(citations)

    return {"content": content, "format": format, "count": len(citations)}


@router.post("/sync-zotero")
async def sync_to_zotero(
    req: SyncZoteroRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """同步论文到 Zotero

    从用户设置中读取 Zotero API Key 和 Library ID。
    """
    paper_ids = req.paper_ids

    # 读取用户 Zotero 配置
    setting_values = await settings_service.get_setting_values(current_user.id, db)
    zotero_cfg = setting_values.get("zotero", {})
    api_key = zotero_cfg.get("api_key", "")
    library_id = zotero_cfg.get("library_id", "")
    library_type = zotero_cfg.get("library_type", "users")

    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 Zotero API Key，请先在设置中添加")
    if not library_id:
        raise HTTPException(status_code=400, detail="未配置 Zotero Library ID，请先在设置中添加")

    result = await db.execute(
        select(Paper).where(Paper.id.in_(paper_ids), Paper.user_id == current_user.id)
    )
    papers = result.scalars().all()

    if not papers:
        return {"success": True, "synced": 0, "total": 0}

    client = ZoteroClient(
        api_key=api_key,
        library_id=library_id,
        library_type=library_type,
    )

    synced = 0
    errors = []
    try:
        for paper in papers:
            metadata = {
                "title": paper.title,
                "creators": [],
            }
            if paper.authors:
                for a in paper.authors.split(","):
                    a = a.strip()
                    if a:
                        metadata["creators"].append(
                            {
                                "creatorType": "author",
                                "name": a,
                            }
                        )
            if paper.doi:
                metadata["DOI"] = paper.doi

            res = await client.add_item("journalArticle", metadata)
            if res.get("success") is not False:
                synced += 1
            else:
                errors.append(f"{paper.title}: {res.get('error', '未知错误')}")
    finally:
        await client.close()

    return {
        "success": synced > 0,
        "synced": synced,
        "total": len(papers),
        "errors": errors if errors else None,
    }


@router.get("/formats")
async def get_formats():
    """返回支持的引用格式列表"""
    return {
        "formats": [
            {"key": "bibtex", "label": "BibTeX"},
            {"key": "ris", "label": "RIS"},
            {"key": "apa", "label": "APA"},
            {"key": "mla", "label": "MLA"},
            {"key": "chicago", "label": "Chicago"},
            {"key": "gbt7714", "label": "GB/T 7714"},
        ]
    }


@router.get("/zotero/status")
async def zotero_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查 Zotero 连接状态"""
    setting_values = await settings_service.get_setting_values(current_user.id, db)
    zotero_cfg = setting_values.get("zotero", {})
    api_key = zotero_cfg.get("api_key", "")
    library_id = zotero_cfg.get("library_id", "")
    library_type = zotero_cfg.get("library_type", "users")

    if not api_key or not library_id:
        return {"configured": False, "connected": False}

    client = ZoteroClient(
        api_key=api_key,
        library_id=library_id,
        library_type=library_type,
    )
    try:
        connected = await client.test_connection()
        return {"configured": True, "connected": connected}
    finally:
        await client.close()


@router.get("/{paper_id}")
async def get_paper_citation(
    paper_id: int,
    format: str = "apa",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单篇论文的格式化引用"""
    supported = ["bibtex", "ris", "apa", "mla", "chicago", "gbt7714", "gbt"]
    if format.lower().strip() not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的引用格式: {format}。支持: {supported}",
        )
    result = await db.execute(
        select(Paper).where(Paper.id == paper_id, Paper.user_id == current_user.id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    paper_info = {
        "title": paper.title,
        "authors": paper.authors or "未知作者",
        "year": paper.created_at.year if paper.created_at else "n.d.",
        "journal": "",
        "doi": paper.doi or "",
    }
    citation = formatter.format(paper_info, format)
    return {
        "paper_id": paper_id,
        "citation": citation,
        "format": format,
        "paper_title": paper.title,
    }
