"""
app.mcp_services — MCP 协议管理框架

公共导出：
  - MCPServerConfig, MCPConfig, TransportType  (配置模型)
  - MCPClient, MCPToolSchema                   (协议客户端)
  - MCPManager                                 (Server 生命周期管理)
  - MCPToolBridge                              (MCP → 内部 Tool 桥接)
  - MCPError, MCPConnectionError,
    MCPTimeoutError, MCPToolError              (自定义异常)
"""

from app.mcp_services.config import MCPConfig, MCPServerConfig, TransportType
from app.mcp_services.client import MCPClient, MCPToolSchema
from app.mcp_services.manager import MCPManager
from app.mcp_services.bridge import MCPToolBridge
from app.mcp_services.exceptions import (
    MCPError,
    MCPConnectionError,
    MCPTimeoutError,
    MCPToolError,
)

__all__ = [
    # config
    "MCPConfig",
    "MCPServerConfig",
    "TransportType",
    # client
    "MCPClient",
    "MCPToolSchema",
    # manager
    "MCPManager",
    # bridge
    "MCPToolBridge",
    # exceptions
    "MCPError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "MCPToolError",
]
