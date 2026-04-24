"""Mendeley API 客户端

使用 Mendeley REST API 进行个人文献库管理。
文档: https://dev.mendeley.com/
"""
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class MendeleyClient:
    """Mendeley API 客户端"""

    BASE_URL = "https://api.mendeley.com"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def search_library(self, query: str, limit: int = 25) -> list[dict]:
        """搜索个人文献库

        Args:
            query: 搜索关键词
            limit: 返回结果数量上限

        Returns:
            文献条目列表
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/documents"
        params = {"search": query, "limit": min(limit, 100)}

        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else []
            logger.warning(f"Mendeley 搜索失败: {resp.status}")
            return []

    async def add_reference(self, metadata: dict) -> dict:
        """添加引用/文档

        Args:
            metadata: 文献元数据，可包含 title, authors, year 等

        Returns:
            API 响应数据
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/documents"

        payload = {}
        if "title" in metadata:
            payload["title"] = metadata["title"]
        if "authors" in metadata:
            authors = metadata["authors"]
            if isinstance(authors, str):
                # 简单拆分
                author_list = []
                for a in authors.split(","):
                    parts = a.strip().split()
                    if len(parts) > 1:
                        author_list.append({
                            "first_name": parts[0],
                            "last_name": " ".join(parts[1:]),
                        })
                    else:
                        author_list.append({"last_name": a.strip()})
                payload["authors"] = author_list
            else:
                payload["authors"] = authors
        if "year" in metadata:
            payload["year"] = int(metadata["year"]) if str(metadata["year"]).isdigit() else None
        if "journal" in metadata or "publisher" in metadata:
            payload["source"] = metadata.get("journal") or metadata.get("publisher", "")
        if "doi" in metadata:
            payload["identifiers"] = {"doi": metadata["doi"]}

        async with session.post(url, json=payload) as resp:
            if resp.status in (200, 201, 202):
                try:
                    return await resp.json()
                except Exception:
                    return {"success": True, "status": resp.status}
            text = await resp.text()
            logger.warning(f"Mendeley 添加引用失败: {resp.status} - {text}")
            return {"success": False, "error": text, "status": resp.status}

    async def get_folders(self) -> list[dict]:
        """获取文件夹列表

        Returns:
            文件夹列表
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/folders"

        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else []
            logger.warning(f"Mendeley 获取文件夹失败: {resp.status}")
            return []

    async def test_connection(self) -> bool:
        """测试连接

        Returns:
            是否连接成功
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}/documents"
        params = {"limit": 1}

        try:
            async with session.get(url, params=params) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Mendeley 连接测试失败: {e}")
            return False

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
