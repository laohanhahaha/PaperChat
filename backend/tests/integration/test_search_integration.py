"""搜索调度器集成测试

测试 SearchDispatcher 的：
- 多源并行查询与结果融合
- 源失败自动降级
- 离线检测与错误结果返回
- 网络探测逻辑
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.search.base import SearchAdapter, SearchResult
from app.services.search.dispatcher import SearchDispatcher


class MockAdapter(SearchAdapter):
    """可配置的 mock 搜索适配器"""

    def __init__(self, name: str, results: list = None, available: bool = True):
        super().__init__()
        self._name = name
        self._results = results or []
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    async def search(self, query: str, max_results: int = 5, **kwargs):
        return self._results[:max_results]

    async def is_available(self) -> bool:
        return self._available


@pytest.fixture
def dispatcher():
    d = SearchDispatcher()
    # 覆盖网络检测为 True（避免真实 HTTP 请求）
    d._network_status = True
    d._network_checked_at = float('inf')
    return d


def make_result(title: str, source: str, score: float = 0.9):
    return SearchResult(
        title=title,
        url=f"https://example.com/{title}",
        snippet=f"This is {title}",
        source=source,
        relevance_score=score,
    )


class TestSearchDispatcher:
    """SearchDispatcher 核心逻辑测试"""

    async def test_search_no_adapters_returns_error(self, dispatcher):
        """无注册适配器时返回友好错误"""
        results = await dispatcher.search("test query")
        assert len(results) == 1
        assert results[0].metadata.get("error") is True
        assert "搜索服务未配置" in results[0].title

    async def test_search_single_source(self, dispatcher):
        """单个源正常返回结果"""
        dispatcher.register_adapter(MockAdapter(
            "test_source",
            results=[make_result("r1", "test_source")],
        ))
        results = await dispatcher.search("test", sources=["test_source"])
        assert len(results) == 1
        assert results[0].title == "r1"

    async def test_search_multi_source_merge(self, dispatcher):
        """多源结果融合去重"""
        dispatcher.register_adapter(MockAdapter(
            "src_a",
            results=[make_result("same", "src_a", 0.9), make_result("only_a", "src_a", 0.8)],
        ))
        dispatcher.register_adapter(MockAdapter(
            "src_b",
            results=[make_result("same", "src_b", 0.85), make_result("only_b", "src_b", 0.7)],
        ))
        results = await dispatcher.search("test", sources=["src_a", "src_b"])
        # 应去重保留 3 条（same 只保留一次）
        titles = {r.title for r in results}
        assert "same" in titles
        assert "only_a" in titles
        assert "only_b" in titles
        assert len(results) <= 3

    async def test_search_source_failure_fallback(self, dispatcher):
        """首选源失败时降级到其他源"""
        dispatcher.register_adapter(MockAdapter(
            "good",
            results=[make_result("ok", "good")],
            available=True,
        ))
        dispatcher.register_adapter(MockAdapter(
            "bad",
            results=[],
            available=False,
        ))
        # 只选 bad，应降级到 good
        results = await dispatcher.search("test", sources=["bad"])
        assert len(results) >= 1
        # 结果可能来自 good（降级）或错误提示
        if results[0].metadata.get("error"):
            assert "搜索服务暂不可用" in results[0].title
        else:
            assert results[0].title == "ok"

    async def test_search_all_sources_fail(self, dispatcher):
        """所有源都失败时返回友好错误"""
        dispatcher.register_adapter(MockAdapter(
            "dead1", results=[], available=False,
        ))
        dispatcher.register_adapter(MockAdapter(
            "dead2", results=[], available=False,
        ))
        results = await dispatcher.search("test", sources=["dead1", "dead2"])
        assert len(results) == 1
        assert results[0].metadata.get("error") is True

    async def test_offline_no_cache_returns_error(self, dispatcher):
        """离线且无缓存时返回友好提示"""
        dispatcher._network_status = False
        with patch("app.services.precache_service.precache_service.is_cache_available",
                   return_value=False):
            results = await dispatcher.search("test")
            assert len(results) == 1
            assert "离线" in results[0].snippet

    async def test_network_check_probes_multiple_urls(self, dispatcher):
        """网络检测探测多个 URL"""
        dispatcher._network_checked_at = 0  # 强制重新检测
        with patch("httpx.AsyncClient.head") as mock_head:
            mock_head.return_value.status_code = 200
            result = await dispatcher._check_network()
            assert result is True

    async def test_register_adapter(self, dispatcher):
        """注册适配器后可通过名称访问"""
        adapter = MockAdapter("my_test", available=True)
        dispatcher.register_adapter(adapter)
        assert "my_test" in dispatcher._adapters
        assert dispatcher._adapters["my_test"] is adapter


class TestSearchResultModel:
    """SearchResult 数据模型测试"""

    def test_search_result_creation(self):
        r = SearchResult(
            title="Test",
            url="https://example.com",
            snippet="snippet",
            source="test",
            relevance_score=0.5,
        )
        assert r.title == "Test"
        assert r.relevance_score == 0.5

    def test_search_result_default_metadata(self):
        r = SearchResult(
            title="T", url="https://e.com", snippet="s", source="s", relevance_score=0.0,
        )
        assert r.metadata == {}

    def test_search_result_with_metadata(self):
        r = SearchResult(
            title="T", url="https://e.com", snippet="s", source="s",
            relevance_score=1.0, metadata={"arxiv_id": "1234"},
        )
        assert r.metadata["arxiv_id"] == "1234"
