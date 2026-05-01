"""论文分析缓存模型

将 Paper 的分析缓存字段拆分为独立表，
减少 Paper 主表的宽度和查询负担
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaperAnalysisCache(Base):
    """论文分析缓存表 — 存储章节概述与深度分析结果"""
    
    __tablename__ = "paper_analysis_cache"
    
    __table_args__ = ()

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    section_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deep_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), default="not_generated")
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系定义
    paper: Mapped["Paper"] = relationship("Paper", back_populates="analysis_cache")
