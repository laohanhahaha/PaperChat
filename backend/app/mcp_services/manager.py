from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.mcp_services.config import MCPConfig, MCPServerConfig
from app.mcp_services.client import MCPClient, MCPToolSchema
from app.mcp_services.exceptions import MCPConnectionError

logger = logging.getLogger(__name__)


class MCPManager:
    """管理所有 MCP Server 的生命周期"""

    def __init__(self, config: Optional[MCPConfig] = None) -> None:
        self._clients: Dict[str, MCPClient] = {}
        self._config: MCPConfig = config or MCPConfig()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动所有已配置且已启用的 Server 连接"""
        logger.info("[MCPManager] 启动，共 %d 个 Server 配置", len(self._config.servers))
        for server_cfg in self._config.servers:
            if not server_cfg.enabled:
                logger.info("[MCPManager] Server %s 已禁用，跳过", server_cfg.name)
                continue
            await self.add_server(server_cfg)

    async def stop(self) -> None:
        """关闭所有连接"""
        logger.info("[MCPManager] 关闭所有 MCP Server 连接（共 %d 个）", len(self._clients))
        names = list(self._clients.keys())
        for name in names:
            await self.remove_server(name)

    # ------------------------------------------------------------------
    # 动态管理
    # ------------------------------------------------------------------

    async def add_server(self, config: MCPServerConfig) -> None:
        """动态添加并连接 Server"""
        if config.name in self._clients:
            logger.warning("[MCPManager] Server %s 已存在，跳过添加", config.name)
            return

        client = MCPClient(config)
        try:
            await client.connect()
            self._clients[config.name] = client
            logger.info("[MCPManager] Server %s 添加成功", config.name)
        except Exception as exc:
            logger.error("[MCPManager] 连接 Server %s 失败: %s", config.name, exc)
            # 不抛出，确保其他 Server 不受影响

    async def remove_server(self, name: str) -> None:
        """断开并移除 Server"""
        client = self._clients.pop(name, None)
        if client is None:
            logger.warning("[MCPManager] Server %s 不存在，无法移除", name)
            return
        try:
            await client.disconnect()
            logger.info("[MCPManager] Server %s 已移除", name)
        except Exception as exc:
            logger.error("[MCPManager] 断开 Server %s 时出错: %s", name, exc)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_client(self, server_name: str) -> Optional[MCPClient]:
        """获取指定 Server 的客户端"""
        return self._clients.get(server_name)

    async def get_all_tools(self) -> List[MCPToolSchema]:
        """并发获取所有已连接 Server 的工具列表"""
        if not self._clients:
            return []

        async def _fetch(name: str, client: MCPClient) -> List[MCPToolSchema]:
            try:
                tools = await client.list_tools()
                # 注入 server_name 便于溯源
                for t in tools:
                    t.server_name = name
                return tools
            except Exception as exc:
                logger.warning("[MCPManager] 获取 %s 工具列表失败: %s", name, exc)
                return []

        results = await asyncio.gather(
            *[_fetch(name, client) for name, client in self._clients.items()]
        )
        return [tool for sublist in results for tool in sublist]

    # ------------------------------------------------------------------
    # 工具调用
    # ------------------------------------------------------------------

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """通过指定 Server 调用工具"""
        client = self._clients.get(server_name)
        if client is None:
            raise MCPConnectionError(
                f"MCPManager: Server '{server_name}' 未注册或未连接"
            )
        return await client.call_tool(tool_name, arguments)

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def health_check_all(self) -> Dict[str, bool]:
        """并发对所有 Server 进行健康检查"""
        if not self._clients:
            return {}

        async def _check(name: str, client: MCPClient) -> tuple[str, bool]:
            status = await client.health_check()
            return name, status

        results = await asyncio.gather(
            *[_check(name, client) for name, client in self._clients.items()]
        )
        return dict(results)
