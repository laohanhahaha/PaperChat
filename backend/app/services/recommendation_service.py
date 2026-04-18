"""论文推荐服务

提供基于内容相似性和用户画像的论文推荐功能
"""
import json
import logging
import numpy as np
from typing import List, Dict, Optional, Any
from datetime import datetime

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper, PaperTextBlock
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


class RecommendationService:
    """论文推荐服务类
    
    功能：
    1. 基于内容相似性推荐（余弦相似度）
    2. 基于用户画像的个性化推荐
    3. 论文嵌入向量计算与缓存
    """
    
    # 嵌入向量缓存 {paper_id: embedding_vector}
    _embedding_cache: Dict[int, List[float]] = {}
    
    # 运行时配置
    _top_k = 5  # 默认推荐数量
    
    async def update_config(self, top_k: int = None):
        """运行时更新推荐配置
        
        Args:
            top_k: 推荐数量
        """
        if top_k is not None:
            self._top_k = top_k
    
    async def _get_paper_text_for_embedding(self, paper_id: int, db: AsyncSession, max_length: int = 2000) -> str:
        """获取用于计算嵌入的论文文本（标题 + 前N字内容）
        
        Args:
            paper_id: 论文 ID
            db: 数据库会话
            max_length: 最大文本长度
            
        Returns:
            组合文本（标题 + 摘要 + 正文开头）
        """
        # 获取论文基本信息
        result = await db.execute(
            select(Paper).where(Paper.id == paper_id)
        )
        paper = result.scalar_one_or_none()
        
        if not paper:
            return ""
        
        # 组合文本：标题 + 作者 + 摘要
        text_parts = [paper.title]
        
        if paper.authors:
            text_parts.append(paper.authors)
        
        if paper.abstract:
            text_parts.append(paper.abstract)
        
        # 获取正文文本块（前N个）
        result = await db.execute(
            select(PaperTextBlock)
            .where(PaperTextBlock.paper_id == paper_id)
            .order_by(PaperTextBlock.page_number, PaperTextBlock.y0)
            .limit(20)  # 取前20个文本块
        )
        text_blocks = result.scalars().all()
        
        for block in text_blocks:
            text_parts.append(block.text)
        
        # 合并并截断
        full_text = " ".join(text_parts)
        return full_text[:max_length]
    
    async def compute_paper_embedding(self, paper_id: int, db: AsyncSession, use_cache: bool = True) -> Optional[List[float]]:
        """计算论文的整体嵌入向量
        
        Args:
            paper_id: 论文 ID
            db: 数据库会话
            use_cache: 是否使用缓存
            
        Returns:
            嵌入向量，计算失败返回 None
        """
        # 检查缓存
        if use_cache and paper_id in self._embedding_cache:
            return self._embedding_cache[paper_id]
        
        try:
            # 获取论文文本
            text = await self._get_paper_text_for_embedding(paper_id, db)
            
            if not text or len(text) < 50:
                return None
            
            # 使用 memory_service 的 embedding 模型
            model = await memory_service.embedding_model
            
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                memory_service._executor,
                lambda: model.encode([text])[0].tolist()
            )
            
            # 缓存结果
            self._embedding_cache[paper_id] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"计算论文 {paper_id} 嵌入失败", exc_info=True)
            return None
    
    async def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数（-1 到 1）
        """
        a = np.array(vec1)
        b = np.array(vec2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    async def get_similar_papers(
        self, 
        paper_id: int, 
        user_id: int, 
        db: AsyncSession,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """基于内容相似性推荐论文
            
        流程：
        1. 获取当前论文的嵌入向量
        2. 获取用户其他所有论文
        3. 计算余弦相似度
        4. 返回最相似的 top_k 篇
        
        Args:
            paper_id: 当前论文 ID
            user_id: 用户 ID
            db: 数据库会话
            top_k: 返回结果数量
            
        Returns:
            相似论文列表，包含相似度分数
        """
        # 使用传入参数或配置值
        top_k = top_k or self._top_k
        
        try:
            # 1. 获取当前论文的嵌入向量
            source_embedding = await self.compute_paper_embedding(paper_id, db)
            
            if not source_embedding:
                return []
            
            # 2. 获取用户其他论文（排除当前论文）
            result = await db.execute(
                select(Paper).where(
                    and_(
                        Paper.user_id == user_id,
                        Paper.id != paper_id
                    )
                )
            )
            other_papers = result.scalars().all()
            
            if not other_papers:
                return []
            
            # 3. 计算相似度
            scored_papers = []
            
            for paper in other_papers:
                # 获取论文嵌入
                paper_embedding = await self.compute_paper_embedding(paper.id, db)
                
                if paper_embedding:
                    similarity = await self._cosine_similarity(source_embedding, paper_embedding)
                    
                    # 转换为百分比（0-100）
                    similarity_percent = max(0, (similarity + 1) / 2 * 100)
                    
                    scored_papers.append({
                        "paper": paper,
                        "similarity": similarity_percent,
                        "raw_similarity": similarity
                    })
            
            # 4. 按相似度排序并取 top_k
            scored_papers.sort(key=lambda x: x["similarity"], reverse=True)
            top_papers = scored_papers[:top_k]
            
            # 5. 组装结果
            recommendations = []
            for item in top_papers:
                paper = item["paper"]
                
                # 获取摘要预览（前100字）
                abstract_preview = ""
                if paper.abstract:
                    abstract_preview = paper.abstract[:100] + "..." if len(paper.abstract) > 100 else paper.abstract
                else:
                    # 从文本块获取预览
                    result = await db.execute(
                        select(PaperTextBlock)
                        .where(PaperTextBlock.paper_id == paper.id)
                        .limit(3)
                    )
                    blocks = result.scalars().all()
                    preview_text = " ".join([b.text for b in blocks])
                    abstract_preview = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
                
                recommendations.append({
                    "id": paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "similarity": round(item["similarity"], 1),
                    "abstract_preview": abstract_preview,
                    "page_count": paper.page_count,
                    "reading_status": paper.reading_status,
                    "category": paper.category,
                    "created_at": paper.created_at.isoformat() if paper.created_at else None
                })
            
            return recommendations
            
        except Exception as e:
            logger.error("获取相似论文失败", exc_info=True)
            return []
    
    async def get_personalized_recommendations(
        self, 
        user_id: int, 
        db: AsyncSession, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """基于用户画像的个性化推荐
        
        流程：
        1. 从 memory_service 获取用户画像
        2. 将用户画像文本向量化
        3. 与用户所有论文计算相似度
        4. 优先推荐未读或阅读中的论文
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            top_k: 返回结果数量
            
        Returns:
            个性化推荐论文列表
        """
        try:
            # 1. 构建用户画像文本
            profile = await memory_service.build_user_profile(user_id, db)
            
            if profile.get("total_memories", 0) == 0:
                # 没有用户画像，返回最近上传的论文
                return await self._get_recent_papers(user_id, db, top_k)
            
            # 构建画像文本
            profile_text_parts = []
            
            # 研究兴趣
            for interest in profile.get("research_interests", []):
                profile_text_parts.append(interest["content"])
            
            # 术语使用
            for term in profile.get("term_usages", []):
                profile_text_parts.append(term["content"])
            
            # 背景信息
            for bg in profile.get("backgrounds", []):
                profile_text_parts.append(bg["content"])
            
            if not profile_text_parts:
                return await self._get_recent_papers(user_id, db, top_k)
            
            profile_text = " ".join(profile_text_parts)
            
            # 2. 计算用户画像嵌入向量
            model = await memory_service.embedding_model
            import asyncio
            loop = asyncio.get_event_loop()
            profile_embedding = await loop.run_in_executor(
                memory_service._executor,
                lambda: model.encode([profile_text])[0].tolist()
            )
            
            # 3. 获取用户所有论文
            result = await db.execute(
                select(Paper).where(Paper.user_id == user_id)
            )
            user_papers = result.scalars().all()
            
            if not user_papers:
                return []
            
            # 4. 计算与每篇论文的相似度
            scored_papers = []
            
            for paper in user_papers:
                paper_embedding = await self.compute_paper_embedding(paper.id, db)
                
                if paper_embedding:
                    similarity = await self._cosine_similarity(profile_embedding, paper_embedding)
                    similarity_percent = max(0, (similarity + 1) / 2 * 100)
                    
                    # 阅读状态权重：未读 > 阅读中 > 已完成
                    status_weight = {
                        "unread": 1.2,
                        "reading": 1.1,
                        "finished": 0.8
                    }.get(paper.reading_status, 1.0)
                    
                    # 时间衰减：最近上传的论文权重略高
                    time_weight = 1.0
                    if paper.created_at:
                        days_since = (datetime.utcnow() - paper.created_at.replace(tzinfo=None)).days
                        time_weight = max(0.8, 1.0 - days_since / 365)  # 一年内从1.0衰减到0.8
                    
                    final_score = similarity_percent * status_weight * time_weight
                    
                    scored_papers.append({
                        "paper": paper,
                        "similarity": similarity_percent,
                        "final_score": final_score,
                        "raw_similarity": similarity
                    })
            
            # 5. 按最终分数排序
            scored_papers.sort(key=lambda x: x["final_score"], reverse=True)
            top_papers = scored_papers[:top_k]
            
            # 6. 组装结果
            recommendations = []
            for item in top_papers:
                paper = item["paper"]
                
                # 获取摘要预览
                abstract_preview = ""
                if paper.abstract:
                    abstract_preview = paper.abstract[:100] + "..." if len(paper.abstract) > 100 else paper.abstract
                else:
                    result = await db.execute(
                        select(PaperTextBlock)
                        .where(PaperTextBlock.paper_id == paper.id)
                        .limit(3)
                    )
                    blocks = result.scalars().all()
                    preview_text = " ".join([b.text for b in blocks])
                    abstract_preview = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
                
                recommendations.append({
                    "id": paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "similarity": round(item["similarity"], 1),
                    "match_reason": self._generate_match_reason(paper, profile),
                    "abstract_preview": abstract_preview,
                    "page_count": paper.page_count,
                    "reading_status": paper.reading_status,
                    "category": paper.category,
                    "created_at": paper.created_at.isoformat() if paper.created_at else None
                })
            
            return recommendations
            
        except Exception as e:
            logger.error("获取个性化推荐失败", exc_info=True)
            return []
    
    async def _get_recent_papers(
        self, 
        user_id: int, 
        db: AsyncSession, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """获取最近上传的论文（作为无画像时的备选）
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            top_k: 返回数量
            
        Returns:
            最近论文列表
        """
        try:
            result = await db.execute(
                select(Paper)
                .where(Paper.user_id == user_id)
                .order_by(Paper.created_at.desc())
                .limit(top_k)
            )
            papers = result.scalars().all()
            
            recommendations = []
            for paper in papers:
                abstract_preview = ""
                if paper.abstract:
                    abstract_preview = paper.abstract[:100] + "..." if len(paper.abstract) > 100 else paper.abstract
                else:
                    result = await db.execute(
                        select(PaperTextBlock)
                        .where(PaperTextBlock.paper_id == paper.id)
                        .limit(3)
                    )
                    blocks = result.scalars().all()
                    preview_text = " ".join([b.text for b in blocks])
                    abstract_preview = preview_text[:100] + "..." if len(preview_text) > 100 else preview_text
                
                recommendations.append({
                    "id": paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "similarity": None,  # 无相似度数据
                    "match_reason": "最近上传",
                    "abstract_preview": abstract_preview,
                    "page_count": paper.page_count,
                    "reading_status": paper.reading_status,
                    "category": paper.category,
                    "created_at": paper.created_at.isoformat() if paper.created_at else None
                })
            
            return recommendations
            
        except Exception as e:
            logger.error("获取最近论文失败", exc_info=True)
            return []
    
    def _generate_match_reason(self, paper: Paper, profile: Dict[str, Any]) -> str:
        """生成匹配原因说明
        
        Args:
            paper: 论文对象
            profile: 用户画像
            
        Returns:
            匹配原因文本
        """
        reasons = []
        
        # 根据阅读状态
        if paper.reading_status == "unread":
            reasons.append("未读")
        elif paper.reading_status == "reading":
            reasons.append("阅读中")
        
        # 根据画像匹配
        if profile.get("research_interests"):
            reasons.append("匹配研究兴趣")
        
        if not reasons:
            return "基于您的阅读历史"
        
        return "、".join(reasons)
    
    def clear_cache(self, paper_id: Optional[int] = None):
        """清除嵌入缓存
        
        Args:
            paper_id: 指定论文 ID，为 None 则清除全部
        """
        if paper_id is not None:
            self._embedding_cache.pop(paper_id, None)
        else:
            self._embedding_cache.clear()
    
    async def search_web_recommendations(self, paper_id: int, db: AsyncSession, max_results: int = 8) -> List[Dict[str, Any]]:
        """从网络搜索相关学术文献
        
        Args:
            paper_id: 当前论文 ID
            db: 数据库会话
            max_results: 最大返回结果数
            
        Returns:
            网络学术文献推荐列表
        """
        from app.services.search_service import search_service
        
        # 获取论文信息
        result = await db.execute(
            select(Paper).where(Paper.id == paper_id)
        )
        paper = result.scalar_one_or_none()
        
        if not paper:
            return []
        
        # 用论文标题构建学术搜索查询
        title = paper.title[:80] if paper.title else ""
        if not title:
            return []
        
        # 构建学术搜索查询（限定学术网站）
        academic_query = f"{title} site:arxiv.org OR site:scholar.google.com OR site:researchgate.net OR site:semanticscholar.org"
        
        try:
            results = await search_service.search(
                query=academic_query,
                max_results=max_results,
                region="wt-wt",
                timelimit="y"  # 最近一年
            )
            
            # 分类来源并格式化
            formatted = []
            for r in results:
                url = r.get('href', '')
                source = 'Academic'
                if 'arxiv.org' in url:
                    source = 'arXiv'
                elif 'scholar.google' in url:
                    source = 'Google Scholar'
                elif 'researchgate.net' in url:
                    source = 'ResearchGate'
                elif 'semanticscholar.org' in url:
                    source = 'Semantic Scholar'
                
                formatted.append({
                    'title': r.get('title', '未知标题'),
                    'url': url,
                    'abstract': r.get('body', ''),
                    'source': source,
                })
            
            return formatted
        except Exception as e:
            logger.error(f"学术搜索失败: {str(e)}")
            return []


# 全局单例
recommendation_service = RecommendationService()
