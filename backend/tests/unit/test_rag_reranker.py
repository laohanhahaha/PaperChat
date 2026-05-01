"""RAG Reranker + HyDE 单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestReranker:
    """Reranker 功能测试"""

    @pytest.fixture
    def service(self):
        from app.services.rag_service import RAGService
        svc = RAGService.__new__(RAGService)
        svc._reranker = None
        svc._reranker_loading = False
        return svc

    @pytest.mark.asyncio
    async def test_rerank_with_no_reranker_falls_back(self, service):
        """Reranker 未加载时降级返回原始结果"""
        docs = [{"text": "doc1"}, {"text": "doc2"}, {"text": "doc3"}]

        # Mock _init_reranker to do nothing (simulate failure)
        with patch.object(service, "_init_reranker"):
            result = await service._rerank("query", docs, top_k=2)
            assert len(result) == 2
            assert result[0]["text"] == "doc1"

    @pytest.mark.asyncio
    async def test_rerank_sorts_by_score(self, service):
        """Reranker 按分数降序排列"""
        mock_reranker = MagicMock()
        mock_reranker.compute_score.return_value = [0.1, 0.9, 0.5]
        service._reranker = mock_reranker
        service._reranker_loading = False

        docs = [{"text": "low"}, {"text": "high"}, {"text": "mid"}]

        result = await service._rerank("query", docs, top_k=3)
        assert result[0]["text"] == "high"
        assert result[1]["text"] == "mid"
        assert result[2]["text"] == "low"
        assert "rerank_score" in result[0]

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self, service):
        """Reranker 结果数量不超过 top_k"""
        mock_reranker = MagicMock()
        mock_reranker.compute_score.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
        service._reranker = mock_reranker
        service._reranker_loading = False

        docs = [{"text": f"doc{i}"} for i in range(5)]

        result = await service._rerank("query", docs, top_k=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_docs(self, service):
        """空文档列表返回空结果"""
        service._reranker = MagicMock()
        service._reranker_loading = False

        result = await service._rerank("query", [], top_k=5)
        assert result == []


class TestHyDE:
    """HyDE 假设文档增强测试"""

    @pytest.fixture
    def service(self):
        from app.services.rag_service import RAGService
        return RAGService.__new__(RAGService)

    @pytest.mark.asyncio
    async def test_hyde_expand_returns_string(self, service):
        """HyDE 扩展返回字符串"""
        with patch("app.services.llm.llm_service.LLMService") as MockLLM:
            instance = MockLLM.return_value
            instance.chat = AsyncMock(return_value="假设文档内容")

            result = await service._hyde_expand("transformer attention mechanism")
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_hyde_expand_fallback_on_error(self, service):
        """HyDE LLM 调用失败时返回原始查询"""
        with patch("app.services.llm.llm_service.LLMService") as MockLLM:
            instance = MockLLM.return_value
            instance.chat = AsyncMock(side_effect=Exception("LLM error"))

            result = await service._hyde_expand("original query")
            assert result == "original query"
