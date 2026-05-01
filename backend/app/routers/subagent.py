"""子智能体管理 API"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.models.custom_subagent import CustomSubAgent

router = APIRouter(prefix="/api/v1/subagents", tags=["subagents"])


class SubAgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    tool_subset: Optional[List[str]] = None
    icon: Optional[str] = None

class SubAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_subset: Optional[List[str]] = None
    icon: Optional[str] = None


@router.get("")
async def list_subagents(user_id: int = 1, db: AsyncSession = Depends(get_db)):
    """列出所有子智能体（含预置）"""
    result = await db.execute(
        select(CustomSubAgent).where(CustomSubAgent.user_id == user_id).order_by(CustomSubAgent.is_preset.desc(), CustomSubAgent.created_at)
    )
    agents = result.scalars().all()
    return [a.to_dict() for a in agents]


@router.post("")
async def create_subagent(data: SubAgentCreate, user_id: int = 1, db: AsyncSession = Depends(get_db)):
    """创建自定义子智能体"""
    agent = CustomSubAgent(
        user_id=user_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        tool_subset=json.dumps(data.tool_subset) if data.tool_subset else None,
        icon=data.icon,
        is_preset=False,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent.to_dict()


@router.put("/{agent_id}")
async def update_subagent(agent_id: int, data: SubAgentUpdate, user_id: int = 1, db: AsyncSession = Depends(get_db)):
    """编辑子智能体"""
    result = await db.execute(
        select(CustomSubAgent).where(CustomSubAgent.id == agent_id, CustomSubAgent.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="子智能体不存在")
    if agent.is_preset:
        raise HTTPException(status_code=403, detail="预置子智能体不可编辑")

    if data.name is not None: agent.name = data.name
    if data.description is not None: agent.description = data.description
    if data.system_prompt is not None: agent.system_prompt = data.system_prompt
    if data.tool_subset is not None: agent.tool_subset = json.dumps(data.tool_subset)
    if data.icon is not None: agent.icon = data.icon

    await db.commit()
    await db.refresh(agent)
    return agent.to_dict()


@router.delete("/{agent_id}")
async def delete_subagent(agent_id: int, user_id: int = 1, db: AsyncSession = Depends(get_db)):
    """删除子智能体（预置不可删）"""
    result = await db.execute(
        select(CustomSubAgent).where(CustomSubAgent.id == agent_id, CustomSubAgent.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="子智能体不存在")
    if agent.is_preset:
        raise HTTPException(status_code=403, detail="预置子智能体不可删除")

    await db.delete(agent)
    await db.commit()
    return {"message": "已删除"}


async def init_preset_subagents(db: AsyncSession, user_id: int = 1):
    """初始化预置子智能体模板（幂等：已存在则跳过）"""
    from app.prompts.research import (
        RETRIEVER_SYSTEM_PROMPT,
        ANALYZER_SYSTEM_PROMPT,
        RECOMMENDER_SYSTEM_PROMPT,
    )

    presets = [
        {
            "name": "检索专家",
            "description": "从论文库中精准定位和收集相关信息，支持本地搜索和联网学术搜索",
            "system_prompt": RETRIEVER_SYSTEM_PROMPT,
            "tool_subset": json.dumps(["search_text", "search_papers", "get_paper_info", "recent_papers"]),
            "icon": "search",
        },
        {
            "name": "分析专家",
            "description": "评估论文中的论点有效性、方法论质量，识别研究间的逻辑关系",
            "system_prompt": ANALYZER_SYSTEM_PROMPT,
            "tool_subset": json.dumps(["summarize", "compare_content", "extract_key_points", "assess_quality", "explain_term"]),
            "icon": "analyze",
        },
        {
            "name": "推荐专家",
            "description": "基于已有分析发现研究空白，推荐后续研究方向和可行步骤",
            "system_prompt": RECOMMENDER_SYSTEM_PROMPT,
            "tool_subset": json.dumps(["search_papers", "search_cards", "find_research_gaps"]),
            "icon": "recommend",
        },
    ]

    for preset in presets:
        # 检查是否已存在
        existing = await db.execute(
            select(CustomSubAgent).where(
                CustomSubAgent.user_id == user_id,
                CustomSubAgent.name == preset["name"],
                CustomSubAgent.is_preset == True,
            )
        )
        if existing.scalar_one_or_none():
            continue

        agent = CustomSubAgent(
            user_id=user_id,
            is_preset=True,
            **preset,
        )
        db.add(agent)

    await db.commit()
