"""用户设置模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSettings(Base):
    """用户设置表模型
    
    存储用户的个性化配置，以 JSON 格式存储所有设置项
    """
    
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, unique=True)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id})>"
