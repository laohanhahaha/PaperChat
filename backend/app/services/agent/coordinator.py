"""多 Agent 研究协调器

ResearchCoordinator 负责：
1. plan()  — 用 LLM 将研究问题分解为结构化子任务（ResearchPlan）
2. execute() — 按依赖关系调度子 Agent（Retriever → Analyzer → Recommender）
3. synthesize() — 整合所有子 Agent 结果为最终报告
4. run() — 主入口，串联完整多 Agent 研究流程

性能说明：
- plan() 1 次 LLM 调用（~500ms-2s）
- execute() 3 个子 Agent 串行，每个 1-3 次 LLM 调用，总耗时约 5-20s
- synthesize() 1 次 LLM 调用（~1-3s）
- 完整流程总耗时约 8-25s，比单 ReAct deep 模式（3-16s）多约 30-60% 开销
- 优势：多角色分工更深入、容错机制保证结果完整性
"""

import json
import logging
import re
import asyncio
from typing import AsyncGenerator, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.agent.research_types import (
    ResearchTask,
    ResearchPlan,
    SubAgentResult,
    ResearchContext,
    AgentRole,
)
from app.prompts.research import (
    ORCHESTRATOR_PLAN_PROMPT,
    ORCHESTRATOR_SYNTHESIZE_PROMPT,
)
from app.services.agent.research_agents import (
    run_retriever_agent,
    run_analyzer_agent,
    run_recommender_agent,
    run_dynamic_agent,
)

logger = logging.getLogger(__name__)

# 默认研究计划（LLM 分解失败时的 fallback）
_DEFAULT_TASKS = [
    ResearchTask(
        task_id="task_1",
        task_type="retrieve",
        query="{query}",
        required_tools=["search_text", "search_papers"],
        depends_on=[],
        agent_name="检索专家",
    ),
    ResearchTask(
        task_id="task_2",
        task_type="analyze",
        query="基于检索结果，深入分析：{query}",
        required_tools=["summarize", "extract_key_points"],
        depends_on=["task_1"],
        agent_name="分析专家",
    ),
    ResearchTask(
        task_id="task_3",
        task_type="recommend",
        query="基于分析结果，推荐后续研究方向：{query}",
        required_tools=[],
        depends_on=["task_2"],
        agent_name="推荐专家",
    ),
]


