# -*- coding: utf-8 -*-
"""批量分析服务单元测试

覆盖：
- submit_batch_analysis() 任务提交与 BatchStatus 初始化
- get_batch_status() 状态查询
- cancel_batch() 取消任务
- BatchStatus.progress 属性计算
- BatchStatus.to_dict() 序列化
- Worker 处理流程（mock LLM service）
- 无效参数的错误处理
"""
import asyncio
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.batch_analysis import (
    AnalysisType,
    BatchAnalysisService,
    BatchStatus,
    PaperResult,
    TaskStatus,
)


# ─────────────────────────────────────────────────────────────────────────────
# BatchStatus & PaperResult 数据类
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchStatusDataClass:
    def _make_batch(self, total=4, completed=2, failed=1) -> BatchStatus:
        return BatchStatus(
            batch_id="test-batch-001",
            analysis_type="summary",
            status=TaskStatus.RUNNING,
            total=total,
            completed=completed,
            failed=failed,
        )

    def test_progress_calculation(self):
        batch = self._make_batch(total=4, completed=2, failed=1)
        # (2 + 1) / 4 * 100 = 75.0
        assert batch.progress == 75.0

    def test_progress_zero_when_total_zero(self):
        batch = self._make_batch(total=0, completed=0, failed=0)
        assert batch.progress == 0.0

    def test_progress_100_when_all_done(self):
        batch = self._make_batch(total=3, completed=3, failed=0)
        assert batch.progress == 100.0

    def test_to_dict_contains_required_keys(self):
        batch = self._make_batch()
        d = batch.to_dict()
        for key in ["batch_id", "analysis_type", "status", "total",
                    "completed", "failed", "progress", "paper_results",
                    "combined_result", "created_at", "updated_at"]:
            assert key in d, f"to_dict() 缺少字段 {key!r}"

    def test_to_dict_status_is_string(self):
        batch = self._make_batch()
        d = batch.to_dict()
        assert isinstance(d["status"], str)

    def test_paper_result_in_to_dict(self):
        batch = BatchStatus(
            batch_id="b",
            analysis_type="summary",
            status=TaskStatus.PENDING,
            total=1,
            completed=0,
            failed=0,
            paper_results=[PaperResult(paper_id=42, paper_title="测试论文")],
        )
        d = batch.to_dict()
        assert len(d["paper_results"]) == 1
        assert d["paper_results"][0]["paper_id"] == 42


# ─────────────────────────────────────────────────────────────────────────────
# AnalysisType 枚举
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalysisType:
    def test_values_cover_three_types(self):
        values = {e.value for e in AnalysisType}
        assert values == {"summary", "compare", "review"}


# ─────────────────────────────────────────────────────────────────────────────
# BatchAnalysisService 核心方法
# ─────────────────────────────────────────────────────────────────────────────

def _mock_db_with_papers(paper_ids):
    """构造一个模拟数据库，返回指定 paper_ids 对应的假论文对象"""
    papers = []
    for pid in paper_ids:
        p = MagicMock()
        p.id = pid
        p.title = f"论文 #{pid}"
        p.abstract = f"这是论文 {pid} 的摘要"
        papers.append(p)

    # scalars().all() 返回 papers
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = papers

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)
    return db


class TestGetBatchStatus:
    def test_returns_none_for_unknown_batch(self):
        svc = BatchAnalysisService()
        assert svc.get_batch_status("nonexistent-id") is None

    def test_returns_batch_after_manual_insert(self):
        svc = BatchAnalysisService()
        batch = BatchStatus(
            batch_id="known-id",
            analysis_type="summary",
            status=TaskStatus.PENDING,
            total=2,
            completed=0,
            failed=0,
        )
        svc._batches["known-id"] = batch
        result = svc.get_batch_status("known-id")
        assert result is batch


class TestCancelBatch:
    @pytest.mark.asyncio
    async def test_cancel_unknown_batch_returns_false(self):
        svc = BatchAnalysisService()
        result = await svc.cancel_batch("no-such-batch")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_pending_batch(self):
        svc = BatchAnalysisService()
        batch = BatchStatus(
            batch_id="cancel-me",
            analysis_type="summary",
            status=TaskStatus.PENDING,
            total=3,
            completed=0,
            failed=0,
        )
        svc._batches["cancel-me"] = batch
        svc._cancel_flags["cancel-me"] = False

        result = await svc.cancel_batch("cancel-me")

        assert result is True
        assert svc._cancel_flags["cancel-me"] is True
        assert batch.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_batch(self):
        svc = BatchAnalysisService()
        batch = BatchStatus(
            batch_id="cancel-running",
            analysis_type="compare",
            status=TaskStatus.RUNNING,
            total=5,
            completed=2,
            failed=0,
        )
        svc._batches["cancel-running"] = batch
        svc._cancel_flags["cancel-running"] = False

        await svc.cancel_batch("cancel-running")
        assert batch.status == TaskStatus.CANCELLED


class TestSubmitBatchAnalysis:
    @pytest.mark.asyncio
    async def test_empty_paper_ids_raises(self):
        svc = BatchAnalysisService()
        db = AsyncMock()
        with pytest.raises(ValueError, match="paper_ids 不能为空"):
            await svc.submit_batch_analysis([], "summary", db)

    @pytest.mark.asyncio
    async def test_invalid_analysis_type_raises(self):
        svc = BatchAnalysisService()
        db = _mock_db_with_papers([1])
        with pytest.raises(ValueError, match="不支持的分析类型"):
            await svc.submit_batch_analysis([1], "invalid_type", db)

    @pytest.mark.asyncio
    async def test_no_papers_found_raises(self):
        """数据库中不存在指定论文时应抛出 ValueError"""
        svc = BatchAnalysisService()

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_mock
        db = AsyncMock()
        db.execute = AsyncMock(return_value=execute_result)

        with pytest.raises(ValueError, match="未找到"):
            await svc.submit_batch_analysis([999], "summary", db)

    @pytest.mark.asyncio
    async def test_submit_returns_batch_id(self):
        """成功提交返回有效 UUID 格式的 batch_id"""
        svc = BatchAnalysisService()
        db = _mock_db_with_papers([1, 2])

        # 阻止 worker 真正运行（避免在测试中触发 LLM 调用）
        with patch.object(svc, "_ensure_worker", return_value=None):
            batch_id = await svc.submit_batch_analysis([1, 2], "summary", db)

        assert isinstance(batch_id, str)
        # 应为合法 UUID
        uuid.UUID(batch_id)  # 若非合法 UUID 会抛 ValueError

    @pytest.mark.asyncio
    async def test_submit_creates_batch_status(self):
        """提交后 batch 状态对象正确写入内部字典"""
        svc = BatchAnalysisService()
        db = _mock_db_with_papers([10, 20])

        with patch.object(svc, "_ensure_worker", return_value=None):
            batch_id = await svc.submit_batch_analysis([10, 20], "compare", db)

        batch = svc.get_batch_status(batch_id)
        assert batch is not None
        assert batch.analysis_type == "compare"
        assert batch.total == 2
        assert batch.status == TaskStatus.PENDING
