"""预缓存服务 — 后台异步预缓存用户关注领域的论文元数据

默认关闭（PRECACHE_ENABLED=False），用户手动开启。
后台任务不影响主线程性能。
"""

import asyncio
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".cache",
    "precache_data.json",
)

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".cache",
    "precache_config.json",
)


class PrecacheService:
    """主动预缓存服务"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._cache = {}  # {query: {results, cached_at}}
        self._cache_ttl = 3600 * 24  # 24小时
        self._papers: List[dict] = []
        self._cache_file = CACHE_FILE
        self._config_file = CONFIG_FILE
        self._bm25: Optional[BM25Okapi] = None
        self._tokenized_corpus: List[List[str]] = []
        self._topics: List[str] = ["cs.AI"]
        self._load_config_from_disk()
        self._load_from_disk()

    async def start(self):
        """启动预缓存后台任务"""
        from app.config import settings

        if not getattr(settings, "PRECACHE_ENABLED", False):
            logger.info("预缓存服务未启用")
            return

        logger.info("启动预缓存后台任务")
        self._task = asyncio.create_task(self._precache_loop())

    async def stop(self):
        """停止预缓存"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _precache_loop(self):
        """后台定时预缓存循环"""
        while True:
            try:
                await self._do_precache()
            except Exception as e:
                logger.error(f"预缓存出错: {e}")
            await asyncio.sleep(3600)  # 每小时执行一次

    async def _do_precache(self):
        """执行预缓存：获取用户关注领域，预缓存热门论文元数据"""
        logger.info("执行预缓存检查...")
        self._cleanup_expired()

        all_papers: List[dict] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for topic in self._topics:
                    params = {
                        "search_query": f"cat:{topic}",
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                        "max_results": 50,
                    }
                    response = await client.get(
                        "http://export.arxiv.org/api/query", params=params
                    )
                    response.raise_for_status()
                    papers = self._parse_arxiv_xml(response.text)
                    all_papers.extend(papers)
                    logger.info(f"主题 {topic} 预缓存 {len(papers)} 条论文")

            # 按 arxiv_id 去重
            seen: set = set()
            unique_papers = []
            for paper in all_papers:
                arxiv_id = paper.get("arxiv_id", "")
                if arxiv_id and arxiv_id not in seen:
                    seen.add(arxiv_id)
                    unique_papers.append(paper)

            self._papers = unique_papers
            self._save_to_disk()
            self._build_bm25()
            logger.info(
                f"预缓存完成，共缓存 {len(unique_papers)} 条论文元数据（去重后）"
            )
        except Exception as e:
            logger.error(f"预缓存获取失败: {e}")

    def _parse_arxiv_xml(self, xml_text: str) -> List[dict]:
        """解析 arXiv Atom XML 响应"""
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []

        for entry in root.findall("atom:entry", ns):
            id_elem = entry.find("atom:id", ns)
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            published_elem = entry.find("atom:published", ns)
            author_elems = entry.findall("atom:author/atom:name", ns)

            arxiv_id = ""
            if id_elem is not None and id_elem.text:
                raw_id = id_elem.text.strip()
                if "/abs/" in raw_id:
                    arxiv_id = raw_id.split("/abs/")[-1].split("v")[0]
                else:
                    arxiv_id = raw_id

            title = (title_elem.text or "").strip().replace("\n", " ") if title_elem is not None else ""
            abstract = (summary_elem.text or "").strip().replace("\n", " ") if summary_elem is not None else ""
            published = (published_elem.text or "").strip() if published_elem is not None else ""
            authors = [a.text.strip() for a in author_elems if a.text]

            papers.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "published": published,
                    "cached_at": datetime.now().isoformat(),
                }
            )

        return papers

    def _save_to_disk(self):
        """将缓存数据持久化到本地 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._papers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存预缓存到磁盘失败: {e}")

    def _save_config_to_disk(self):
        """将主题配置持久化到本地 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump({"topics": self._topics}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存预缓存配置到磁盘失败: {e}")

    def _load_config_from_disk(self):
        """从本地 JSON 文件加载主题配置"""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                topics = config.get("topics", [])
                if topics and isinstance(topics, list):
                    self._topics = topics
                    logger.info(f"从磁盘加载预缓存主题: {self._topics}")
        except Exception as e:
            logger.error(f"从磁盘加载预缓存配置失败: {e}")

    def update_topics(self, topics: List[str]) -> None:
        """更新关注的 arXiv 主题列表

        Args:
            topics: arXiv 分类代码列表
        """
        self._topics = list(dict.fromkeys([t.strip() for t in topics if t.strip()]))
        self._save_config_to_disk()
        logger.info(f"更新预缓存主题: {self._topics}")

    def get_topics(self) -> List[str]:
        """获取当前关注的 arXiv 主题列表"""
        return self._topics.copy()

    def _load_from_disk(self):
        """从本地 JSON 文件加载缓存数据"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._papers = json.load(f)
                self._build_bm25()
                logger.info(f"从磁盘加载预缓存 {len(self._papers)} 条论文元数据")
        except Exception as e:
            logger.error(f"从磁盘加载预缓存失败: {e}")
            self._papers = []

    def _build_bm25(self):
        """基于当前缓存论文构建 BM25 索引"""
        if not self._papers:
            self._bm25 = None
            self._tokenized_corpus = []
            return

        self._tokenized_corpus = []
        for paper in self._papers:
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
            tokens = self._tokenize(text)
            self._tokenized_corpus.append(tokens)

        self._bm25 = BM25Okapi(self._tokenized_corpus)

    def _tokenize(self, text: str) -> List[str]:
        """轻量级分词：按空格和标点分割，转小写"""
        return [t.lower() for t in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text)]

    def search_cached(self, query: str, top_k: int = 10) -> List[dict]:
        """对缓存的论文元数据进行 BM25 关键词匹配

        Args:
            query: 搜索查询
            top_k: 返回的最大结果数

        Returns:
            按相关性分数降序排列的结果列表
        """
        if not self._papers or self._bm25 is None:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        indexed = [(i, float(scores[i])) for i in range(len(scores))]
        indexed.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed[:top_k]:
            paper = self._papers[idx].copy()
            paper["score"] = score
            paper["source"] = "offline_cache"
            results.append(paper)

        return results

    def is_cache_available(self) -> bool:
        """检查缓存数据是否存在且非空"""
        return len(self._papers) > 0

    def _cleanup_expired(self):
        """清理过期缓存"""
        now = datetime.now().timestamp()
        expired = [
            k
            for k, v in self._cache.items()
            if now - v.get("cached_at", 0) > self._cache_ttl
        ]
        for k in expired:
            del self._cache[k]
        if expired:
            logger.info(f"清理 {len(expired)} 条过期预缓存")

    def get_cached(self, query: str) -> Optional[dict]:
        """获取预缓存结果"""
        entry = self._cache.get(query)
        if entry and (
            datetime.now().timestamp() - entry["cached_at"] < self._cache_ttl
        ):
            return entry["results"]
        return None

    def set_cached(self, query: str, results: dict):
        """设置预缓存"""
        self._cache[query] = {
            "results": results,
            "cached_at": datetime.now().timestamp(),
        }


# 全局单例
precache_service = PrecacheService()
