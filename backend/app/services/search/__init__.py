"""搜索服务模块 —— 多源搜索集群"""
from app.services.search.search_service import SearchService, search_service
from app.services.search.base import SearchAdapter, SearchResult
from app.services.search.duckduckgo_adapter import DuckDuckGoAdapter
from app.services.search.bing_adapter import BingAdapter
from app.services.search.tavily_adapter import TavilyAdapter
from app.services.search.brave_adapter import BraveAdapter
from app.services.search.dispatcher import SearchDispatcher

__all__ = [
    "SearchService",
    "search_service",
    "SearchAdapter",
    "SearchResult",
    "DuckDuckGoAdapter",
    "BingAdapter",
    "TavilyAdapter",
    "BraveAdapter",
    "SearchDispatcher",
]
