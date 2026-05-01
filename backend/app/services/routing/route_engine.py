"""智能模型路由器 — 基于查询复杂度和用户偏好自动选择最优模型

从 app.services.llm.llm_service.ModelRouter 提取，修复本地模式返回错误的问题。
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ModelRouter:
    """智能模型路由器 — 基于查询复杂度和用户偏好自动选择最优模型

    路由决策 <1ms（纯规则判断），不引入额外延迟。
    """

    # 任务复杂度映射
    TASK_COMPLEXITY = {
        "simple_qa": "simple",
        "explain_term": "simple",
        "translate": "simple",
        "summarize": "medium",
        "key_points": "medium",
        "compare_content": "complex",
        "deep_analysis": "complex",
        "literature_review": "complex",
        "research_assistant": "complex",
        "multimodal": "medium",
    }

    async def route(
        self,
        query: str,
        task_type: str,
        user_id: int,
        db=None,
        paper_id: int = None,
        paper_ids: Optional[List[int]] = None,
    ) -> dict:
        """路由决策

        Args:
            query: 用户查询
            task_type: 任务类型
            user_id: 用户 ID
            db: 数据库会话（可选）
            paper_id: 当前论文 ID，用于隐私检查
            paper_ids: 当前选中的多篇论文 ID 列表

        Returns:
            {
                "model": "模型名",
                "tier": "cloud_standard|cloud_premium",
                "estimated_cost": 0.0,
                "needs_confirmation": False,
                "reason": "路由原因说明",
                "privacy_enforced": False
            }
        """
        # Import here to avoid circular import at module level
        from app.services.llm.llm_service import llm_service as _llm

        # 0. 隐私检查：隐私论文强制使用默认模型
        if paper_id:
            try:
                result = await self._check_paper_privacy(paper_id, db)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"隐私检查失败（非阻塞）: {e}")

        if paper_ids:
            try:
                result = await self._check_papers_privacy(paper_ids, db)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"多论文隐私检查失败（非阻塞）: {e}")

        from app.services.settings_service import SettingsService
        from app.services.cost.cost_service import CostService

        settings_svc = SettingsService()
        cost_svc = CostService()

        # 1. 获取用户偏好
        if db:
            user_settings = await settings_svc.get_setting_values(user_id, db)
        else:
            user_settings = {}
        routing = user_settings.get("routing", {})
        model_mode = routing.get("model_mode", "smart_route")
        budget_limit = routing.get("budget_limit", 10.0)
        confirm_threshold = routing.get("confirm_threshold", 0.5)

        # 2. 固定模式
        if model_mode == "local_only":
            return {
                "model": _llm._model,
                "tier": "cloud_standard",
                "estimated_cost": 0,
                "needs_confirmation": False,
                "reason": "用户选择仅本地模式（当前环境无本地模型，使用默认云端模型）",
                "privacy_enforced": False,
            }
        elif model_mode == "cloud_only":
            return await self._select_cloud(
                task_type, cost_svc, user_id, budget_limit, confirm_threshold, db
            )

        # 3. 智能路由
        complexity = self.TASK_COMPLEXITY.get(task_type, "medium")

        # 检查预算
        if db:
            try:
                budget_info = await cost_svc.get_budget_status_by_user_id(db, user_id)
                budget_remaining = budget_limit - budget_info.get("used", 0)
            except Exception:
                budget_remaining = budget_limit
        else:
            budget_remaining = budget_limit

        if budget_remaining <= 0:
            return {
                "model": _llm._model,
                "tier": "cloud_standard",
                "estimated_cost": 0,
                "needs_confirmation": False,
                "reason": "月度预算已用尽，使用默认模型",
                "privacy_enforced": False,
            }

        # 按复杂度选择
        if complexity == "simple":
            return {
                "model": _llm._model,
                "tier": "cloud_standard",
                "estimated_cost": 0,
                "needs_confirmation": False,
                "reason": "简单任务，使用默认模型",
                "privacy_enforced": False,
            }
        elif complexity == "medium":
            estimated = 0.01
            return {
                "model": _llm._model,
                "tier": "cloud_standard",
                "estimated_cost": estimated,
                "needs_confirmation": estimated > confirm_threshold,
                "reason": "中等复杂度，使用云端标准模型",
                "privacy_enforced": False,
            }
        else:
            estimated = 0.05
            return {
                "model": _llm._model,
                "tier": "cloud_premium",
                "estimated_cost": estimated,
                "needs_confirmation": estimated > confirm_threshold,
                "reason": "复杂任务，使用云端高级模型",
                "privacy_enforced": False,
            }

    async def _select_cloud(
        self, task_type, cost_svc, user_id, budget_limit, confirm_threshold, db=None
    ) -> dict:
        """选择云端模型"""
        from app.services.llm.llm_service import llm_service as _llm

        complexity = self.TASK_COMPLEXITY.get(task_type, "medium")
        if complexity in ("simple", "medium"):
            return {
                "model": _llm._model,
                "tier": "cloud_standard",
                "estimated_cost": 0.01,
                "needs_confirmation": False,
                "reason": "云端标准模型",
                "privacy_enforced": False,
            }
        else:
            estimated = 0.05
            return {
                "model": _llm._model,
                "tier": "cloud_premium",
                "estimated_cost": estimated,
                "needs_confirmation": estimated > confirm_threshold,
                "reason": "云端高级模型",
                "privacy_enforced": False,
            }

    async def _check_paper_privacy(self, paper_id: int, db=None) -> Optional[dict]:
        """检查单篇论文隐私状态"""
        from app.services.llm.llm_service import llm_service as _llm

        try:
            from app.models.paper import Paper
            from sqlalchemy import select

            _db = db
            _should_close = False
            if _db is None:
                from app.database import AsyncSessionLocal

                _db = AsyncSessionLocal()
                _should_close = True
            try:
                result = await _db.execute(select(Paper).where(Paper.id == paper_id))
                paper = result.scalar_one_or_none()
                if paper and paper.is_private:
                    return {
                        "model": _llm._model,
                        "tier": "cloud_standard",
                        "reason": "privacy_enforced",
                        "privacy_enforced": True,
                        "estimated_cost": 0.0,
                        "needs_confirmation": False,
                    }
            finally:
                if _should_close:
                    await _db.close()
        except Exception:
            logger.warning("隐私检查失败（非阻塞）", exc_info=True)
        return None

    async def _check_papers_privacy(self, paper_ids: list, db=None) -> Optional[dict]:
        """检查多篇论文隐私状态"""
        from app.services.llm.llm_service import llm_service as _llm

        try:
            from app.models.paper import Paper
            from sqlalchemy import select

            _db = db
            _should_close = False
            if _db is None:
                from app.database import AsyncSessionLocal

                _db = AsyncSessionLocal()
                _should_close = True
            try:
                result = await _db.execute(
                    select(Paper).where(Paper.id.in_(paper_ids))
                )
                papers = result.scalars().all()
                if any(p.is_private for p in papers):
                    return {
                        "model": _llm._model,
                        "tier": "cloud_standard",
                        "reason": "privacy_enforced",
                        "privacy_enforced": True,
                        "estimated_cost": 0.0,
                        "needs_confirmation": False,
                    }
            finally:
                if _should_close:
                    await _db.close()
        except Exception:
            logger.warning("多论文隐私检查失败（非阻塞）", exc_info=True)
        return None


# 全局单例
model_router = ModelRouter()
