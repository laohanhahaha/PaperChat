"""聊天会话模型

提供对话会话和消息的持久化存储
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSession(Base):
    """聊天会话表模型"""
    
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    paper_id: Mapped[Optional[int]] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)  # 单论文会话（兼容旧数据）
    paper_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # 多论文会话（跨文档问答）
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系定义
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    paper: Mapped[Optional["Paper"]] = relationship("Paper")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )
    
    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, title={self.title[:30]}...)>"
    
    def is_cross_doc_session(self) -> bool:
        """判断是否为跨文档会话"""
        return self.paper_ids is not None and len(self.paper_ids) > 0
    
    def get_related_paper_ids(self) -> list:
        """获取会话关联的所有论文ID"""
        if self.paper_ids:
            return self.paper_ids
        elif self.paper_id:
            return [self.paper_id]
        return []


class ChatMessage(Base):
    """聊天消息表模型"""
    
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" / "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 引用来源
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # 关系定义
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    feedbacks: Mapped[List["MessageFeedback"]] = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role={self.role})>"
