"""Agent 核心服务 — 工具注册表、任务规划与执行

职责说明（拆分后）：
- 工具注册：_register_tools() 从 tools/ 子包导入所有工具类并实例化
- 意图识别：classify_intent() 委托给 intent.py 的 classify_intent_full()
- 任务规划：plan_tasks() —— 简单请求直接生成；复杂请求用 LLM 规划
- 任务执行：execute_plan() —— 逐步调用工具，流式 yield 进度/结果
- 结果聚合：aggregate_results() —— LLM 流式整合多步结果

Agent 多步推理每多一步需要额外一次 LLM 调用：
- 意图识别：约 500ms + 200 tokens
- 任务规划：约 1-2s + 500 tokens
- 每步工具调用：取决于具体工具
- 结果聚合：约 1-2s + 500-2000 tokens

总体性能影响：
- 简单请求增加约 1s（只做意图识别后直接走 RAG 问答）
- 复杂请求增加 3-8s
"""
from typing import AsyncGenerator
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service

# 从独立模块导入工具基类，避免循环依赖
from app.services.core.tool_base import Tool, ToolContext, ToolResult  # noqa: F401 — 重新导出以保持向后兼容

# 工具统一管理层
from app.tools import ToolRegistry, ToolExecutor

# 意图识别（关键词 + LLM 双通道）
from app.services.agent.intent import (  # noqa: F401 — 重新导出以保持向后兼容
    classify_by_keywords,
    classify_by_llm,
    classify_intent_full,
    INTENT_KEYWORDS,
    INTENT_CLASSIFICATION_PROMPT,
)
from app.prompts.agent import TASK_PLANNING_PROMPT  # 从 app.prompts 统一导入（保持向后兼容）
from app.services.agent.planner import AgentPlanner  # 任务规划器（已拆分）

logger = logging.getLogger(__name__)

# TASK_PLANNING_PROMPT 已迁移至 app.prompts.agent，此处通过顶部 import 引入


