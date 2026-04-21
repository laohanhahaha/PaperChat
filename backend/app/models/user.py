"""用户模型"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """用户表模型"""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # 关系定义
    papers: Mapped[List["Paper"]] = relationship("Paper", back_populates="user")
    highlights: Mapped[List["Highlight"]] = relationship("Highlight", back_populates="user")
    notes: Mapped[List["Note"]] = relationship("Note", back_populates="user")
    chat_sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="user")
    memories: Mapped[List["UserMemory"]] = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")
    message_feedbacks: Mapped[List["MessageFeedback"]] = relationship("MessageFeedback", back_populates="user", cascade="all, delete-orphan")
    knowledge_cards: Mapped[List["KnowledgeCard"]] = relationship("KnowledgeCard", back_populates="user", cascade="all, delete-orphan")
    agent_metrics: Mapped[List["AgentMetric"]] = relationship("AgentMetric", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
