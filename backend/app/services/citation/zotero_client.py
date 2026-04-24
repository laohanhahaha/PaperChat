"""Zotero Web API 客户端

使用 Zotero REST API 进行文献库搜索、条目添加、集合管理和格式导出。
文档: https://www.zotero.org/support/dev/web_api/v3/start
"""
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Zotero Web API 客户端"""

    BASE_URL = "https://api.zotero.org"

    def __init__(
        self,
        api_key: str,
        library_id: str,
        library_type: str = "users",
    ):
        self.api_key = api_key
        self.library_id = library_id
        self.library_type = library_type  # "users" or "groups"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Zotero-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    def _library_url(self, endpoint: str = "") -> str:
        """构建以文献库为前缀的 URL"""
        base = f"{self.BASE_URL}/{self.library_type}/{self.library_id}"
        if endpoint:
            return f"{base}/{endpoint.lstrip('/')}"
        return base

    async def search_library(self, query: str, limit: int = 25) -> list[dict]:
        """搜索文献库

        Args:
            query: 搜索关键词
            limit: 返回结果数量上限

        Returns:
            文献条目列表
        """
        session = await self._get_session()
        url = self._library_url("items")
        params = {"q": query, "limit": min(limit, 100), "format": "json"}

        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else []
            logger.warning(f"Zotero 搜索失败: {resp.status}")
            return []

    async def add_item(self, item_type: str, metadata: dict) -> dict:
        """添加文献条目

        Args:
            item_type: 条目类型，如 journalArticle, book, conferencePaper
            metadata: 条目元数据字典

        Returns:
            API 响应数据
        """
        session = await self._get_session()
        url = self._library_url("items")

        payload = [
            {
                "itemType": item_type,
                **metadata,
            }
        ]

        async with session.post(url, json=payload) as resp:
            if resp.status in (200, 201, 204):
                try:
                    return await resp.json()
                except Exception:
                    return {"success": True, "status": resp.status}
            text = await resp.text()
            logger.warning(f"Zotero 添加条目失败: {resp.status} - {text}")
            return {"success": False, "error": text, "status": resp.status}

    async def get_collections(self) -> list[dict]:
        """获取所有集合/文件夹

        Returns:
            集合列表
        """
        session = await self._get_session()
        url = self._library_url("collections")
        params = {"format": "json"}

        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else []
            logger.warning(f"Zotero 获取集合失败: {resp.status}")
            return []

    async def export_bibtex(self, item_keys: list[str]) -> str:
        """导出 BibTeX 格式

        Args:
            item_keys: Zotero 条目 key 列表

        Returns:
            BibTeX 字符串
        """
        if not item_keys:
            return ""
        session = await self._get_session()
        # 通过 item key 过滤并请求 bibtex 格式
        url = self._library_url("items")
        params = {
            "itemKey": ",".join(item_keys),
            "format": "bibtex",
        }

        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Zotero 导出 BibTeX 失败: {resp.status}")
            return ""

    async def export_ris(self, item_keys: list[str]) -> str:
        """导出 RIS 格式

        Args:
            item_keys: Zotero 条目 key 列表

        Returns:
            RIS 字符串
        """
        if not item_keys:
            return ""
        session = await self._get_session()
        url = self._library_url("items")
        params = {
            "itemKey": ",".join(item_keys),
            "format": "ris",
        }

        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Zotero 导出 RIS 失败: {resp.status}")
            return ""

    async def test_connection(self) -> bool:
        """测试 API Key 有效性

        Returns:
            是否连接成功
        """
        session = await self._get_session()
        url = self._library_url("items")
        params = {"limit": 1, "format": "json"}

        try:
            async with session.get(url, params=params) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Zotero 连接测试失败: {e}")
            return False

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
