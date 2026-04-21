"""RAG 检索服务

提供基于 ChromaDB 的向量检索和 BM25 混合检索功能
"""
import os
import json
import asyncio
import logging
import time
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索服务类
    
    功能：
    1. 论文文本智能分块
    2. 向量化存储到 ChromaDB
    3. 混合检索（语义检索 + BM25关键词检索）
    4. 结果重排序（RRF融合算法）
    """
    
    def __init__(self):
        # ChromaDB 持久化存储路径
        chroma_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
        os.makedirs(chroma_db_path, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Embedding 模型（使用小型多语言模型，适合学术中英文）
        # 注意：首次加载需要下载模型，约400MB
        self._embedding_model = None
        self._model_lock = asyncio.Lock()
        
        # 线程池用于同步模型的异步调用
        self._executor = ThreadPoolExecutor(max_workers=min(4, (os.cpu_count() or 4) + 1))
        
        # BM25 索引缓存（paper_id -> (bm25_instance, all_docs)）
        self._bm25_cache: Dict[str, Tuple] = {}

        # 索引状态追踪（正在索引的论文ID集合）
        self._indexing_papers: set = set()

        # 运行时配置
        self._top_k = 5  # 默认检索数量
        self._chunk_size = 800  # 默认分块大小
        self._chunk_overlap = 200  # 默认块重叠
    
    async def update_config(
        self,
        top_k: int = None,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """运行时更新 RAG 配置
        
        注意：chunk_size 和 chunk_overlap 只影响新建索引的论文，
        已索引的论文需要重新索引才能生效。
        
        Args:
            top_k: 检索数量（立即生效）
            chunk_size: 分块大小（仅影响新索引）
            chunk_overlap: 块重叠（仅影响新索引）
        """
        if top_k is not None:
            self._top_k = top_k
        if chunk_size is not None:
            self._chunk_size = chunk_size
        if chunk_overlap is not None:
            self._chunk_overlap = chunk_overlap
    
    @property
    async def embedding_model(self):
        """懒加载 Embedding 模型
        
        首次访问时才加载模型，避免后端启动时阻塞。
        模型加载约需 2-3 秒，仅在首次使用时发生。
        """
        if self._embedding_model is None:
            async with self._model_lock:
                if self._embedding_model is None:
                    # 延迟导入，避免启动时加载
                    from sentence_transformers import SentenceTransformer
                    # 在线程池中加载模型，避免阻塞事件循环
                    loop = asyncio.get_event_loop()
                    self._embedding_model = await loop.run_in_executor(
                        self._executor,
                        lambda: SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    )
        return self._embedding_model
    
    def get_or_create_collection(self, paper_id: int) -> chromadb.Collection:
        """为每篇论文创建/获取独立的 collection"""
        return self.chroma_client.get_or_create_collection(
            name=f"paper_{paper_id}",
            metadata={"hnsw:space": "cosine"}
        )
    
    def smart_chunk_text(self, text_blocks: List[Dict[str, Any]], chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """智能分块策略
            
        策略：
        - 按文本块自然边界分块
        - 每块 500-1000 字
        - 相邻块有 200 字重叠
        - 保留页码信息
    
        Args:
            text_blocks: 文本块列表，每个块包含 text, page_number 等
            chunk_size: 目标块大小（字符数），None 则使用配置值
            overlap: 相邻块重叠字符数，None 则使用配置值
                
        Returns:
            分块后的列表，每个块包含 text 和 metadata
        """
        # 使用传入参数或配置值
        chunk_size = chunk_size or self._chunk_size
        overlap = overlap or self._chunk_overlap
        chunks = []
        current_chunk = ""
        current_meta = {"pages": [], "start_block": 0}
        
        for i, block in enumerate(text_blocks):
            text = block.get("text", "").strip()
            if not text:
                continue
                
            page = block.get("page_number", 0)
            
            # 如果当前块加上新文本超过目标大小，且当前块不为空，则保存当前块
            if len(current_chunk) + len(text) > chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": {
                        "pages": list(set(current_meta["pages"])),
                        "chunk_index": len(chunks)
                    }
                })
                # 保留 overlap 部分作为下一块的开头
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + " " + text
                current_meta = {"pages": [page], "start_block": i}
            else:
                current_chunk += " " + text if current_chunk else text
                if page not in current_meta["pages"]:
                    current_meta["pages"].append(page)
        
        # 保存最后一个块
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {
                    "pages": list(set(current_meta["pages"])),
                    "chunk_index": len(chunks)
                }
            })
        
        return chunks
    
    def _get_or_build_bm25(self, paper_id, collection):
        """获取或构建 BM25 索引（带缓存）

        首次调用时从 collection 获取所有文档并构建 BM25 索引，
        后续调用直接返回缓存，避免重复构建（节省 100-500ms）。
        """
        cache_key = str(paper_id)
        if cache_key in self._bm25_cache:
            return self._bm25_cache[cache_key]

        all_docs = collection.get()
        tokenized = [doc.split() for doc in all_docs["documents"]]
        bm25 = BM25Okapi(tokenized)
        self._bm25_cache[cache_key] = (bm25, all_docs)
        return bm25, all_docs

    def invalidate_bm25_cache(self, paper_id):
        """索引重建或删除时清除缓存"""
        self._bm25_cache.pop(str(paper_id), None)

    async def delete_index(self, paper_id: int):
        """清理指定论文的 ChromaDB collection 和 BM25 缓存"""
        collection_name = f"paper_{paper_id}"
        try:
            self.chroma_client.delete_collection(collection_name)
            logger.info(f"Deleted ChromaDB collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Collection {collection_name} not found or already deleted: {e}")
        # 清理 BM25 缓存
        self.invalidate_bm25_cache(paper_id)
        # 从索引状态集合中移除
        self._indexing_papers.discard(paper_id)

    async def rebuild_index(self, paper_id: int):
        """重新构建指定论文的索引（先删除后重建）"""
        from app.database import AsyncSessionLocal
        from app.services.core.event_bus import event_bus, Event, EventTypes

        await event_bus.publish(Event(
            type=EventTypes.INDEX_REBUILD_STARTED,
            data={'paper_id': paper_id}
        ))
        try:
            async with AsyncSessionLocal() as db:
                # 先删除旧索引
                await self.delete_index(paper_id)
                # 从数据库获取论文信息
                from app.models.paper import Paper
                paper = await db.get(Paper, paper_id)
                if not paper:
                    raise ValueError(f"Paper {paper_id} not found")
                # 重新解析获取文本块
                from app.services.paper.pdf_service import pdf_service
                text_blocks = await pdf_service.extract_text_blocks(paper.file_path)
                # 重新构建索引
                await self.index_paper(paper_id, text_blocks)
            await event_bus.publish(Event(
                type=EventTypes.INDEX_REBUILD_COMPLETED,
                data={'paper_id': paper_id, 'success': True}
            ))
        except Exception as e:
            logger.error(f"Failed to rebuild index for paper {paper_id}: {e}")
            await event_bus.publish(Event(
                type=EventTypes.INDEX_REBUILD_COMPLETED,
                data={'paper_id': paper_id, 'success': False, 'error': str(e)}
            ))
            raise

    async def get_index_status(self, paper_id: int) -> Dict[str, Any]:
        """返回索引状态"""
        collection_name = f"paper_{paper_id}"
        is_indexing = paper_id in self._indexing_papers
        try:
            collection = self.chroma_client.get_collection(collection_name)
            count = collection.count()
            return {'paper_id': paper_id, 'status': 'indexing' if is_indexing else 'ready', 'chunk_count': count}
        except Exception:
            return {'paper_id': paper_id, 'status': 'indexing' if is_indexing else 'not_indexed', 'chunk_count': 0}

    async def index_paper(self, paper_id: int, text_blocks: List[Dict[str, Any]], max_retries: int = 2) -> bool:
        """将论文文本块向量化并存入 ChromaDB

        Args:
            paper_id: 论文 ID
            text_blocks: 文本块列表
            max_retries: 最大重试次数

        Returns:
            是否成功建立索引
        """
        from app.services.core.event_bus import event_bus, Event, EventTypes

        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                collection = self.get_or_create_collection(paper_id)

                # 检查是否已建立索引
                if collection.count() > 0:
                    await event_bus.publish(Event(
                        type=EventTypes.INDEX_REBUILD_COMPLETED,
                        data={'paper_id': paper_id, 'success': True}
                    ))
                    return True  # 已索引，跳过

                chunks = self.smart_chunk_text(text_blocks)
                if not chunks:
                    await event_bus.publish(Event(
                        type=EventTypes.INDEX_REBUILD_COMPLETED,
                        data={'paper_id': paper_id, 'success': False, 'error': 'No chunks generated'}
                    ))
                    return False

                texts = [c["text"] for c in chunks]
                metadatas = [c["metadata"] for c in chunks]
                ids = [f"chunk_{i}" for i in range(len(chunks))]

                # 获取 embedding 模型并编码
                model = await self.embedding_model
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    self._executor,
                    lambda: model.encode(texts).tolist()
                )

                # 将 metadata 中的 list 转为 JSON 字符串（ChromaDB 不支持 list 值）
                for m in metadatas:
                    m["pages"] = json.dumps(m["pages"])

                collection.add(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )

                duration_ms = round((time.time() - start_time) * 1000)
                logger.info(f"RAG index_paper completed", extra={"paper_id": paper_id, "duration_ms": duration_ms, "chunk_count": len(chunks)})

                await event_bus.publish(Event(
                    type=EventTypes.INDEX_REBUILD_COMPLETED,
                    data={'paper_id': paper_id, 'success': True}
                ))
                return True

            except Exception as e:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # 2s, 4s
                    logger.warning(f"Index attempt {attempt+1} failed for paper {paper_id}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All index attempts failed for paper {paper_id}: {e}")
                    await event_bus.publish(Event(
                        type=EventTypes.INDEX_REBUILD_COMPLETED,
                        data={'paper_id': paper_id, 'success': False, 'error': str(e)}
                    ))
                    return False
    
    async def search(self, paper_id: int, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """混合检索：语义检索 + BM25 关键词检索，结果重排序
    
        使用 RRF (Reciprocal Rank Fusion) 算法融合两种检索结果
    
        Args:
            paper_id: 论文 ID
            query: 查询文本
            top_k: 返回结果数量，None 则使用配置值
                
        Returns:
            检索结果列表，包含 text, score, pages, chunk_index
        """
        # 使用传入参数或配置值
        top_k = top_k or self._top_k
        start_time = time.time()
        try:
            collection = self.get_or_create_collection(paper_id)
            
            if collection.count() == 0:
                return []
            
            # 1. 语义检索
            model = await self.embedding_model
            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                self._executor,
                lambda: model.encode([query]).tolist()
            )
            
            semantic_results = collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k * 2, collection.count())
            )
            
            # 2. BM25 关键词检索（使用缓存）
            bm25, all_docs = self._get_or_build_bm25(paper_id, collection)
            bm25_scores = bm25.get_scores(query.split())
            
            # 3. 融合排序（RRF - Reciprocal Rank Fusion）
            # RRF 公式：score = Σ 1/(k + rank)，k=60 是常数
            K = 60  # RRF 常数
            doc_scores: Dict[str, float] = {}
            
            # 语义检索排名得分
            for i, doc_id in enumerate(semantic_results["ids"][0]):
                doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (K + i + 1)
            
            # BM25 排名得分
            bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)
            for rank, (idx, score) in enumerate(bm25_ranked[:top_k * 2]):
                doc_id = all_docs["ids"][idx]
                doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (K + rank + 1)
            
            # 4. 按融合分数排序
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            
            # 5. 组装结果
            results = []
            for doc_id, score in sorted_docs:
                idx = all_docs["ids"].index(doc_id)
                metadata = all_docs["metadatas"][idx]
                pages = json.loads(metadata.get("pages", "[]"))
                results.append({
                    "text": all_docs["documents"][idx],
                    "score": score,
                    "pages": pages,
                    "chunk_index": metadata.get("chunk_index", 0)
                })
            
            duration_ms = round((time.time() - start_time) * 1000)
            logger.info(f"RAG search completed", extra={"paper_id": paper_id, "duration_ms": duration_ms, "results_count": len(results)})
            
            return results
            
        except Exception as e:
            logger.error(f"检索论文 {paper_id} 失败", exc_info=True)
            return []
    
    async def search_multiple_papers(self, paper_ids: List[int], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """跨论文检索
        
        Args:
            paper_ids: 论文 ID 列表
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表，包含 paper_id, text, score, pages, chunk_index
        """
        # 并行检索所有论文
        tasks = [self.search(pid, query, top_k=3) for pid in paper_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果，跳过异常
        all_results = []
        for paper_id, result in zip(paper_ids, results_list):
            if isinstance(result, Exception):
                logger.error(f"跨论文检索 {paper_id} 失败: {result}")
                continue
            for r in result:
                r["paper_id"] = paper_id
            all_results.extend(result)

        # 按分数排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]
    
    async def delete_paper_index(self, paper_id: int) -> bool:
        """删除论文的向量索引
        
        Args:
            paper_id: 论文 ID
            
        Returns:
            是否成功删除
        """
        self.invalidate_bm25_cache(paper_id)
        try:
            collection_name = f"paper_{paper_id}"
            self.chroma_client.delete_collection(name=collection_name)
            return True
        except Exception as e:
            logger.error(f"删除论文 {paper_id} 索引失败", exc_info=True)
            return False
    
    async def reindex_paper(self, paper_id: int, text_blocks: List[Dict[str, Any]]) -> bool:
        """重建论文向量索引
        
        Args:
            paper_id: 论文 ID
            text_blocks: 文本块列表
            
        Returns:
            是否成功重建索引
        """
        # 清除旧缓存
        self.invalidate_bm25_cache(paper_id)
        # 先删除旧索引
        await self.delete_paper_index(paper_id)
        # 重新建立索引
        return await self.index_paper(paper_id, text_blocks)
    
    def is_indexing(self, paper_id: int) -> bool:
        """检查论文是否正在索引"""
        return paper_id in self._indexing_papers

    def try_start_indexing(self, paper_id: int) -> bool:
        """原子检查+标记。若已在索引中返回 False，否则标记并返回 True"""
        if paper_id in self._indexing_papers:
            return False
        self._indexing_papers.add(paper_id)
        return True

    def finish_indexing(self, paper_id: int):
        """标记索引完成"""
        self._indexing_papers.discard(paper_id)

    async def reindex_paper_async(self, paper_id: int, blocks_data: list):
        """异步重建索引（带状态追踪）

        注意：此方法由调用方负责调用 try_start_indexing 和 finish_indexing
        如需原子操作，请使用 try_start_indexing + finish_indexing 组合
        """
        self._indexing_papers.add(paper_id)
        try:
            await self.reindex_paper(paper_id, blocks_data)
        finally:
            self._indexing_papers.discard(paper_id)


# 全局单例
rag_service = RAGService()
