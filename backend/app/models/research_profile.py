"""研究画像数据模型

用户研究画像相关数据模型，包括研究领域、阅读偏好、知识盲区、研究阶段等
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Float, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserDomain(Base):
    """用户研究领域"""

    __tablename__ = "user_domains"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    domain_name: Mapped[str] = mapped_column(String, nullable=False)  # 领域名称
    domain_type: Mapped[str] = mapped_column(String, default="related")  # primary/sub/related
    frequency: Mapped[int] = mapped_column(Integer, default=1)  # 出现频次
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<UserDomain(id={self.id}, user_id={self.user_id}, domain={self.domain_name})>"


class ReadingPreference(Base):
    """阅读偏好"""

    __tablename__ = "reading_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    preference_type: Mapped[str] = mapped_column(String, nullable=False)  # methodology/experiment/survey/review
    count: Mapped[int] = mapped_column(Integer, default=0)  # 阅读数量
    ratio: Mapped[float] = mapped_column(Float, default=0.0)  # 占比
    top_venues: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # 常读会议/期刊
    top_authors: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # 常读作者
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<ReadingPreference(id={self.id}, user_id={self.user_id}, type={self.preference_type})>"


class KnowledgeBlindspot(Base):
    """知识盲区"""

    __tablename__ = "knowledge_blindspots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    concept: Mapped[str] = mapped_column(String, nullable=False)  # 盲区概念
    query_count: Mapped[int] = mapped_column(Integer, default=1)  # 查询次数
    status: Mapped[str] = mapped_column(String, default="blind")  # blind/improving/mastered
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<KnowledgeBlindspot(id={self.id}, user_id={self.user_id}, concept={self.concept[:30]})>"


class ResearchStage(Base):
    """研究阶段"""

    __tablename__ = "research_stages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    stage: Mapped[str] = mapped_column(String, default="survey")  # survey/design/experiment/writing
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 置信度
    evidence: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # 推断证据
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<ResearchStage(id={self.id}, user_id={self.user_id}, stage={self.stage})>"
