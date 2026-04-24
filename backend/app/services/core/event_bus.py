"""事件总线服务

提供发布-订阅模式的事件系统，支持同步和异步处理器
"""
import asyncio
import logging
from typing import Callable, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件数据类"""
    type: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventBus:
    """事件总线

    支持：
    - 同步和异步处理器
    - 事件订阅/取消订阅
    - 异步发布，处理器异常不中断其他处理器
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件

        Args:
            event_type: 事件类型名称
            handler: 事件处理函数，可以是同步或异步函数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Handler '{handler.__name__}' subscribed to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅事件

        Args:
            event_type: 事件类型名称
            handler: 要移除的事件处理函数
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.info(f"Handler '{handler.__name__}' unsubscribed from '{event_type}'")
            except ValueError:
                logger.warning(
                    f"Handler '{handler.__name__}' not found for event '{event_type}'"
                )

    async def publish(self, event: Event) -> None:
        """发布事件

        依次调用所有订阅了该事件类型的处理器。
        单个处理器异常不会中断其他处理器的执行。

        Args:
            event: 要发布的事件对象
        """
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.debug(f"No handlers for event '{event.type}'")
            return

        logger.debug(
            f"Publishing event '{event.type}' to {len(handlers)} handler(s)"
        )
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler '{handler.__name__}' error for "
                    f"'{event.type}': {e}",
                    exc_info=True,
                )

    def has_handlers(self, event_type: str) -> bool:
        """检查某个事件类型是否有处理器"""
        return bool(self._handlers.get(event_type))

    def get_handler_count(self, event_type: str) -> int:
        """获取某个事件类型的处理器数量"""
        return len(self._handlers.get(event_type, []))

    def clear(self) -> None:
        """清空所有订阅"""
        self._handlers.clear()
        logger.info("EventBus cleared all handlers")


# 全局实例
event_bus = EventBus()


class EventTypes:
    """事件类型常量

    集中管理所有事件类型名称，避免硬编码字符串
    """
    PAPER_UPLOADED = "paper.uploaded"
    PAPER_DELETED = "paper.deleted"
    ANALYSIS_COMPLETED = "analysis.completed"
    SESSION_CREATED = "session.created"
    INDEX_REBUILD_STARTED = "index.rebuild_started"
    INDEX_REBUILD_COMPLETED = "index.rebuild_completed"
    SETTINGS_CHANGED = "settings.changed"
    INDEX_REBUILT = "index.rebuilt"
    SESSION_UPDATED = "session.updated"  # 会话消息更新，触发后台预压缩
