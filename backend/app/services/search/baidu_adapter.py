"""百度搜索开放平台 API 适配器"""
import asyncio
import os
import logging
from typing import List, Optional

import aiohttp

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)

BAIDU_SEARCH_URL = "https://openapi.baidu.com/rest/2.0/search"
DEFAULT_TIMEOUT = 5


class BaiduAdapter(SearchAdapter):
    name: str = "baidu"
    requires_api_key: bool = True

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BAIDU_SEARCH_API_KEY", "")

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        if not self._api_key:
            logger.warning("百度搜索 API Key 未配置")
            return []

        params = {
            "q": query,
            "api_key": self._api_key,
            "num": max_results,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", DEFAULT_TIMEOUT))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BAIDU_SEARCH_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"百度 API 返回非 200 状态码: {resp.status}")
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
                        source="baidu",
                        relevance_score=max(0.0, 1.0 - i * 0.1),
                        metadata={},
                    )
                )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"百度搜索超时: {query}")
            return []
        except Exception as e:
            logger.warning(f"百度搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return bool(self._api_key)
