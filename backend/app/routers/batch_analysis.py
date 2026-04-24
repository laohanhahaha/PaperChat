"""批量分析路由

提供批量分析任务的提交、查询、结果获取与取消接口。
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.batch_analysis import batch_analysis_service, AnalysisType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analysis", tags=["批量分析"])


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────

class BatchAnalysisRequest(BaseModel):
    paper_ids: List[int] = Field(..., min_length=1, description="论文 ID 列表（至少 1 篇）")
    analysis_type: str = Field(
        ...,
        description="分析类型：summary（批量摘要）/ compare（对比分析）/ review（批量综述）",
    )


class BatchSubmitResponse(BaseModel):
    batch_id: str
    message: str


# ─── 路由 ─────────────────────────────────────────────────────────────────────

@router.post(
    "/batch",
    response_model=BatchSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="提交批量分析任务",
)
async def submit_batch_analysis(
    body: BatchAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交批量分析任务，立即返回 batch_id，任务在后台异步执行。

    - **paper_ids**: 需要分析的论文 ID 列表
    - **analysis_type**: `summary` | `compare` | `review`
    """
    try:
        batch_id = await batch_analysis_service.submit_batch_analysis(
            paper_ids=body.paper_ids,
            analysis_type=body.analysis_type,
            db=db,
        )
        return BatchSubmitResponse(
            batch_id=batch_id,
            message=f"批量分析任务已提交，共 {len(body.paper_ids)} 篇论文",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"提交批量分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="提交批量分析任务失败，请稍后重试",
        )


@router.get(
    "/batch/{batch_id}",
    summary="查询批量分析进度",
)
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """查询指定批量任务的进度。

    返回字段：
    - **status**: pending / running / completed / failed / cancelled
    - **progress**: 0.0 ~ 100.0（百分比）
    - **completed**: 已完成数量
    - **failed**: 失败数量
    - **paper_results**: 每篇论文的状态（不含 result 内容，减少流量）
    """
    batch = batch_analysis_service.get_batch_status(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {batch_id} 不存在或已过期",
        )
    data = batch.to_dict()
    # 进度查询不返回完整 result 内容
    for pr in data["paper_results"]:
        pr.pop("result", None)
    return data


@router.get(
    "/batch/{batch_id}/results",
    summary="获取批量分析结果",
)
async def get_batch_results(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取批量分析的完整结果（包含每篇论文的分析内容）。

    建议在 status 为 completed 后调用，以免获取到不完整的结果。
    """
    batch = batch_analysis_service.get_batch_results(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {batch_id} 不存在或已过期",
        )
    return batch.to_dict()


@router.delete(
    "/batch/{batch_id}",
    summary="取消批量分析任务",
    status_code=status.HTTP_200_OK,
)
async def cancel_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """取消正在执行或等待中的批量分析任务。

    对已完成的任务调用此接口会返回 404。
    """
    cancelled = await batch_analysis_service.cancel_batch(batch_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {batch_id} 不存在或已过期",
        )
    return {"message": f"任务 {batch_id} 已请求取消", "batch_id": batch_id}
