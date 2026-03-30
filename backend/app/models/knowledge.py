"""知识库模型

知识卡片和知识关联的数据模型定义
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, func, Float, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeCard(Base):
    """知识卡片表模型"""
    
    __tablename__ = "knowledge_cards"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI 生成的简要摘要
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "highlight", "chat", "manual", "analysis"
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 来源对象 ID
    paper_id: Mapped[Optional[int]] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)  # 关联论文
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # 标签列表
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 分类
    importance: Mapped[float] = mapped_column(Float, default=1.0)  # 重要性权重
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    
    # 关系定义
    user: Mapped["User"] = relationship("User", back_populates="knowledge_cards")
    paper: Mapped[Optional["Paper"]] = relationship("Paper", back_populates="knowledge_cards")
    relations_as_source: Mapped[list["KnowledgeRelation"]] = relationship(
        "KnowledgeRelation",
        foreign_keys="KnowledgeRelation.source_card_id",
        back_populates="source_card",
        cascade="all, delete-orphan"
    )
    relations_as_target: Mapped[list["KnowledgeRelation"]] = relationship(
        "KnowledgeRelation",
        foreign_keys="KnowledgeRelation.target_card_id",
        back_populates="target_card",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeCard(id={self.id}, title={self.title[:30]}...)>"


class KnowledgeRelation(Base):
    """知识关联表模型"""
    
    __tablename__ = "knowledge_relations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    source_card_id: Mapped[int] = mapped_column(ForeignKey("knowledge_cards.id"), nullable=False)
    target_card_id: Mapped[int] = mapped_column(ForeignKey("knowledge_cards.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "related", "prerequisite", "extends", "contradicts", "supports"
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    
    # 关系定义
    source_card: Mapped["KnowledgeCard"] = relationship(
        "KnowledgeCard",
        foreign_keys=[source_card_id],
        back_populates="relations_as_source"
    )
    target_card: Mapped["KnowledgeCard"] = relationship(
        "KnowledgeCard",
        foreign_keys=[target_card_id],
        back_populates="relations_as_target"
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeRelation(id={self.id}, {self.source_card_id}->{self.target_card_id}, type={self.relation_type})>"
