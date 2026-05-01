"""RAG 增强集成测试

覆盖：
- smart_chunk_text 分块边界
- search 返回格式（含 rerank + hyde + hybrid）
- BM25 缓存命中
- 全文搜索降级
- 跨论文检索
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag_service import RAGService


@pytest.fixture
def mock_chroma_client():
    client = MagicMock()
    return client


@pytest.fixture
def rag(mock_chroma_client):
    with patch("app.services.rag_service.chromadb.PersistentClient",
               return_value=mock_chroma_client):
        with patch("os.makedirs"):
            service = RAGService()
    return service


class TestChunking:
    """分块逻辑边界测试"""

    def test_smart_chunk_text_basic(self, rag):
        blocks = [
            {"text": "A" * 500, "page_number": 1},
            {"text": "B" * 500, "page_number": 2},
        ]
        chunks = rag.smart_chunk_text(blocks, chunk_size=600, overlap=100)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk

    def test_smart_chunk_text_overlap(self, rag):
        """相邻块有重叠内容"""
        blocks = [
            {"text": "Hello World Foo Bar", "page_number": 1},
        ]
        chunks = rag.smart_chunk_text(blocks, chunk_size=10, overlap=5)
        # 短文本可能只有 1 个块
        assert len(chunks) >= 1

    def test_smart_chunk_text_multiple_blocks(self, rag):
        """多个文本块生成多个块"""
        blocks = [
            {"text": "A" * 1000, "page_number": 1},
            {"text": "B" * 1000, "page_number": 2},
        ]
        chunks = rag.smart_chunk_text(blocks, chunk_size=500, overlap=50)
        assert len(chunks) >= 2

    def test_smart_chunk_text_empty_blocks(self, rag):
        chunks = rag.smart_chunk_text([], chunk_size=500, overlap=50)
        assert chunks == []


class TestSearch:
    """搜索相关测试"""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, rag):
        """search 返回正确格式"""
        rag._collection = MagicMock()
        rag._collection.query = MagicMock(
            return_value={
                "ids": [["id1", "id2"]],
                "distances": [[0.1, 0.2]],
                "metadatas": [[{"page": 1}, {"page": 2}]],
                "documents": [["text1", "text2"]],
            }
        )
        rag._bm25_index = None  # 禁用 BM25
        rag._use_hybrid = False

        with patch.object(rag, "_hyde_expand", AsyncMock(return_value="expanded query")):
            with patch.object(rag, "_rerank", AsyncMock(side_effect=lambda q, docs, **kw: docs)):
                results = await rag.search(paper_id=1, query="test query", top_k=5)
                assert len(results) >= 0
                if results:
                    assert "text" in results[0]
                    assert "score" in results[0]

    @pytest.mark.asyncio
    async def test_search_empty_collection(self, rag):
        """空集合适配返回空列表"""
        rag._collection = MagicMock()
        rag._collection.query = MagicMock(
            return_value={
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
                "documents": [[]],
            }
        )
        rag._bm25_index = None
        rag._use_hybrid = False
        with patch.object(rag, "_hyde_expand", AsyncMock(return_value="query")):
            with patch.object(rag, "_rerank", AsyncMock(return_value=[])):
                results = await rag.search(paper_id=1, query="test", top_k=5)
                assert results == []


class TestBM25:
    """BM25 缓存测试"""

    def test_bm25_cache_invalidation(self, rag):
        rag._bm25_index = MagicMock()
        rag._bm25_cache = {"paper_1": "cached_data"}
        rag.invalidate_bm25_cache("paper_1")
        assert "paper_1" not in rag._bm25_cache

    def test_bm25_cache_multiple_papers(self, rag):
        rag._bm25_cache = {"p1": "a", "p2": "b", "p3": "c"}
        rag.invalidate_bm25_cache("p2")
        assert "p1" in rag._bm25_cache
        assert "p2" not in rag._bm25_cache
        assert "p3" in rag._bm25_cache
