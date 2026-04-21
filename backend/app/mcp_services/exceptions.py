class MCPError(Exception):
    """MCP 基础异常"""


class MCPConnectionError(MCPError):
    """MCP Server 连接失败"""


class MCPTimeoutError(MCPError):
    """MCP 工具调用超时"""


class MCPToolError(MCPError):
    """MCP 工具执行错误"""
