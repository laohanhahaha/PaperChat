"""高亮标注相关的 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HighlightCreate(BaseModel):
    """创建高亮标注模型"""
    paper_id: int
    page: int
    rects: str           # JSON string: [{"x0":..,"y0":..,"x1":..,"y1":..}]
    color: str = "#FFEB3B"
    highlight_type: str = "highlight"   # highlight/underline/strikethrough
    selected_text: str


class HighlightUpdate(BaseModel):
    """更新高亮标注模型"""
    color: Optional[str] = None
    highlight_type: Optional[str] = None


class HighlightResponse(BaseModel):
    """高亮标注响应模型"""
    id: int
    paper_id: int
    user_id: int
    page: int
    rects: str
    color: str
    highlight_type: str
    selected_text: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}
