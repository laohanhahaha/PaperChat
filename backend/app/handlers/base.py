"""Handler 抽象基类

定义 WebSocket 聊天处理器的公共 6 步流程：
  1. 获取/创建会话
  2. 保存用户消息
  3. 加载历史记录
  4. 执行业务逻辑（子类实现 _process）
  5. 保存 assistant 消息
  6. 发送 done 信号

子类只需实现 `_process()` 方法。
"""
import json
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.services.chat.session_service import get_or_create_session, auto_title
from app.services.chat.message_service import save_message, load_chat_history
from app.services.core.event_bus import event_bus, Event, EventTypes

logger = logging.getLogger(__name__)


class ChatHandlerBase(ABC):
    """聊天处理器抽象基类

    公共骨架流程（Template Method 模式）：
    handle() 方法负责会话管理、消息持久化和 done 信号；
    子类通过 _process() 实现具体的业务逻辑，并 yield 文本块。

    Attributes:
        channel: WebSocket 消息类型标识，如 "rag_chat" / "cross_doc_chat"
        chunk_type: 流式内容消息的 type 字段，如 "rag_chat_chunk"
    """

    channel: str = ""       # 子类须声明，用于 done 信号的 channel 字段
    chunk_type: str = ""    # 子类须声明，用于流式块的 type 字段

    async def handle(
        self,
        websocket,
        db,
        state,
        message: str,
        user_id: int,
        session_id: Any = None,
        paper_id: Any = None,
        task_key: str = "chat",
        **kwargs
    ) -> None:
        """执行公共 6 步流程

        Args:
            websocket: WebSocket 连接
            db: 数据库会话
            state: 当前连接状态对象
            message: 用户消息文本
            user_id: 当前用户 ID
            session_id: 会话 ID（可为 None，自动创建）
            paper_id: 关联论文 ID（可为 None）
            task_key: 任务 key，用于 state.running_tasks 管理
            **kwargs: 传递给 _process() 的额外参数
        """
        state.current_user_id = user_id
        if paper_id is not None:
            state.current_paper_id = paper_id

        try:
            # Step 1: 获取或创建会话
            session = await get_or_create_session(db, session_id, user_id, paper_id)
            state.current_session_id = session.id

            # Step 2: 保存用户消息（子类可通过 _user_message_meta 提供附加元数据）
            user_meta = self._user_message_meta(**kwargs)
            await save_message(db, session.id, "user", message, user_meta)

            # Step 3: 加载会话历史
            history = await load_chat_history(db, session.id, limit=10)

            # Step 4: 执行业务逻辑（子类实现）
            full_response, sources = await self._process(
                websocket=websocket,
                db=db,
                message=message,
                history=history,
                session=session,
                paper_id=paper_id,
                user_id=user_id,
                **kwargs
            )

            # Step 5: 保存 assistant 消息
            await save_message(db, session.id, "assistant", full_response, sources or [])

            # 更新会话标题
            await auto_title(db, session, message)

            # 发布会话更新事件，触发 L3 后台预压缩
            asyncio.create_task(event_bus.publish(Event(
                type=EventTypes.SESSION_UPDATED,
                data={"session_id": session.id, "user_id": user_id}
            )))

            # Step 6: 发送 done 信号
            await websocket.send_text(json.dumps({
                "type": "done",
                "channel": self.channel,
                "session_id": session.id
            }))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 处理失败: {e}", exc_info=True)
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"处理失败: {str(e)}"
            }))
        finally:
            state.running_tasks.pop(task_key, None)

    def _user_message_meta(self, **kwargs) -> Any:
        """返回保存用户消息时附加的 meta 数据（默认 None）

        子类可重写以提供 paper_ids 等信息。
        """
        return None

    @abstractmethod
    async def _process(
        self,
        websocket,
        db,
        message: str,
        history,
        session,
        paper_id: Any,
        user_id: int,
        **kwargs
    ):
        """执行核心业务逻辑

        Args:
            websocket: WebSocket 连接
            db: 数据库会话
            message: 用户消息
            history: 历史记录（ChatMessageHistory）
            session: 当前会话对象
            paper_id: 论文 ID（可为 None）
            user_id: 用户 ID
            **kwargs: 额外参数（如 paper_ids / enable_search）

        Returns:
            Tuple[str, list]: (full_response 完整回答文本, sources 引用来源列表)
        """
        raise NotImplementedError
