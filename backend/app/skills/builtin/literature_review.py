"""文献综述 Skill — 组合多工具生成系统性文献综述

工作流：
    Step 1  search_papers     → 搜索与研究主题相关的论文
    Step 2  search_text       → 对每篇论文提取关键段落/内容
    Step 3  literature_review → 综合上述内容生成结构化综述

注意：当前实现为框架级示例，展示 Skill 如何编排多步骤工作流。
      真实工具调用将在 Task #72（统一调用接口集成）中接入 ToolRegistry。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillContext, SkillResult, SkillStep

logger = logging.getLogger(__name__)


class LiteratureReviewSkill(BaseSkill):
    """文献综述 Skill

    给定研究主题，自动完成：
    1. 多源论文检索
    2. 逐篇关键内容抽取
    3. 综合生成结构化文献综述
    """

    # ------------------------------------------------------------------
    # 接口实现
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "literature_review"

    @property
    def description(self) -> str:
        return (
            "根据研究主题自动检索相关论文，提取核心内容，"
            "生成结构化文献综述报告。适用于开题调研、综述撰写等场景。"
        )

    @property
    def tags(self) -> List[str]:
        return ["review", "literature", "survey", "综述", "文献", "调研"]

    @property
    def steps(self) -> List[SkillStep]:
        return [
            SkillStep(
                name="search_papers",
                tool_name="search_papers",
                description="根据研究主题关键词检索相关论文",
                params_template={
                    "query": "{topic}",
                    "top_k": 10,
                },
            ),
            SkillStep(
                name="search_text",
                tool_name="search_text",
                description="对检索到的每篇论文提取与主题相关的关键段落",
                params_template={
                    "query": "{topic}",
                    "paper_ids": "{paper_ids}",
                    "top_k": 5,
                },
            ),
            SkillStep(
                name="literature_review",
                tool_name="literature_review",
                description="综合所有论文内容，生成结构化文献综述",
                params_template={
                    "topic": "{topic}",
                    "papers": "{paper_summaries}",
                },
            ),
        ]

    # ------------------------------------------------------------------
    # 执行逻辑
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        """执行文献综述工作流

        执行顺序：
            search_papers → search_text（per paper） → literature_review

        实际工具调用由外层 SkillExecutor（Task #72）负责注入；
        当前实现展示完整的上下文流转与步骤回调逻辑。

        Args:
            ctx: 执行上下文
                - ctx.user_query:          用户原始查询（作为研究主题）
                - ctx.variables["topic"]:  可选，覆盖研究主题
                - ctx.paper_ids:           可选，限定检索范围

        Returns:
            SkillResult，data 字段包含综述文本与引用论文列表
        """
        total = len(self.steps)
        steps_done = 0

        # 提取研究主题
        topic: str = ctx.variables.get("topic") or ctx.user_query
        logger.info("[LiteratureReviewSkill] 开始执行，主题: %s", topic)

        # ----------------------------------------------------------------
        # Step 1: search_papers
        # ----------------------------------------------------------------
        step1 = self.steps[0]
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 search_papers(query=topic, top_k=10)
            # 框架示例：模拟检索结果结构
            search_result: Dict[str, Any] = {
                "papers": ctx.paper_ids or [],  # 实际会由 tool 填充
                "total": len(ctx.paper_ids),
            }
            ctx.variables["paper_ids"] = search_result["papers"]
            ctx.variables["search_result"] = search_result
            steps_done += 1
            await self.on_step_complete(step1, search_result, ctx)
            logger.debug("[Step 1/3] search_papers 完成，命中 %d 篇", len(search_result["papers"]))
        except Exception as exc:
            logger.error("[Step 1/3] search_papers 失败: %s", exc)
            fallback = await self.on_error(step1, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"search_papers 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        # ----------------------------------------------------------------
        # Step 2: search_text — 对每篇论文提取关键段落
        # ----------------------------------------------------------------
        step2 = self.steps[1]
        paper_summaries: List[Dict[str, Any]] = []
        paper_ids: List[str] = ctx.variables.get("paper_ids", [])
        try:
            for paper_id in paper_ids:
                # TODO(Task #72): 通过 ToolRegistry 调用 search_text(query=topic, paper_id=paper_id)
                # 框架示例：模拟单篇提取结构
                text_result: Dict[str, Any] = {
                    "paper_id": paper_id,
                    "snippets": [],   # 实际由 tool 填充
                    "summary": "",    # 实际由 tool 填充
                }
                paper_summaries.append(text_result)

            ctx.variables["paper_summaries"] = paper_summaries
            steps_done += 1
            await self.on_step_complete(step2, paper_summaries, ctx)
            logger.debug("[Step 2/3] search_text 完成，处理 %d 篇", len(paper_summaries))
        except Exception as exc:
            logger.error("[Step 2/3] search_text 失败: %s", exc)
            fallback = await self.on_error(step2, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"search_text 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        # ----------------------------------------------------------------
        # Step 3: literature_review — 生成综述
        # ----------------------------------------------------------------
        step3 = self.steps[2]
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 literature_review(topic=topic, papers=paper_summaries)
            # 框架示例：占位结果结构
            review_result: Dict[str, Any] = {
                "topic": topic,
                "review_text": (
                    f"[框架占位] 关于「{topic}」的文献综述，"
                    f"共引用 {len(paper_ids)} 篇论文。"
                    "（实际内容将由 LLM 在 Task #72 集成后生成）"
                ),
                "cited_papers": paper_ids,
                "sections": [
                    "研究背景",
                    "主要方法",
                    "关键发现",
                    "研究空白与展望",
                ],
            }
            ctx.variables["review_result"] = review_result
            steps_done += 1
            await self.on_step_complete(step3, review_result, ctx)
            logger.info("[Step 3/3] literature_review 完成")
        except Exception as exc:
            logger.error("[Step 3/3] literature_review 失败: %s", exc)
            fallback = await self.on_error(step3, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"literature_review 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        return SkillResult(
            success=True,
            data=review_result,
            steps_completed=steps_done,
            total_steps=total,
        )
