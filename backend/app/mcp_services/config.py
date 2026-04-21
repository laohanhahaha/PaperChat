from pydantic import BaseModel
from typing import Optional, Dict
from enum import Enum


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class MCPServerConfig(BaseModel):
    """MCP Server 连接配置"""

    name: str                                       # Server 标识名
    transport: TransportType = TransportType.STDIO
    command: Optional[str] = None                   # stdio 模式的启动命令
    args: list[str] = []                            # 启动参数
    url: Optional[str] = None                       # SSE/HTTP 模式的 URL
    api_key: Optional[str] = None                   # 认证密钥
    timeout: float = 10.0                           # 请求超时秒数
    max_retries: int = 2                            # 最大重试次数
    env: Dict[str, str] = {}                        # 环境变量
    enabled: bool = True                            # 是否启用


class MCPConfig(BaseModel):
    """MCP 全局配置"""

    servers: list[MCPServerConfig] = []
    default_timeout: float = 10.0
    auto_reconnect: bool = True
    health_check_interval: float = 60.0             # 健康检查间隔秒数
