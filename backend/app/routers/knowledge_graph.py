"""知识图谱路由

提供知识图谱数据查询、构建触发等接口
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.knowledge_graph import GraphNode, GraphEdge
from app.models.user import User
from app.services.user.auth_service import get_current_user
from app.services.knowledge.graph_service import graph_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["knowledge-graph"])


@router.get("/{user_id}")
async def get_user_graph(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户完整图谱

    路径参数:
        - user_id: 用户 ID

    返回:
        - D3.js force graph 兼容格式的图谱数据
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他用户的图谱",
        )

    # 查询该用户的所有节点
    nodes_result = await db.execute(
        select(GraphNode).where(GraphNode.user_id == user_id)
    )
    nodes = nodes_result.scalars().all()

    # 查询该用户的所有边
    edges_result = await db.execute(
        select(GraphEdge).where(GraphEdge.user_id == user_id)
    )
    edges = edges_result.scalars().all()

    # 组装 D3.js force graph 兼容格式
    return {
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "type": node.node_type,
                "description": node.description or "",
                "paper_ids": node.paper_ids or [],
            }
            for node in nodes
        ],
        "links": [
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "relation_type": edge.relation_type,
                "weight": edge.weight,
                "evidence": edge.evidence or "",
            }
            for edge in edges
        ],
    }


@router.get("/{user_id}/paper/{paper_id}")
async def get_paper_subgraph(
    user_id: int,
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取单篇论文子图

    路径参数:
        - user_id: 用户 ID
        - paper_id: 论文 ID

    返回:
        - D3.js force graph 兼容格式的子图数据
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他用户的图谱",
        )

    # 筛选 paper_ids 包含该 paper_id 的节点
    nodes_result = await db.execute(
        select(GraphNode).where(
            GraphNode.user_id == user_id,
            GraphNode.paper_ids.contains([paper_id]),
        )
    )
    nodes = nodes_result.scalars().all()

    # 收集子图节点 ID 集合，用于筛选边
    node_ids = {node.id for node in nodes}

    # 筛选 paper_id 匹配的边（且边的两端节点都在子图中）
    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.user_id == user_id,
            GraphEdge.paper_id == paper_id,
        )
    )
    edges = edges_result.scalars().all()

    # 只保留两端节点都在子图中的边
    valid_edges = [
        edge for edge in edges
        if edge.source_id in node_ids and edge.target_id in node_ids
    ]

    return {
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "type": node.node_type,
                "description": node.description or "",
                "paper_ids": node.paper_ids or [],
            }
            for node in nodes
        ],
        "links": [
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "relation_type": edge.relation_type,
                "weight": edge.weight,
                "evidence": edge.evidence or "",
            }
            for edge in valid_edges
        ],
    }


@router.post("/build/{paper_id}")
async def build_graph(
    paper_id: int,
    user_id: int = Query(..., description="用户 ID"),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
):
    """
    手动触发图谱构建

    路径参数:
        - paper_id: 论文 ID

    查询参数:
        - user_id: 用户 ID

    返回:
        - 构建状态信息
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权为其他用户构建图谱",
        )

    async def _build_graph_task():
        """后台任务：执行图谱构建"""
        async with AsyncSessionLocal() as db:
            try:
                result = await graph_service.update_graph(paper_id, user_id, db)
                logger.info(
                    "图谱后台构建完成",
                    extra={"paper_id": paper_id, "result": result},
                )
            except Exception as e:
                logger.error(
                    "图谱后台构建失败",
                    extra={"paper_id": paper_id, "error": str(e)},
                    exc_info=True,
                )

    background_tasks.add_task(_build_graph_task)

    return {"status": "building", "paper_id": paper_id}


@router.get("/{user_id}/search")
async def search_graph_nodes(
    user_id: int,
    query: str = Query(..., min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    搜索图谱节点

    路径参数:
        - user_id: 用户 ID

    查询参数:
        - query: 搜索关键词

    返回:
        - 匹配的节点列表
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权搜索其他用户的图谱",
        )

    # 在 name 和 description 中进行 LIKE 搜索
    search_pattern = f"%{query}%"
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.user_id == user_id,
            or_(
                GraphNode.name.ilike(search_pattern),
                GraphNode.description.ilike(search_pattern),
            ),
        )
    )
    nodes = result.scalars().all()

    return [
        {
            "id": node.id,
            "name": node.name,
            "type": node.node_type,
            "description": node.description or "",
            "paper_ids": node.paper_ids or [],
        }
        for node in nodes
    ]
