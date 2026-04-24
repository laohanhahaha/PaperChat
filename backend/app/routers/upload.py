"""图片上传 API

性能: 上传+压缩单张 ~200-500ms（取决于图片大小）
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
import uuid
import os
import io

from app.config import settings

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "images")
MAX_SIZE_MB = settings.MAX_IMAGE_SIZE_MB


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """上传图片，返回 image_id 和缩略图 URL

    - > 2MB 自动 JPEG 压缩到 85% 质量
    - 保存原图和缩略图
    """
    # 1. 校验文件类型和大小
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "仅支持图片文件")

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"图片不能超过 {MAX_SIZE_MB}MB")

    # 2. 生成 image_id
    image_id = str(uuid.uuid4())[:12]
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 3. 保存原图
    ext = os.path.splitext(file.filename or ".jpg")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        ext = ".jpg"
    original_path = os.path.join(UPLOAD_DIR, f"{image_id}_original{ext}")
    with open(original_path, "wb") as f:
        f.write(content)

    # 4. 打开图片进行处理
    img = Image.open(io.BytesIO(content))
    # 处理透明通道（PNG → JPEG 需要）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 5. 生成缩略图（最大 200x200）
    thumb = img.copy()
    thumb.thumbnail((200, 200))
    thumb_path = os.path.join(UPLOAD_DIR, f"{image_id}_thumb.jpg")
    thumb.save(thumb_path, "JPEG", quality=85)

    # 6. 压缩版（用于 LLM 分析，< 2MB）
    if len(content) > 2 * 1024 * 1024:
        compressed = img.copy()
        # 缩小到最大 1920px 边
        compressed.thumbnail((1920, 1920))
        compressed_path = os.path.join(UPLOAD_DIR, f"{image_id}.jpg")
        compressed.save(compressed_path, "JPEG", quality=85)
    else:
        compressed_path = original_path

    return {
        "image_id": image_id,
        "thumbnail_url": f"/api/v1/upload/images/{image_id}_thumb.jpg",
        "compressed_url": f"/api/v1/upload/images/{image_id}.jpg" if compressed_path != original_path else None,
        "original_name": file.filename,
        "size": len(content),
    }


@router.get("/images/{filename}")
async def serve_image(filename: str):
    """静态图片服务"""
    # 安全校验：防止目录遍历
    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(404, "图片不存在")
    return FileResponse(path)
