"""Brave Search API 适配器"""
import asyncio
import os
import logging
from typing import List, Optional

import aiohttp

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_TIMEOUT = 15


class BraveAdapter(SearchAdapter):
    name: str = "brave"
    requires_api_key: bool = True

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY", "")

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        if not self._api_key:
            logger.warning("Brave Search API Key 未配置")
            return []

        params = {
            "q": query,
            "count": max_results,
            "offset": kwargs.get("offset", 0),
        }
        if kwargs.get("search_type") == "news":
            params["search_filter"] = "news"

        headers = {
            "X-Subscription-Token": self._api_key,
            "Accept": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", DEFAULT_TIMEOUT))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BRAVE_SEARCH_URL, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"Brave API 返回非 200 状态码: {resp.status}")
                        return []
                    data = await resp.json()

            web_results = data.get("web", {}).get("results", [])
            results = []
            for i, r in enumerate(web_results):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("description", ""),
                        source="brave",
                        relevance_score=max(0.0, 1.0 - i * 0.1),
                        metadata={
                            "page_age": r.get("page_age", ""),
                            "language": r.get("language", ""),
                        },
                    )
                )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"Brave 搜索超时: {query}")
            return []
        except Exception as e:
            logger.warning(f"Brave 搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return bool(self._api_key)
