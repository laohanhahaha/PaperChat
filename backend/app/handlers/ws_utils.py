"""WebSocket 通信工具

提供 WebSocket 消息发送的缓冲和工具函数
"""
import json
import asyncio
import time


class ChunkBuffer:
    """合并高频 WebSocket chunk 消息，减少发送次数

    性能影响说明：
    - 默认 50ms 的合并间隔对用户体验影响极小（人眼感知延迟约 100ms）
    - 可显著减少 WebSocket 消息数量（通常减少 80-90%）
    - 降低前端 React 重渲染频率，提升整体流畅度
    """
    def __init__(self, websocket, interval_ms=50):
        self.websocket = websocket
        self.interval = interval_ms / 1000  # 转换为秒
        self.buffer = ""
        self.last_flush = time.time()
        self._lock = asyncio.Lock()
        self._closed = False

    async def add(self, chunk: str, msg_type: str = "stream"):
        """添加 chunk 到缓冲区，如果达到间隔时间则自动 flush

        Args:
            chunk: 要发送的文本内容
            msg_type: 消息类型，默认 "stream"，也可用于 "chat_chunk", "rag_chat_chunk" 等
        """
        if self._closed:
            return

        async with self._lock:
            self.buffer += chunk
            now = time.time()
            if now - self.last_flush >= self.interval:
                await self._flush(msg_type)

    async def flush(self, msg_type: str = "stream"):
        """强制刷新缓冲区，发送所有累积的内容"""
        if self._closed:
            return

        async with self._lock:
            await self._flush(msg_type)

    async def _flush(self, msg_type: str):
        """内部刷新方法（需在持有锁的情况下调用）"""
        if self.buffer:
            await self.websocket.send_text(json.dumps({
                "type": msg_type,
                "content": self.buffer
            }))
            self.buffer = ""
            self.last_flush = time.time()

    def close(self):
        """关闭 buffer，不再接受新内容"""
        self._closed = True


async def send_chunk_with_buffer(websocket, chunk_buffer, chunk: str, msg_type: str = "stream"):
    """使用 buffer 发送 chunk 的辅助函数

    如果 chunk_buffer 为 None，则直接发送；否则使用 buffer。
    这样允许 handler 选择是否使用缓冲功能。
    """
    if chunk_buffer is not None:
        await chunk_buffer.add(chunk, msg_type)
    else:
        await websocket.send_text(json.dumps({
            "type": msg_type,
            "content": chunk
        }))
