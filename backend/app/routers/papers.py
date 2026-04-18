"""论文管理路由

提供论文上传、查询、更新、删除、文本提取等接口
"""
import os
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Query, Body
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db, AsyncSessionLocal
from app.config import settings
from app.models.paper import Paper, PaperTextBlock
from app.models.paper_analysis import PaperAnalysisCache
from app.models.user import User
from app.schemas.paper import PaperCreate, PaperUpdate, PaperResponse, PaperListResponse, BatchUploadResponse
from app.services.pdf_service import pdf_service
from app.services.auth_service import get_current_user
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.services.event_bus import event_bus, Event, EventTypes

router = APIRouter(prefix="/api/v1/papers", tags=["论文"])


# 确保上传目录存在
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# 阅读状态更新请求模型
class ReadingStatusUpdate(BaseModel):
    """阅读状态更新模型"""
    status: str  # "reading" 或 "finished"


@router.patch("/{paper_id}/reading-status")
async def mark_reading_status(
    paper_id: int,
    update_data: ReadingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    标记论文阅读状态并更新阅读时间
    
    路径参数:
        - paper_id: 论文 ID
    
    请求体:
        - status: 阅读状态 ("reading" 或 "finished")
    
    返回:
        - 更新成功消息
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 验证状态值
    if update_data.status not in ["unread", "reading", "finished"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的阅读状态，必须是 unread、reading 或 finished"
        )
    
    # 更新阅读状态和时间
    paper.reading_status = update_data.status
    paper.last_read_at = datetime.now()
    
    await db.commit()
    await db.refresh(paper)
    
    return {"message": "阅读状态已更新", "reading_status": paper.reading_status, "last_read_at": paper.last_read_at}


@router.get("", response_model=PaperListResponse)
async def list_papers(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选"),
    reading_status: Optional[str] = Query(None, description="阅读状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文列表
    
    查询参数:
        - page: 页码（默认 1）
        - page_size: 每页数量（默认 20）
        - search: 搜索关键词（模糊匹配标题/作者）
        - category: 分类过滤
        - reading_status: 阅读状态过滤
    
    返回:
        - 论文列表及分页信息
    """
    # 构建基础查询
    query = select(Paper).where(Paper.user_id == current_user.id)
    count_query = select(func.count(Paper.id)).where(Paper.user_id == current_user.id)
    
    # 添加搜索条件
    if search:
        search_filter = or_(
            Paper.title.contains(search),
            Paper.authors.contains(search)
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # 添加分类筛选
    if category:
        query = query.where(Paper.category == category)
        count_query = count_query.where(Paper.category == category)
    
    # 添加阅读状态筛选
    if reading_status:
        query = query.where(Paper.reading_status == reading_status)
        count_query = count_query.where(Paper.reading_status == reading_status)
    
    # 获取总数
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 分页查询
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Paper.created_at.desc()).options(
        selectinload(Paper.text_blocks)
    )
    
    result = await db.execute(query)
    papers = result.scalars().all()
    
    return PaperListResponse(
        total=total,
        papers=[PaperResponse.model_validate(p) for p in papers]
    )


@router.post("/upload", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
async def upload_paper(
    file: UploadFile = File(..., description="PDF 文件"),
    title: Optional[str] = Form(None, description="标题（可选）"),
    category: Optional[str] = Form(None, description="分类（可选）"),
    tags: Optional[str] = Form(None, description="标签（可选，逗号分隔）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传论文
    
    请求:
        - file: PDF 文件（multipart/form-data）
        - title: 标题（可选，从 PDF 元数据提取）
        - category: 分类（可选）
        - tags: 标签（可选，逗号分隔）
    
    返回:
        - 上传成功的论文信息
    """
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 PDF 文件"
        )
    
    # 读取文件内容
    content = await file.read()

    # 验证 PDF magic bytes
    if not content[:5] == b'%PDF-':
        raise HTTPException(status_code=400, detail="上传的文件不是有效的 PDF 格式")
    
    # 验证文件大小
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大 {settings.MAX_FILE_SIZE / 1024 / 1024}MB）"
        )
    
    # 生成 UUID 文件名
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}.pdf"
    file_path = UPLOAD_DIR / file_name
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        # 提取 PDF 元数据
        metadata = await pdf_service.extract_metadata(str(file_path))
        
        # 提取文本块
        text_blocks = await pdf_service.extract_text_blocks(str(file_path))
        
        # 使用用户提供的标题或从 PDF 提取的标题
        final_title = title or metadata.get("title", "未命名论文")
        if not final_title or final_title == "未命名论文":
            # 使用原始文件名（去掉扩展名）
            final_title = file.filename.rsplit('.', 1)[0] if file.filename else "未命名论文"
        
        # 创建论文记录
        paper = Paper(
            user_id=current_user.id,
            title=final_title,
            authors=metadata.get("authors", ""),
            file_path=str(file_path),
            file_size=len(content),
            page_count=metadata.get("page_count", 0),
            tags=tags,
            category=category,
            reading_status="unread"
        )
        
        db.add(paper)
        await db.flush()  # 获取 paper.id
        
        # 保存文本块
        for block in text_blocks:
            text_block = PaperTextBlock(
                paper_id=paper.id,
                page_number=block["page_number"],
                text=block["text"],
                x0=block["x0"],
                y0=block["y0"],
                x1=block["x1"],
                y1=block["y1"],
                block_type=block["block_type"]
            )
            db.add(text_block)
        
        await db.commit()
        await db.refresh(paper)
        
        # 异步建立向量索引（不阻塞上传响应）
        asyncio.create_task(rag_service.index_paper(paper.id, text_blocks))

        # 发布论文上传事件（fire-and-forget）
        asyncio.create_task(event_bus.publish(Event(
            type=EventTypes.PAPER_UPLOADED,
            data={"paper_id": paper.id, "user_id": current_user.id}
        )))

        return PaperResponse.model_validate(paper)

    except Exception as e:
        # 清理已保存的文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理 PDF 文件失败: {str(e)}"
        )


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文详情
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 论文详细信息
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    return PaperResponse.model_validate(paper)


