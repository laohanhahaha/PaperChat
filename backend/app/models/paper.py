"""论文模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, func, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Paper(Base):
    """论文表模型"""
    
    __tablename__ = "papers"
    
    __table_args__ = (
        Index('ix_papers_user_status', 'user_id', 'reading_status'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(default=0)
    page_count: Mapped[int] = mapped_column(default=0)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reading_status: Mapped[str] = mapped_column(String(20), default="unread", index=True)  # unread/reading/finished
    last_read_page: Mapped[int] = mapped_column(default=0)
    last_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # 最后阅读时间
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # 关系定义
    user: Mapped["User"] = relationship("User", back_populates="papers")
    analysis_cache: Mapped[Optional["PaperAnalysisCache"]] = relationship(
        "PaperAnalysisCache",
        back_populates="paper",
        uselist=False,
        cascade="all, delete-orphan"
    )
    text_blocks: Mapped[list["PaperTextBlock"]] = relationship(
        "PaperTextBlock", 
        back_populates="paper", 
        cascade="all, delete-orphan"
    )
    highlights: Mapped[list["Highlight"]] = relationship(
        "Highlight",
        back_populates="paper",
        cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="paper",
        cascade="all, delete-orphan"
    )
    knowledge_cards: Mapped[list["KnowledgeCard"]] = relationship(
        "KnowledgeCard",
        back_populates="paper",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Paper(id={self.id}, title={self.title[:30]}...)>"


class PaperTextBlock(Base):
    """论文文本块模型 - 存储 PDF 解析后的文本块信息"""
    
    __tablename__ = "paper_text_blocks"
    
    __table_args__ = (
        Index('ix_textblocks_paper_page', 'paper_id', 'page_number', 'y0'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    x0: Mapped[float]
    y0: Mapped[float]
    x1: Mapped[float]
    y1: Mapped[float]
    block_type: Mapped[str] = mapped_column(String(50), default="text")
    
    # 关系定义
    paper: Mapped["Paper"] = relationship("Paper", back_populates="text_blocks")
    
    def __repr__(self) -> str:
        return f"<PaperTextBlock(id={self.id}, paper_id={self.paper_id}, page={self.page_number})>"
