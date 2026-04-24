"""引用管理服务

提供外部引用管理工具（Zotero/Mendeley）集成和多种引用格式格式化。
"""
from app.services.citation.zotero_client import ZoteroClient
from app.services.citation.mendeley_client import MendeleyClient
from app.services.citation.citation_formatter import CitationFormatter

__all__ = ["ZoteroClient", "MendeleyClient", "CitationFormatter"]