class _RegistryDictView:
    """ToolRegistry 的 dict 兼容视图

    提供 .get(name) 接口，使 execute_plan 中的 self.tools.get(tool_name)
    无需改动即可通过 ToolRegistry 查找工具（向后兼容）。
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def get(self, name: str):
        return self._registry.get(name)

    def values(self):
        return self._registry.list_tools()

    def __len__(self) -> int:
        return len(self._registry)

    def keys(self):
        """返回所有已注册工具的名称列表"""
        return [tool.name for tool in self._registry.list_tools()]

    def items(self):
        """返回 (name, tool) 元组列表，与字典.items()兼容"""
        return [(tool.name, tool) for tool in self._registry.list_tools()]

    def __iter__(self):
        """支持 for name in self.tools 迭代"""
        return iter(self.keys())

    def __contains__(self, name: str) -> bool:
        """支持 'tool_name' in self.tools 检查"""
        return self.get(name) is not None


class AgentService:
    """Agent 核心服务"""

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self._register_tools()
        # 向后兼容：提供 dict 视图，execute_plan 通过 self.tools.get() 访问
        self.tools = _RegistryDictView(self.tool_registry)
        # 任务规划器（已拆分至 planner.py）
        self._planner = AgentPlanner()

    def _register_tools(self) -> None:
        """从 tools/ 子包导入并注册所有可用工具到 ToolRegistry"""
        from app.services.agent.tools import (
            # paper_tools
            SearchTextTool,
            ExtractKeyPointsTool,
            GetPaperInfoTool,
            # analysis_tools
            SummarizeTool,
            TranslateTool,
            ExplainTermTool,
            CompareContentTool,
            AssessQualityTool,
            # writing_tools
            LiteratureReviewTool,
            CitePaperTool,
            PolishTextTool,
            # knowledge_tools
            SaveCardTool,
            SearchCardsTool,
            # query_tools
            RecentPapersTool,
            SearchPapersTool,
            GenerateOutlineTool,
            # cross_doc_tools
            DetectContradictionTool,
            TraceEvolutionTool,
            VerifyConsistencyTool,
            FindResearchGapsTool,
            CrossPaperReasonTool,
            # multimodal_tools
            MultimodalSearchTool,
        )
        tools = [
            SearchTextTool(),
            ExtractKeyPointsTool(),
            SummarizeTool(),
            TranslateTool(),
            ExplainTermTool(),
            GetPaperInfoTool(),
            CompareContentTool(),
            GenerateOutlineTool(),
            AssessQualityTool(),
            # 写作类
            LiteratureReviewTool(),
            CitePaperTool(),
            PolishTextTool(),
            # 知识库类
            SaveCardTool(),
            SearchCardsTool(),
            # 论文查询类
            RecentPapersTool(),
            SearchPapersTool(),
            # 跨论文推理类
            DetectContradictionTool(),
            TraceEvolutionTool(),
            VerifyConsistencyTool(),
            FindResearchGapsTool(),
            CrossPaperReasonTool(),
            # 多模态工具
            MultimodalSearchTool(),
        ]
        self.tool_registry.register_many(tools)

    def get_tools(self) -> list:
        """返回所有已注册工具列表（供外部使用）"""
        return self.tool_registry.list_tools()

    def get_tool_schemas(self) -> list[dict]:
        """返回所有工具的 JSON Schema 列表"""
        return self.tool_registry.get_schemas()

    def get_all_schemas(self) -> list[dict]:
        """返回所有工具的 schema 列表，供 ReAct Prompt 使用"""
        return self.tool_registry.get_schemas()

    def get_tools_description(self) -> str:
        """返回格式化的工具描述字符串，用于 Prompt 注入"""
        lines = []
        for tool in self.tool_registry.list_tools():
            schema = tool.get_schema()
            params = schema.get("parameters", {}).get("properties", {})
            required = schema.get("parameters", {}).get("required", [])
            param_strs = []
            for pname, pinfo in params.items():
                req = " (required)" if pname in required else ""
                param_strs.append(f"{pname}: {pinfo.get('type', 'any')}{req}")
            params_desc = ", ".join(param_strs) if param_strs else "无参数"
            lines.append(f"- {schema['name']}: {schema['description']} | 参数: {params_desc}")
        return "\n".join(lines)

    async def classify_intent(self, user_message: str) -> dict:
        """意图识别（委托给 intent.classify_intent_full）

        使用 LLM 判断用户请求类型，返回：
        {
            "intent": "simple_qa|analysis|comparison|search|writing|multi_step",
            "requires_tools": ["search_text", "summarize"],
            "complexity": "low|medium|high",
            "reasoning": "判断理由"
        }

        性能：约 500ms + 200 tokens
        """
        return await classify_intent_full(user_message)

    async def plan_tasks(self, user_message: str, intent: dict, context: dict = None) -> list[dict]:
        """任务规划（委托给 AgentPlanner）

        对于复杂请求，拆解为有序的子任务列表：
        [
            {"step": 1, "tool": "search_text", "params": {...}, "description": "搜索相关内容"},
            {"step": 2, "tool": "summarize", "params": {...}, "description": "生成摘要"},
            ...
        ]

        简单请求：直接返回单步计划（无 LLM 调用）
        复杂请求：委托 AgentPlanner 使用 LLM 进行多步规划

        性能：约 1-2s + 500 tokens（仅复杂请求）
        """
        return await self._planner.plan(user_message, intent, context)

    async def execute_plan(self, plan: list[dict], context: dict) -> AsyncGenerator[dict, None]:
        """执行任务计划

        逐步执行，每步返回进度和结果：
        yield {"type": "step_start", "step": 1, "description": "搜索相关内容"}
        yield {"type": "step_result", "step": 1, "result": {...}}
        ...
        yield {"type": "final_answer", "content": "最终整合答案"}

        性能：取决于具体工具调用
        """
        step_results = {}
        db = context.get("db")
        paper_id = context.get("paper_id")
        paper_ids = context.get("paper_ids", [])
        user_id = context.get("user_id")
        session_id = context.get("session_id")

        # 创建统一的工具执行上下文
        ctx = ToolContext(
            db=db,
            paper_id=paper_id,
            paper_ids=paper_ids,
            user_id=user_id,
            session_id=session_id
        )

        for step in plan:
            step_num = step.get("step", 1)
            tool_name = step.get("tool", "")
            params = step.get("params", {})
            description = step.get("description", f"执行步骤 {step_num}")

            # 发送步骤开始事件
            yield {
                "type": "step_start",
                "step": step_num,
                "description": description,
                "tool": tool_name
            }

            try:
                # 获取工具并执行
                tool = self.tools.get(tool_name)
                if not tool:
                    result = {"error": f"未知工具: {tool_name}"}
                else:
                    tool_result = await tool.execute(ctx, **params)
                    # 将 ToolResult 转换为 dict 以保持兼容性
                    result = {
                        "success": tool_result.success,
                        **tool_result.data
                    }
                    if tool_result.error:
                        result["error"] = tool_result.error

                step_results[step_num] = result

                # 发送步骤结果
                yield {
                    "type": "step_result",
                    "step": step_num,
                    "result": result,
                    "status": "success" if result.get("success", True) and not result.get("error") else "error"
                }

            except Exception as e:
                error_result = {"error": str(e), "success": False}
                step_results[step_num] = error_result
                yield {
                    "type": "step_result",
                    "step": step_num,
                    "result": error_result,
                    "status": "error"
                }

        # 聚合结果生成最终答案
        async for chunk in self.aggregate_results(step_results, context.get("original_question", "")):
            yield {
                "type": "final_answer_chunk",
                "content": chunk
            }

    async def aggregate_results(self, step_results: dict, original_question: str) -> AsyncGenerator[str, None]:
        """结果聚合

        将多步工具调用结果整合为连贯的最终回答
        使用 LLM 流式输出

        性能：约 1-2s + 500-2000 tokens
        """
        if not step_results:
            yield "抱歉，没有获取到任何结果。"
            return

        # 构建结果摘要
        results_summary = []
        for step_num, result in sorted(step_results.items()):
            # 简化结果用于提示词
            simplified = self._simplify_result(result)
            results_summary.append(f"步骤 {step_num}: {simplified}")

        prompt = f"""请基于以下工具执行结果，回答用户的问题。

