"""学术写作辅助路由

提供论文大纲生成、段落初稿生成、学术润色、引用格式生成等功能
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
import json

from app.database import get_db
from app.models.paper import Paper
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service
from app.rate_limiter import limiter

router = APIRouter(prefix="/api/v1/writing", tags=["writing"])


class OutlineRequest(BaseModel):
    """大纲生成请求"""
    topic: str
    paper_ids: list[int] = []  # 参考论文
    requirements: str = ""  # 额外要求


class DraftRequest(BaseModel):
    """段落初稿生成请求"""
    outline_section: str  # 大纲节点文本
    context: str = ""  # 参考内容/上下文
    style: str = "academic"  # academic/formal/concise


class PolishRequest(BaseModel):
    """学术润色请求"""
    text: str
    polish_type: str = "academic"  # academic/grammar/fluency/concise


class CitationRequest(BaseModel):
    """引用格式生成请求"""
    paper_ids: list[int]
    format: str = "apa"  # apa/mla/chicago/gbt7714


async def fetch_reference_papers(db: AsyncSession, paper_ids: list[int], user_id: int) -> list[dict]:
    """获取参考论文信息"""
    if not paper_ids:
        return []
    
    papers = []
    for paper_id in paper_ids:
        result = await db.execute(
            select(Paper).where(
                and_(Paper.id == paper_id, Paper.user_id == user_id)
            )
        )
        paper = result.scalar_one_or_none()
        if paper:
            papers.append({
                "id": paper.id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "doi": paper.doi,
            })
    return papers


@router.post("/outline")
@limiter.limit("20/minute")
async def generate_outline(
    request: Request,
    req: OutlineRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成论文大纲（流式）
    
    如果提供了 paper_ids，会获取论文摘要作为上下文参考
    """
    # 获取参考论文信息
    reference_papers = await fetch_reference_papers(db, req.paper_ids, user.id)
    
    async def stream_generator():
        try:
            async for chunk in llm_service.generate_outline(
                topic=req.topic,
                paper_ids=req.paper_ids,
                requirements=req.requirements,
                reference_papers=reference_papers
            ):
                # SSE 格式
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 结束标记
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/draft")
@limiter.limit("20/minute")
async def generate_draft(
    request: Request,
    req: DraftRequest,
    user: User = Depends(get_current_user)
):
    """生成段落初稿（流式）"""
    async def stream_generator():
        try:
            async for chunk in llm_service.generate_draft(
                outline_section=req.outline_section,
                context=req.context,
                style=req.style
            ):
                # SSE 格式
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 结束标记
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/polish")
@limiter.limit("20/minute")
async def polish_text(
    request: Request,
    req: PolishRequest,
    user: User = Depends(get_current_user)
):
    """学术润色（流式）
    
    polish_type:
    - academic: 学术表达优化
    - grammar: 语法修正
    - fluency: 流畅性提升
    - concise: 精简表达
    """
    # 验证润色类型
    valid_types = ["academic", "grammar", "fluency", "concise"]
    if req.polish_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的润色类型，支持: {', '.join(valid_types)}"
        )
    
    async def stream_generator():
        try:
            async for chunk in llm_service.polish_text(
                text=req.text,
                polish_type=req.polish_type
            ):
                # SSE 格式
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 结束标记
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/citations")
async def generate_citations(
    req: CitationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量生成引用格式（非流式）
    
    format:
    - apa: APA格式
    - mla: MLA格式
    - chicago: Chicago格式
    - gbt7714: GB/T 7714格式
    """
    # 验证格式
    valid_formats = ["apa", "mla", "chicago", "gbt7714"]
    if req.format not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的引用格式，支持: {', '.join(valid_formats)}"
        )
    
    # 获取论文元数据
    citations = []
    for idx, paper_id in enumerate(req.paper_ids, 1):
        result = await db.execute(
            select(Paper).where(
                and_(Paper.id == paper_id, Paper.user_id == user.id)
            )
        )
        paper = result.scalar_one_or_none()
        
        if not paper:
            citations.append({
                "paper_id": paper_id,
                "citation": None,
                "error": "论文不存在或无权访问"
            })
            continue
        
        # 构建论文信息
        paper_info = {
            "title": paper.title,
            "authors": paper.authors or "未知作者",
            "year": "n.d.",  # 默认无日期
            "journal": "",
            "index": idx
        }
        
        # 尝试从标题或DOI中提取年份
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', paper.title or "")
        if year_match:
            paper_info["year"] = year_match.group(0)
        
        # 生成引用
        try:
            citation = await llm_service.generate_citation(paper_info, req.format)
            citations.append({
                "paper_id": paper_id,
                "title": paper.title,
                "citation": citation
            })
        except Exception as e:
            citations.append({
                "paper_id": paper_id,
                "title": paper.title,
                "citation": None,
                "error": str(e)
            })
    
    return {
        "format": req.format,
        "total": len(req.paper_ids),
        "citations": citations
    }


@router.get("/formats")
async def get_citation_formats():
    """获取支持的引用格式列表"""
    return {
        "formats": [
            {"id": "apa", "name": "APA", "description": "美国心理学会格式，常用于社会科学"},
            {"id": "mla", "name": "MLA", "description": "现代语言协会格式，常用于人文学科"},
            {"id": "chicago", "name": "Chicago", "description": "芝加哥格式，常用于历史学"},
            {"id": "gbt7714", "name": "GB/T 7714", "description": "中国国家标准，中文学术论文常用"}
        ],
        "polish_types": [
            {"id": "academic", "name": "学术表达", "description": "提升学术性，使用更专业的术语和句式"},
            {"id": "grammar", "name": "语法修正", "description": "修正语法错误、标点问题"},
            {"id": "fluency", "name": "流畅性", "description": "优化句子流畅度，改善可读性"},
            {"id": "concise", "name": "精简表达", "description": "删除冗余内容，使表达更简洁"}
        ],
        "writing_styles": [
            {"id": "academic", "name": "学术风格", "description": "严谨、专业、客观"},
            {"id": "formal", "name": "正式风格", "description": "规范、礼貌、清晰"},
            {"id": "concise", "name": "简洁风格", "description": "精炼、直接、高效"}
        ]
    }
