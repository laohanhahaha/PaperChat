"""论文相关的 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class PaperCreate(BaseModel):
    """论文创建模型"""
    title: Optional[str] = None  # 上传时可以为空，后续自动提取
    tags: Optional[str] = None
    category: Optional[str] = None


class PaperUpdate(BaseModel):
    """论文更新模型"""
    title: Optional[str] = None
    authors: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    reading_status: Optional[str] = None
    last_read_page: Optional[int] = None


class PaperResponse(BaseModel):
    """论文响应模型"""
    id: int
    user_id: int
    title: str
    authors: Optional[str]
    abstract: Optional[str]
    doi: Optional[str]
    file_path: str
    file_size: int
    page_count: int
    tags: Optional[str]
    category: Optional[str]
    reading_status: str
    is_private: bool = False
    last_read_page: int
    last_read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class PaperListResponse(BaseModel):
    """论文列表响应模型"""
    total: int
    papers: List[PaperResponse]


class PaperTextBlockResponse(BaseModel):
    """论文文本块响应模型"""
    id: int
    paper_id: int
    page_number: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_type: str
    
    model_config = {"from_attributes": True}


class BatchUploadResult(BaseModel):
    """批量上传单个文件结果"""
    filename: str
    status: str  # success / error
    paper_id: Optional[int] = None
    message: Optional[str] = None


class BatchUploadResponse(BaseModel):
    """批量上传响应模型"""
    total: int
    success: int
    failed: int
    results: List[BatchUploadResult]
