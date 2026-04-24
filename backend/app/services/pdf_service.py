"""PDF 处理服务

提供 PDF 文件解析、文本提取、元数据提取、图片提取等功能
"""
import base64
import hashlib
import json
import os
import logging
import pdfplumber
import fitz  # PyMuPDF
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class PDFService:
    """PDF 处理服务类"""

    @staticmethod
    async def extract_metadata(file_path: str) -> Dict[str, Any]:
        """
        提取 PDF 元数据（标题、页数等）

        Args:
            file_path: PDF 文件路径

        Returns:
            包含元数据的字典
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = {
                    "title": "",
                    "page_count": len(pdf.pages),
                    "authors": "",
                }

                # 尝试从 PDF 元数据中提取标题和作者
                if pdf.metadata:
                    metadata["title"] = pdf.metadata.get("Title", "") or ""
                    metadata["authors"] = pdf.metadata.get("Author", "") or ""

                # 如果没有标题，尝试从第一页提取
                if not metadata["title"] and len(pdf.pages) > 0:
                    first_page = pdf.pages[0]
                    text = first_page.extract_text() or ""
                    lines = text.strip().split('\n')
                    if lines:
                        # 通常标题在第一行或前几行
                        metadata["title"] = lines[0][:200] if lines[0] else "未命名论文"

                if not metadata["title"]:
                    metadata["title"] = "未命名论文"

                return metadata
        except Exception as e:
            return {
                "title": "未命名论文",
                "page_count": 0,
                "authors": "",
            }

    @staticmethod
    async def extract_text_blocks(file_path: str) -> List[Dict[str, Any]]:
        """
        提取文本块及其坐标信息

        Args:
            file_path: PDF 文件路径

        Returns:
            文本块列表，每个块包含文本和坐标信息
        """
        blocks = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # 提取字符级别的信息
                    chars = page.chars
                    if not chars:
                        continue

                    # 按 y 坐标分组（同一行的字符）
                    lines = {}
                    for char in chars:
                        # 使用 y0 作为行的标识（取整到小数点后1位，处理微小偏差）
                        y_key = round(char.get("top", 0), 1)
                        if y_key not in lines:
                            lines[y_key] = []
                        lines[y_key].append(char)

                    # 对每一行排序并合并成文本块
                    for y_key in sorted(lines.keys()):
                        line_chars = sorted(lines[y_key], key=lambda c: c.get("x0", 0))
                        if not line_chars:
                            continue

                        # 合并字符为文本
                        text = "".join(c.get("text", "") for c in line_chars).strip()
                        if not text:
                            continue

                        # 计算边界框
                        x0 = min(c.get("x0", 0) for c in line_chars)
                        y0 = min(c.get("top", 0) for c in line_chars)
                        x1 = max(c.get("x1", 0) for c in line_chars)
                        y1 = max(c.get("bottom", 0) for c in line_chars)

                        blocks.append({
                            "page_number": page_num,
                            "text": text,
                            "x0": x0,
                            "y0": y0,
                            "x1": x1,
                            "y1": y1,
                            "block_type": "text"
                        })

        except Exception as e:
            logger.error("提取文本块失败", exc_info=True)

        return blocks

    @staticmethod
    async def extract_full_text(file_path: str) -> str:
        """
        提取全文文本（用于 LLM 分析）

        Args:
            file_path: PDF 文件路径

        Returns:
            提取的文本内容
        """
        full_text = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)

        except Exception as e:
            logger.error("提取全文失败", exc_info=True)

        return "\n\n".join(full_text)

    @staticmethod
    async def get_page_count(file_path: str) -> int:
        """
        获取 PDF 总页数

        Args:
            file_path: PDF 文件路径

        Returns:
            页数
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            return 0

    @staticmethod
    async def validate_pdf(file_path: str) -> bool:
        """
        验证文件是否为有效的 PDF

        Args:
            file_path: 文件路径

        Returns:
            是否有效
        """
        try:
            # 检查文件扩展名
            if not file_path.lower().endswith('.pdf'):
                return False

            # 检查文件头
            with open(file_path, 'rb') as f:
                header = f.read(5)
                if header != b'%PDF-':
                    return False

            # 尝试用 pdfplumber 打开
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages) > 0

        except Exception as e:
            return False

    # ──────────────────────────────────────────────
    # 图片提取（基于 PyMuPDF）
    # ──────────────────────────────────────────────

    def _get_cache_path(self, file_path: str, page_num: int) -> str:
        """生成图片缓存文件路径"""
        key = hashlib.md5(f"{file_path}:{page_num}".encode()).hexdigest()
        cache_dir = os.path.join("uploads", ".image_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{key}.json")

    @staticmethod
    def _find_figure_label(page: fitz.Page, rect: fitz.Rect) -> Optional[str]:
        """在图片区域上下方搜索 Fig./Figure/图 标题文本"""
        # 搜索区域：图片上方 80pt 和下方 40pt 的横向带状区域
        search_margin_top = 80
        search_margin_bottom = 40

        top_rect = fitz.Rect(rect.x0, max(0, rect.y0 - search_margin_top), rect.x1, rect.y0)
        bottom_rect = fitz.Rect(rect.x0, rect.y1, rect.x1, rect.y1 + search_margin_bottom)

        for zone in [top_rect, bottom_rect]:
            text = page.get_text("text", clip=zone)
            for line in text.splitlines():
                line_stripped = line.strip()
                lower = line_stripped.lower()
                if lower.startswith("fig") or lower.startswith("figure") or line_stripped.startswith("图"):
                    return line_stripped
        return None

    async def extract_page_images(self, file_path: str, page_num: int) -> list[dict]:
        """提取指定页的所有图片

        返回: [{base64: str, bbox: [x0,y0,x1,y1], type: str, index: int, width: int, height: int}]
        性能: 单页 100-500ms（取决于图片数量和大小）；缓存命中时 < 50ms
        """
        # 缓存检查
        cache_path = self._get_cache_path(file_path, page_num)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass  # 缓存损坏时继续提取

        doc = fitz.open(file_path)
        page = doc[page_num]
        images = []
        for idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            # 获取图片在页面上的位置
            rects = page.get_image_rects(xref)
            bbox = [rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1] if rects else [0, 0, 0, 0]
            images.append({
                "base64": base64.b64encode(base_image["image"]).decode(),
                "bbox": bbox,
                "type": base_image.get("ext", "png"),
                "index": idx,
                "width": base_image.get("width", 0),
                "height": base_image.get("height", 0),
            })
        doc.close()

        # 写入缓存
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(images, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"图片缓存写入失败: {e}")

        return images

    async def extract_all_images(self, file_path: str) -> list[dict]:
        """提取全文档所有图片（带页码）

        性能: 20页PDF ~2-5s
        """
        doc = fitz.open(file_path)
        all_images = []
        for page_num in range(len(doc)):
            page_images = await self.extract_page_images(file_path, page_num)
            for img in page_images:
                img["page"] = page_num
            all_images.extend(page_images)
        doc.close()
        return all_images

    async def detect_figures_and_tables(self, file_path: str, page_num: int) -> list[dict]:
        """检测图表区域（启发式算法）

        基于: 图片位置 + 文本块间距 + 标题匹配("Fig.", "Table", "图")
        返回: [{bbox, type: "figure"|"table", label, page}]
        性能: 单页 ~200ms
        """
        doc = fitz.open(file_path)
        page = doc[page_num]
        figures = []

        # 1. 从图片位置检测 figures
        for idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if rects:
                rect = rects[0]
                # 检查图片上方的文本是否包含 "Fig" 或 "图"
                label = self._find_figure_label(page, rect)
                figures.append({
                    "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                    "type": "figure",
                    "label": label or f"Figure {idx+1}",
                    "page": page_num,
                    "index": idx,
                })

        # 2. 从文本块检测 tables（查找有规律间距的文本块组）
        blocks = page.get_text("blocks")
        # 简单启发式: 查找包含 "Table" 或 "表" 的文本块
        for block in blocks:
            text = block[4] if len(block) > 4 else ""
            if any(kw in text.lower() for kw in ["table", "表"]):
                figures.append({
                    "bbox": [block[0], block[1], block[2], block[3]],
                    "type": "table",
                    "label": text.strip()[:50],
                    "page": page_num,
                })

        doc.close()
        return figures


# 全局单例
pdf_service = PDFService()
