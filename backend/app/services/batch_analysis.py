"""批量分析服务

提供对多篇论文的批量分析功能，支持：
- 批量摘要（summary）
- 对比分析（compare）
- 批量综述（review）

内部使用 asyncio.Queue + Worker 模式，每篇论文完成后通过 EventBus 推送进度。
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AnalysisType(str, Enum):
    SUMMARY = "summary"   # 批量摘要
    COMPARE = "compare"   # 对比分析
    REVIEW = "review"     # 批量综述


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PaperResult:
    """单篇论文的分析结果"""
    paper_id: int
    paper_title: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""


@dataclass
class BatchStatus:
    """批量任务状态"""
    batch_id: str
    analysis_type: str
    status: TaskStatus
    total: int
    completed: int
    failed: int
    paper_results: List[PaperResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    # 仅 compare / review 类型使用
    combined_result: Optional[str] = None

    @property
    def progress(self) -> float:
        if self.total == 0:
            return 0.0
        return round((self.completed + self.failed) / self.total * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "analysis_type": self.analysis_type,
            "status": self.status.value,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "progress": self.progress,
            "paper_results": [
                {
                    "paper_id": pr.paper_id,
                    "paper_title": pr.paper_title,
                    "status": pr.status.value,
                    "result": pr.result,
                    "error": pr.error,
                }
                for pr in self.paper_results
            ],
            "combined_result": self.combined_result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BatchAnalysisService:
    """批量分析服务

    使用内存字典存储 batch 状态（无需持久化，重启后失效）。
    使用 asyncio.Queue + Worker 单 worker 模式顺序处理任务，
    避免并发 LLM 请求带来过多 token 消耗与超时风险。
    """

    def __init__(self):
        self._batches: Dict[str, BatchStatus] = {}
        self._cancel_flags: Dict[str, bool] = {}  # True = 已请求取消
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    async def submit_batch_analysis(
        self,
        paper_ids: List[int],
        analysis_type: str,
        db: AsyncSession,
    ) -> str:
        """提交批量分析任务

        Args:
            paper_ids: 论文 ID 列表
            analysis_type: 分析类型（summary / compare / review）
            db: 数据库 session（仅用于读取论文信息）

        Returns:
            batch_id: 任务唯一标识
        """
        if not paper_ids:
            raise ValueError("paper_ids 不能为空")
        if analysis_type not in [e.value for e in AnalysisType]:
            raise ValueError(f"不支持的分析类型: {analysis_type}")

        # 读取论文基本信息
        from app.models.paper import Paper
        result = await db.execute(select(Paper).where(Paper.id.in_(paper_ids)))
        papers = result.scalars().all()

        if not papers:
            raise ValueError("未找到任何指定论文")

        batch_id = str(uuid.uuid4())
        paper_results = [
            PaperResult(paper_id=p.id, paper_title=p.title or f"论文#{p.id}")
            for p in papers
        ]

        batch = BatchStatus(
            batch_id=batch_id,
            analysis_type=analysis_type,
            status=TaskStatus.PENDING,
            total=len(paper_results),
            completed=0,
            failed=0,
            paper_results=paper_results,
        )
        self._batches[batch_id] = batch
        self._cancel_flags[batch_id] = False

        # 将任务放入队列，附带 paper 文本信息
        papers_info = [
            {"id": p.id, "title": p.title or f"论文#{p.id}", "abstract": p.abstract or ""}
            for p in papers
        ]
        await self._queue.put((batch_id, analysis_type, papers_info))

        # 确保 worker 正在运行
        self._ensure_worker()

        logger.info(
            f"批量分析任务已提交",
            extra={"batch_id": batch_id, "analysis_type": analysis_type, "count": len(papers)},
        )
        return batch_id

    def get_batch_status(self, batch_id: str) -> Optional[BatchStatus]:
        return self._batches.get(batch_id)

    def get_batch_results(self, batch_id: str) -> Optional[BatchStatus]:
        return self._batches.get(batch_id)

    async def cancel_batch(self, batch_id: str) -> bool:
        if batch_id not in self._batches:
            return False
        self._cancel_flags[batch_id] = True
        batch = self._batches[batch_id]
        if batch.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            batch.status = TaskStatus.CANCELLED
            batch.updated_at = datetime.utcnow()
        return True

    # ------------------------------------------------------------------
    # Worker 内部逻辑
    # ------------------------------------------------------------------

    def _ensure_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        """后台 worker，串行处理队列中的批量任务"""
        while True:
            try:
                batch_id, analysis_type, papers_info = await asyncio.wait_for(
                    self._queue.get(), timeout=60.0
                )
            except asyncio.TimeoutError:
                # 队列长时间空闲则退出，下次有任务时重新启动
                break

            try:
                await self._process_batch(batch_id, analysis_type, papers_info)
            except Exception as e:
                logger.error(f"批量任务处理异常 batch_id={batch_id}: {e}", exc_info=True)
                batch = self._batches.get(batch_id)
                if batch:
                    batch.status = TaskStatus.FAILED
                    batch.updated_at = datetime.utcnow()
            finally:
                self._queue.task_done()

    async def _process_batch(
        self,
        batch_id: str,
        analysis_type: str,
        papers_info: List[dict],
    ):
        batch = self._batches[batch_id]
        batch.status = TaskStatus.RUNNING
        batch.updated_at = datetime.utcnow()

        # 获取 LLM service（通过直接导入单例）
        from app.services.llm.llm_service import llm_service

        # 发布任务开始事件
        await self._publish_progress(batch_id, "started")

        if analysis_type == AnalysisType.SUMMARY:
            await self._process_summary(batch, papers_info, llm_service)
        elif analysis_type == AnalysisType.COMPARE:
            await self._process_compare(batch, papers_info, llm_service)
        elif analysis_type == AnalysisType.REVIEW:
            await self._process_review(batch, papers_info, llm_service)

        # 最终状态
        if self._cancel_flags.get(batch_id):
            batch.status = TaskStatus.CANCELLED
        elif batch.failed > 0 and batch.completed == 0:
            batch.status = TaskStatus.FAILED
        else:
            batch.status = TaskStatus.COMPLETED

        batch.updated_at = datetime.utcnow()
        await self._publish_progress(batch_id, "finished")
        logger.info(f"批量任务完成 batch_id={batch_id} status={batch.status.value}")

    async def _process_summary(self, batch: BatchStatus, papers_info: List[dict], llm_service):
        """逐篇生成摘要"""
        for pr in batch.paper_results:
            if self._cancel_flags.get(batch.batch_id):
                pr.status = TaskStatus.CANCELLED
                continue

            pr.status = TaskStatus.RUNNING
            paper_data = next((p for p in papers_info if p["id"] == pr.paper_id), None)
            if not paper_data:
                pr.status = TaskStatus.FAILED
                pr.error = "找不到论文信息"
                batch.failed += 1
                continue

            try:
                text = self._build_summary_input(paper_data)
                result_chunks = []
                async for chunk in llm_service.summarize_text(text):
                    result_chunks.append(chunk)
                pr.result = "".join(result_chunks)
                pr.status = TaskStatus.COMPLETED
                batch.completed += 1
            except Exception as e:
                pr.status = TaskStatus.FAILED
                pr.error = str(e)
                batch.failed += 1
                logger.warning(f"摘要失败 paper_id={pr.paper_id}: {e}")

            batch.updated_at = datetime.utcnow()
            await self._publish_progress(batch.batch_id, "paper_done", {"paper_id": pr.paper_id})

    async def _process_compare(self, batch: BatchStatus, papers_info: List[dict], llm_service):
        """整体对比分析（一次调用 LLM）"""
        papers_text = [
            {"title": p["title"], "text": self._build_summary_input(p)}
            for p in papers_info
        ]
        try:
            result_chunks = []
            async for chunk in llm_service.compare_papers(papers_text):
                result_chunks.append(chunk)
            combined = "".join(result_chunks)
            batch.combined_result = combined
            # 标记所有论文为完成
            for pr in batch.paper_results:
                pr.status = TaskStatus.COMPLETED
                pr.result = "（见整体对比结果）"
            batch.completed = len(batch.paper_results)
        except Exception as e:
            for pr in batch.paper_results:
                pr.status = TaskStatus.FAILED
                pr.error = str(e)
            batch.failed = len(batch.paper_results)
            logger.warning(f"对比分析失败 batch_id={batch.batch_id}: {e}")

        batch.updated_at = datetime.utcnow()
        await self._publish_progress(batch.batch_id, "compare_done")

    async def _process_review(self, batch: BatchStatus, papers_info: List[dict], llm_service):
        """生成文献综述（一次调用 LLM）"""
        papers_text = [
            {"title": p["title"], "text": self._build_summary_input(p)}
            for p in papers_info
        ]
        try:
            result_chunks = []
            async for chunk in llm_service.generate_review(papers_text):
                result_chunks.append(chunk)
            combined = "".join(result_chunks)
            batch.combined_result = combined
            for pr in batch.paper_results:
                pr.status = TaskStatus.COMPLETED
                pr.result = "（见整体综述结果）"
            batch.completed = len(batch.paper_results)
        except Exception as e:
            for pr in batch.paper_results:
                pr.status = TaskStatus.FAILED
                pr.error = str(e)
            batch.failed = len(batch.paper_results)
            logger.warning(f"综述生成失败 batch_id={batch.batch_id}: {e}")

        batch.updated_at = datetime.utcnow()
        await self._publish_progress(batch.batch_id, "review_done")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary_input(paper_data: dict) -> str:
        parts = [f"标题：{paper_data.get('title', '未知')}"]
        if paper_data.get("abstract"):
            parts.append(f"摘要：{paper_data['abstract']}")
        return "\n\n".join(parts)

    async def _publish_progress(self, batch_id: str, event_name: str, extra: dict = None):
        """通过 EventBus 推送进度"""
        try:
            from app.services.event_bus import event_bus, Event, EventTypes
            batch = self._batches.get(batch_id)
            data = {
                "batch_id": batch_id,
                "event": event_name,
                "progress": batch.progress if batch else 0,
                **(extra or {}),
            }
            await event_bus.publish(Event(type=EventTypes.ANALYSIS_COMPLETED, data=data))
        except Exception as e:
            logger.debug(f"进度事件推送失败（非阻塞）: {e}")


# 全局单例
batch_analysis_service = BatchAnalysisService()
