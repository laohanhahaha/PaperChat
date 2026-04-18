"""功能开关服务

提供功能开关的查询、设置和列表功能，带内存缓存（TTL 60s，线程安全）
"""
import logging
import threading
import time
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.feature_flag import FeatureFlag

logger = logging.getLogger(__name__)


class _CacheEntry:
    """缓存条目"""
    __slots__ = ("value", "expire_at")

    def __init__(self, value: bool, expire_at: float):
        self.value = value
        self.expire_at = expire_at


class FeatureFlagService:
    """功能开关服务

    - 查询 flag 时优先走内存缓存，减少数据库查询
    - 缓存 TTL 为 60 秒
    - 使用 threading.Lock 保证线程安全
    """

    CACHE_TTL = 60  # 秒

    def __init__(self):
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def _is_cache_valid(self, name: str) -> bool:
        """检查缓存条目是否仍然有效"""
        entry = self._cache.get(name)
        if entry is None:
            return False
        return time.monotonic() < entry.expire_at

    def _set_cache(self, name: str, value: bool) -> None:
        """写入缓存"""
        with self._lock:
            self._cache[name] = _CacheEntry(
                value=value,
                expire_at=time.monotonic() + self.CACHE_TTL,
            )

    def _invalidate_cache(self, name: str) -> None:
        """使指定 key 的缓存失效"""
        with self._lock:
            self._cache.pop(name, None)

    def _invalidate_all(self) -> None:
        """清空全部缓存"""
        with self._lock:
            self._cache.clear()

    async def get_flag(self, db: AsyncSession, name: str) -> bool:
        """查询功能开关是否启用

        不存在时返回 False
        """
        # 先查缓存
        if self._is_cache_valid(name):
            entry = self._cache.get(name)
            return entry.value

        # 查数据库
        stmt = select(FeatureFlag).where(FeatureFlag.name == name)
        result = await db.execute(stmt)
        flag = result.scalar_one_or_none()

        value = flag.enabled if flag else False
        self._set_cache(name, value)
        return value

    async def set_flag(
        self,
        db: AsyncSession,
        name: str,
        enabled: bool,
        description: str = "",
    ) -> FeatureFlag:
        """创建或更新功能开关

        如果 name 已存在则更新 enabled 和 description，否则新建
        """
        stmt = select(FeatureFlag).where(FeatureFlag.name == name)
        result = await db.execute(stmt)
        flag = result.scalar_one_or_none()

        if flag:
            flag.enabled = enabled
            if description:
                flag.description = description
            logger.info(f"Feature flag '{name}' updated: enabled={enabled}")
        else:
            flag = FeatureFlag(
                name=name,
                enabled=enabled,
                description=description,
            )
            db.add(flag)
            logger.info(f"Feature flag '{name}' created: enabled={enabled}")

        await db.flush()

        # 更新缓存
        self._set_cache(name, enabled)
        return flag

    async def list_flags(self, db: AsyncSession) -> List[FeatureFlag]:
        """列出所有功能开关"""
        stmt = select(FeatureFlag).order_by(FeatureFlag.id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_flag(self, db: AsyncSession, name: str) -> bool:
        """删除功能开关

        返回是否删除成功（flag 是否存在）
        """
        stmt = select(FeatureFlag).where(FeatureFlag.name == name)
        result = await db.execute(stmt)
        flag = result.scalar_one_or_none()

        if flag:
            await db.delete(flag)
            await db.flush()
            self._invalidate_cache(name)
            logger.info(f"Feature flag '{name}' deleted")
            return True
        return False


# 全局实例
feature_flag_service = FeatureFlagService()
