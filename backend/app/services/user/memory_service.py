"""用户记忆服务

提供用户长期记忆的提取、存储、召回和管理功能
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer
import numpy as np

from app.models.memory import UserMemory
from app.config import settings
from app.prompts.service import MEMORY_EXTRACTION_PROMPT  # 从 app.prompts 统一导入

logger = logging.getLogger(__name__)


class MemoryService:
    """用户记忆管理服务"""
    
    def __init__(self):
        self._embedding_model = None
        self._model_lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    @property
    async def embedding_model(self) -> SentenceTransformer:
        """懒加载 Embedding 模型"""
        if self._embedding_model is None:
            async with self._model_lock:
                if self._embedding_model is None:
                    loop = asyncio.get_event_loop()
                    self._embedding_model = await loop.run_in_executor(
                        self._executor,
                        lambda: SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    )
        return self._embedding_model
    
    async def _get_embedding(self, text: str) -> List[float]:
        """获取文本的向量嵌入"""
        model = await self.embedding_model
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            self._executor,
            lambda: model.encode([text])[0].tolist()
        )
        return embedding
    
    async def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    async def extract_memory(
        self, 
        user_id: int, 
        question: str, 
        answer: str, 
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """从对话中提取值得记忆的信息
        
        使用 LLM 判断对话中是否包含：
        - 用户研究方向/兴趣
        - 用户偏好（语言、回答风格等）
        - 重要的学术概念理解
        
        Returns:
            提取的记忆列表，每个记忆包含 type 和 content
        """
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        try:
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com",
                temperature=0.3,
                max_tokens=1000,
            )
            
            prompt = MEMORY_EXTRACTION_PROMPT.format(
                question=question[:500],
                answer=answer[:1000]
            )
            
            messages = [
                SystemMessage(content="你是一个智能记忆提取助手。"),
                HumanMessage(content=prompt)
            ]
            
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            memories = json.loads(content)
            
            if not isinstance(memories, list):
                return []
            
            # 过滤并存储有效记忆
            valid_memories = []
            for mem in memories:
                if isinstance(mem, dict) and "type" in mem and "content" in mem:
                    if mem["content"] and len(mem["content"]) > 5:
                        valid_memories.append(mem)
                        # 异步存储记忆
                        await self.store_memory(
                            user_id=user_id,
                            memory_type=mem["type"],
                            content=mem["content"],
                            db=db
                        )
            
            return valid_memories
            
        except Exception as e:
            logger.error("记忆提取失败", exc_info=True)
            return []
    
    async def store_memory(
        self, 
        user_id: int, 
        memory_type: str, 
        content: str, 
        db: AsyncSession,
        importance: float = 1.0
    ) -> Optional[UserMemory]:
        """存储新记忆
        
        流程：
        1. 检查是否已有类似记忆（避免重复）
        2. 向量化存储
        
        Returns:
            创建的记忆对象，如果已存在类似记忆则返回 None
        """
        try:
            # 1. 检查是否已有类似记忆（内容相似度>0.85视为重复）
            existing_memories = await db.execute(
                select(UserMemory).where(
                    and_(
                        UserMemory.user_id == user_id,
                        UserMemory.memory_type == memory_type
                    )
                )
            )
            existing = existing_memories.scalars().all()
            
            # 获取新内容的嵌入
            new_embedding = await self._get_embedding(content)
            
            # 检查相似度
            for mem in existing:
                if mem.embedding:
                    try:
                        existing_embedding = json.loads(mem.embedding)
                        similarity = await self._cosine_similarity(new_embedding, existing_embedding)
                        if similarity > 0.85:
                            # 更新现有记忆的访问时间和重要性
                            mem.last_accessed = datetime.utcnow()
                            mem.importance = min(mem.importance + 0.1, 2.0)
                            await db.commit()
                            return None
                    except:
                        pass
            
            # 2. 创建新记忆
            memory = UserMemory(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                embedding=json.dumps(new_embedding),
                importance=importance,
                access_count=0,
                last_accessed=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            
            db.add(memory)
            await db.commit()
            await db.refresh(memory)
            
            return memory
            
        except Exception as e:
            logger.error("存储记忆失败", exc_info=True)
            await db.rollback()
            return None
    
    async def recall_memories(
        self, 
        user_id: int, 
        query: str, 
        db: AsyncSession, 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """根据当前问题召回相关记忆
        
        使用向量相似度检索相关记忆，按重要性和相关性排序
        
        Returns:
            相关记忆列表
        """
        try:
            # 1. 获取用户的所有记忆
            result = await db.execute(
                select(UserMemory).where(UserMemory.user_id == user_id)
            )
            memories = result.scalars().all()
            
            if not memories:
                return []
            
            # 2. 获取查询的嵌入向量
            query_embedding = await self._get_embedding(query)
            
            # 3. 计算相似度并排序
            scored_memories = []
            for mem in memories:
                if mem.embedding:
                    try:
                        mem_embedding = json.loads(mem.embedding)
                        similarity = await self._cosine_similarity(query_embedding, mem_embedding)
                        
                        # 综合得分 = 相似度 * 重要性权重 * 时间衰减因子
                        time_decay = self._calculate_time_decay(mem.last_accessed)
                        score = similarity * mem.importance * time_decay
                        
                        scored_memories.append({
                            "memory": mem,
                            "score": score,
                            "similarity": similarity
                        })
                    except:
                        pass
            
            # 4. 按得分排序并取 top_k
            scored_memories.sort(key=lambda x: x["score"], reverse=True)
            top_memories = scored_memories[:top_k]
            
            # 5. 更新访问计数和最后访问时间
            for item in top_memories:
                mem = item["memory"]
                mem.access_count += 1
                mem.last_accessed = datetime.utcnow()
            
            await db.commit()
            
            # 6. 返回结果
            return [
                {
                    "id": item["memory"].id,
                    "type": item["memory"].memory_type,
                    "content": item["memory"].content,
                    "importance": item["memory"].importance,
                    "score": item["score"],
                    "similarity": item["similarity"]
                }
                for item in top_memories
            ]
            
        except Exception as e:
            logger.error("记忆召回失败", exc_info=True)
            return []
    
    def _calculate_time_decay(self, last_accessed: datetime) -> float:
        """计算时间衰减因子
        
        最近访问的记忆权重更高
        """
        days_since_access = (datetime.utcnow() - last_accessed).days
        # 指数衰减：30天后衰减到 0.5
        import math
        return math.exp(-days_since_access / 30)
    
    async def build_user_profile(self, user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """构建用户画像
        
        聚合用户所有记忆，提取研究方向、偏好等
        
        Returns:
            用户画像字典
        """
        try:
            result = await db.execute(
                select(UserMemory).where(UserMemory.user_id == user_id)
            )
            memories = result.scalars().all()
            
            profile = {
                "user_id": user_id,
                "total_memories": len(memories),
                "research_interests": [],
                "preferences": [],
                "term_usages": [],
                "backgrounds": [],
                "created_at": datetime.utcnow().isoformat()
            }
            
            for mem in memories:
                mem_dict = {
                    "content": mem.content,
                    "importance": mem.importance,
                    "access_count": mem.access_count
                }
                
                if mem.memory_type == "research_interest":
                    profile["research_interests"].append(mem_dict)
                elif mem.memory_type == "preference":
                    profile["preferences"].append(mem_dict)
                elif mem.memory_type == "term_usage":
                    profile["term_usages"].append(mem_dict)
                elif mem.memory_type == "background":
                    profile["backgrounds"].append(mem_dict)
            
            return profile
            
        except Exception as e:
            logger.error("构建用户画像失败", exc_info=True)
            return {"user_id": user_id, "error": str(e)}
    
    async def decay_memories(self, user_id: int, db: AsyncSession):
        """记忆衰减：降低长期未访问记忆的重要性
        
        超过90天未访问的记忆，重要性降低10%
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            result = await db.execute(
                select(UserMemory).where(
                    and_(
                        UserMemory.user_id == user_id,
                        UserMemory.last_accessed < cutoff_date,
                        UserMemory.importance > 0.5
                    )
                )
            )
            old_memories = result.scalars().all()
            
            for mem in old_memories:
                mem.importance *= 0.9  # 降低10%
            
            await db.commit()
            
        except Exception as e:
            logger.error("记忆衰减处理失败", exc_info=True)
            await db.rollback()
    
    async def delete_memory(self, memory_id: int, user_id: int, db: AsyncSession) -> bool:
        """删除指定记忆"""
        try:
            result = await db.execute(
                select(UserMemory).where(
                    and_(
                        UserMemory.id == memory_id,
                        UserMemory.user_id == user_id
                    )
                )
            )
            memory = result.scalar_one_or_none()
            
            if memory:
                await db.delete(memory)
                await db.commit()
                return True
            return False
            
        except Exception as e:
            logger.error("删除记忆失败", exc_info=True)
            await db.rollback()
            return False
    
    async def get_user_memories(
        self, 
        user_id: int, 
        db: AsyncSession,
        memory_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取用户的所有记忆"""
        try:
            query = select(UserMemory).where(UserMemory.user_id == user_id)
            
            if memory_type:
                query = query.where(UserMemory.memory_type == memory_type)
            
            query = query.order_by(desc(UserMemory.importance)).limit(limit)
            
            result = await db.execute(query)
            memories = result.scalars().all()
            
            return [mem.to_dict() for mem in memories]
            
        except Exception as e:
            logger.error("获取用户记忆失败", exc_info=True)
            return []


# 全局单例
memory_service = MemoryService()
