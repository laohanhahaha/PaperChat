"""笔记相关的 Pydantic 模型"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NoteCreate(BaseModel):
    """创建笔记模型"""
    paper_id: int
    highlight_id: Optional[int] = None  # 可选绑定高亮
    content: str


class NoteUpdate(BaseModel):
    """更新笔记模型"""
    content: Optional[str] = None
    highlight_id: Optional[int] = None


class NoteResponse(BaseModel):
    """笔记响应模型"""
    id: int
    paper_id: int
    user_id: int
    highlight_id: Optional[int]
    content: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class NoteWithHighlightResponse(NoteResponse):
    """带高亮信息的笔记响应模型"""
    highlight_text: Optional[str] = None  # 关联的高亮文本
