"""知识图谱模型

知识图谱节点（实体）和边（关系）的数据模型定义
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, func, Float, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GraphNode(Base):
    """知识图谱节点（实体）"""

    __tablename__ = "graph_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)  # 实体名称
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)  # concept/method/dataset/metric/author
    description: Mapped[Optional[str]] = mapped_column(Text, default="")  # 简要描述
    paper_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # 出现在哪些论文中 [1, 3, 5]
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 所属用户
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # 关系定义
    edges_out: Mapped[list["GraphEdge"]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.source_id",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    edges_in: Mapped[list["GraphEdge"]] = relationship(
        "GraphEdge",
        foreign_keys="GraphEdge.target_id",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GraphNode(id={self.id}, name={self.name[:30]}, type={self.node_type})>"


class GraphEdge(Base):
    """知识图谱边（关系）"""

    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id"), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # uses/improves/contradicts/extends/evaluates_on
    weight: Mapped[float] = mapped_column(Float, default=1.0)  # 关系强度
    paper_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 来源论文ID
    evidence: Mapped[Optional[str]] = mapped_column(Text, default="")  # 证据文本
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # 关系定义
    source_node: Mapped["GraphNode"] = relationship(
        "GraphNode",
        foreign_keys=[source_id],
        back_populates="edges_out"
    )
    target_node: Mapped["GraphNode"] = relationship(
        "GraphNode",
        foreign_keys=[target_id],
        back_populates="edges_in"
    )

    def __repr__(self) -> str:
        return f"<GraphEdge(id={self.id}, {self.source_id}->{self.target_id}, type={self.relation_type})>"
