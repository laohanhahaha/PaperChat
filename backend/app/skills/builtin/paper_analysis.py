"""论文深度分析 Skill — 组合多工具完成单篇论文全面分析

工作流：
    Step 1  get_paper_info     → 获取论文元数据（标题/作者/年份/期刊等）
    Step 2  extract_key_points → 提取核心知识点、方法与实验结论
    Step 3  assess_quality     → 从多维度评估论文质量
    Step 4  summarize          → 生成全面的结构化分析摘要

注意：当前实现为框架级示例，展示 Skill 如何编排多步骤工作流。
      真实工具调用将在 Task #72（统一调用接口集成）中接入 ToolRegistry。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillContext, SkillResult, SkillStep

logger = logging.getLogger(__name__)


class PaperAnalysisSkill(BaseSkill):
    """论文深度分析 Skill

    给定单篇论文 ID，自动完成：
    1. 元数据提取（作者、期刊、引用数等）
    2. 核心知识点与研究方法提取
    3. 多维质量评估（创新性、方法严谨性、实验设计等）
    4. 生成结构化分析报告
    """

    # ------------------------------------------------------------------
    # 接口实现
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "paper_analysis"

    @property
    def description(self) -> str:
        return (
            "对单篇论文进行深度分析，提取核心知识点、评估研究质量，"
            "生成包含元数据、核心观点、质量评分的结构化分析报告。"
            "适用于论文精读、研究评估、课题选题等场景。"
        )

    @property
    def tags(self) -> List[str]:
        return ["analysis", "paper", "quality", "分析", "论文", "精读", "评估"]

    @property
    def steps(self) -> List[SkillStep]:
        return [
            SkillStep(
                name="get_paper_info",
                tool_name="get_paper_info",
                description="获取论文元数据：标题、作者、摘要、期刊、引用数等",
                params_template={
                    "paper_id": "{paper_id}",
                },
            ),
            SkillStep(
                name="extract_key_points",
                tool_name="extract_key_points",
                description="提取论文核心知识点、研究方法、实验设计与结论",
                params_template={
                    "paper_id": "{paper_id}",
                    "aspects": [
                        "research_question",
                        "methodology",
                        "key_findings",
                        "contributions",
                        "limitations",
                    ],
                },
            ),
            SkillStep(
                name="assess_quality",
                tool_name="assess_quality",
                description="从多维度评估论文质量（创新性、方法严谨性、实验设计、写作质量）",
                params_template={
                    "paper_id": "{paper_id}",
                    "dimensions": [
                        "novelty",
                        "methodology_rigor",
                        "experimental_design",
                        "writing_clarity",
                        "reproducibility",
                    ],
                },
                optional=True,  # 质量评估为可选步骤（部分论文可能缺少足够内容）
            ),
            SkillStep(
                name="summarize",
                tool_name="summarize",
                description="综合所有分析结果，生成结构化深度分析报告",
                params_template={
                    "paper_id": "{paper_id}",
                    "paper_info": "{paper_info}",
                    "key_points": "{key_points}",
                    "quality_assessment": "{quality_assessment}",
                },
            ),
        ]

    # ------------------------------------------------------------------
    # 执行逻辑
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        """执行论文深度分析工作流

        执行顺序：
            get_paper_info → extract_key_points → assess_quality（可选）→ summarize

        实际工具调用由外层 SkillExecutor（Task #72）负责注入；
        当前实现展示完整的上下文流转与步骤回调逻辑。

        Args:
            ctx: 执行上下文
                - ctx.paper_id: 必填，待分析论文 ID
                - ctx.user_query: 用户分析意图（可影响摘要侧重点）

        Returns:
            SkillResult，data 字段包含完整分析报告字典
        """
        total = len(self.steps)
        steps_done = 0

        paper_id = ctx.paper_id or ctx.variables.get("paper_id")
        if not paper_id:
            return SkillResult(
                success=False,
                error="PaperAnalysisSkill 需要 ctx.paper_id，当前未提供",
                steps_completed=0,
                total_steps=total,
            )

        logger.info("[PaperAnalysisSkill] 开始执行，paper_id: %s", paper_id)

        # ----------------------------------------------------------------
        # Step 1: get_paper_info
        # ----------------------------------------------------------------
        step1 = self.steps[0]
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 get_paper_info(paper_id=paper_id)
            paper_info: Dict[str, Any] = {
                "paper_id": paper_id,
                "title": "",        # 实际由 tool 填充
                "authors": [],      # 实际由 tool 填充
                "year": None,       # 实际由 tool 填充
                "venue": "",        # 实际由 tool 填充
                "abstract": "",     # 实际由 tool 填充
                "citation_count": 0,
            }
            ctx.variables["paper_info"] = paper_info
            steps_done += 1
            await self.on_step_complete(step1, paper_info, ctx)
            logger.debug("[Step 1/4] get_paper_info 完成")
        except Exception as exc:
            logger.error("[Step 1/4] get_paper_info 失败: %s", exc)
            fallback = await self.on_error(step1, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"get_paper_info 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        # ----------------------------------------------------------------
        # Step 2: extract_key_points
        # ----------------------------------------------------------------
        step2 = self.steps[1]
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 extract_key_points(paper_id=paper_id)
            key_points: Dict[str, Any] = {
                "paper_id": paper_id,
                "research_question": "",    # 实际由 tool 填充
                "methodology": "",          # 实际由 tool 填充
                "key_findings": [],         # 实际由 tool 填充
                "contributions": [],        # 实际由 tool 填充
                "limitations": [],          # 实际由 tool 填充
            }
            ctx.variables["key_points"] = key_points
            steps_done += 1
            await self.on_step_complete(step2, key_points, ctx)
            logger.debug("[Step 2/4] extract_key_points 完成")
        except Exception as exc:
            logger.error("[Step 2/4] extract_key_points 失败: %s", exc)
            fallback = await self.on_error(step2, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"extract_key_points 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        # ----------------------------------------------------------------
        # Step 3: assess_quality（可选步骤）
        # ----------------------------------------------------------------
        step3 = self.steps[2]
        quality_assessment: Optional[Dict[str, Any]] = None
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 assess_quality(paper_id=paper_id)
            quality_assessment = {
                "paper_id": paper_id,
                "novelty": None,             # 实际由 tool 填充（0–5 评分）
                "methodology_rigor": None,   # 实际由 tool 填充
                "experimental_design": None, # 实际由 tool 填充
                "writing_clarity": None,     # 实际由 tool 填充
                "reproducibility": None,     # 实际由 tool 填充
                "overall_score": None,       # 实际由 tool 填充
            }
            ctx.variables["quality_assessment"] = quality_assessment
            steps_done += 1
            await self.on_step_complete(step3, quality_assessment, ctx)
            logger.debug("[Step 3/4] assess_quality 完成")
        except Exception as exc:
            # 可选步骤：失败时记录日志但继续执行
            logger.warning("[Step 3/4] assess_quality 失败（可选步骤，跳过）: %s", exc)
            ctx.variables["quality_assessment"] = None
            # steps_done 不递增（可选步骤跳过不计入）

        # ----------------------------------------------------------------
        # Step 4: summarize
        # ----------------------------------------------------------------
        step4 = self.steps[3]
        try:
            # TODO(Task #72): 通过 ToolRegistry 调用 summarize(...)
            summary_result: Dict[str, Any] = {
                "paper_id": paper_id,
                "paper_info": ctx.variables.get("paper_info"),
                "key_points": ctx.variables.get("key_points"),
                "quality_assessment": ctx.variables.get("quality_assessment"),
                "analysis_text": (
                    f"[框架占位] 论文「{paper_id}」的深度分析报告。"
                    "（实际内容将由 LLM 在 Task #72 集成后生成）"
                ),
                "user_query": ctx.user_query,
            }
            ctx.variables["summary_result"] = summary_result
            steps_done += 1
            await self.on_step_complete(step4, summary_result, ctx)
            logger.info("[Step 4/4] summarize 完成")
        except Exception as exc:
            logger.error("[Step 4/4] summarize 失败: %s", exc)
            fallback = await self.on_error(step4, exc, ctx)
            if fallback is not None:
                return fallback
            return SkillResult(
                success=False,
                error=f"summarize 失败: {exc}",
                steps_completed=steps_done,
                total_steps=total,
            )

        return SkillResult(
            success=True,
            data=summary_result,
            steps_completed=steps_done,
            total_steps=total,
        )
