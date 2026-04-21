"""
MCPToolBridge — 将 MCP 工具动态转换为内部 Tool 接口。

使用 TYPE_CHECKING 避免与 app.tools.base 的循环导入；
运行时需要 Tool 基类时，在方法内部延迟 import。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from app.mcp_services.client import MCPToolSchema
from app.mcp_services.manager import MCPManager

if TYPE_CHECKING:
    from app.tools.base import Tool

logger = logging.getLogger(__name__)


class MCPToolBridge:
    """将 MCP 工具转换为内部 Tool 接口"""

    def __init__(self, mcp_manager: MCPManager) -> None:
        self._manager = mcp_manager

    # ------------------------------------------------------------------
    # 单工具桥接
    # ------------------------------------------------------------------

    def create_tool(self, server_name: str, mcp_schema: MCPToolSchema) -> "Tool":
        """将单个 MCP 工具转换为内部 Tool 实例（动态子类）"""
        # 延迟 import 避免循环依赖
        from app.tools.base import Tool  # noqa: PLC0415

        manager = self._manager
        _server = server_name
        _schema = mcp_schema

        class _MCPBridgedTool(Tool):
            """由 MCPToolBridge 动态生成的 MCP 工具包装类"""

            name: str = _schema.name
            description: str = _schema.description

            async def execute(self, arguments: Dict[str, Any], **kwargs: Any) -> Any:
                logger.info(
                    "[MCPToolBridge] 调用 server=%s tool=%s",
                    _server,
                    _schema.name,
                )
                return await manager.call_tool(_server, _schema.name, arguments)

        _MCPBridgedTool.__name__ = f"MCP_{server_name}_{mcp_schema.name}"
        _MCPBridgedTool.__qualname__ = _MCPBridgedTool.__name__

        return _MCPBridgedTool()

    # ------------------------------------------------------------------
    # 批量桥接
    # ------------------------------------------------------------------

    async def bridge_all(self) -> List["Tool"]:
        """桥接所有 MCP Server 的工具为内部 Tool 列表"""
        all_schemas: List[MCPToolSchema] = await self._manager.get_all_tools()

        tools: List[Tool] = []
        for schema in all_schemas:
            try:
                tool = self.create_tool(schema.server_name, schema)
                tools.append(tool)
            except Exception as exc:
                logger.warning(
                    "[MCPToolBridge] 桥接工具 %s/%s 失败: %s",
                    schema.server_name,
                    schema.name,
                    exc,
                )

        logger.info("[MCPToolBridge] 共桥接 %d 个 MCP 工具", len(tools))
        return tools
