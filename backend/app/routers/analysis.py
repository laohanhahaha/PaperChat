"""论文分析路由

提供多论文对比分析和文献综述生成功能
"""
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models.paper import Paper, PaperTextBlock
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.llm_service import llm_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 每篇论文最大字符数（约3000字）
MAX_PAPER_TEXT_LENGTH = 3000
# 总上下文最大字符数（约15000字）
MAX_TOTAL_TEXT_LENGTH = 15000


class CompareRequest(BaseModel):
    """对比分析请求"""
    paper_ids: List[int] = Field(..., description="要对比的论文 ID 列表", min_length=2, max_length=10)


async def get_paper_text_content(db: AsyncSession, paper_id: int, user_id: int, max_length: int = MAX_PAPER_TEXT_LENGTH) -> dict:
    """
    获取论文的文本内容（截断到指定长度）
    
    Args:
        db: 数据库会话
        paper_id: 论文ID
        user_id: 用户ID（用于权限验证）
        max_length: 最大字符数
        
    Returns:
        {"title": "论文标题", "text": "截断后的文本内容"}
    """
    # 查询论文
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == user_id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"论文 ID {paper_id} 不存在"
        )
    
    # 查询文本块
    result = await db.execute(
        select(PaperTextBlock)
        .where(PaperTextBlock.paper_id == paper_id)
        .order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    )
    blocks = result.scalars().all()
    
    # 拼接文本
    texts = [block.text for block in blocks]
    full_text = "\n".join(texts)
    
    # 截断文本
    if len(full_text) > max_length:
        # 尝试在句子边界截断
        truncated = full_text[:max_length]
        # 找到最后一个句号、问号或换行符
        for sep in ["\n\n", "。", "？", "!", "\n"]:
            last_sep = truncated.rfind(sep)
            if last_sep > max_length * 0.8:  # 至少保留80%的内容
                truncated = truncated[:last_sep + 1]
                break
        full_text = truncated + "\n[内容已截断...]"
    
    return {
        "title": paper.title,
        "text": full_text
    }


@router.post("/compare")
async def compare_papers(
    req: CompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    多论文对比分析（流式返回）
    
    请求体:
        - paper_ids: 要对比的论文 ID 列表（2-10篇）
    
    返回:
        - SSE 流式响应，每行一个 JSON 对象
    """
    if len(req.paper_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要选择 2 篇论文进行对比"
        )
    
    if len(req.paper_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多只能选择 10 篇论文进行对比"
        )
    
    # 获取各论文的文本内容
    papers_text = []
    for paper_id in req.paper_ids:
        try:
            paper_data = await get_paper_text_content(db, paper_id, user.id)
            papers_text.append(paper_data)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取论文 ID {paper_id} 内容失败: {str(e)}"
            )
    
    async def generate():
        """生成 SSE 流"""
        try:
            async for chunk in llm_service.compare_papers(papers_text):
                if chunk:
                    # SSE 格式: data: {...}\n\n
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            # 发送完成标记
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@router.post("/review")
async def generate_review(
    req: CompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成文献综述（流式返回）
    
    请求体:
        - paper_ids: 要生成综述的论文 ID 列表（2-10篇）
    
    返回:
        - SSE 流式响应，Markdown 格式的文献综述
    """
    if len(req.paper_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要选择 2 篇论文生成综述"
        )
    
    if len(req.paper_ids) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多只能选择 10 篇论文生成综述"
        )
    
    # 获取各论文的文本内容
    papers_text = []
    for paper_id in req.paper_ids:
        try:
            paper_data = await get_paper_text_content(db, paper_id, user.id)
            papers_text.append(paper_data)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取论文 ID {paper_id} 内容失败: {str(e)}"
            )
    
    async def generate():
        """生成 SSE 流"""
        try:
            async for chunk in llm_service.generate_review(papers_text):
                if chunk:
                    # SSE 格式: data: {...}\n\n
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            # 发送完成标记
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
