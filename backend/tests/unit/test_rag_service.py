"""RAG 服务单元测试

测试 RAGService 的核心逻辑，全部 mock 外部依赖（ChromaDB、embedding 模型）。

覆盖：
- smart_chunk_text 分块逻辑
- index_paper 调用 embedding + collection.add
- search 返回格式
- delete_paper_index / invalidate_bm25_cache
- BM25 缓存命中 / 失效
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.services.rag_service import RAGService


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_chroma_client():
    """模拟 ChromaDB 客户端"""
    client = MagicMock()
    return client


@pytest.fixture
def rag(mock_chroma_client):
    """创建 RAGService 实例，patch ChromaDB 初始化"""
    with patch("app.services.rag_service.chromadb.PersistentClient", return_value=mock_chroma_client):
        with patch("os.makedirs"):
            service = RAGService()
    return service


# ── 测试：smart_chunk_text ───────────────────────────────────────────────────

def test_smart_chunk_text_basic(rag):
    """基本分块：多个块能正确拆分"""
    blocks = [
        {"text": "A" * 500, "page_number": 1},
        {"text": "B" * 500, "page_number": 2},
    ]
    chunks = rag.smart_chunk_text(blocks, chunk_size=600, overlap=100)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert "text" in chunk
        assert "metadata" in chunk
        assert "pages" in chunk["metadata"]
        assert "chunk_index" in chunk["metadata"]


def test_smart_chunk_text_empty_blocks(rag):
    """空文本块列表返回空列表"""
    chunks = rag.smart_chunk_text([])
    assert chunks == []


def test_smart_chunk_text_empty_text_ignored(rag):
    """文本为空的块被跳过"""
    blocks = [
        {"text": "", "page_number": 1},
        {"text": "   ", "page_number": 2},
        {"text": "有效内容", "page_number": 3},
    ]
    chunks = rag.smart_chunk_text(blocks)
    assert len(chunks) == 1
    assert "有效内容" in chunks[0]["text"]


def test_smart_chunk_text_small_blocks_merged(rag):
    """小块合并到一个 chunk"""
    blocks = [
        {"text": "短文本一", "page_number": 1},
        {"text": "短文本二", "page_number": 2},
    ]
    # chunk_size 足够大，应该合并为一个块
    chunks = rag.smart_chunk_text(blocks, chunk_size=10000)
    assert len(chunks) == 1


def test_smart_chunk_text_chunk_index_increments(rag):
    """chunk_index 从 0 开始递增"""
    blocks = [{"text": "X" * 500, "page_number": i} for i in range(5)]
    chunks = rag.smart_chunk_text(blocks, chunk_size=600, overlap=50)
    for i, chunk in enumerate(chunks):
        assert chunk["metadata"]["chunk_index"] == i


# ── 测试：index_paper ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_index_paper_calls_embedding_and_add(rag):
    """index_paper 应调用 embedding 模型并向 collection 写入数据"""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0  # 未索引
    rag.chroma_client.get_or_create_collection.return_value = mock_collection

    mock_model = MagicMock()
    import numpy as np
    mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

    # 直接设置 _embedding_model，绕过 async property
    rag._embedding_model = mock_model

    text_blocks = [{"text": "测试文本内容，足够长的段落", "page_number": 1}]
    result = await rag.index_paper(paper_id=1, text_blocks=text_blocks)

    assert result is True
    assert mock_collection.add.called


@pytest.mark.asyncio
async def test_index_paper_skips_if_already_indexed(rag):
    """已索引的论文不重复写入"""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 5  # 已有数据

    rag.chroma_client.get_or_create_collection.return_value = mock_collection

    result = await rag.index_paper(paper_id=99, text_blocks=[])

    assert result is True
    assert not mock_collection.add.called  # 不应调用 add


@pytest.mark.asyncio
async def test_index_paper_returns_false_on_empty_chunks(rag):
    """空文本块导致索引失败，返回 False"""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    rag.chroma_client.get_or_create_collection.return_value = mock_collection

    result = await rag.index_paper(paper_id=2, text_blocks=[])

    assert result is False


# ── 测试：search 返回格式 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_empty_when_no_index(rag):
    """collection 为空时 search 返回空列表"""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    rag.chroma_client.get_or_create_collection.return_value = mock_collection

    results = await rag.search(paper_id=1, query="test query")
    assert results == []


@pytest.mark.asyncio
async def test_search_result_format(rag):
    """search 返回的每条结果都包含必要字段"""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 2

    # 模拟 collection.query 结果
    mock_collection.query.return_value = {
        "ids": [["chunk_0", "chunk_1"]],
        "documents": [["doc text 0", "doc text 1"]],
        "metadatas": [[
            {"pages": json.dumps([1]), "chunk_index": 0},
            {"pages": json.dumps([2]), "chunk_index": 1},
        ]],
    }

    # 模拟 collection.get 结果（用于 BM25）
    mock_collection.get.return_value = {
        "ids": ["chunk_0", "chunk_1"],
        "documents": ["doc text 0", "doc text 1"],
        "metadatas": [
            {"pages": json.dumps([1]), "chunk_index": 0},
            {"pages": json.dumps([2]), "chunk_index": 1},
        ],
    }

    rag.chroma_client.get_or_create_collection.return_value = mock_collection

    # mock embedding model
    mock_model = MagicMock()
    import numpy as np
    mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

    with patch.object(
        RAGService,
        "embedding_model",
        new_callable=lambda: property(lambda self: _async_return(mock_model))
    ):
        results = await rag.search(paper_id=1, query="test", top_k=2)

    assert isinstance(results, list)
    for r in results:
        assert "text" in r
        assert "score" in r
        assert "pages" in r
        assert "chunk_index" in r


# ── 测试：delete_paper_index ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_paper_index_calls_delete_collection(rag):
    """delete_paper_index 调用 chroma_client.delete_collection"""
    await rag.delete_paper_index(paper_id=5)
    rag.chroma_client.delete_collection.assert_called_once_with(name="paper_5")


@pytest.mark.asyncio
async def test_delete_paper_index_clears_bm25_cache(rag):
    """delete_paper_index 清除对应的 BM25 缓存"""
    rag._bm25_cache["5"] = (MagicMock(), MagicMock())
    await rag.delete_paper_index(paper_id=5)
    assert "5" not in rag._bm25_cache


@pytest.mark.asyncio
async def test_delete_paper_index_handles_missing_collection(rag):
    """collection 不存在时 delete_paper_index 不应抛出异常"""
    rag.chroma_client.delete_collection.side_effect = Exception("not found")
    # 不应抛出
    await rag.delete_paper_index(paper_id=999)


# ── 测试：BM25 缓存命中 / 失效 ────────────────────────────────────────────────

def test_bm25_cache_hit(rag):
    """BM25 缓存命中时直接返回，不重新构建"""
    mock_bm25 = MagicMock()
    mock_all_docs = {"ids": ["c0"], "documents": ["text"], "metadatas": [{}]}
    rag._bm25_cache["1"] = (mock_bm25, mock_all_docs)

    mock_collection = MagicMock()
    result_bm25, result_docs = rag._get_or_build_bm25(paper_id=1, collection=mock_collection)

    assert result_bm25 is mock_bm25
    assert result_docs is mock_all_docs
    # 缓存命中时不应调用 collection.get
    mock_collection.get.assert_not_called()


def test_bm25_cache_miss_builds_index(rag):
    """BM25 缓存未命中时构建索引并存入缓存"""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["c0", "c1"],
        "documents": ["hello world", "foo bar baz"],
        "metadatas": [{}, {}],
    }

    result_bm25, result_docs = rag._get_or_build_bm25(paper_id=42, collection=mock_collection)

    assert "42" in rag._bm25_cache
    mock_collection.get.assert_called_once()


def test_invalidate_bm25_cache(rag):
    """invalidate_bm25_cache 正确移除缓存条目"""
    rag._bm25_cache["7"] = (MagicMock(), MagicMock())
    rag.invalidate_bm25_cache(paper_id=7)
    assert "7" not in rag._bm25_cache


def test_invalidate_bm25_cache_nonexistent_key_safe(rag):
    """invalidate_bm25_cache 对不存在的 key 不抛出异常"""
    rag.invalidate_bm25_cache(paper_id=9999)


# ── 测试：配置更新 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_config(rag):
    """update_config 正确更新运行时配置"""
    await rag.update_config(top_k=10, chunk_size=1000, chunk_overlap=300)
    assert rag._top_k == 10
    assert rag._chunk_size == 1000
    assert rag._chunk_overlap == 300


@pytest.mark.asyncio
async def test_update_config_partial(rag):
    """update_config 只更新传入的参数"""
    original_chunk_size = rag._chunk_size
    await rag.update_config(top_k=3)
    assert rag._top_k == 3
    assert rag._chunk_size == original_chunk_size  # 未传入，不变


# ── 测试：索引状态追踪 ─────────────────────────────────────────────────────────

def test_try_start_indexing(rag):
    """try_start_indexing 原子标记，重复调用返回 False"""
    assert rag.try_start_indexing(1) is True
    assert rag.try_start_indexing(1) is False  # 已在索引中


def test_finish_indexing(rag):
    """finish_indexing 清除标记"""
    rag._indexing_papers.add(2)
    rag.finish_indexing(2)
    assert not rag.is_indexing(2)


def test_is_indexing(rag):
    """is_indexing 正确反映状态"""
    assert rag.is_indexing(3) is False
    rag._indexing_papers.add(3)
    assert rag.is_indexing(3) is True


# ── 辅助：将普通值包装为 awaitable ───────────────────────────────────────────

async def _async_return(value):
    return value
