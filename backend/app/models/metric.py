"""Agent 指标采集模型

存储 Agent 运行时的性能指标和调用统计，用于监控和优化
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentMetric(Base):
    """Agent 运行指标表
    
    记录每次 Agent 运行的详细指标：
    - 运行模式、步数、耗时
    - 工具调用详情（名称、耗时、成功率、缓存命中）
    - LLM 调用次数、缓存命中次数
    - 成功/失败状态及错误信息
    """
    
    __tablename__ = "agent_metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    agent_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # 'quick'/'deep'/'deep_research'
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_calls: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # 关系定义
    user: Mapped["User"] = relationship("User", back_populates="agent_metrics")
    
    def __repr__(self) -> str:
        return f"<AgentMetric(id={self.id}, user_id={self.user_id}, mode={self.agent_mode}, success={self.success})>"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_mode": self.agent_mode,
            "total_steps": self.total_steps,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "tool_calls": self.tool_calls,
            "llm_calls": self.llm_calls,
            "cache_hits": self.cache_hits,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
