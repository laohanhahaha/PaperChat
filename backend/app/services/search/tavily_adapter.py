"""Tavily Search API 适配器"""
import asyncio
import os
import logging
from typing import List, Optional

import aiohttp

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT = 15


class TavilyAdapter(SearchAdapter):
    name: str = "tavily"
    requires_api_key: bool = True

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY", "")

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        if not self._api_key:
            logger.warning("Tavily API Key 未配置")
            return []

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": kwargs.get("search_depth", "basic"),
        }
        if kwargs.get("include_answer"):
            payload["include_answer"] = True

        try:
            timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", DEFAULT_TIMEOUT))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(TAVILY_SEARCH_URL, json=payload) as resp:
                    if resp.status != 200:
                        logger.warning(f"Tavily API 返回非 200 状态码: {resp.status}")
                        return []
                    data = await resp.json()

            raw_results = data.get("results", [])
            results = []
            for i, r in enumerate(raw_results):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("content", ""),
                        source="tavily",
                        relevance_score=r.get("score", max(0.0, 1.0 - i * 0.1)),
                        metadata={
                            "raw_content": r.get("raw_content", ""),
                        },
                    )
                )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"Tavily 搜索超时: {query}")
            return []
        except Exception as e:
            logger.warning(f"Tavily 搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return bool(self._api_key)