@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: int,
    update_data: PaperUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新论文信息
    
    路径参数:
        - paper_id: 论文 ID
    
    请求体:
        - title: 标题（可选）
        - authors: 作者（可选）
        - abstract: 摘要（可选）
        - doi: DOI（可选）
        - category: 分类（可选）
        - tags: 标签（可选）
        - reading_status: 阅读状态（可选）
        - last_read_page: 最后阅读页码（可选）
    
    返回:
        - 更新后的论文信息
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 更新字段
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(paper, field, value)
    
    await db.commit()
    await db.refresh(paper)
    
    return PaperResponse.model_validate(paper)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除论文
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 删除成功消息
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 删除关联的文件
    file_path = Path(paper.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # 删除数据库记录（级联删除 text_blocks, highlights, notes）
    await db.delete(paper)
    await db.commit()

    # 发布论文删除事件（fire-and-forget）
    asyncio.create_task(event_bus.publish(Event(
        type=EventTypes.PAPER_DELETED,
        data={"paper_id": paper_id, "user_id": current_user.id}
    )))

    return None


@router.get("/{paper_id}/file")
async def get_paper_file(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取 PDF 文件
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - PDF 文件
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    file_path = Path(paper.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=f"{paper.title}.pdf",
        media_type="application/pdf"
    )


@router.get("/{paper_id}/text")
async def get_paper_text(
    paper_id: int,
    page: Optional[int] = Query(None, description="指定页码（可选，默认全部）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文文本内容
    
    路径参数:
        - paper_id: 论文 ID
    
    查询参数:
        - page: 指定页码（可选，默认全部）
    
    返回:
        - 论文文本内容
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 查询文本块
    query = select(PaperTextBlock).where(PaperTextBlock.paper_id == paper_id)
    if page:
        query = query.where(PaperTextBlock.page_number == page)
    query = query.order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    
    result = await db.execute(query)
    blocks = result.scalars().all()
    
    # 拼接文本
    texts = [block.text for block in blocks]
    full_text = "\n".join(texts)
    
    return {"text": full_text, "page_count": paper.page_count}


@router.get("/{paper_id}/blocks")
async def get_paper_blocks(
    paper_id: int,
    page: Optional[int] = Query(None, description="指定页码（可选，默认全部）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文文本块（带位置信息）
    
    路径参数:
        - paper_id: 论文 ID
    
    查询参数:
        - page: 指定页码（可选，默认全部）
    
    返回:
        - 文本块列表（包含坐标信息）
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 查询文本块
    query = select(PaperTextBlock).where(PaperTextBlock.paper_id == paper_id)
    if page:
        query = query.where(PaperTextBlock.page_number == page)
    query = query.order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    
    result = await db.execute(query)
    blocks = result.scalars().all()
    
    return {
        "blocks": [
            {
                "id": b.id,
                "page_number": b.page_number,
                "text": b.text,
                "x0": b.x0,
                "y0": b.y0,
                "x1": b.x1,
                "y1": b.y1,
                "block_type": b.block_type
            }
            for b in blocks
        ]
    }


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_papers(
    files: List[UploadFile] = File(..., description="PDF 文件列表"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import asyncio
    """
    批量上传多个 PDF 文件
    
    请求:
        - files: PDF 文件列表（multipart/form-data）
    
    返回:
        - 批量上传结果（成功/失败统计及详细信息）
    """
    results = []
    errors = []
    
    for file in files:
        try:
            # 验证文件类型
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                errors.append({
                    "filename": file.filename or "未知文件",
                    "status": "error",
                    "message": "只支持 PDF 文件"
                })
                continue
            
            # 读取文件内容
            content = await file.read()

            # 验证 PDF magic bytes
            if not content[:5] == b'%PDF-':
                errors.append({
                    "filename": file.filename or "未知文件",
                    "status": "error",
                    "message": "上传的文件不是有效的 PDF 格式"
                })
                continue

            # 验证文件大小
            if len(content) > settings.MAX_FILE_SIZE:
                errors.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": f"文件大小超过限制（最大 {settings.MAX_FILE_SIZE / 1024 / 1024}MB）"
                })
                continue
            
            # 生成 UUID 文件名
            file_id = str(uuid.uuid4())
            file_name = f"{file_id}.pdf"
            file_path = UPLOAD_DIR / file_name
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(content)
            
            try:
                # 提取 PDF 元数据
                metadata = await pdf_service.extract_metadata(str(file_path))
                
                # 提取文本块
                text_blocks = await pdf_service.extract_text_blocks(str(file_path))
                
                # 使用原始文件名（去掉扩展名）作为标题
                final_title = file.filename.rsplit('.', 1)[0] if file.filename else "未命名论文"
                if not final_title:
                    final_title = metadata.get("title", "未命名论文")
                
                # 创建论文记录
                paper = Paper(
                    user_id=current_user.id,
                    title=final_title,
                    authors=metadata.get("authors", ""),
                    file_path=str(file_path),
                    file_size=len(content),
                    page_count=metadata.get("page_count", 0),
                    reading_status="unread"
                )
                
                db.add(paper)
                await db.flush()  # 获取 paper.id
                
                # 保存文本块
                for block in text_blocks:
                    text_block = PaperTextBlock(
                        paper_id=paper.id,
                        page_number=block["page_number"],
                        text=block["text"],
                        x0=block["x0"],
                        y0=block["y0"],
                        x1=block["x1"],
                        y1=block["y1"],
                        block_type=block["block_type"]
                    )
                    db.add(text_block)
                
                await db.commit()
                await db.refresh(paper)
                
                # 异步建立向量索引
                asyncio.create_task(rag_service.index_paper(paper.id, text_blocks))

                # 发布论文上传事件（fire-and-forget）
                asyncio.create_task(event_bus.publish(Event(
                    type=EventTypes.PAPER_UPLOADED,
                    data={"paper_id": paper.id, "user_id": current_user.id}
                )))

                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "paper_id": paper.id
                })
                
            except Exception as e:
                # 清理已保存的文件
                if file_path.exists():
                    file_path.unlink()
                errors.append({
                    "filename": file.filename,
                    "status": "error",
                    "message": f"处理 PDF 文件失败: {str(e)}"
                })
                
        except Exception as e:
            errors.append({
                "filename": file.filename or "未知文件",
                "status": "error",
                "message": f"上传失败: {str(e)}"
            })
    
    return {
        "total": len(files),
        "success": len(results),
        "failed": len(errors),
        "results": results + errors
    }


@router.post("/batch-upload-zip", response_model=BatchUploadResponse)
async def batch_upload_zip(
    file: UploadFile = File(..., description="ZIP 文件"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从 ZIP 文件中批量导入 PDF
    
    请求:
        - file: ZIP 文件（multipart/form-data）
    
    返回:
        - 批量上传结果（成功/失败统计及详细信息）
    """
    import zipfile
    import io
    
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 ZIP 文件"
        )
    
    # 读取 ZIP 文件内容
    content = await file.read()
    
    # 验证文件大小
    if len(content) > settings.MAX_FILE_SIZE * 2:  # ZIP 文件限制放宽到 100MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ZIP 文件大小超过限制（最大 {settings.MAX_FILE_SIZE * 2 / 1024 / 1024}MB）"
        )
    
    results = []
    errors = []
    
    try:
        # 使用 BytesIO 读取 ZIP 文件
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # 获取所有 PDF 文件
            pdf_files = [name for name in zf.namelist() 
                        if name.lower().endswith('.pdf') and not name.startswith('__MACOSX')]
            
            if not pdf_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP 文件中未找到 PDF 文件"
                )
            
            for pdf_name in pdf_files:
                try:
                    # 读取 PDF 文件内容
                    pdf_content = zf.read(pdf_name)

                    # 验证 PDF magic bytes
                    if not pdf_content[:5] == b'%PDF-':
                        errors.append({
                            "filename": pdf_name,
                            "status": "error",
                            "message": "上传的文件不是有效的 PDF 格式"
                        })
                        continue

                    # 验证文件大小
                    if len(pdf_content) > settings.MAX_FILE_SIZE:
                        errors.append({
                            "filename": pdf_name,
                            "status": "error",
                            "message": f"文件大小超过限制（最大 {settings.MAX_FILE_SIZE / 1024 / 1024}MB）"
                        })
                        continue
                    
                    # 生成 UUID 文件名
                    file_id = str(uuid.uuid4())
                    file_name = f"{file_id}.pdf"
                    file_path = UPLOAD_DIR / file_name
                    
                    # 保存文件
                    with open(file_path, "wb") as f:
                        f.write(pdf_content)
                    
                    try:
                        # 提取 PDF 元数据
                        metadata = await pdf_service.extract_metadata(str(file_path))
                        
                        # 提取文本块
                        text_blocks = await pdf_service.extract_text_blocks(str(file_path))
                        
                        # 使用 ZIP 中的文件名作为标题
                        final_title = pdf_name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                        if not final_title:
                            final_title = metadata.get("title", "未命名论文")
                        
                        # 创建论文记录
                        paper = Paper(
                            user_id=current_user.id,
                            title=final_title,
                            authors=metadata.get("authors", ""),
                            file_path=str(file_path),
                            file_size=len(pdf_content),
                            page_count=metadata.get("page_count", 0),
                            reading_status="unread"
                        )
                        
                        db.add(paper)
                        await db.flush()  # 获取 paper.id
                        
                        # 保存文本块
                        for block in text_blocks:
                            text_block = PaperTextBlock(
                                paper_id=paper.id,
                                page_number=block["page_number"],
                                text=block["text"],
                                x0=block["x0"],
                                y0=block["y0"],
                                x1=block["x1"],
                                y1=block["y1"],
                                block_type=block["block_type"]
                            )
                            db.add(text_block)
                        
                        await db.commit()
                        await db.refresh(paper)
                        
                        # 异步建立向量索引
                        asyncio.create_task(rag_service.index_paper(paper.id, text_blocks))

                        # 发布论文上传事件（fire-and-forget）
                        asyncio.create_task(event_bus.publish(Event(
                            type=EventTypes.PAPER_UPLOADED,
                            data={"paper_id": paper.id, "user_id": current_user.id}
                        )))

                        results.append({
                            "filename": pdf_name,
                            "status": "success",
                            "paper_id": paper.id
                        })
                        
                    except Exception as e:
                        # 清理已保存的文件
                        if file_path.exists():
                            file_path.unlink()
                        errors.append({
                            "filename": pdf_name,
                            "status": "error",
                            "message": f"处理 PDF 文件失败: {str(e)}"
                        })
                        
                except Exception as e:
                    errors.append({
                        "filename": pdf_name,
                        "status": "error",
                        "message": f"提取失败: {str(e)}"
                    })
                    
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 ZIP 文件"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理 ZIP 文件失败: {str(e)}"
        )
    
    return {
        "total": len(pdf_files) if 'pdf_files' in dir() else 0,
        "success": len(results),
        "failed": len(errors),
        "results": results + errors
    }


@router.post("/{paper_id}/search")
async def search_paper_content(
    paper_id: int,
    query: str = Form(..., description="搜索关键词"),
    top_k: int = Form(5, description="返回结果数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    搜索论文内容
    
    路径参数:
        - paper_id: 论文 ID
    
    表单参数:
        - query: 搜索关键词
        - top_k: 返回结果数量（默认 5）
    
    返回:
        - 检索结果列表，包含相关文本块和页码
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 执行检索
    results = await rag_service.search(paper_id, query, top_k)
    
    return {
        "paper_id": paper_id,
        "query": query,
        "total": len(results),
        "results": results
    }


@router.post("/{paper_id}/reindex")
async def reindex_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重建论文向量索引
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 重建结果
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 获取文本块
    from app.models.paper import PaperTextBlock
    result = await db.execute(
        select(PaperTextBlock).where(PaperTextBlock.paper_id == paper_id)
    )
    text_blocks = result.scalars().all()
    
    if not text_blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="论文没有文本内容，无法建立索引"
        )
    
    # 转换为字典列表
    blocks_data = [
        {
            "page_number": block.page_number,
            "text": block.text
        }
        for block in text_blocks
    ]
    
    # 重建索引
    success = await rag_service.reindex_paper(paper_id, blocks_data)
    
    if success:
        # 获取索引状态
        status = await rag_service.get_index_status(paper_id)
        return {
            "paper_id": paper_id,
            "success": True,
            "message": "索引重建成功",
            "index_status": status
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="索引重建失败"
        )


@router.get("/{paper_id}/index-status")
async def get_paper_index_status(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文向量索引状态
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 索引状态信息
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    status = await rag_service.get_index_status(paper_id)
    return status


@router.get("/{paper_id}/analysis")
async def get_paper_analysis_cache(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取论文分析缓存
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 章节概述和深度分析的缓存内容
    """
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="论文不存在"
        )
    
    # 从分析缓存表读取
    cache_result = await db.execute(
        select(PaperAnalysisCache).where(PaperAnalysisCache.paper_id == paper_id)
    )
    cache = cache_result.scalar_one_or_none()
    
    return {
        "paper_id": paper_id,
        "section_analysis": cache.section_analysis if cache else None,
        "deep_analysis": cache.deep_analysis if cache else None,
        "has_section_analysis": bool(cache.section_analysis) if cache else False,
        "has_deep_analysis": bool(cache.deep_analysis) if cache else False
    }


@router.post("/{paper_id}/extract-keywords")
async def extract_paper_keywords(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发论文关键词提取
    
    路径参数:
        - paper_id: 论文 ID
    
    返回:
        - 提取的关键词列表
    """
    # 验证论文存在且属于当前用户
    result = await db.execute(
        select(Paper).where(and_(Paper.id == paper_id, Paper.user_id == current_user.id))
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    
    # 获取论文文本块
    result = await db.execute(
        select(PaperTextBlock).where(PaperTextBlock.paper_id == paper_id).order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
    )
    blocks = result.scalars().all()
    
    if not blocks:
        raise HTTPException(status_code=400, detail="论文没有文本内容，无法提取关键词")
    
    # 拼接文本
    full_text = "\n".join([b.text for b in blocks])
    
    # 提取关键词
    keywords = await llm_service.extract_keywords(text=full_text, title=paper.title, max_keywords=5)
    
    if keywords:
        paper.tags = json.dumps(keywords, ensure_ascii=False)
        await db.commit()
        await db.refresh(paper)
    
    return {"paper_id": paper_id, "keywords": keywords}
