"""自定义子智能体模型

存储用户创建和系统预置的子智能体配置，供多 Agent 研究模式动态使用。
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CustomSubAgent(Base):
    __tablename__ = "custom_subagents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tool_subset: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array, null = 不限制
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # 图标标识
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关系
    user = relationship("User", backref="custom_subagents")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tool_subset": json.loads(self.tool_subset) if self.tool_subset else None,
            "icon": self.icon,
            "is_preset": self.is_preset,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
