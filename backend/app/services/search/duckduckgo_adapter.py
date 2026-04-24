"""DuckDuckGo 搜索适配器 —— 封装现有 SearchService"""
import logging
from typing import List

from app.services.search.base import SearchAdapter, SearchResult
from app.services.search.search_service import search_service

logger = logging.getLogger(__name__)


class DuckDuckGoAdapter(SearchAdapter):
    name: str = "duckduckgo"
    requires_api_key: bool = False

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        try:
            results = await search_service.search(
                query=query,
                max_results=max_results,
                region=kwargs.get("region", "wt-wt"),
                timelimit=kwargs.get("timelimit"),
            )
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                    source="duckduckgo",
                    relevance_score=0.0,
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"DuckDuckGo 搜索失败: {e}")
            return []

    async def is_available(self) -> bool:
        return True
