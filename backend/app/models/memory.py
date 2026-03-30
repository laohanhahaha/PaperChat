"""用户记忆模型

提供用户长期记忆的持久化存储和向量化管理
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserMemory(Base):
    """用户记忆表模型
    
    存储用户的长期记忆，包括：
    - preference: 用户偏好（语言、回答风格等）
    - research_interest: 研究方向/兴趣
    - term_usage: 常用术语理解
    - feedback_pattern: 反馈模式
    """
    
    __tablename__ = "user_memories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=1.0)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # 关系定义
    user: Mapped["User"] = relationship("User", back_populates="memories")
    
    def __repr__(self) -> str:
        return f"<UserMemory(id={self.id}, user_id={self.user_id}, type={self.memory_type})>"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
