"""文件夹扫描与批量导入路由

提供本地文件夹 PDF 扫描和批量导入功能
"""
import hashlib
import shutil
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.config import settings
from app.models.paper import Paper, PaperTextBlock
from app.models.user import User
from app.services.pdf_service import pdf_service
from app.services.auth_service import get_current_user
from app.services.event_bus import event_bus, Event, EventTypes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/papers", tags=["文件夹导入"])

# 上传目录
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── 工具函数 ──────────────────────────────────────────────

def compute_file_hash(file_path: str) -> str:
    """计算文件 SHA-256 hash，返回前32位 hex 字符串"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:32]


# ── Schema ────────────────────────────────────────────────

class ScanFolderRequest(BaseModel):
    folder_path: str
    recursive: bool = True


class ScanFileItem(BaseModel):
    filename: str
    path: str
    size_mb: float
    file_hash: str
    status: str  # "new" | "exists"


class ScanFolderResponse(BaseModel):
    total: int
    new_count: int
    exists_count: int
    files: List[ScanFileItem]


class ImportFolderRequest(BaseModel):
    file_paths: List[str]


class ImportResultItem(BaseModel):
    filename: str
    status: str  # "success" | "skipped" | "error"
    paper_id: Optional[int] = None
    message: str = ""


class ImportFolderResponse(BaseModel):
    total: int
    imported: int
    skipped: int
    failed: int
    details: List[ImportResultItem]


# ── 扫描端点 ──────────────────────────────────────────────

@router.post("/scan-folder", response_model=ScanFolderResponse)
async def scan_folder(
    req: ScanFolderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫描本地文件夹中的 PDF 文件，标注新文件与已存在文件"""
    folder = Path(req.folder_path)

    if not folder.exists() or not folder.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"路径不存在或不是目录: {req.folder_path}",
        )

    # 枚举 PDF 文件
    try:
        pdf_files = list(folder.rglob("*.pdf") if req.recursive else folder.glob("*.pdf"))
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"权限不足，无法读取目录: {req.folder_path}",
        )

    if not pdf_files:
        return ScanFolderResponse(total=0, new_count=0, exists_count=0, files=[])

    # 计算所有文件 hash
    file_infos: List[dict] = []
    for pdf_path in pdf_files:
        try:
            file_hash = await asyncio.to_thread(compute_file_hash, str(pdf_path))
            size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 2)
            file_infos.append({
                "filename": pdf_path.name,
                "path": str(pdf_path),
                "size_mb": size_mb,
                "file_hash": file_hash,
            })
        except (PermissionError, OSError) as e:
            logger.warning(f"无法读取文件 {pdf_path}: {e}")
            continue

    if not file_infos:
        return ScanFolderResponse(total=0, new_count=0, exists_count=0, files=[])

    # 批量查询数据库中已存在的 hash
    all_hashes = [f["file_hash"] for f in file_infos]
    result = await db.execute(
        select(Paper.file_hash).where(Paper.file_hash.in_(all_hashes))
    )
    existing_hashes = set(result.scalars().all())

    # 构建结果
    files: List[ScanFileItem] = []
    new_count = 0
    exists_count = 0
    for info in file_infos:
        is_exists = info["file_hash"] in existing_hashes
        if is_exists:
            exists_count += 1
        else:
            new_count += 1
        files.append(ScanFileItem(
            filename=info["filename"],
            path=info["path"],
            size_mb=info["size_mb"],
            file_hash=info["file_hash"],
            status="exists" if is_exists else "new",
        ))

    # 按 status 排序：new 在前
    files.sort(key=lambda f: (0 if f.status == "new" else 1, f.filename))

    return ScanFolderResponse(
        total=len(files),
        new_count=new_count,
        exists_count=exists_count,
        files=files,
    )


# ── 导入端点 ──────────────────────────────────────────────

