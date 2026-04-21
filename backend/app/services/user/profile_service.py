"""研究画像服务

用户研究画像异步更新管道和主动推荐引擎
"""
import re
import logging
import asyncio
from collections import Counter
from datetime import datetime
from sqlalchemy import select, func as sa_func
from app.models.research_profile import UserDomain, ReadingPreference, KnowledgeBlindspot, ResearchStage
from app.models.paper import Paper
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ProfileService:
    # 研究阶段关键词
    STAGE_KEYWORDS = {
        "survey": ["综述", "调研", "review", "survey", "相关工作", "背景"],
        "design": ["方法设计", "模型设计", "架构", "framework", "proposed", "设计"],
        "experiment": ["实验", "结果", "评估", "benchmark", "对比", "ablation"],
        "writing": ["写作", "润色", "引用", "参考文献", "投稿", "格式"],
    }
    
    # 停用词（不作为领域关键词）
    STOP_WORDS = {"的", "了", "是", "在", "和", "与", "或", "这", "那", "有", "我", "你",
                  "the", "a", "an", "is", "are", "in", "on", "for", "to", "of", "and"}
    
    async def update_profile_async(self, user_id: int, interaction_data: dict):
        """交互后异步更新画像（不阻塞主流程）
        
        interaction_data: {
            "message": str,           # 用户消息
            "intent": str,            # 识别到的意图
            "paper_id": int|None,     # 相关论文ID
            "tool_used": str|None,    # 使用的工具
        }
        """
        try:
            async with AsyncSessionLocal() as db:
                message = interaction_data.get("message", "")
                paper_id = interaction_data.get("paper_id")
                
                # 1. 提取关键词 -> 更新 UserDomain
                await self._update_domains(user_id, message, db)
                
                # 2. 如果有论文，更新阅读偏好
                if paper_id:
                    await self._update_reading_preference(user_id, paper_id, db)
                
                # 3. 检测重复提问概念 -> 更新盲区
                await self._update_blindspots(user_id, message, db)
                
                # 4. 推断研究阶段
                await self._update_research_stage(user_id, message, db)
                
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update profile for user {user_id}: {e}")
    
    async def _update_domains(self, user_id: int, message: str, db):
        """从消息中提取领域关键词，更新 UserDomain"""
        # 简单的关键词提取：提取 2-6 字的中文词组和 3+ 字母的英文词
        keywords = self._extract_keywords(message)
        
        for keyword in keywords[:5]:  # 最多取5个
            existing = await db.execute(
                select(UserDomain).where(
                    UserDomain.user_id == user_id,
                    UserDomain.domain_name == keyword
                )
            )
            domain = existing.scalar_one_or_none()
            if domain:
                domain.frequency += 1
                domain.last_seen_at = datetime.utcnow()
                # 频次高的自动升级
                if domain.frequency >= 10 and domain.domain_type == "related":
                    domain.domain_type = "sub"
                elif domain.frequency >= 20 and domain.domain_type == "sub":
                    domain.domain_type = "primary"
            else:
                db.add(UserDomain(user_id=user_id, domain_name=keyword, domain_type="related"))
    
    async def _update_reading_preference(self, user_id: int, paper_id: int, db):
        """更新阅读偏好"""
        # 从 Paper 获取论文类型信息（如果有的话）
        paper = await db.get(Paper, paper_id)
        if not paper:
            return
        # 默认按 methodology 统计
        pref_type = "methodology"  # 可以根据论文内容推断
        
        existing = await db.execute(
            select(ReadingPreference).where(
                ReadingPreference.user_id == user_id,
                ReadingPreference.preference_type == pref_type
            )
        )
        pref = existing.scalar_one_or_none()
        if pref:
            pref.count += 1
        else:
            db.add(ReadingPreference(user_id=user_id, preference_type=pref_type, count=1))
        
        # 更新所有偏好的比例
        all_prefs = (await db.execute(
            select(ReadingPreference).where(ReadingPreference.user_id == user_id)
        )).scalars().all()
        total = sum(p.count for p in all_prefs)
        for p in all_prefs:
            p.ratio = p.count / total if total > 0 else 0
    
    async def _update_blindspots(self, user_id: int, message: str, db):
        """检测重复提问的概念，标记为盲区"""
        # 提取问题中的核心概念（较长的专业词汇）
        concepts = [k for k in self._extract_keywords(message) if len(k) >= 3]
        
        for concept in concepts[:3]:
            existing = await db.execute(
                select(KnowledgeBlindspot).where(
                    KnowledgeBlindspot.user_id == user_id,
                    KnowledgeBlindspot.concept == concept
                )
            )
            blindspot = existing.scalar_one_or_none()
            if blindspot:
                blindspot.query_count += 1
                blindspot.updated_at = datetime.utcnow()
                # 查询3+次标记为盲区
                if blindspot.query_count >= 3 and blindspot.status == "improving":
                    blindspot.status = "blind"
            else:
                db.add(KnowledgeBlindspot(
                    user_id=user_id, concept=concept, 
                    query_count=1, status="improving"
                ))
    
    async def _update_research_stage(self, user_id: int, message: str, db):
        """推断研究阶段"""
        detected_stage = None
        max_score = 0
        
        for stage, keywords in self.STAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message.lower())
            if score > max_score:
                max_score = score
                detected_stage = stage
        
        if detected_stage and max_score > 0:
            existing = await db.execute(
                select(ResearchStage).where(ResearchStage.user_id == user_id)
            )
            stage_record = existing.scalar_one_or_none()
            if stage_record:
                if stage_record.stage != detected_stage:
                    # 置信度渐进更新
                    stage_record.confidence = max(0.3, stage_record.confidence - 0.1)
                    evidence = stage_record.evidence or []
                    evidence.append({"stage": detected_stage, "message": message[:100]})
                    stage_record.evidence = evidence[-10:]  # 保留最近10条
                    # 如果新阶段证据积累足够多，切换
                    recent_stages = [e["stage"] for e in evidence[-5:]]
                    if recent_stages.count(detected_stage) >= 3:
                        stage_record.stage = detected_stage
                        stage_record.confidence = 0.7
                else:
                    stage_record.confidence = min(1.0, stage_record.confidence + 0.05)
            else:
                db.add(ResearchStage(
                    user_id=user_id, stage=detected_stage, confidence=0.5,
                    evidence=[{"stage": detected_stage, "message": message[:100]}]
                ))
    
    def _extract_keywords(self, text: str) -> list[str]:
        """简单关键词提取（不使用 LLM）"""
        # 中文：提取 2-8 字连续汉字
        cn_words = re.findall(r'[\u4e00-\u9fff]{2,8}', text)
        # 英文：提取 3+ 字母单词
        en_words = re.findall(r'[a-zA-Z]{3,}', text)
        
        # 过滤停用词
        keywords = [w for w in cn_words + en_words if w.lower() not in self.STOP_WORDS]
        
        # 按长度排序（较长的更可能是专业术语）
        keywords.sort(key=len, reverse=True)
        return keywords
    
    async def get_recommendations(self, user_id: int, db) -> list[dict]:
        """基于画像的主动推荐"""
        recommendations = []
        
        # 1. 获取用户盲区
        blindspots = (await db.execute(
            select(KnowledgeBlindspot).where(
                KnowledgeBlindspot.user_id == user_id,
                KnowledgeBlindspot.status == "blind"
            ).order_by(KnowledgeBlindspot.query_count.desc()).limit(5)
        )).scalars().all()
        
        # 2. 获取用户主要研究领域
        domains = (await db.execute(
            select(UserDomain).where(
                UserDomain.user_id == user_id
            ).order_by(UserDomain.frequency.desc()).limit(10)
        )).scalars().all()
        
        # 3. 基于盲区和领域推荐（从已有论文库中搜索）
        search_terms = [b.concept for b in blindspots] + [d.domain_name for d in domains[:3]]
        
        for term in search_terms[:5]:
            papers = (await db.execute(
                select(Paper).where(
                    Paper.title.ilike(f"%{term}%")
                ).limit(3)
            )).scalars().all()
            for paper in papers:
                recommendations.append({
                    "paper_id": paper.id,
                    "title": paper.title,
                    "reason": f"与你的研究领域「{term}」相关",
                    "source": "blindspot" if term in [b.concept for b in blindspots] else "domain"
                })
        
        # 去重
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec["paper_id"] not in seen:
                seen.add(rec["paper_id"])
                unique_recs.append(rec)
        
        return unique_recs[:10]
    
    async def get_profile_summary(self, user_id: int, db) -> dict:
        """获取用户画像摘要"""
        domains = (await db.execute(
            select(UserDomain).where(UserDomain.user_id == user_id)
            .order_by(UserDomain.frequency.desc())
        )).scalars().all()
        
        preferences = (await db.execute(
            select(ReadingPreference).where(ReadingPreference.user_id == user_id)
        )).scalars().all()
        
        blindspots = (await db.execute(
            select(KnowledgeBlindspot).where(KnowledgeBlindspot.user_id == user_id)
            .order_by(KnowledgeBlindspot.query_count.desc())
        )).scalars().all()
        
        stage = (await db.execute(
            select(ResearchStage).where(ResearchStage.user_id == user_id)
        )).scalar_one_or_none()
        
        return {
            "domains": [{"name": d.domain_name, "type": d.domain_type, "frequency": d.frequency} for d in domains],
            "preferences": [{"type": p.preference_type, "count": p.count, "ratio": p.ratio} for p in preferences],
            "blindspots": [{"id": b.id, "concept": b.concept, "count": b.query_count, "status": b.status} for b in blindspots],
            "stage": {"stage": stage.stage, "confidence": stage.confidence} if stage else None,
        }


profile_service = ProfileService()
