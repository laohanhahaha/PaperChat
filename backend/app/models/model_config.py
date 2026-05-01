"""模型配置数据模型

存储用户自定义的 LLM 模型配置，支持多模型管理和切换
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelConfig(Base):
    """模型配置表模型

    存储用户添加的自定义 LLM 模型配置，每个用户可有多个模型，
    其中最多一个为激活状态（is_active=True）
    """

    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, nullable=False)
    api_base_url: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<ModelConfig(id={self.id}, user_id={self.user_id}, model_name={self.model_name}, is_active={self.is_active})>"
