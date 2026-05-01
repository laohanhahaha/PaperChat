"""MCP 协议客户端

MCPClient — 负责与单个 MCP Server 通信，支持：
  - stdio 传输：子进程 stdin/stdout JSON-RPC 2.0
  - sse 传输：HTTP SSE 双向通道
  - streamable_http 传输：HTTP POST/响应
  - 自动重连（指数退避，最多 3 次）
  - 工具列表缓存
  - 完整健康检查
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from app.mcp_services.config import MCPServerConfig, TransportType
from app.mcp_services.exceptions import (
    MCPConnectionError,
    MCPTimeoutError,
    MCPToolError,
)
from app.mcp_services.transport import (
    SseTransport,
    StdioTransport,
    StreamableHttpTransport,
)

logger = logging.getLogger(__name__)

# 自动重连参数
_MAX_RECONNECT_ATTEMPTS = 3
_RECONNECT_BASE_DELAY = 1.0   # 指数退避基数（秒）

_TransportUnion = Union[StdioTransport, SseTransport, StreamableHttpTransport]


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------

@dataclass
class MCPToolSchema:
    """MCP 工具 Schema 表示"""

    name: str
    description: str
    input_schema: dict = field(default_factory=dict)   # JSON Schema
    server_name: str = ""                               # 所属 Server 名称


# ---------------------------------------------------------------------------
# MCPClient
# ---------------------------------------------------------------------------

class MCPClient:
    """MCP 协议客户端 — 负责与单个 MCP Server 通信"""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._connected: bool = False
        self._transport: Optional[_TransportUnion] = None
        self._tools_cache: Optional[List[MCPToolSchema]] = None
        # 重连锁：防止并发触发多次重连
        self._reconnect_lock = asyncio.Lock()
        # 保留向后兼容占位属性
        self._process: Optional[Any] = None

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        if self._transport is None:
            return False
        return self._transport.is_alive

    # ------------------------------------------------------------------
    # 传输层构建
    # ------------------------------------------------------------------

    def _build_transport(self) -> _TransportUnion:
        """根据配置创建对应传输层实例"""
        transport_type = self.config.transport
        timeout = self.config.timeout or 30.0

        if transport_type == TransportType.STDIO:
            if not self.config.command:
                raise MCPConnectionError(
                    f"[{self.config.name}] stdio 传输需要配置 command"
                )
            return StdioTransport(
                command=self.config.command,
                args=self.config.args or [],
                env=self.config.env or {},
                timeout=timeout,
            )

        elif transport_type == TransportType.SSE:
            if not self.config.url:
                raise MCPConnectionError(
                    f"[{self.config.name}] SSE 传输需要配置 url"
                )
            return SseTransport(
                url=self.config.url,
                api_key=self.config.api_key,
                timeout=timeout,
            )

        elif transport_type == TransportType.STREAMABLE_HTTP:
            if not self.config.url:
                raise MCPConnectionError(
                    f"[{self.config.name}] HTTP 传输需要配置 url"
                )
            return StreamableHttpTransport(
                url=self.config.url,
                api_key=self.config.api_key,
                timeout=timeout,
            )

        else:
            raise MCPConnectionError(
                f"[{self.config.name}] 不支持的传输类型: {transport_type}"
            )

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """建立与 MCP Server 的连接"""
        if self._connected and self.is_connected:
            logger.debug("[MCPClient] %s 已连接，跳过重复连接", self.config.name)
            return

        logger.info(
            "[MCPClient] 正在连接 MCP Server: %s (transport=%s)",
            self.config.name,
            self.config.transport,
        )

        transport = self._build_transport()
        try:
            await transport.connect()
        except Exception as exc:
            raise MCPConnectionError(
                f"[{self.config.name}] 启动失败: {type(exc).__name__}: {exc}"
            ) from exc

        self._transport = transport
        # stdio 兼容占位属性
        if isinstance(transport, StdioTransport):
            self._process = transport._process

        # 发送 initialize 握手
        try:
            await self._initialize()
        except Exception as exc:
            logger.error(
                "[MCPClient] %s initialize 握手失败: %s，标记为连接失败",
                self.config.name,
                exc,
            )
            # initialize 失败，断开传输层，不标记为已连接
            try:
                await transport.close()
            except Exception:
                pass
            self._transport = None
            self._process = None
            raise MCPConnectionError(
                f"[{self.config.name}] initialize 握手失败: {exc}"
            ) from exc

        self._connected = True
        self._tools_cache = None   # 重置缓存
        logger.info("[MCPClient] %s 连接成功", self.config.name)

    async def disconnect(self) -> None:
        """断开连接"""
        if not self._connected and self._transport is None:
            return
        logger.info("[MCPClient] 断开 MCP Server: %s", self.config.name)
        if self._transport is not None:
            try:
                await self._transport.close()
            except Exception as exc:
                logger.debug("[MCPClient] 关闭传输层时出现异常（可忽略）: %s", exc)
            self._transport = None
        self._process = None
        self._connected = False
        self._tools_cache = None

    async def _initialize(self) -> None:
        """发送 MCP initialize 请求，获取 server capabilities"""
        assert self._transport is not None
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
            "clientInfo": {"name": "chatpdf-mcp-client", "version": "1.0.0"},
        }
        try:
            resp = await self._transport.send_request("initialize", params)
            caps = resp.get("result", {}).get("capabilities", {})
            logger.debug(
                "[MCPClient] %s initialize OK，服务器能力: %s",
                self.config.name,
                list(caps.keys()),
            )
            # 发送 initialized 通知（无需等待响应）
            await self._send_notification("notifications/initialized")
        except Exception as exc:
            logger.warning("[MCPClient] %s initialize 异常: %s", self.config.name, exc)
            raise

    async def _send_notification(self, method: str, params: Any = None) -> None:
        """发送 JSON-RPC 通知（无 id，无需响应）"""
        if self._transport is None:
            return
        # 通知使用独立路径绕过请求-响应锁，直接写 stdin（仅 stdio）
        if isinstance(self._transport, StdioTransport):
            import json as _json
            payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
            if (
                self._transport._process is not None
                and self._transport._process.stdin is not None
            ):
                data = (_json.dumps(payload) + "\n").encode("utf-8")
                self._transport._process.stdin.write(data)
                try:
                    await self._transport._process.stdin.drain()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 内部 JSON-RPC 发送（带自动重连）
    # ------------------------------------------------------------------

    async def _send_jsonrpc(self, method: str, params: Any = None) -> dict:
        """发送 JSON-RPC 请求，连接断开时自动尝试重连"""
        if self._transport is None or not self.is_connected:
            await self._try_reconnect()

        assert self._transport is not None
        try:
            return await self._transport.send_request(method, params)
        except (ConnectionError, BrokenPipeError, OSError) as exc:
            logger.warning(
                "[MCPClient] %s 通信错误: %s，尝试自动重连", self.config.name, exc
            )
            await self._try_reconnect()
            return await self._transport.send_request(method, params)

    async def _try_reconnect(self) -> None:
        """自动重连（指数退避，最多 _MAX_RECONNECT_ATTEMPTS 次）"""
        async with self._reconnect_lock:
            if self.is_connected:
                return   # 已由其他协程重连成功

            logger.info("[MCPClient] %s 开始自动重连...", self.config.name)
            for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
                try:
                    # 先断开旧连接
                    if self._transport is not None:
                        try:
                            await self._transport.close()
                        except Exception:
                            pass
                        self._transport = None
                        self._connected = False

                    await self.connect()
                    logger.info(
                        "[MCPClient] %s 重连成功（第 %d 次）",
                        self.config.name,
                        attempt,
                    )
                    return
                except Exception as exc:
                    delay = _RECONNECT_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "[MCPClient] %s 第 %d 次重连失败: %s，%.1f 秒后重试",
                        self.config.name,
                        attempt,
                        exc,
                        delay,
                    )
                    if attempt < _MAX_RECONNECT_ATTEMPTS:
                        await asyncio.sleep(delay)

            raise MCPConnectionError(
                f"[{self.config.name}] 自动重连失败（已尝试 {_MAX_RECONNECT_ATTEMPTS} 次）"
            )

    # ------------------------------------------------------------------
    # 工具操作
    # ------------------------------------------------------------------

    async def list_tools(self) -> List[MCPToolSchema]:
        """获取 Server 提供的工具列表（带缓存）"""
        if not self._connected:
            raise MCPConnectionError(f"MCPClient [{self.config.name}] 未连接")

        if self._tools_cache is not None:
            logger.debug("[MCPClient] %s list_tools 命中缓存", self.config.name)
            return self._tools_cache

        logger.debug("[MCPClient] %s 发送 tools/list 请求", self.config.name)
        try:
            resp = await self._send_jsonrpc("tools/list")
        except Exception as exc:
            raise MCPToolError(
                f"[{self.config.name}] tools/list 请求失败: {exc}"
            ) from exc

        raw_tools = resp.get("result", {}).get("tools", [])
        schemas: List[MCPToolSchema] = []
        for t in raw_tools:
            schemas.append(
                MCPToolSchema(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server_name=self.config.name,
                )
            )

        self._tools_cache = schemas
        logger.info(
            "[MCPClient] %s list_tools 返回 %d 个工具", self.config.name, len(schemas)
        )
        return schemas

    def invalidate_tools_cache(self) -> None:
        """清除工具列表缓存，下次 list_tools() 重新请求"""
        self._tools_cache = None

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
        """实际发送 tools/call JSON-RPC 2.0 请求"""
        logger.debug(
            "[MCPClient] %s 调用工具 %s，参数=%s",
            self.config.name,
            tool_name,
            arguments,
        )

        params = {"name": tool_name, "arguments": arguments}

        try:
            resp = await self._send_jsonrpc("tools/call", params)
        except MCPConnectionError:
            raise
        except Exception as exc:
            raise MCPToolError(
                f"[{self.config.name}] 工具 {tool_name} 请求失败: {exc}"
            ) from exc

        result = resp.get("result", {})

        # MCP 规范：content 列表 + isError 标志
        is_error = result.get("isError", False)
        content = result.get("content", [])

        if is_error:
            error_text = _extract_text_content(content) or str(result)
            raise MCPToolError(
                f"[{self.config.name}] 工具 {tool_name} 返回错误: {error_text}"
            )

        # 返回纯文本内容（多个 content 块合并）或完整 result
        text = _extract_text_content(content)
        if text is not None:
            return text

        return result

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """健康检查：验证连接存活"""
        if not self._connected:
            return False

        # stdio：检查子进程存活
        if isinstance(self._transport, StdioTransport):
            alive = self._transport.is_alive
            if not alive:
                logger.warning(
                    "[MCPClient] %s health_check: 子进程已退出", self.config.name
                )
                self._connected = False
                return False

        # 发送 ping 请求
        try:
            await self._send_jsonrpc("ping")
            logger.debug("[MCPClient] %s health_check OK", self.config.name)
            return True
        except Exception as exc:
            logger.warning(
                "[MCPClient] %s health_check ping 失败: %s", self.config.name, exc
            )
            # 连接失效，标记断开
            self._connected = False
            return False


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _extract_text_content(content: list) -> Optional[str]:
    """从 MCP content 列表中提取纯文本，无文本则返回 None"""
    if not content:
        return None
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    if parts:
        return "\n".join(parts)
    return None