用户问题：{original_question}

工具执行结果：
{chr(10).join(results_summary)}

要求：
1. 整合所有步骤的结果，给出完整、连贯的回答
2. 保持学术性和专业性
3. 使用中文回答
4. 如有具体数据或引用，请保留

请直接输出最终答案："""

        messages = [
            SystemMessage(content="你是学术问答专家，擅长整合信息并给出清晰的回答。"),
            HumanMessage(content=prompt)
        ]

        async for chunk in llm_service.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    def _simplify_result(self, result: dict, max_length: int = 500) -> str:
        """简化结果用于提示词，避免过长"""
        if "error" in result:
            return f"错误: {result['error']}"

        # 提取关键信息
        if "summary" in result:
            return f"摘要: {result['summary'][:max_length]}"
        if "explanation" in result:
            return f"解释: {result['explanation'][:max_length]}"
        if "translation" in result:
            return f"翻译: {result['translation'][:max_length]}"
        if "results" in result and isinstance(result["results"], list):
            count = len(result["results"])
            return f"检索到 {count} 条结果"
        if "points" in result:
            count = len(result["points"])
            return f"提取了 {count} 个知识点"
        if "comparison" in result:
            return f"对比结果: {result['comparison'][:max_length]}"
        if "outline" in result:
            return f"提纲: {result['outline'][:max_length]}"
        if "assessment" in result:
            return f"评估: {result['assessment'][:max_length]}"
        # 新增工具结果简化
        if "review" in result:
            return f"文献综述: {result['review'][:max_length]}"
        if "citation" in result:
            return f"引用: {result['citation'][:max_length]}"
        if "polished_text" in result:
            return f"润色结果: {result['polished_text'][:max_length]}"
        if "cards" in result and isinstance(result.get("cards"), list):
            count = len(result["cards"])
            return f"找到 {count} 张知识卡片"
        if "papers" in result and isinstance(result.get("papers"), list):
            count = len(result["papers"])
            return f"找到 {count} 篇论文"
        # 跨论文推理类结果简化
        if "analysis" in result and result.get("type") == "cross_paper":
            topic_key = "topic" if "topic" in result else "method_name" if "method_name" in result else "claim" if "claim" in result else "field" if "field" in result else "hypothesis" if "hypothesis" in result else ""
            topic_val = result.get(topic_key, "")
            return f"跨论文分析({topic_key}={topic_val}): {result['analysis'][:max_length]}"

        # 默认返回 JSON 字符串
        return json.dumps(result, ensure_ascii=False)[:max_length]


# 全局单例
agent_service = AgentService()
