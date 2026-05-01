from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.mcp_services.config import MCPConfig, MCPServerConfig
from app.mcp_services.client import MCPClient, MCPToolSchema
from app.mcp_services.exceptions import MCPConnectionError

logger = logging.getLogger(__name__)

# 健康检查任务轮询间隔（秒）
_HEALTH_CHECK_INTERVAL = 60.0


class MCPManager:
    """管理所有 MCP Server 的生命周期

    特性：
    - 并发启动/关闭所有已配置 Server
    - 定期健康检查 + 自动重连断线 Server
    - 动态添加/移除 Server
    - 统一 call_tool 接口
    """

    def __init__(self, config: Optional[MCPConfig] = None) -> None:
        self._clients: Dict[str, MCPClient] = {}
        self._config: MCPConfig = config or MCPConfig()
        self._health_task: Optional[asyncio.Task] = None  # 后台健康检查任务

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动所有已配置且已启用的 Server 连接，并启动后台健康检查"""
        logger.info("[MCPManager] 启动，共 %d 个 Server 配置", len(self._config.servers))
        # 并发连接所有启用的 Server
        tasks = []
        for server_cfg in self._config.servers:
            if not server_cfg.enabled:
                logger.info("[MCPManager] Server %s 已禁用，跳过", server_cfg.name)
                continue
            tasks.append(self.add_server(server_cfg))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 启动后台健康检查（如果配置了自动重连）
        if self._config.auto_reconnect:
            self._health_task = asyncio.create_task(
                self._health_check_loop(),
                name="mcp-health-check",
            )
            logger.info("[MCPManager] 后台健康检查任务已启动")

    async def stop(self) -> None:
        """关闭所有连接，停止健康检查"""
        # 停止健康检查任务
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

        logger.info("[MCPManager] 关闭所有 MCP Server 连接（共 %d 个）", len(self._clients))
        names = list(self._clients.keys())
        # 并发关闭
        await asyncio.gather(
            *[self.remove_server(name) for name in names],
            return_exceptions=True,
        )

    # ------------------------------------------------------------------
    # 动态管理
    # ------------------------------------------------------------------

    async def add_server(self, config: MCPServerConfig) -> bool:
        """动态添加并连接 Server

        Returns:
            True 表示连接成功，False 表示失败（不抛出异常）
        """
        if config.name in self._clients:
            logger.warning("[MCPManager] Server %s 已存在，跳过添加", config.name)
            return True

        client = MCPClient(config)
        try:
            await client.connect()
            self._clients[config.name] = client
            logger.info("[MCPManager] Server %s 添加成功", config.name)
            return True
        except Exception as exc:
            import traceback
            logger.error(
                "[MCPManager] 启动 Server %s 失败: %s\n%s",
                config.name, repr(exc), traceback.format_exc()
            )
            return False

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

    async def _health_check_loop(self) -> None:
        """后台健康检查循环：定期检查并自动重连断线 Server"""
        interval = self._config.health_check_interval or _HEALTH_CHECK_INTERVAL
        logger.debug("[MCPManager] 健康检查循环启动，间隔 %.0fs", interval)
        while True:
            try:
                await asyncio.sleep(interval)
                await self._reconnect_unhealthy()
            except asyncio.CancelledError:
                logger.debug("[MCPManager] 健康检查循环已取消")
                break
            except Exception as exc:
                logger.error("[MCPManager] 健康检查循环异常: %s", exc)

    async def _reconnect_unhealthy(self) -> None:
        """检查所有 Server 健康状态，对断线的 Server 执行重连"""
        if not self._clients:
            return

        statuses = await self.health_check_all()
        unhealthy = [name for name, ok in statuses.items() if not ok]

        if not unhealthy:
            logger.debug("[MCPManager] 所有 %d 个 Server 健康正常", len(statuses))
            return

        logger.warning(
            "[MCPManager] 检测到 %d 个 Server 不健康: %s，尝试重连",
            len(unhealthy),
            unhealthy,
        )

        async def _reconnect_one(name: str) -> None:
            client = self._clients.get(name)
            if client is None:
                return
            try:
                await client.disconnect()
                await client.connect()
                logger.info("[MCPManager] Server %s 重连成功", name)
            except Exception as exc:
                logger.error("[MCPManager] Server %s 重连失败: %s", name, exc)

        await asyncio.gather(
            *[_reconnect_one(name) for name in unhealthy],
            return_exceptions=True,
        )

    # ------------------------------------------------------------------
    # 工具缓存管理
    # ------------------------------------------------------------------

    def invalidate_tools_cache(self, server_name: Optional[str] = None) -> None:
        """清除工具缓存（指定 Server 或全部）"""
        if server_name:
            client = self._clients.get(server_name)
            if client:
                client.invalidate_tools_cache()
        else:
            for client in self._clients.values():
                client.invalidate_tools_cache()