class ResearchCoordinator:
    """多 Agent 研究协调器

    协调 Retriever、Analyzer、Recommender 三个子 Agent 完成复杂研究任务。
    依赖关系：Retriever 先行 → Analyzer（接收 Retriever 结果）→ Recommender（接收 Analyzer 结果）
    无依赖的任务按类型并行执行（注：当前实现因 SQLAlchemy AsyncSession 限制，实际为有序执行）。
    """

    def __init__(self, react_agent, llm_service, ctx, saved_agents=None):
        """
        Args:
            react_agent: ReActAgent 实例
            llm_service: LLM 服务实例（需有 .llm 属性支持 ainvoke）
            ctx: ToolContext 工具执行上下文
            saved_agents: 已保存的子智能体模板列表（可选）
        """
        self.react_agent = react_agent
        self.llm_service = llm_service
        self.ctx = ctx
        self.context: Optional[ResearchContext] = None
        self.saved_agents = saved_agents or []

    async def plan(self, query: str, chat_history: str = "") -> ResearchPlan:
        """用 LLM 将研究问题分解为子任务

        Args:
            query: 用户研究问题
            chat_history: 对话历史（用于上下文感知分解）

        Returns:
            ResearchPlan 对象，失败时返回默认 3 步计划
        """
        logger.warning(f"[DIAG] Coordinator.plan() 开始: query={query[:100]}")
        try:
            # 构建可用工具描述
            try:
                available_tools = "\n".join([
                    f"- {name}: {tool.description}"
                    for name, tool in self.react_agent.tools.items()
                ])
                if not available_tools:
                    available_tools = "（工具列表为空）"
            except Exception as e:
                logger.warning(f"获取工具列表失败，使用默认工具描述: {e}")
                available_tools = "检索类：search_papers, search_text, get_paper_info, recent_papers\n分析类：summarize, compare_content, extract_key_points, assess_quality, explain_term\n其他：search_cards, save_card, translate, generate_outline"

            # 构建已保存子智能体列表
            saved_agents_text = "暂无已保存的子智能体"
            if self.saved_agents:
                saved_agents_text = "\n".join([
                    f"- ID:{a['id']} 名称:{a['name']} 描述:{a['description']} 工具:{a.get('tool_subset', '不限')}"
                    for a in self.saved_agents
                ])

            prompt_text = ORCHESTRATOR_PLAN_PROMPT.format(
                research_question=query,
                available_tools=available_tools,
                saved_agents=saved_agents_text,
            )
            messages = [
                SystemMessage(content="你是研究任务规划专家，严格按 JSON 格式输出研究计划。"),
                HumanMessage(content=prompt_text),
            ]
            response = await self.llm_service.llm.ainvoke(messages)
            raw = response.content

            # 提取 JSON（可能被 markdown 代码块包裹）
            json_content = raw
            if "```json" in raw:
                json_content = raw.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in raw:
                json_content = raw.split("```", 1)[1].split("```", 1)[0].strip()

            # 尝试直接解析
            data = None
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError:
                # 使用正则提取 JSON 对象
                json_match = re.search(r'\{.*\}', json_content, re.DOTALL)
                if not json_match:
                    raise ValueError("LLM 未返回有效 JSON")
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError as je:
                    raise ValueError(f"JSON 解析失败: {je}")
            # 解析新格式（agents 数组）或旧格式（tasks 数组）兼容
            agents = data.get("agents", data.get("tasks", []))
            tasks = []
            for t in agents:
                agent_name = t.get("agent_name", "")
                agent_prompt = t.get("agent_prompt", "")
                required_tools = t.get("tool_subset", t.get("required_tools", []))
                agent_icon = t.get("agent_icon", "")

                # 处理 agent_ref 引用已保存的子智能体模板
                agent_ref = t.get("agent_ref")
                if agent_ref:
                    matching = next(
                        (a for a in self.saved_agents if str(a.get("id")) == str(agent_ref)),
                        None
                    )
                    if matching:
                        agent_name = agent_name or matching.get("name", "")
                        agent_prompt = agent_prompt or matching.get("system_prompt", matching.get("description", ""))
                        if not required_tools:
                            ref_tools = matching.get("tool_subset", [])
                            required_tools = ref_tools if isinstance(ref_tools, list) else []
                        agent_icon = agent_icon or matching.get("icon", "")
                        logger.info(f"使用已保存模板 '{matching.get('name')}' 创建子智能体")
                    else:
                        logger.warning(f"找不到引用的子智能体模板 ID: {agent_ref}")

                # 确保 required_tools 是列表
                if not isinstance(required_tools, list):
                    required_tools = []

                tasks.append(ResearchTask(
                    task_id=t.get("task_id", f"task_{len(tasks)+1}"),
                    task_type=t.get("task_type", "custom"),
                    query=t.get("query", query),
                    required_tools=required_tools,
                    depends_on=t.get("depends_on", []),
                    agent_name=agent_name,
                    agent_prompt=agent_prompt,
                    agent_icon=agent_icon,
                ))

            if not tasks:
                raise ValueError("解析出的任务列表为空")

            logger.warning(f"[DIAG] plan() 返回 {len(tasks)} 个任务, 来源=LLM")
            logger.info(f"[Coordinator] plan() 来源: LLM分解, 任务数: {len(tasks)}, 任务列表: {[(t.task_id, t.task_type, t.agent_name, t.required_tools) for t in tasks]}")
            return ResearchPlan(
                research_question=data.get("research_question", query),
                tasks=tasks,
                metadata={"source": "llm"},
            )

        except Exception as e:
            logger.warning(f"LLM 分解研究任务失败，使用默认计划: {type(e).__name__}: {e}")
            if 'raw' in locals():
                logger.debug(f"LLM 原始响应前500字符: {raw[:500]}")
            # fallback：默认 3 步计划
            fallback_tasks = []
            for t in _DEFAULT_TASKS:
                fallback_tasks.append(ResearchTask(
                    task_id=t.task_id,
                    task_type=t.task_type,
                    query=t.query.replace("{query}", query),
                    required_tools=list(t.required_tools),
                    depends_on=list(t.depends_on),
                    agent_name=t.agent_name,
                    agent_prompt=t.agent_prompt,
                    agent_icon=t.agent_icon,
                ))
            logger.warning(f"[DIAG] plan() 返回 {len(fallback_tasks)} 个任务, 来源=默认(fallback)")
            logger.info(f"[Coordinator] plan() 来源: 默认计划(fallback), 任务数: {len(fallback_tasks)}, 任务列表: {[(t.task_id, t.task_type, t.agent_name, t.required_tools) for t in fallback_tasks]}")
            return ResearchPlan(
                research_question=query,
                tasks=fallback_tasks,
                metadata={"source": "fallback"},
            )

    async def _run_task(self, task: ResearchTask, chat_history: str = "") -> AsyncGenerator[dict, None]:
        """执行单个子任务，注入前置任务上下文

        按 task_type 路由到对应子 Agent，并将前置任务结果拼入 query 上下文。
        """
        # 构建增强 query（注入前置 Agent 的发现）
        enriched_query = task.query
        if self.context and task.depends_on:
            prior_findings = []
            for dep_id in task.depends_on:
                dep_result = self.context.results.get(dep_id)
                if dep_result and dep_result.success:
                    # 构建包含完整信息的前置任务结果
                    parts = [f"[前置任务 {dep_id} 结果摘要]\n{dep_result.findings}"]
                    # 附加原始工具输出（包含论文元数据：标题、摘要、URL等）
                    if dep_result.evidence:
                        evidence_text = "\n---\n".join(dep_result.evidence[:5])  # 最多5条关键证据
                        parts.append(f"\n[前置任务 {dep_id} 检索到的论文详情]\n{evidence_text}")
                    prior_findings.append("\n".join(parts))
            if prior_findings:
                enriched_query = "\n\n".join(prior_findings) + f"\n\n当前任务：{task.query}"

        logger.info(f"[Coordinator] 执行任务: id={task.task_id}, type={task.task_type}, agent_name={task.agent_name}, tools={task.required_tools}, has_prompt={bool(task.agent_prompt)}")

        # 路由逻辑：优先动态 → 预置 → fallback
        if task.agent_prompt:
            # 动态子智能体（LLM 生成了自定义 prompt）
            agent_gen = run_dynamic_agent(
                self.react_agent, enriched_query, self.ctx, chat_history,
                agent_name=task.agent_name or f"agent_{task.task_id}",
                system_prompt=task.agent_prompt,
                tool_subset=task.required_tools or None,
            )
        elif task.task_type == "retrieve":
            agent_gen = run_retriever_agent(self.react_agent, enriched_query, self.ctx, chat_history)
        elif task.task_type == "analyze":
            agent_gen = run_analyzer_agent(self.react_agent, enriched_query, self.ctx, chat_history)
        elif task.task_type == "recommend":
            agent_gen = run_recommender_agent(self.react_agent, enriched_query, self.ctx, chat_history)
        else:
            # 未知类型 + 无自定义 prompt → 用通用动态工厂
            agent_gen = run_dynamic_agent(
                self.react_agent, enriched_query, self.ctx, chat_history,
                agent_name=task.agent_name or task.task_type,
                system_prompt="",
                tool_subset=task.required_tools or None,
            )

        # 流式 yield 事件，收集 agent_final 用于 SubAgentResult
        final_content = ""
        evidence_parts = []
        has_error = False

        async for event in agent_gen:
            yield event
            # 收集最终结果
            if event.get("type") == "agent_final":
                final_content = event.get("content", "")
                has_error = bool(event.get("error", False))
            # 收集 observation 作为证据
            elif event.get("type") == "agent_observation":
                obs = event.get("content", "")
                if obs and not obs.startswith("[ERROR]"):
                    evidence_parts.append(obs[:2000])  # 保留足够的工具输出内容（含论文元数据）

        # 记录子任务结果到 context
        role_name = task.agent_name or {
            "retrieve": AgentRole.RETRIEVER.value,
            "analyze": AgentRole.ANALYZER.value,
            "recommend": AgentRole.RECOMMENDER.value,
        }.get(task.task_type, task.task_type)

        result = SubAgentResult(
            task_id=task.task_id,
            role=role_name,
            success=not has_error and bool(final_content) and "抱歉" not in final_content and "无法处理" not in final_content,
            findings=final_content,
            evidence=evidence_parts[:15],  # 最多保留 15 条证据
            error=final_content if has_error else None,
        )
        if self.context:
            self.context.add_result(result)

    async def execute(self, plan: ResearchPlan, chat_history: str = "") -> AsyncGenerator[dict, None]:
        """按依赖关系调度子 Agent

        执行策略：
        - 无依赖任务（首轮）优先执行
        - 前置任务完成后，依赖它们的任务进入执行队列
        - 每轮从 plan.get_ready_tasks() 取当前可执行任务集
        - 同轮任务有序执行（避免 AsyncSession 并发冲突）

        Args:
            plan: 研究计划
            chat_history: 对话历史

        Yields:
            各子 Agent 的事件流
        """
        # 初始化研究上下文
        self.context = ResearchContext(plan=plan)
        completed_ids = []

        max_rounds = len(plan.tasks) + 1  # 防止死循环
        round_count = 0

        while not self.context.is_plan_complete() and round_count < max_rounds:
            round_count += 1
            ready_tasks = plan.get_ready_tasks(completed_ids)
            if not ready_tasks:
                logger.warning("没有可执行任务，可能存在循环依赖，停止执行")
                break

            # 发送当前批次开始事件
            task_names = [t.task_id for t in ready_tasks]
            yield {
                "type": "agent_thought",
                "sub_agent": "orchestrator",
                "step": round_count,
                "content": f"开始执行任务：{', '.join(task_names)}",
            }

            # 有序执行当前批次任务（容错：单个任务失败不影响其他）
            for task in ready_tasks:
                yield {
                    "type": "agent_thought",
                    "sub_agent": "orchestrator",
                    "step": round_count,
                    "content": f"正在执行 [{task.task_type}] 任务：{task.query[:80]}...",
                }
                try:
                    async for event in self._run_task(task, chat_history):
                        yield event
                except Exception as e:
                    logger.error(f"任务 {task.task_id} 执行异常: {e}")
                    # 记录失败结果，继续执行
                    fail_result = SubAgentResult(
                        task_id=task.task_id,
                        role=task.task_type,
                        success=False,
                        findings="",
                        error=str(e),
                    )
                    self.context.add_result(fail_result)
                    yield {
                        "type": "agent_thought",
                        "sub_agent": "orchestrator",
                        "step": round_count,
                        "content": f"任务 {task.task_id} 遇到错误，已跳过：{str(e)[:100]}",
                    }

                completed_ids.append(task.task_id)

    async def synthesize(self, context: ResearchContext, query: str) -> str:
        """整合所有子 Agent 结果为最终报告

        Args:
            context: 包含所有子任务结果的研究上下文
            query: 原始研究问题

        Returns:
            综合研究报告文本
        """
        # 格式化子 Agent 结果
        results_text_parts = []
        for task_id, result in context.results.items():
            task = context.plan.get_task_by_id(task_id)
            task_type = task.task_type if task else "unknown"
            status = "成功" if result.success else f"失败（{result.error}）"
            parts = [
                f"=== {result.role.upper()} 任务（{task_id}）状态：{status} ===",
                f"任务描述：{task.query if task else '未知'}",
                f"主要发现：{result.findings[:500] if result.findings else '无'}",
            ]
            if result.evidence:
                evidence_preview = "\n".join(f"  - {e[:150]}" for e in result.evidence[:5])
                parts.append(f"支撑证据：\n{evidence_preview}")
            results_text_parts.append("\n".join(parts))

        sub_agent_results = "\n\n".join(results_text_parts) if results_text_parts else "无子任务结果"

        try:
            prompt_text = ORCHESTRATOR_SYNTHESIZE_PROMPT.format(
                sub_agent_results=sub_agent_results,
                research_question=query,
            )
            messages = [
                SystemMessage(content="你是学术研究整合专家，擅长将多维度研究结果整合为结构清晰的报告。"),
                HumanMessage(content=prompt_text),
            ]
            response = await self.llm_service.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"结果整合 LLM 调用失败: {e}")
            # fallback：直接拼接各子任务结果
            fallback_parts = [f"# 多 Agent 研究报告\n\n**研究问题：** {query}\n"]
            for task_id, result in context.results.items():
                if result.success and result.findings:
                    fallback_parts.append(f"## {result.role}\n{result.findings[:800]}\n")
            if len(fallback_parts) == 1:
                fallback_parts.append("未能收集到足够的研究结果，请重试。")
            return "\n".join(fallback_parts)

    async def run(self, query: str, chat_history: str = "") -> AsyncGenerator[dict, None]:
        """多 Agent 研究主入口：计划 → 执行 → 整合

        完整流程：
        1. Orchestrator 分解任务（1 次 LLM）
        2. 子 Agent 按依赖顺序执行（3-9 次 LLM）
        3. Orchestrator 整合结果（1 次 LLM）
        总耗时约 8-25s（比普通 ReAct deep 模式多 30-60%）

        Args:
            query: 用户研究问题
            chat_history: 对话历史

        Yields:
            事件字典（含 sub_agent 字段区分来源）
        """
        logger.warning(f"[DIAG] Coordinator.run() 开始: query={query[:100]}")
        # 阶段 1：任务分解
        yield {
            "type": "agent_thought",
            "sub_agent": "orchestrator",
            "step": 0,
            "content": "正在分析研究问题，制定研究计划...",
        }

        try:
            plan = await self.plan(query, chat_history)
        except Exception as e:
            logger.error(f"研究计划制定失败: {e}")
            yield {
                "type": "agent_final",
                "sub_agent": "orchestrator",
                "content": f"抱歉，无法制定研究计划：{str(e)}",
            }
            return

        yield {
            "type": "agent_thought",
            "sub_agent": "orchestrator",
            "step": 0,
            "content": f"已将研究问题分解为 {len(plan.tasks)} 个子任务（来源：{'LLM 分解' if plan.metadata.get('source') == 'llm' else '默认计划'}）",
        }

        # 阶段 2：执行子 Agent
        try:
            async for event in self.execute(plan, chat_history):
                yield event
        except Exception as e:
            logger.error(f"子 Agent 执行阶段失败: {e}")
            yield {
                "type": "agent_thought",
                "sub_agent": "orchestrator",
                "step": 99,
                "content": f"部分子任务执行遇到问题：{str(e)[:100]}，尝试整合已有结果...",
            }

        # 确保 context 已初始化（execute 可能提前失败）
        if self.context is None:
            self.context = ResearchContext(plan=plan)

        # 阶段 3：整合结果
        yield {
            "type": "agent_thought",
            "sub_agent": "orchestrator",
            "step": 99,
            "content": f"所有子任务已完成（{len(self.context.results)} 个），正在整合研究结果...",
        }

        try:
            final_report = await self.synthesize(self.context, query)
        except Exception as e:
            logger.error(f"结果整合失败: {e}")
            final_report = f"研究分析已完成，但整合报告生成失败：{str(e)}"

        yield {
            "type": "agent_final",
            "sub_agent": "orchestrator",
            "content": final_report,
        }
