"""搜索调度器 —— 多源搜索智能调度与结果融合"""
import asyncio
import logging
from typing import Dict, List, Optional

from app.services.search.base import SearchAdapter, SearchResult

logger = logging.getLogger(__name__)


class SearchDispatcher:
    """多源搜索智能调度器

    功能：
    1. 注册多个搜索适配器
    2. 根据 search_type 自动选择最优搜索源
    3. 多源并行查询 + 结果融合去重
    4. 失败自动降级
    """

    def __init__(self):
        self._adapters: Dict[str, SearchAdapter] = {}
        self._default_source = "duckduckgo"

    def register_adapter(self, adapter: SearchAdapter) -> None:
        """注册搜索适配器"""
        self._adapters[adapter.name] = adapter
        logger.info(f"[SearchDispatcher] 注册搜索源: {adapter.name}")

    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        max_results: int = 5,
        search_type: str = "general",
        **kwargs
    ) -> List[SearchResult]:
        """智能搜索入口

        Args:
            query: 搜索查询
            sources: 指定搜索源列表，None 时自动选择
            max_results: 最大结果数
            search_type: 搜索类型 ("general" | "academic" | "news")
            **kwargs: 额外参数透传给适配器

        Returns:
            融合去重后的搜索结果列表
        """
        # 确定要使用的搜索源
        if sources is None:
            sources = await self._select_sources(search_type)
        else:
            # 过滤掉未注册的源
            sources = [s for s in sources if s in self._adapters]

        if not sources:
            sources = [self._default_source]

        logger.info(f"[SearchDispatcher] 查询 '{query[:40]}...' 使用源: {sources}")

        # 并行查询所有选中的源
        tasks = []
        for source in sources:
            adapter = self._adapters.get(source)
            if adapter:
                tasks.append(self._search_with_fallback(adapter, query, max_results, **kwargs))

        if not tasks:
            logger.warning("[SearchDispatcher] 没有可用的搜索适配器")
            return []

        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集有效结果
        all_results: List[List[SearchResult]] = []
        for i, res in enumerate(results_per_source):
            source_name = sources[i]
            if isinstance(res, Exception):
                logger.warning(f"[SearchDispatcher] 源 {source_name} 查询异常: {res}")
            elif isinstance(res, list):
                if res:
                    logger.info(f"[SearchDispatcher] 源 {source_name} 返回 {len(res)} 条结果")
                all_results.append(res)

        # 融合去重
        merged = self._merge_results(all_results, max_results)
        logger.info(f"[SearchDispatcher] 融合后返回 {len(merged)} 条结果")
        return merged

    async def _search_with_fallback(
        self,
        adapter: SearchAdapter,
        query: str,
        max_results: int,
        **kwargs
    ) -> List[SearchResult]:
        """单个适配器搜索，失败返回空列表"""
        try:
            return await adapter.search(query, max_results=max_results, **kwargs)
        except Exception as e:
            logger.warning(f"[SearchDispatcher] 适配器 {adapter.name} 失败: {e}")
            return []

    async def _select_sources(self, search_type: str) -> List[str]:
        """根据搜索类型和可用性选择搜索源"""
        # 检查各源可用性
        available = {}
        for name, adapter in self._adapters.items():
            try:
                if await adapter.is_available():
                    available[name] = adapter
            except Exception as e:
                logger.debug(f"[SearchDispatcher] 检查 {name} 可用性失败: {e}")

        if search_type == "academic":
            # 学术搜索：优先 Tavily（如果可用），其次是 Bing/Brave，最后 DuckDuckGo
            priority = ["tavily", "bing", "brave", "duckduckgo"]
        elif search_type == "news":
            # 新闻搜索：优先 Bing/Brave
            priority = ["bing", "brave", "tavily", "duckduckgo"]
        else:
            # 通用搜索：优先 Tavily（专为 AI 设计），Bing/Brave 其次，
            # Wigolo 作为通用备选，Baidu 适合中文搜索，降级到 DuckDuckGo
            priority = ["tavily", "brave", "bing", "wigolo", "baidu", "duckduckgo"]

        selected = [name for name in priority if name in available]

        # 默认至少返回 duckduckgo（始终可用）
        if not selected and "duckduckgo" in self._adapters:
            selected = ["duckduckgo"]

        return selected

    def _merge_results(self, all_results: List[List[SearchResult]], max_results: int) -> List[SearchResult]:
        """多源结果融合：按 URL 去重 + relevance_score 排序"""
        seen_urls: set = set()
        merged: List[SearchResult] = []

        for results in all_results:
            for r in results:
                if not r.url or r.url in seen_urls:
                    continue
                seen_urls.add(r.url)
                merged.append(r)

        merged.sort(key=lambda x: x.relevance_score, reverse=True)
        return merged[:max_results]

    def get_registered_sources(self) -> List[str]:
        """获取所有已注册的搜索源名称"""
        return list(self._adapters.keys())

    async def get_available_sources(self) -> List[str]:
        """获取当前可用的搜索源名称"""
        available = []
        for name, adapter in self._adapters.items():
            try:
                if await adapter.is_available():
                    available.append(name)
            except Exception:
                pass
        return available
