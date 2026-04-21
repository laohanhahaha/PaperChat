from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.mcp_services.config import MCPServerConfig, TransportType
from app.mcp_services.exceptions import (
    MCPConnectionError,
    MCPTimeoutError,
    MCPToolError,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPToolSchema:
    """MCP 工具 Schema 表示"""

    name: str
    description: str
    input_schema: dict = field(default_factory=dict)   # JSON Schema
    server_name: str = ""                               # 所属 Server 名称


class MCPClient:
    """MCP 协议客户端 — 负责与单个 MCP Server 通信"""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._connected: bool = False
        self._process: Optional[Any] = None   # stdio 子进程占位

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # 连接管理（placeholder — 实际 MCP SDK 接入后完善）
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """建立与 MCP Server 的连接（placeholder）"""
        if self._connected:
            logger.debug("[MCPClient] %s 已连接，跳过重复连接", self.config.name)
            return

        logger.info(
            "[MCPClient] 正在连接 MCP Server: %s (transport=%s)",
            self.config.name,
            self.config.transport,
        )
        # TODO: 根据 transport 类型启动子进程或建立 HTTP 连接
        # stdio  → subprocess + stdin/stdout JSON-RPC
        # sse    → httpx AsyncClient + SSE stream
        # http   → httpx AsyncClient + POST /messages
        self._connected = True
        logger.info("[MCPClient] %s 连接成功（placeholder）", self.config.name)

    async def disconnect(self) -> None:
        """断开连接（placeholder）"""
        if not self._connected:
            return
        logger.info("[MCPClient] 断开 MCP Server: %s", self.config.name)
        # TODO: 终止子进程 / 关闭 HTTP 连接
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
        self._connected = False

    # ------------------------------------------------------------------
    # 工具操作
    # ------------------------------------------------------------------

    async def list_tools(self) -> List[MCPToolSchema]:
        """获取 Server 提供的工具列表（placeholder）"""
        if not self._connected:
            raise MCPConnectionError(f"MCPClient [{self.config.name}] 未连接")

        logger.debug("[MCPClient] %s list_tools（placeholder）", self.config.name)
        # TODO: 发送 MCP tools/list 请求并解析响应
        return []

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """调用 MCP 工具，带超时控制 + 指数退避重试"""
        if not self._connected:
            raise MCPConnectionError(f"MCPClient [{self.config.name}] 未连接")

        last_exc: Exception = MCPToolError(f"工具 {tool_name} 调用失败（未执行）")

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._do_call_tool(tool_name, arguments),
                    timeout=self.config.timeout,
                )
                return result

            except asyncio.TimeoutError as exc:
                last_exc = MCPTimeoutError(
                    f"工具 {tool_name} 调用超时（{self.config.timeout}s），"
                    f"第 {attempt + 1} 次"
                )
                logger.warning(str(last_exc))

            except MCPToolError:
                raise

            except Exception as exc:
                last_exc = MCPToolError(
                    f"工具 {tool_name} 调用异常（第 {attempt + 1} 次）: {exc}"
                )
                logger.warning(str(last_exc))

            if attempt < self.config.max_retries:
                wait = 2 ** attempt          # 指数退避: 1s, 2s, …
                logger.info(
                    "[MCPClient] %s 第 %d 次重试，等待 %.1fs",
                    self.config.name,
                    attempt + 2,
                    wait,
                )
                await asyncio.sleep(wait)

        raise last_exc

    async def _do_call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """实际发送 tools/call 请求（placeholder）"""
        # TODO: 构造 JSON-RPC 请求并发送
        logger.debug(
            "[MCPClient] %s 调用工具 %s，参数=%s（placeholder）",
            self.config.name,
            tool_name,
            arguments,
        )
        raise NotImplementedError(
            f"MCPClient._do_call_tool 尚未接入真实 MCP SDK（server={self.config.name}）"
        )

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """健康检查（placeholder）"""
        if not self._connected:
            return False
        try:
            # TODO: 发送 ping 或轻量请求验证连接存活
            logger.debug("[MCPClient] %s health_check OK（placeholder）", self.config.name)
            return True
        except Exception as exc:
            logger.warning("[MCPClient] %s health_check 失败: %s", self.config.name, exc)
            return False
