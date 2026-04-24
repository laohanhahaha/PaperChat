"""Bing Web Search API 适配器"""
import asyncio
import os
import logging
from typing import List, Optional

import aiohttp

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)

BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"
DEFAULT_TIMEOUT = 15


class BingAdapter(SearchAdapter):
    name: str = "bing"
    requires_api_key: bool = True

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BING_SEARCH_API_KEY", "")

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        if not self._api_key:
            logger.warning("Bing Search API Key 未配置")
            return []

        params = {
            "q": query,
            "count": max_results,
        }
        if kwargs.get("region"):
            params["mkt"] = kwargs["region"]

        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", DEFAULT_TIMEOUT))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BING_SEARCH_URL, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"Bing API 返回非 200 状态码: {resp.status}")
                        return []
                    data = await resp.json()

            web_pages = data.get("webPages", {}).get("value", [])
            results = []
            for i, page in enumerate(web_pages):
                results.append(
                    SearchResult(
                        title=page.get("name", ""),
                        url=page.get("url", ""),
                        snippet=page.get("snippet", ""),
                        source="bing",
                        relevance_score=max(0.0, 1.0 - i * 0.1),
                        metadata={
                            "dateLastCrawled": page.get("dateLastCrawled", ""),
                        },
                    )
                )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"Bing 搜索超时: {query}")
            return []
        except Exception as e:
            logger.warning(f"Bing 搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return bool(self._api_key)
