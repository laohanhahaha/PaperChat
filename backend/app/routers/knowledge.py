"""知识库路由

提供知识卡片的 CRUD、搜索、关联管理等 API
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import KnowledgeCard, KnowledgeRelation
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.knowledge_service import knowledge_service
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# ============== 请求/响应模型 ==============

class KnowledgeCardCreate(BaseModel):
    """创建知识卡片请求"""
    title: str = Field(..., min_length=1, max_length=200, description="卡片标题")
    content: str = Field(..., min_length=1, description="卡片内容")
    summary: Optional[str] = Field(None, description="摘要")
    source_type: Optional[str] = Field(None, description="来源类型: highlight/chat/manual/analysis")
    source_id: Optional[int] = Field(None, description="来源对象ID")
    paper_id: Optional[int] = Field(None, description="关联论文ID")
    tags: List[str] = Field(default=[], description="标签列表")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    importance: float = Field(default=1.0, ge=0.0, le=10.0, description="重要性权重")


class KnowledgeCardUpdate(BaseModel):
    """更新知识卡片请求"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = Field(None, max_length=100)
    importance: Optional[float] = Field(None, ge=0.0, le=10.0)


class KnowledgeCardResponse(BaseModel):
    """知识卡片响应"""
    id: int
    user_id: int
    title: str
    content: str
    summary: Optional[str]
    source_type: Optional[str]
    source_id: Optional[int]
    paper_id: Optional[int]
    tags: List[str]
    category: Optional[str]
    importance: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class KnowledgeCardListResponse(BaseModel):
    """知识卡片列表响应"""
    cards: List[KnowledgeCardResponse]
    total: int
    page: int
    page_size: int


class KnowledgeRelationCreate(BaseModel):
    """创建知识关联请求"""
    target_card_id: int = Field(..., description="目标卡片ID")
    relation_type: str = Field(..., description="关联类型: related/prerequisite/extends/contradicts/supports")
    description: Optional[str] = Field(None, max_length=200, description="关联描述")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度")


class KnowledgeRelationResponse(BaseModel):
    """知识关联响应"""
    id: int
    source_card_id: int
    target_card_id: int
    relation_type: str
    description: Optional[str]
    confidence: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExtractFromChatRequest(BaseModel):
    """从问答提取知识请求"""
    content: str = Field(..., min_length=1, description="问答内容")
    paper_id: Optional[int] = Field(None, description="关联论文ID")


class AutoTagResponse(BaseModel):
    """自动标签响应"""
    tags: List[str]


class FindRelationsResponse(BaseModel):
    """发现关联响应"""
    relations: List[dict]


class GraphDataResponse(BaseModel):
    """知识图谱数据响应"""
    nodes: List[dict]
    edges: List[dict]


class StatsResponse(BaseModel):
    """统计信息响应"""
    total_cards: int
    total_relations: int
    category_stats: dict
    source_stats: dict
    tag_cloud: dict


# ============== 路由定义 ==============

