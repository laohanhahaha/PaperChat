"""费用与预算数据模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageRecord(Base):
    """LLM 调用使用记录表"""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(100), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    session_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<UsageRecord(id={self.id}, model={self.model}, cost={self.cost:.6f})>"


class BudgetConfig(Base):
    """预算配置表（单行配置）"""

    __tablename__ = "budget_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    monthly_limit: Mapped[float] = mapped_column(Float, default=10.0)  # 默认 10 美元/月
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<BudgetConfig(monthly_limit={self.monthly_limit})>"
