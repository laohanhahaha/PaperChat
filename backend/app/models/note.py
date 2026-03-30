"""笔记模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Note(Base):
    """笔记表模型"""
    
    __tablename__ = "notes"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    highlight_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("highlights.id", ondelete="SET NULL"), 
        nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # 关系定义
    paper: Mapped["Paper"] = relationship("Paper", back_populates="notes")
    user: Mapped["User"] = relationship("User", back_populates="notes")
    highlight: Mapped[Optional["Highlight"]] = relationship("Highlight", back_populates="notes")
    
    def __repr__(self) -> str:
        return f"<Note(id={self.id}, paper_id={self.paper_id}, highlight_id={self.highlight_id})>"