@router.post("/import-folder", response_model=ImportFolderResponse)
async def import_folder(
    req: ImportFolderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导入指定的 PDF 文件到系统"""
    details: List[ImportResultItem] = []
    imported = 0
    skipped = 0
    failed = 0

    for file_path_str in req.file_paths:
        src_path = Path(file_path_str)

        # 1. 校验文件存在且为 .pdf
        if not src_path.exists():
            details.append(ImportResultItem(
                filename=src_path.name, status="error", message="文件不存在",
            ))
            failed += 1
            continue

        if not src_path.suffix.lower() == ".pdf":
            details.append(ImportResultItem(
                filename=src_path.name, status="error", message="不是 PDF 文件",
            ))
            failed += 1
            continue

        # 2. 计算 hash 并检查是否已存在
        try:
            file_hash = await asyncio.to_thread(compute_file_hash, str(src_path))
        except (PermissionError, OSError) as e:
            details.append(ImportResultItem(
                filename=src_path.name, status="error", message=f"无法读取文件: {e}",
            ))
            failed += 1
            continue

        existing = await db.execute(
            select(Paper.id).where(Paper.file_hash == file_hash).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            details.append(ImportResultItem(
                filename=src_path.name, status="skipped", message="文件已存在（hash 重复）",
            ))
            skipped += 1
            continue

        # 3. 复制文件到 uploads 目录
        file_id = str(uuid.uuid4())
        dest_path = UPLOAD_DIR / f"{file_id}.pdf"
        try:
            await asyncio.to_thread(shutil.copy2, str(src_path), str(dest_path))
        except (PermissionError, OSError) as e:
            details.append(ImportResultItem(
                filename=src_path.name, status="error", message=f"复制文件失败: {e}",
            ))
            failed += 1
            continue

        try:
            # 4. 提取元数据
            metadata = await pdf_service.extract_metadata(str(dest_path))

            # 5. 提取文本块
            text_blocks = await pdf_service.extract_text_blocks(str(dest_path))

            # 6. 使用文件名作为标题（去掉扩展名），或从元数据提取
            final_title = metadata.get("title", "")
            if not final_title or final_title == "未命名论文":
                final_title = src_path.stem

            file_size = dest_path.stat().st_size

            # 7. 创建 Paper 记录
            paper = Paper(
                user_id=current_user.id,
                title=final_title,
                authors=metadata.get("authors", ""),
                file_path=str(dest_path),
                file_size=file_size,
                page_count=metadata.get("page_count", 0),
                file_hash=file_hash,
                reading_status="unread",
            )
            db.add(paper)
            await db.flush()

            # 8. 批量创建 PaperTextBlock 记录
            for block in text_blocks:
                text_block = PaperTextBlock(
                    paper_id=paper.id,
                    page_number=block["page_number"],
                    text=block["text"],
                    x0=block["x0"],
                    y0=block["y0"],
                    x1=block["x1"],
                    y1=block["y1"],
                    block_type=block["block_type"],
                )
                db.add(text_block)

            await db.commit()
            await db.refresh(paper)

            # 9. 发布 PAPER_UPLOADED 事件
            asyncio.create_task(event_bus.publish(Event(
                type=EventTypes.PAPER_UPLOADED,
                data={
                    "paper_id": paper.id,
                    "user_id": current_user.id,
                    "text_blocks": text_blocks,
                },
            )))

            details.append(ImportResultItem(
                filename=src_path.name, status="success",
                paper_id=paper.id, message="导入成功",
            ))
            imported += 1

        except Exception as e:
            logger.error(f"导入文件失败 {src_path.name}: {e}")
            # 清理已复制的文件
            if dest_path.exists():
                dest_path.unlink()
            # 回滚当前事务中未提交的变更
            await db.rollback()
            details.append(ImportResultItem(
                filename=src_path.name, status="error", message=f"处理失败: {e}",
            ))
            failed += 1

    return ImportFolderResponse(
        total=len(req.file_paths),
        imported=imported,
        skipped=skipped,
        failed=failed,
        details=details,
    )
