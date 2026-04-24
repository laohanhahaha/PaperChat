"""学术 MCP Server 预定义配置

提供 5 个学术数据源的 MCPServerConfig，默认均关闭（enabled=False）。
通过环境变量传入各 Server 所需的 API Key。
"""

import sys
from typing import List

from app.mcp_services.config import MCPServerConfig, TransportType


def get_academic_server_configs() -> List[MCPServerConfig]:
    """返回 5 个学术 MCP Server 的预定义配置"""
    return [
        MCPServerConfig(
            name="arxiv",
            transport=TransportType.STDIO,
            command=sys.executable,
            args=["-m", "app.mcp_services.servers.arxiv_server"],
            enabled=False,
        ),
        MCPServerConfig(
            name="semantic_scholar",
            transport=TransportType.STDIO,
            command=sys.executable,
            args=["-m", "app.mcp_services.servers.semantic_scholar_server"],
            env={"S2_API_KEY": ""},
            enabled=False,
        ),
        MCPServerConfig(
            name="crossref",
            transport=TransportType.STDIO,
            command=sys.executable,
            args=["-m", "app.mcp_services.servers.crossref_server"],
            env={"CROSSREF_MAILTO": "chatpdf@example.com"},
            enabled=False,
        ),
        MCPServerConfig(
            name="dblp",
            transport=TransportType.STDIO,
            command=sys.executable,
            args=["-m", "app.mcp_services.servers.dblp_server"],
            enabled=False,
        ),
        MCPServerConfig(
            name="zotero",
            transport=TransportType.STDIO,
            command=sys.executable,
            args=["-m", "app.mcp_services.servers.zotero_server"],
            env={"ZOTERO_API_KEY": "", "ZOTERO_LIBRARY_ID": ""},
            enabled=False,
        ),
    ]
