"""PDF 处理服务

提供 PDF 文件解析、文本提取、元数据提取等功能
"""
import os
import pdfplumber
from typing import Optional, List, Dict, Any
from pathlib import Path


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
            print(f"提取文本块失败: {e}")
            
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
            print(f"提取全文失败: {e}")
            
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


# 全局单例
pdf_service = PDFService()
