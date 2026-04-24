"""KeyRotationService — API Key 自动轮换服务

后台 asyncio.Task 定期检查所有已配置 Key 的年龄，
在到期前通过 WebSocket 广播提醒事件。

性能说明：
    - 后台检查默认每小时执行一次（check_interval_seconds=3600），
      仅遍历内存中的 Key 元数据 + 时间比较，CPU 开销可忽略
    - WebSocket 广播为非阻塞 fire-and-forget，不影响主循环
    - Key 元数据存储在内存 dict 中，读写均为 O(1)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.security.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class KeyMetadata:
    """单个 Key 的元数据"""

    def __init__(
        self,
        service: str,
        created_at: Optional[datetime] = None,
        last_rotated_at: Optional[datetime] = None,
    ):
        self.service = service
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_rotated_at = last_rotated_at

    @property
    def expires_at(self) -> datetime:
        """计算过期时间（基于 created_at + rotation_interval_days）"""
        from app.services.security.key_rotation import get_key_rotation_service

        svc = get_key_rotation_service()
        return self.created_at + timedelta(days=svc.rotation_interval_days)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "created_at": self.created_at.isoformat(),
            "last_rotated_at": self.last_rotated_at.isoformat() if self.last_rotated_at else None,
            "expires_at": self.expires_at.isoformat(),
        }


class KeyRotationService:
    """API Key 自动轮换后台服务

    功能：
      1. 定期检查所有已配置 Key 的年龄
      2. 到期前 7 天 / 1 天通过 WebSocket 广播 key_expiry_warning 事件
      3. 提供 get_key_status / check_all_keys 查询接口
      4. start() / stop() 生命周期管理

    配置项：
      - rotation_interval_days: Key 轮换周期（默认 90 天）
      - check_interval_seconds: 后台检查间隔（默认 3600 秒 / 1 小时）
      - warning_days_before: 提前多少天发出到期警告列表（默认 [7, 1]）
    """

    def __init__(
        self,
        rotation_interval_days: int = 90,
        check_interval_seconds: int = 3600,
        warning_days_before: Optional[List[int]] = None,
        metadata_store_path: Optional[str] = None,
    ):
        self.rotation_interval_days = rotation_interval_days
        self.check_interval_seconds = check_interval_seconds
        self.warning_days_before = warning_days_before or [7, 1]

        # Key 元数据存储：service_name → KeyMetadata
        self._key_metadata: Dict[str, KeyMetadata] = {}

        # 后台任务引用
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # WebSocket 广播函数引用（由 lifespan 注入）
        self._ws_broadcast = None

        # 元数据持久化路径（可选，默认不持久化）
        self._metadata_store_path = metadata_store_path or os.environ.get(
            "KEY_METADATA_PATH"
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动后台轮换检查任务"""
        if self._running:
            logger.warning("KeyRotationService 已在运行，跳过重复启动")
            return

        self._running = True
        # 加载持久化的元数据
        self._load_metadata()
        # 启动后台循环
        self._task = asyncio.create_task(self._check_loop())
        logger.info(
            f"KeyRotationService 已启动（检查间隔={self.check_interval_seconds}s，"
            f"轮换周期={self.rotation_interval_days}天）"
        )

    async def stop(self) -> None:
        """停止后台轮换检查任务"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 持久化元数据
        self._save_metadata()
        logger.info("KeyRotationService 已停止")

    def set_ws_broadcast(self, broadcast_fn) -> None:
        """注入 WebSocket 广播函数

        Args:
            broadcast_fn: async function(event_type: str, data: dict)
        """
        self._ws_broadcast = broadcast_fn

    # ------------------------------------------------------------------
    # Key 元数据管理
    # ------------------------------------------------------------------

    def register_key(self, service: str, created_at: Optional[datetime] = None) -> None:
        """注册一个 Key 的元数据

        如果该 service 已注册，不覆盖（除非强制）。

        Args:
            service: 服务名称
            created_at: Key 创建时间，默认当前时间
        """
        if service not in self._key_metadata:
            self._key_metadata[service] = KeyMetadata(
                service=service, created_at=created_at
            )
            logger.debug(f"Key 元数据已注册: {service}")

    def update_key_rotation(self, service: str) -> None:
        """记录 Key 已轮换，更新 last_rotated_at 并重置 created_at

        Args:
            service: 服务名称
        """
        now = datetime.now(timezone.utc)
        if service in self._key_metadata:
            meta = self._key_metadata[service]
            meta.last_rotated_at = now
            meta.created_at = now  # 轮换后重新计时
            logger.info(f"Key 轮换时间已更新: {service}")
        else:
            self._key_metadata[service] = KeyMetadata(service=service, created_at=now)
            logger.info(f"Key 元数据已创建（轮换触发）: {service}")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def get_key_status(self, service: str) -> Dict[str, Any]:
        """获取单个 Key 的轮换状态

        Args:
            service: 服务名称

        Returns:
            {
                "service": str,
                "status": "valid" | "expiring_soon" | "expired",
                "created_at": str | None,
                "expires_at": str | None,
                "days_until_expiry": int | None,
                "last_rotated_at": str | None,
            }
        """
        if service not in self._key_metadata:
            return {
                "service": service,
                "status": "valid",
                "created_at": None,
                "expires_at": None,
                "days_until_expiry": None,
                "last_rotated_at": None,
            }

        meta = self._key_metadata[service]
        now = datetime.now(timezone.utc)
        expires_at = meta.expires_at
        days_left = (expires_at - now).days

        if days_left <= 0:
            status = "expired"
        elif days_left <= min(self.warning_days_before):
            status = "expiring_soon"
        else:
            status = "valid"

        return {
            "service": service,
            "status": status,
            "created_at": meta.created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "days_until_expiry": max(days_left, 0),
            "last_rotated_at": (
                meta.last_rotated_at.isoformat() if meta.last_rotated_at else None
            ),
        }

    def check_all_keys(self) -> List[Dict[str, Any]]:
        """批量检查所有已配置 Key 的轮换状态

        Returns:
            所有 Key 的状态列表
        """
        return [self.get_key_status(svc) for svc in self._key_metadata]

    # ------------------------------------------------------------------
    # 后台检查循环
    # ------------------------------------------------------------------

    async def _check_loop(self) -> None:
        """后台定时检查 Key 年龄并广播到期警告

        性能：每小时一次遍历内存 dict（O(n)，n = Key 数量，通常 < 10），
              仅做时间比较 + 可选 WebSocket 广播，CPU 开销可忽略。
        """
        while self._running:
            try:
                await self._perform_check()
            except Exception as e:
                logger.error(f"Key 轮换检查异常（非阻断）: {e}")

            # 等待下次检查
            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _perform_check(self) -> None:
        """执行一次完整的 Key 年龄检查"""
        now = datetime.now(timezone.utc)
        warnings = []

        for service, meta in self._key_metadata.items():
            expires_at = meta.expires_at
            days_left = (expires_at - now).days

            # 检查是否需要发出警告
            for warn_day in self.warning_days_before:
                if days_left == warn_day or days_left <= 0:
                    status = "expired" if days_left <= 0 else "expiring_soon"
                    warning = {
                        "service": service,
                        "status": status,
                        "days_until_expiry": max(days_left, 0),
                        "expires_at": expires_at.isoformat(),
                    }
                    warnings.append(warning)
                    break  # 只发一次警告

        if warnings:
            logger.warning(f"Key 到期警告: {json.dumps(warnings, ensure_ascii=False)}")
            await self._broadcast_expiry_warning(warnings)

    async def _broadcast_expiry_warning(self, warnings: List[Dict[str, Any]]) -> None:
        """通过 WebSocket 广播 key_expiry_warning 事件

        性能：fire-and-forget 模式，非阻塞，不影响主循环。
        """
        if self._ws_broadcast:
            try:
                await self._ws_broadcast(
                    "key_expiry_warning",
                    {
                        "type": "key_expiry_warning",
                        "warnings": warnings,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"WebSocket 广播 Key 到期警告失败: {e}")
        else:
            logger.debug("WebSocket 广播函数未设置，跳过到期警告广播")

    # ------------------------------------------------------------------
    # 元数据持久化（可选）
    # ------------------------------------------------------------------

    def _load_metadata(self) -> None:
        """从文件加载元数据（如果路径已配置）"""
        if not self._metadata_store_path:
            return
        try:
            if os.path.exists(self._metadata_store_path):
                with open(self._metadata_store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    created = datetime.fromisoformat(item["created_at"])
                    last_rotated = (
                        datetime.fromisoformat(item["last_rotated_at"])
                        if item.get("last_rotated_at")
                        else None
                    )
                    meta = KeyMetadata(
                        service=item["service"],
                        created_at=created,
                        last_rotated_at=last_rotated,
                    )
                    self._key_metadata[item["service"]] = meta
                logger.info(
                    f"已加载 {len(data)} 条 Key 元数据: {self._metadata_store_path}"
                )
        except Exception as e:
            logger.error(f"加载 Key 元数据失败: {e}")

    def _save_metadata(self) -> None:
        """持久化元数据到文件（如果路径已配置）"""
        if not self._metadata_store_path:
            return
        try:
            data = [meta.to_dict() for meta in self._key_metadata.values()]
            with open(self._metadata_store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(
                f"已保存 {len(data)} 条 Key 元数据: {self._metadata_store_path}"
            )
        except Exception as e:
            logger.error(f"保存 Key 元数据失败: {e}")


# 全局单例
_key_rotation_service: Optional["KeyRotationService"] = None


def get_key_rotation_service() -> "KeyRotationService":
    """获取全局 KeyRotationService 单例"""
    global _key_rotation_service
    if _key_rotation_service is None:
        _key_rotation_service = KeyRotationService()
    return _key_rotation_service


def set_key_rotation_service(service: "KeyRotationService") -> None:
    """设置全局 KeyRotationService 单例（供 lifespan 初始化时使用）"""
    global _key_rotation_service
    _key_rotation_service = service
