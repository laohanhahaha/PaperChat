# -*- coding: utf-8 -*-
"""MCP 客户端单元测试

覆盖：
- MCPClient.connect() 连接成功 / 失败流程（mock transport）
- MCPClient.disconnect() 断开连接后状态重置
- MCPClient.list_tools() 缓存机制（首次请求 + 命中缓存）
- MCPClient.call_tool() JSON-RPC 请求格式
- MCPClient.is_connected 属性
- MCPClient._try_reconnect() 自动重连（最终失败抛出异常）
- MCPClient.invalidate_tools_cache()
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.mcp_services.client import MCPClient, MCPToolSchema
from app.mcp_services.config import MCPServerConfig, TransportType
from app.mcp_services.exceptions import MCPConnectionError, MCPToolError


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sse_config(name: str = "test-server") -> MCPServerConfig:
    return MCPServerConfig(
        name=name,
        transport=TransportType.SSE,
        url="http://localhost:9999/sse",
        timeout=5.0,
        max_retries=1,
    )


def _make_transport_mock(is_alive: bool = True) -> MagicMock:
    """返回模拟 transport，is_alive 属性可控"""
    transport = MagicMock()
    type(transport).is_alive = PropertyMock(return_value=is_alive)
    transport.connect = AsyncMock()
    transport.close = AsyncMock()
    transport.send_request = AsyncMock()
    return transport


# ─────────────────────────────────────────────────────────────────────────────
# is_connected 属性
# ─────────────────────────────────────────────────────────────────────────────

class TestIsConnected:
    def test_not_connected_by_default(self):
        client = MCPClient(_sse_config())
        assert client.is_connected is False

    def test_connected_false_when_transport_none(self):
        client = MCPClient(_sse_config())
        client._connected = True
        client._transport = None
        assert client.is_connected is False

    def test_connected_true_when_transport_alive(self):
        client = MCPClient(_sse_config())
        client._connected = True
        client._transport = _make_transport_mock(is_alive=True)
        assert client.is_connected is True

    def test_connected_false_when_transport_not_alive(self):
        client = MCPClient(_sse_config())
        client._connected = True
        client._transport = _make_transport_mock(is_alive=False)
        assert client.is_connected is False


# ─────────────────────────────────────────────────────────────────────────────
# connect / disconnect
# ─────────────────────────────────────────────────────────────────────────────

class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(self):
        """connect() 成功后 _connected == True"""
        client = MCPClient(_sse_config())
        mock_transport = _make_transport_mock()
        mock_transport.send_request.return_value = {"result": {"capabilities": {}}}

        with patch.object(client, "_build_transport", return_value=mock_transport):
            await client.connect()

        assert client._connected is True
        mock_transport.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_skips_if_already_connected(self):
        """已连接时 connect() 不重复连接"""
        client = MCPClient(_sse_config())
        mock_transport = _make_transport_mock(is_alive=True)
        client._connected = True
        client._transport = mock_transport

        with patch.object(client, "_build_transport") as build_mock:
            await client.connect()
            build_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_failure_raises_mcp_connection_error(self):
        """transport.connect() 抛异常时 MCPConnectionError 向上传播"""
        client = MCPClient(_sse_config())
        mock_transport = _make_transport_mock()
        mock_transport.connect.side_effect = ConnectionRefusedError("connection refused")

        with patch.object(client, "_build_transport", return_value=mock_transport):
            with pytest.raises(MCPConnectionError):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_resets_tools_cache(self):
        """connect() 应清空工具缓存"""
        client = MCPClient(_sse_config())
        client._tools_cache = [MCPToolSchema(name="old_tool", description="old")]

        mock_transport = _make_transport_mock()
        mock_transport.send_request.return_value = {"result": {"capabilities": {}}}

        with patch.object(client, "_build_transport", return_value=mock_transport):
            await client.connect()

        assert client._tools_cache is None


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        """disconnect() 后 _connected == False，_transport == None"""
        client = MCPClient(_sse_config())
        mock_transport = _make_transport_mock()
        client._connected = True
        client._transport = mock_transport
        client._tools_cache = []

        await client.disconnect()

        assert client._connected is False
        assert client._transport is None
        assert client._tools_cache is None
        mock_transport.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_no_op_when_not_connected(self):
        """未连接时 disconnect() 不抛异常"""
        client = MCPClient(_sse_config())
        await client.disconnect()  # 不应抛出


# ─────────────────────────────────────────────────────────────────────────────
# list_tools 缓存机制
# ─────────────────────────────────────────────────────────────────────────────

class TestListTools:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self):
        client = MCPClient(_sse_config())
        with pytest.raises(MCPConnectionError):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_returns_tools_from_server(self):
        client = MCPClient(_sse_config())
        client._connected = True

        raw_response = {
            "result": {
                "tools": [
                    {"name": "search", "description": "搜索工具", "inputSchema": {}},
                    {"name": "summarize", "description": "摘要工具", "inputSchema": {}},
                ]
            }
        }

        with patch.object(client, "_send_jsonrpc", new=AsyncMock(return_value=raw_response)):
            tools = await client.list_tools()

        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[1].name == "summarize"

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_second_request(self):
        """第二次 list_tools() 应命中缓存，不再发送请求"""
        client = MCPClient(_sse_config())
        client._connected = True

        raw_response = {"result": {"tools": [{"name": "t1", "description": "", "inputSchema": {}}]}}
        send_mock = AsyncMock(return_value=raw_response)

        with patch.object(client, "_send_jsonrpc", new=send_mock):
            await client.list_tools()
            await client.list_tools()

        # send_jsonrpc 只应被调用一次
        send_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_cache_forces_new_request(self):
        """invalidate_tools_cache() 后 list_tools() 重新请求"""
        client = MCPClient(_sse_config())
        client._connected = True

        raw_response = {"result": {"tools": [{"name": "t1", "description": "", "inputSchema": {}}]}}
        send_mock = AsyncMock(return_value=raw_response)

        with patch.object(client, "_send_jsonrpc", new=send_mock):
            await client.list_tools()
            client.invalidate_tools_cache()
            await client.list_tools()

        assert send_mock.await_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# call_tool
# ─────────────────────────────────────────────────────────────────────────────

class TestCallTool:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self):
        client = MCPClient(_sse_config())
        with pytest.raises(MCPConnectionError):
            await client.call_tool("my_tool", {"arg": "val"})

    @pytest.mark.asyncio
    async def test_returns_tool_result(self):
        client = MCPClient(_sse_config())
        client._connected = True

        tool_response = {"result": {"content": [{"type": "text", "text": "结果"}]}}

        with patch.object(client, "_do_call_tool", new=AsyncMock(return_value=tool_response)):
            result = await client.call_tool("my_tool", {"query": "test"})

        assert result == tool_response


# ─────────────────────────────────────────────────────────────────────────────
# 自动重连
# ─────────────────────────────────────────────────────────────────────────────

class TestTryReconnect:
    @pytest.mark.asyncio
    async def test_reconnect_raises_after_max_attempts(self):
        """所有重连尝试均失败时抛出 MCPConnectionError"""
        client = MCPClient(_sse_config("reconnect-test"))
        # connect() 始终失败
        with patch.object(client, "connect", new=AsyncMock(
            side_effect=MCPConnectionError("连接失败")
        )):
            with patch("asyncio.sleep", new=AsyncMock()):  # 跳过等待
                with pytest.raises(MCPConnectionError, match="自动重连失败"):
                    await client._try_reconnect()

    @pytest.mark.asyncio
    async def test_reconnect_succeeds_on_second_attempt(self):
        """第二次重连成功时不抛异常"""
        client = MCPClient(_sse_config("reconnect-ok"))
        call_count = [0]

        async def flaky_connect():
            call_count[0] += 1
            if call_count[0] < 2:
                raise MCPConnectionError("首次失败")
            client._connected = True

        with patch.object(client, "connect", new=AsyncMock(side_effect=flaky_connect)):
            with patch("asyncio.sleep", new=AsyncMock()):
                await client._try_reconnect()

        assert client._connected is True
