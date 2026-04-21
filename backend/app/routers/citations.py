"""引用管理路由

提供论文引用元数据查询、单篇/批量格式化引用导出接口。
所有格式化均为纯字符串模板（<1ms），零 LLM 调用。
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.user.auth_service import get_current_user
from app.services.export.citation_service import citation_service

router = APIRouter(prefix="/api/v1/citations", tags=["citations"])


# ── 请求/响应模型 ──────────────────────────────────────────────────


class ExportRequest(BaseModel):
    """批量导出请求体"""
    paper_ids: list[int] = Field(..., min_length=1, max_length=100, description="论文 ID 列表")
    format: str = Field("bibtex", pattern=r"^(bibtex|apa|gbt)$", description="导出格式")


class CitationResponse(BaseModel):
    """单篇引用响应"""
    metadata: dict
    bibtex: str
    apa: str
    gbt: str


class ExportResponse(BaseModel):
    """批量导出响应"""
    content: str
    format: str
    count: int


# ── 接口 ──────────────────────────────────────────────────────────


@router.get("/{paper_id}", response_model=CitationResponse)
async def get_citation(
    paper_id: int,
    format: str = Query("bibtex", pattern=r"^(bibtex|apa|gbt)$", description="默认展示格式"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单篇论文引用元数据 + 全格式引用

    路径参数:
        - paper_id: 论文 ID

    查询参数:
        - format: 默认展示格式 (bibtex|apa|gbt)

    返回:
        - metadata: 元数据字典
        - bibtex: BibTeX 格式引用
        - apa: APA 格式引用
        - gbt: GB/T 7714 格式引用
    """
    try:
        meta = await citation_service.extract_metadata(paper_id, db)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在",
        )

    return CitationResponse(
        metadata=meta,
        bibtex=citation_service.generate_bibtex(meta),
        apa=citation_service.generate_apa(meta),
        gbt=citation_service.generate_gbt(meta),
    )


@router.post("/export", response_model=ExportResponse)
async def export_citations(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导出参考文献列表

    请求体:
        - paper_ids: 论文 ID 列表 (1-100)
        - format: 导出格式 (bibtex|apa|gbt)

    返回:
        - content: 合并后的引用文本
        - format: 导出格式
        - count: 成功导出条目数
    """
    content = await citation_service.batch_export(
        paper_ids=request.paper_ids,
        db=db,
        format=request.format,
    )
    # 统计有效条目数（按双换行分隔）
    count = len([e for e in content.split("\n\n") if e.strip()]) if content else 0

    return ExportResponse(
        content=content,
        format=request.format,
        count=count,
    )
