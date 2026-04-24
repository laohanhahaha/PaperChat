"""Wigolo 搜索 API 适配器"""
import asyncio
import os
import logging
from typing import List, Optional

import aiohttp

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)

WIGOLO_SEARCH_URL = "https://api.wigolo.com/v1/search"
DEFAULT_TIMEOUT = 5


class WigoloAdapter(SearchAdapter):
    name: str = "wigolo"
    requires_api_key: bool = True

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("WIGOLO_API_KEY", "")

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        if not self._api_key:
            logger.warning("Wigolo 搜索 API Key 未配置")
            return []

        params = {
            "q": query,
            "limit": max_results,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", DEFAULT_TIMEOUT))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(WIGOLO_SEARCH_URL, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"Wigolo API 返回非 200 状态码: {resp.status}")
                        return []
                    data = await resp.json()

            # 解析搜索结果（兼容多种可能的响应结构）
            raw_results = []
            if isinstance(data, list):
                raw_results = data
            elif isinstance(data, dict):
                raw_results = (
                    data.get("results", [])
                    or data.get("data", [])
                    or data.get("result", [])
                    or data.get("items", [])
                    or []
                )

            results = []
            for i, item in enumerate(raw_results[:max_results]):
                title = item.get("title") or item.get("name", "")
                url = item.get("url") or item.get("link", "")
                snippet = item.get("snippet") or item.get("abstract") or item.get("description", "")
                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="wigolo",
                        relevance_score=max(0.0, 1.0 - i * 0.1),
                        metadata={},
                    )
                )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"Wigolo 搜索超时: {query}")
            return []
        except Exception as e:
            logger.warning(f"Wigolo 搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return bool(self._api_key)