@router.get("/cards", response_model=KnowledgeCardListResponse)
async def get_cards(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="分类筛选"),
    source_type: Optional[str] = Query(None, description="来源类型筛选"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识卡片列表（支持分页、筛选、搜索）"""
    query = select(KnowledgeCard).where(KnowledgeCard.user_id == current_user.id)
    
    # 应用筛选条件
    if category:
        query = query.where(KnowledgeCard.category == category)
    if source_type:
        query = query.where(KnowledgeCard.source_type == source_type)
    if tag:
        query = query.where(KnowledgeCard.tags.contains([tag]))
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                KnowledgeCard.title.ilike(search_pattern),
                KnowledgeCard.content.ilike(search_pattern)
            )
        )
    
    # 获取总数
    count_query = select(func.count(KnowledgeCard.id)).where(KnowledgeCard.user_id == current_user.id)
    if category:
        count_query = count_query.where(KnowledgeCard.category == category)
    if source_type:
        count_query = count_query.where(KnowledgeCard.source_type == source_type)
    if tag:
        count_query = count_query.where(KnowledgeCard.tags.contains([tag]))
    if search:
        count_query = count_query.where(
            or_(
                KnowledgeCard.title.ilike(search_pattern),
                KnowledgeCard.content.ilike(search_pattern)
            )
        )
    
    result = await db.execute(count_query)
    total = result.scalar()
    
    # 分页
    query = query.order_by(desc(KnowledgeCard.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    cards = result.scalars().all()
    
    return {
        "cards": cards,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post("/cards", response_model=KnowledgeCardResponse)
async def create_card(
    data: KnowledgeCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建知识卡片"""
    card = KnowledgeCard(
        user_id=current_user.id,
        title=data.title,
        content=data.content,
        summary=data.summary,
        source_type=data.source_type or "manual",
        source_id=data.source_id,
        paper_id=data.paper_id,
        tags=data.tags,
        category=data.category,
        importance=data.importance
    )
    
    db.add(card)
    await db.commit()
    await db.refresh(card)
    
    # 向量化索引
    await knowledge_service.index_card(card)
    
    return card


@router.get("/cards/{card_id}", response_model=KnowledgeCardResponse)
async def get_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取卡片详情"""
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    return card


@router.put("/cards/{card_id}", response_model=KnowledgeCardResponse)
async def update_card(
    card_id: int,
    data: KnowledgeCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新卡片"""
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(card, key, value)
    
    await db.commit()
    await db.refresh(card)
    
    # 重新索引
    await knowledge_service.index_card(card)
    
    return card


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除卡片"""
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    # 删除向量索引
    await knowledge_service.delete_card_index(current_user.id, card_id)
    
    await db.delete(card)
    await db.commit()
    
    return {"message": "卡片已删除"}


@router.post("/cards/from-highlight/{highlight_id}", response_model=KnowledgeCardResponse)
async def create_from_highlight(
    highlight_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从高亮创建知识卡片"""
    try:
        card = await knowledge_service.extract_from_highlight(
            highlight_id, current_user.id, db
        )
        return card
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.post("/cards/from-chat", response_model=KnowledgeCardResponse)
async def create_from_chat(
    data: ExtractFromChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从问答创建知识卡片"""
    try:
        card = await knowledge_service.extract_from_chat(
            data.content, current_user.id, data.paper_id, db
        )
        return card
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/search")
async def search_cards(
    query: str = Query(..., min_length=1, description="搜索关键词"),
    top_k: int = Query(10, ge=1, le=50, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """全局搜索知识卡片"""
    results = await knowledge_service.search(
        current_user.id, query, db, top_k=top_k
    )
    return {"results": results, "query": query}


@router.get("/cards/{card_id}/relations", response_model=List[KnowledgeRelationResponse])
async def get_card_relations(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取卡片的关联关系"""
    # 验证卡片存在且属于当前用户
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    # 获取作为源的关联
    result = await db.execute(
        select(KnowledgeRelation).where(KnowledgeRelation.source_card_id == card_id)
    )
    source_relations = result.scalars().all()
    
    # 获取作为目标的关联
    result = await db.execute(
        select(KnowledgeRelation).where(KnowledgeRelation.target_card_id == card_id)
    )
    target_relations = result.scalars().all()
    
    return list(source_relations) + list(target_relations)


@router.post("/cards/{card_id}/find-relations", response_model=FindRelationsResponse)
async def find_relations(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """自动发现卡片关联"""
    try:
        relations = await knowledge_service.find_relations(
            card_id, current_user.id, db
        )
        return {"relations": relations}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发现关联失败: {str(e)}")


@router.post("/relations", response_model=KnowledgeRelationResponse)
async def create_relation(
    source_card_id: int,
    data: KnowledgeRelationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动创建关联"""
    # 验证源卡片
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == source_card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="源卡片不存在")
    
    # 验证目标卡片
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == data.target_card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="目标卡片不存在")
    
    # 检查是否已存在
    result = await db.execute(
        select(KnowledgeRelation).where(
            and_(
                KnowledgeRelation.source_card_id == source_card_id,
                KnowledgeRelation.target_card_id == data.target_card_id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="关联已存在")
    
    relation = KnowledgeRelation(
        source_card_id=source_card_id,
        target_card_id=data.target_card_id,
        relation_type=data.relation_type,
        description=data.description,
        confidence=data.confidence
    )
    
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    
    return relation


@router.delete("/relations/{relation_id}")
async def delete_relation(
    relation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除关联"""
    # 获取关联并验证权限
    result = await db.execute(
        select(KnowledgeRelation)
        .join(KnowledgeCard, KnowledgeRelation.source_card_id == KnowledgeCard.id)
        .where(
            and_(
                KnowledgeRelation.id == relation_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    relation = result.scalar_one_or_none()
    
    if not relation:
        raise HTTPException(status_code=404, detail="关联不存在")
    
    await db.delete(relation)
    await db.commit()
    
    return {"message": "关联已删除"}


@router.get("/graph", response_model=GraphDataResponse)
async def get_graph_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识图谱数据（节点+边）"""
    data = await knowledge_service.get_graph_data(current_user.id, db)
    return data


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识库统计信息"""
    stats = await knowledge_service.get_stats(current_user.id, db)
    return stats


@router.post("/cards/{card_id}/auto-tag", response_model=AutoTagResponse)
async def auto_tag_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """为卡片自动生成标签"""
    result = await db.execute(
        select(KnowledgeCard).where(
            and_(
                KnowledgeCard.id == card_id,
                KnowledgeCard.user_id == current_user.id
            )
        )
    )
    card = result.scalar_one_or_none()
    
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    tags = await knowledge_service.auto_tag(card.content)
    
    # 更新卡片标签
    card.tags = tags
    await db.commit()
    
    return {"tags": tags}


# 导入 func
from sqlalchemy import func
