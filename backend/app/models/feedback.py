"""用户反馈模型

提供用户对回答的反馈（点赞/点踩/文字反馈）的持久化存储
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageFeedback(Base):
    """消息反馈表模型
    
    存储用户对聊天消息的反馈：
    - rating: 1=👍 (好评), -1=👎 (差评)
    - comment: 可选的文字反馈
    """
    
    __tablename__ = "message_feedbacks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=👍, -1=👎
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # 关系定义
    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="feedbacks")
    user: Mapped["User"] = relationship("User", back_populates="message_feedbacks")
    
    def __repr__(self) -> str:
        return f"<MessageFeedback(id={self.id}, message_id={self.message_id}, rating={self.rating})>"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
