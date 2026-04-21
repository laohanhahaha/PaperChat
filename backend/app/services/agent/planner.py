"""Agent 任务规划器

职责：
- 判断请求复杂度，决定是否需要多步规划
- 简单请求直接生成单步计划
- 复杂请求调用 LLM 进行多步分解

性能影响：
- 简单请求：跳过 LLM 调用，无额外延迟
- 复杂请求：约 1-2s + 500 tokens（一次 LLM 调用）
"""
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service
from app.prompts.agent import TASK_PLANNING_PROMPT

logger = logging.getLogger(__name__)


class AgentPlanner:
    """Agent 任务规划器

    根据意图识别结果，将用户请求分解为有序的子任务列表。

    简单请求（complexity=low 或 intent=simple_qa）：
        直接生成单步计划，无需 LLM 调用。

    复杂请求（complexity=medium/high）：
        调用 LLM 使用 TASK_PLANNING_PROMPT 进行多步分解，
        返回结构化的步骤列表。
    """

    async def plan(
        self,
        user_message: str,
        intent: dict,
        context: dict | None = None,
    ) -> list[dict]:
        """生成任务执行计划

        Args:
            user_message: 用户原始消息
            intent: classify_intent_full 返回的意图字典，含 intent/complexity 字段
            context: 上下文信息，如 paper_id、paper_ids 等

        Returns:
            步骤列表，每项格式：
            {
                "step": int,
                "tool": str,
                "params": dict,
                "description": str,
                "depends_on": list
            }
        """
        context = context or {}
        complexity = intent.get("complexity", "low")
        intent_type = intent.get("intent", "simple_qa")

        if complexity == "low" or intent_type == "simple_qa":
            return self._simple_plan(user_message, context)

        return await self._llm_plan(user_message, intent, context)

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    def _simple_plan(self, user_message: str, context: dict) -> list[dict]:
        """为简单请求生成单步计划（无 LLM 调用）"""
        paper_id = context.get("paper_id")
        if paper_id:
            return [{
                "step": 1,
                "tool": "search_text",
                "params": {"paper_id": paper_id, "query": user_message, "top_k": 5},
                "description": "搜索相关内容并直接回答",
                "depends_on": []
            }]
        return [{
            "step": 1,
            "tool": "explain_term",
            "params": {"term": user_message, "context": ""},
            "description": "直接回答用户问题",
            "depends_on": []
        }]

    async def _llm_plan(
        self,
        user_message: str,
        intent: dict,
        context: dict,
    ) -> list[dict]:
        """调用 LLM 进行复杂多步任务规划

        约 1-2s + 500 tokens
        """
        prompt = TASK_PLANNING_PROMPT.format(
            message=user_message,
            intent=json.dumps(intent, ensure_ascii=False),
            context=json.dumps(context, ensure_ascii=False)
        )

        messages = [
            SystemMessage(content="你是任务规划专家。"),
            HumanMessage(content=prompt)
        ]

        try:
            response = await llm_service.llm.ainvoke(messages)
            content = response.content

            # 提取 JSON 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            plan: list[dict] = json.loads(content.strip())

            # 注入上下文中的 paper_id
            paper_id = context.get("paper_id")
            if paper_id:
                for step in plan:
                    if "paper_id" in step.get("params", {}):
                        step["params"]["paper_id"] = paper_id

            return plan

        except Exception as e:
            logger.warning(f"[AgentPlanner] LLM 规划失败，降级为默认计划: {e}")
            return self._fallback_plan(user_message, context)

    def _fallback_plan(self, user_message: str, context: dict) -> list[dict]:
        """LLM 规划失败时的降级方案"""
        paper_id = context.get("paper_id")
        if paper_id:
            return [{
                "step": 1,
                "tool": "search_text",
                "params": {"paper_id": paper_id, "query": user_message, "top_k": 5},
                "description": "搜索相关内容（规划失败后的默认步骤）",
                "depends_on": []
            }]
        return []


# 全局单例
agent_planner = AgentPlanner()
