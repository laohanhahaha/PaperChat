"""高亮标注模型"""
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Highlight(Base):
    """高亮标注表模型"""
    
    __tablename__ = "highlights"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    page: Mapped[int]
    rects: Mapped[str] = mapped_column(Text)  # JSON: [{"x0":..,"y0":..,"x1":..,"y1":..}]
    color: Mapped[str] = mapped_column(String(20), default="#FFEB3B")
    highlight_type: Mapped[str] = mapped_column(String(20), default="highlight")  # highlight/underline/strikethrough
    selected_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # 关系定义
    paper: Mapped["Paper"] = relationship("Paper", back_populates="highlights")
    user: Mapped["User"] = relationship("User", back_populates="highlights")
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="highlight",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Highlight(id={self.id}, paper_id={self.paper_id}, page={self.page})>"
