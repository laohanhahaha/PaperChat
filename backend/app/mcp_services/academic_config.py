"""MCP Server 预定义配置

提供 2 个 MCP Server 的配置：
- academic_mcp: 学术论文搜索/下载/阅读（基于 academic-mcp 包）
- open_websearch: 通用网络搜索（基于 open-webSearch）
"""

import os
from pathlib import Path
from typing import List

from app.mcp_services.config import MCPServerConfig, TransportType


def get_mcp_server_configs() -> List[MCPServerConfig]:
    """返回所有 MCP Server 的预定义配置"""

    # 项目根目录
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    venv_dir = project_root / "chatpdf_venv"

    return [
        MCPServerConfig(
            name="academic_mcp",
            transport=TransportType.STDIO,
            command=str(venv_dir / "Scripts" / "academic-mcp.exe"),
            args=[],
            timeout=15.0,
            max_retries=2,
            env={
                "ACADEMIC_MCP_DOWNLOAD_PATH": str(project_root / "backend" / "uploads"),
                # === 学术源镜像配置 (国内用户) ===
                # Google Scholar - 国内无法访问，必须使用镜像
                "GOOGLE_SCHOLAR_MIRROR": "https://scholar.lanfanshu.cn",
                # Sci-Hub - 域名经常变化，国内可能无法访问，可配置当前可用域名
                "SCI_HUB_MIRROR": "https://sci-hub.se",
                # === 以下源国内可访问，保留环境变量支持方便后续配置代理 ===
                # arXiv - 国内可访问但可能较慢
                # "ARXIV_MIRROR": "http://export.arxiv.org",
                # PubMed/NCBI - 国内可访问但可能较慢
                # "PUBMED_MIRROR": "https://eutils.ncbi.nlm.nih.gov",
                # PMC - 国内可访问但可能较慢
                # "PMC_MIRROR": "https://eutils.ncbi.nlm.nih.gov",
                # bioRxiv - 国内通常可直接访问
                # "BIORXIV_MIRROR": "https://api.biorxiv.org",
                # medRxiv - 国内通常可直接访问
                # "MEDRXIV_MIRROR": "https://api.biorxiv.org",
                # Semantic Scholar - 国内通常可直接访问
                # "SEMANTIC_SCHOLAR_MIRROR": "https://api.semanticscholar.org",
                # CrossRef - 国内可直接访问
                # "CROSSREF_MIRROR": "https://api.crossref.org",
                # IACR - 国内通常可直接访问
                # "IACR_MIRROR": "https://eprint.iacr.org",
                # ScienceDirect/Elsevier - 国内可直接访问
                # "SCIENCEDIRECT_MIRROR": "https://api.elsevier.com",
                # Springer - 国内可直接访问
                # "SPRINGER_MIRROR": "http://api.springernature.com",
                # IEEE - 国内可直接访问
                # "IEEE_MIRROR": "http://ieeexploreapi.ieee.org",
                # Scopus - 国内可直接访问
                # "SCOPUS_MIRROR": "https://api.elsevier.com",
                # CORE - 国内通常可直接访问
                # "CORE_MIRROR": "https://api.core.ac.uk",
            },
            enabled=True,
        ),
        MCPServerConfig(
            name="open_websearch",
            transport=TransportType.STDIO,
            command="node",
            args=[str(venv_dir / "open-webSearch" / "build" / "index.js")],
            timeout=15.0,
            max_retries=2,
            env={"MODE": "stdio"},
            enabled=True,
        ),
    ]
