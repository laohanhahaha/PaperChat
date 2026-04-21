"""知识库服务

提供知识卡片的 CRUD、自动提取、标签生成、关联发现等功能
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, or_, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeCard, KnowledgeRelation
from app.models.highlight import Highlight
from app.models.paper import Paper
from app.services.llm_service import llm_service
from app.services.rag.rag_service import rag_service
from langchain_core.messages import SystemMessage, HumanMessage
from app.prompts.service import (  # 从 app.prompts 统一导入
    AUTO_TAG_PROMPT,
    FIND_RELATIONS_PROMPT,
    EXTRACT_FROM_HIGHLIGHT_PROMPT,
    EXTRACT_FROM_CHAT_PROMPT,
)

logger = logging.getLogger(__name__)


# AUTO_TAG_PROMPT 、FIND_RELATIONS_PROMPT 、EXTRACT_FROM_HIGHLIGHT_PROMPT 、EXTRACT_FROM_CHAT_PROMPT
# 已迁移至 app.prompts.service，此处通过顶部 import 引入


class KnowledgeService:
    """知识库服务类"""
    
    async def extract_from_highlight(
        self, 
        highlight_id: int, 
        user_id: int, 
        db: AsyncSession
    ) -> KnowledgeCard:
        """从高亮一键生成知识卡片
        
        Args:
            highlight_id: 高亮 ID
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            创建的知识卡片
        """
        # 获取高亮文本
        result = await db.execute(
            select(Highlight).where(
                and_(Highlight.id == highlight_id, Highlight.user_id == user_id)
            )
        )
        highlight = result.scalar_one_or_none()
        
        if not highlight:
            raise ValueError(f"高亮 {highlight_id} 不存在或无权限")
        
        # 使用 LLM 生成标题和摘要
        prompt = EXTRACT_FROM_HIGHLIGHT_PROMPT.format(highlight_text=highlight.selected_text)
        messages = [
            SystemMessage(content="你是一个专业的学术知识提取助手。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        try:
            # 解析 JSON 响应
            content = response.content.strip()
            # 移除可能的 markdown 代码块标记
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            extracted = json.loads(content)
        except (json.JSONDecodeError, KeyError) as e:
            # 如果解析失败，使用简单方式生成
            extracted = {
                "title": highlight.selected_text[:30] + "..." if len(highlight.selected_text) > 30 else highlight.selected_text,
                "content": highlight.selected_text,
                "summary": highlight.selected_text[:100] + "..." if len(highlight.selected_text) > 100 else highlight.selected_text
            }
        
        # 自动生成标签
        tags = await self.auto_tag(extracted["content"])
        
        # 创建知识卡片
        card = KnowledgeCard(
            user_id=user_id,
            title=extracted["title"],
            content=extracted["content"],
            summary=extracted.get("summary"),
            source_type="highlight",
            source_id=highlight_id,
            paper_id=highlight.paper_id,
            tags=tags,
            importance=1.0
        )
        
        db.add(card)
        await db.commit()
        await db.refresh(card)
        
        # 向量化索引
        await self.index_card(card)
        
        return card
    
    async def extract_from_chat(
        self, 
        message_content: str, 
        user_id: int, 
        paper_id: Optional[int],
        db: AsyncSession
    ) -> KnowledgeCard:
        """从问答回答中提取知识卡片
        
        Args:
            message_content: 问答内容
            user_id: 用户 ID
            paper_id: 关联论文 ID（可选）
            db: 数据库会话
            
        Returns:
            创建的知识卡片
        """
        # 使用 LLM 生成标题和摘要
        prompt = EXTRACT_FROM_CHAT_PROMPT.format(chat_content=message_content)
        messages = [
            SystemMessage(content="你是一个专业的学术知识提取助手。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm_service.llm.ainvoke(messages)
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            extracted = json.loads(content)
        except (json.JSONDecodeError, KeyError) as e:
            extracted = {
                "title": message_content[:30] + "..." if len(message_content) > 30 else message_content,
                "content": message_content,
                "summary": message_content[:100] + "..." if len(message_content) > 100 else message_content
            }
        
        # 自动生成标签
        tags = await self.auto_tag(extracted["content"])
        
        # 创建知识卡片
        card = KnowledgeCard(
            user_id=user_id,
            title=extracted["title"],
            content=extracted["content"],
            summary=extracted.get("summary"),
            source_type="chat",
            paper_id=paper_id,
            tags=tags,
            importance=1.0
        )
        
        db.add(card)
        await db.commit()
        await db.refresh(card)
        
        # 向量化索引
        await self.index_card(card)
        
        return card
    
    async def auto_tag(self, content: str) -> List[str]:
        """使用 LLM 自动生成标签
        
        Args:
            content: 内容文本
            
        Returns:
            标签列表
        """
        prompt = AUTO_TAG_PROMPT.format(content=content[:2000])  # 限制长度
        messages = [
            SystemMessage(content="你是一个专业的学术标签生成助手。"),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await llm_service.llm.ainvoke(messages)
            # 解析标签（每行一个）
            tags = [tag.strip() for tag in response.content.strip().split('\n') if tag.strip()]
            # 过滤掉可能的编号
            tags = [tag.lstrip('0123456789.- ') for tag in tags]
            return tags[:5]  # 最多返回 5 个标签
        except Exception as e:
            logger.error("自动生成标签失败", exc_info=True)
            return []
    
    async def find_relations(
        self, 
        card_id: int, 
        user_id: int, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """使用 LLM 识别知识卡片与现有卡片之间的关联
        
        Args:
            card_id: 新卡片 ID
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            关联列表
        """
        # 获取目标卡片
        result = await db.execute(
            select(KnowledgeCard).where(
                and_(KnowledgeCard.id == card_id, KnowledgeCard.user_id == user_id)
            )
        )
        new_card = result.scalar_one_or_none()
        
        if not new_card:
            raise ValueError(f"卡片 {card_id} 不存在或无权限")
        
        # 获取用户所有其他卡片
        result = await db.execute(
            select(KnowledgeCard).where(
                and_(
                    KnowledgeCard.user_id == user_id,
                    KnowledgeCard.id != card_id
                )
            )
        )
        existing_cards = result.scalars().all()
        
        if len(existing_cards) == 0:
            return []
        
        # 构建现有卡片描述
        cards_desc = []
        for card in existing_cards:
            summary = card.summary or card.content[:100]
            cards_desc.append(f"ID:{card.id} - {card.title}\n摘要：{summary}")
        
        # 调用 LLM 分析关联
        prompt = FIND_RELATIONS_PROMPT.format(
            new_title=new_card.title,
            new_summary=new_card.summary or new_card.content[:200],
            existing_cards="\n\n".join(cards_desc[:20])  # 限制卡片数量
        )
        
        messages = [
            SystemMessage(content="你是一个知识关联分析助手。"),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await llm_service.llm.ainvoke(messages)
            content = response.content.strip()
            
            # 解析 JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            relations = json.loads(content)
            
            # 验证并过滤结果
            valid_relations = []
            for rel in relations:
                if isinstance(rel, dict) and "target_card_id" in rel:
                    valid_relations.append({
                        "target_card_id": rel["target_card_id"],
                        "relation_type": rel.get("relation_type", "related"),
                        "description": rel.get("description", ""),
                        "confidence": rel.get("confidence", 0.8)
                    })
            
            return valid_relations
            
        except Exception as e:
            logger.error("发现关联失败", exc_info=True)
            return []
    
    async def search(
        self, 
        user_id: int, 
        query: str, 
        db: AsyncSession,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """知识库全局检索
        
        使用 RAG 向量检索 + 数据库关键词搜索
        
        Args:
            user_id: 用户 ID
            query: 查询文本
            db: 数据库会话
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        results = []
        vector_results = []
        
        # 1. 向量检索
        try:
            collection_name = f"knowledge_{user_id}"
            from app.services.rag.rag_service import rag_service
            
            # 获取 collection
            try:
                collection = rag_service.chroma_client.get_collection(name=collection_name)
                if collection.count() > 0:
                    model = await rag_service.embedding_model
                    import asyncio
                    loop = asyncio.get_event_loop()
                    query_embedding = await loop.run_in_executor(
                        rag_service._executor,
                        lambda: model.encode([query]).tolist()
                    )
                    
                    vector_results_data = collection.query(
                        query_embeddings=query_embedding,
                        n_results=min(top_k, collection.count())
                    )
                    
                    for i, doc_id in enumerate(vector_results_data["ids"][0]):
                        card_id = int(doc_id.replace("card_", ""))
                        vector_results.append({
                            "card_id": card_id,
                            "vector_score": vector_results_data["distances"][0][i]
                        })
            except Exception as e:
                logger.error("向量检索失败", exc_info=True)
        except Exception as e:
            logger.error("向量检索初始化失败", exc_info=True)
        
        # 2. 数据库关键词搜索
        keyword_pattern = f"%{query}%"
        result = await db.execute(
            select(KnowledgeCard).where(
                and_(
                    KnowledgeCard.user_id == user_id,
                    or_(
                        KnowledgeCard.title.ilike(keyword_pattern),
                        KnowledgeCard.content.ilike(keyword_pattern),
                        KnowledgeCard.tags.contains([query])
                    )
                )
            ).limit(top_k * 2)
        )
        keyword_cards = result.scalars().all()
        
        # 合并结果
        seen_ids = set()
        
        # 优先添加向量检索结果
        for vr in vector_results:
            if vr["card_id"] not in seen_ids:
                result = await db.execute(
                    select(KnowledgeCard).where(KnowledgeCard.id == vr["card_id"])
                )
                card = result.scalar_one_or_none()
                if card:
                    results.append({
                        "id": card.id,
                        "title": card.title,
                        "summary": card.summary,
                        "tags": card.tags,
                        "category": card.category,
                        "source_type": card.source_type,
                        "paper_id": card.paper_id,
                        "created_at": card.created_at.isoformat() if card.created_at else None,
                        "score": 1.0 - (vr["vector_score"] if vr["vector_score"] else 0)
                    })
                    seen_ids.add(card.id)
        
        # 添加关键词搜索结果
        for card in keyword_cards:
            if card.id not in seen_ids:
                results.append({
                    "id": card.id,
                    "title": card.title,
                    "summary": card.summary,
                    "tags": card.tags,
                    "category": card.category,
                    "source_type": card.source_type,
                    "paper_id": card.paper_id,
                    "created_at": card.created_at.isoformat() if card.created_at else None,
                    "score": 0.5  # 关键词匹配默认分数
                })
                seen_ids.add(card.id)
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    async def index_card(self, card: KnowledgeCard):
        """将知识卡片向量化存入 ChromaDB
        
        Args:
            card: 知识卡片对象
        """
        try:
            from app.services.rag.rag_service import rag_service
            
            collection_name = f"knowledge_{card.user_id}"
            collection = rag_service.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            # 准备文本（标题 + 内容 + 标签）
            text_parts = [card.title, card.content]
            if card.tags:
                text_parts.extend(card.tags)
            text = " ".join(text_parts)
            
            # 获取 embedding 模型
            model = await rag_service.embedding_model
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                rag_service._executor,
                lambda: model.encode([text]).tolist()
            )
            
            # 添加到 collection
            collection.add(
                documents=[text],
                embeddings=embedding,
                metadatas=[{
                    "card_id": card.id,
                    "title": card.title,
                    "category": card.category or ""
                }],
                ids=[f"card_{card.id}"]
            )
            
        except Exception as e:
            logger.error(f"索引知识卡片 {card.id} 失败", exc_info=True)
    
    async def delete_card_index(self, user_id: int, card_id: int):
        """删除知识卡片的向量索引
        
        Args:
            user_id: 用户 ID
            card_id: 卡片 ID
        """
        try:
            from app.services.rag.rag_service import rag_service
            collection_name = f"knowledge_{user_id}"
            collection = rag_service.chroma_client.get_collection(name=collection_name)
            collection.delete(ids=[f"card_{card_id}"])
        except Exception as e:
            logger.error(f"删除卡片索引 {card_id} 失败", exc_info=True)
    
    async def get_graph_data(
        self, 
        user_id: int, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """获取知识图谱数据（节点+边）
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            包含 nodes 和 edges 的字典
        """
        # 获取所有卡片
        result = await db.execute(
            select(KnowledgeCard).where(KnowledgeCard.user_id == user_id)
        )
        cards = result.scalars().all()
        
        # 获取所有关联
        card_ids = [c.id for c in cards]
        if card_ids:
            result = await db.execute(
                select(KnowledgeRelation).where(
                    or_(
                        KnowledgeRelation.source_card_id.in_(card_ids),
                        KnowledgeRelation.target_card_id.in_(card_ids)
                    )
                )
            )
            relations = result.scalars().all()
        else:
            relations = []
        
        # 构建节点
        nodes = []
        for card in cards:
            nodes.append({
                "id": card.id,
                "title": card.title,
                "summary": card.summary,
                "content": card.content,
                "tags": card.tags,
                "category": card.category,
                "importance": card.importance,
                "paper_id": card.paper_id,
                "source_type": card.source_type,
                "created_at": card.created_at.isoformat() if card.created_at else None
            })
        
        # 构建边
        edges = []
        for rel in relations:
            edges.append({
                "id": rel.id,
                "source": rel.source_card_id,
                "target": rel.target_card_id,
                "type": rel.relation_type,
                "description": rel.description,
                "confidence": rel.confidence
            })
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    async def get_stats(
        self, 
        user_id: int, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """获取知识库统计信息
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            
        Returns:
            统计信息字典
        """
        # 总卡片数
        result = await db.execute(
            select(func.count(KnowledgeCard.id)).where(KnowledgeCard.user_id == user_id)
        )
        total_cards = result.scalar()
        
        # 分类统计
        result = await db.execute(
            select(KnowledgeCard.category, func.count(KnowledgeCard.id))
            .where(KnowledgeCard.user_id == user_id)
            .group_by(KnowledgeCard.category)
        )
        category_stats = {cat or "未分类": count for cat, count in result.all()}
        
        # 来源类型统计
        result = await db.execute(
            select(KnowledgeCard.source_type, func.count(KnowledgeCard.id))
            .where(KnowledgeCard.user_id == user_id)
            .group_by(KnowledgeCard.source_type)
        )
        source_stats = {src or "未知": count for src, count in result.all()}
        
        # 标签云
        result = await db.execute(
            select(KnowledgeCard.tags).where(KnowledgeCard.user_id == user_id)
        )
        all_tags = []
        for (tags,) in result.all():
            if tags:
                all_tags.extend(tags)
        
        tag_cloud = {}
        for tag in all_tags:
            tag_cloud[tag] = tag_cloud.get(tag, 0) + 1
        
        # 关联数
        result = await db.execute(
            select(func.count(KnowledgeRelation.id))
            .join(KnowledgeCard, KnowledgeRelation.source_card_id == KnowledgeCard.id)
            .where(KnowledgeCard.user_id == user_id)
        )
        total_relations = result.scalar()
        
        return {
            "total_cards": total_cards,
            "total_relations": total_relations,
            "category_stats": category_stats,
            "source_stats": source_stats,
            "tag_cloud": tag_cloud
        }


# 全局单例
knowledge_service = KnowledgeService()
