"""ConfigAgent — LLM 驱动的自主配置 Agent

复用 ReActAgent 的推理循环逻辑，使用专用的系统提示词和配置工具集。
事件流格式与 ReActAgent 完全一致，前端 AgentProgress 组件可直接复用。

性能影响：
- 配置意图检测：关键词匹配 O(1)，<1ms
- ConfigAgent 推理循环：每轮 1 次 LLM 调用（500ms-2s），通常 2-4 轮
- 工具执行：configure_service 启动 MCP Server 约 1-3s，validate_service 约 200ms-2s
- 总体：简单配置（免费服务）约 3-8s，需 API Key 的服务约 5-15s
"""
import json
import logging
from typing import AsyncGenerator, Optional, List

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service
from app.tools.base import Tool, ToolContext, ToolResult
from app.tools.config_tools import (
    ListAvailableServicesTool,
    ConfigureServiceTool,
    ValidateServiceTool,
    GetServiceStatusTool,
    UpdateApiKeyTool,
)
from app.prompts.config import CONFIG_AGENT_SYSTEM_PROMPT, CONFIG_AGENT_USER_PROMPT

logger = logging.getLogger(__name__)


# 配置意图检测关键词
CONFIG_INTENT_KEYWORDS = [
    "配置", "设置", "接入", "连接", "启用", "关闭",
    "服务", "API Key", "apikey", "api key",
    "configure", "setup", "connect", "enable", "disable",
    "arxiv", "semantic scholar", "crossref", "dblp", "zotero",
    "websearch", "academic",
    "MCP", "mcp",
]


def is_config_intent(message: str) -> bool:
    """检测消息是否包含配置意图

    性能影响：关键词匹配 O(n)，n 为关键词数量（约 15 个），<1ms。
    """
    message_lower = message.lower()
    for keyword in CONFIG_INTENT_KEYWORDS:
        if keyword.lower() in message_lower:
            return True
    return False


class ConfigAgent:
    """LLM 驱动的自主配置 Agent

    复用 ReAct 的 Thought-Action-Observation 循环，
    使用专用的配置工具集和系统提示词。

    用法：
        agent = ConfigAgent.from_app_state(app.state)
        async for event in agent.run(query, ctx):
            # event.type: agent_thought / agent_action / agent_observation / agent_final
            ...
    """

    def __init__(
        self,
        mcp_manager=None,
        health_service=None,
        settings_service=None,
        tool_registry=None,
        event_bus=None,
        max_iterations: int = 5,
    ):
        self.mcp_manager = mcp_manager
        self.health_service = health_service
        self.settings_service = settings_service
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self.max_iterations = max_iterations

        # 初始化配置工具集（通过闭包注入服务引用）
        self.tools: dict[str, Tool] = {}
        self._init_tools()

    @classmethod
    def from_app_state(cls, app_state) -> "ConfigAgent":
        """从 FastAPI app.state 创建 ConfigAgent 实例

        Args:
            app_state: FastAPI app.state 对象

        Returns:
            ConfigAgent 实例
        """
        return cls(
            mcp_manager=getattr(app_state, "mcp_manager", None),
            health_service=getattr(app_state, "health_service", None),
            settings_service=getattr(app_state, "settings_service", None),
            tool_registry=getattr(app_state, "tool_registry", None),
            event_bus=getattr(app_state, "event_bus", None),
        )

    def _init_tools(self):
        """初始化配置工具集"""
        tool_instances = [
            ListAvailableServicesTool(
                mcp_manager=self.mcp_manager,
            ),
            ConfigureServiceTool(
                mcp_manager=self.mcp_manager,
                tool_registry=self.tool_registry,
                event_bus=self.event_bus,
            ),
            ValidateServiceTool(
                mcp_manager=self.mcp_manager,
                health_service=self.health_service,
                settings_service=self.settings_service,
            ),
            GetServiceStatusTool(
                mcp_manager=self.mcp_manager,
                health_service=self.health_service,
            ),
            UpdateApiKeyTool(
                settings_service=self.settings_service,
                mcp_manager=self.mcp_manager,
            ),
        ]
        for tool in tool_instances:
            self.tools[tool.name] = tool

    def get_tools_description(self) -> str:
        """生成工具描述文本（供系统提示词使用）"""
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
            if tool.parameters.get("properties"):
                props = tool.parameters["properties"]
                required = tool.parameters.get("required", [])
                for pname, pdef in props.items():
                    req_mark = "（必填）" if pname in required else "（可选）"
                    lines.append(f"    - {pname}: {pdef.get('description', '')}{req_mark}")
        return "\n".join(lines)

    async def run(
        self,
        query: str,
        ctx: ToolContext,
        chat_history: str = "",
        thinking_mode: str = "quick",
    ) -> AsyncGenerator[dict, None]:
        """执行配置任务，返回事件流（与 ReActAgent 格式一致）

        Args:
            query: 用户问题
            ctx: 工具执行上下文
            chat_history: 格式化后的对话历史
            thinking_mode: "quick"(max_iterations=3) 或 "deep"(max_iterations=5)

        Yields:
            事件字典：
            - {"type": "agent_thought", "step": N, "content": "思考内容"}
            - {"type": "agent_action", "step": N, "tool": "工具名", "input": {...}}
            - {"type": "agent_observation", "step": N, "content": "工具结果"}
            - {"type": "agent_final", "content": "最终回答"}
        """
        max_iter = 3 if thinking_mode == "quick" else self.max_iterations
        tools_desc = self.get_tools_description()
        scratchpad = []

        try:
            for i in range(max_iter):
                # 1. 构建 prompt
                prompt = self._build_prompt(query, scratchpad, chat_history, max_iter, tools_desc)

                # 2. 调用 LLM
                response = await self._call_llm(prompt)
                parsed = self._parse_response(response)

                # 3. yield thought
                if parsed.get("thought"):
                    yield {"type": "agent_thought", "step": i + 1, "content": parsed["thought"]}

                # 4. 检查 Final Answer
                if parsed.get("is_final"):
                    yield {"type": "agent_final", "content": parsed["final_answer"]}
                    return

                # 5. 如果没有 action，强制结束
                if not parsed.get("action"):
                    yield {"type": "agent_final", "content": parsed.get("thought", "抱歉，我无法处理这个配置请求。")}
                    return

                # 6. yield action
                yield {
                    "type": "agent_action",
                    "step": i + 1,
                    "tool": parsed["action"],
                    "input": parsed.get("action_input", {}),
                }

                # 7. 执行工具
                observation = await self._execute_tool(parsed["action"], parsed.get("action_input", {}), ctx)

                # 8. yield observation
                yield {"type": "agent_observation", "step": i + 1, "content": observation}

                # 9. 记录到 scratchpad
                scratchpad.append((parsed.get("thought", ""), parsed["action"], parsed.get("action_input", {}), observation))

            # 超过最大轮次，强制总结
            summary = await self._force_summarize(query, scratchpad)
            yield {"type": "agent_final", "content": summary}

        except Exception as e:
            logger.error(f"ConfigAgent run failed: {e}")
            yield {"type": "agent_final", "content": f"抱歉，处理配置请求时发生错误：{str(e)}"}

    def _build_prompt(self, query, scratchpad, chat_history, max_iterations, tools_desc):
        """构建 ConfigAgent Prompt"""
        system_content = CONFIG_AGENT_SYSTEM_PROMPT.format(
            tools_description=tools_desc,
            max_iterations=max_iterations,
        )

        # 构建 Scratchpad 文本
        scratchpad_text = ""
        if scratchpad:
            lines = []
            for thought, action, action_input, observation in scratchpad:
                lines.append(f"Thought: {thought}")
                lines.append(f"Action: {action}")
                lines.append(f"Action Input: {json.dumps(action_input, ensure_ascii=False)}")
                lines.append(f"Observation: {observation}")
                lines.append("")
            scratchpad_text = "\n".join(lines)

        user_content = CONFIG_AGENT_USER_PROMPT.format(
            chat_history=chat_history if chat_history else "",
            query=query,
            scratchpad=scratchpad_text,
        )

        return [
            SystemMessage(content=system_content),
            HumanMessage(content=user_content),
        ]

    async def _call_llm(self, messages: list) -> str:
        """调用 LLM 获取响应"""
        try:
            response = await llm_service.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"ConfigAgent LLM 调用失败: {e}")
            return "Thought: 调用语言模型时出错\nFinal Answer: 抱歉，系统暂时无法处理您的配置请求，请稍后重试。"

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 响应，提取 Thought/Action/Final Answer"""
        import re

        result = {"thought": "", "action": None, "action_input": {}, "final_answer": None, "is_final": False, "raw": response}

        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\n(?:Action|Final Answer):|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # 检查 Final Answer
        final_match = re.search(r'Final Answer:\s*(.+)', response, re.DOTALL | re.IGNORECASE)
        if final_match:
            result["final_answer"] = final_match.group(1).strip()
            result["is_final"] = True
            return result

        # 提取 Action
        action_match = re.search(r'Action:\s*(\w+)', response, re.IGNORECASE)
        if action_match:
            result["action"] = action_match.group(1).strip()

            # 提取 Action Input
            action_input_match = re.search(r'Action Input:\s*(\{.*?\})', response, re.DOTALL | re.IGNORECASE)
            if action_input_match:
                try:
                    result["action_input"] = json.loads(action_input_match.group(1))
                except json.JSONDecodeError:
                    try:
                        result["action_input"] = json.loads(action_input_match.group(1).strip())
                    except json.JSONDecodeError:
                        logger.warning(f"ConfigAgent 无法解析 Action Input JSON: {action_input_match.group(1)}")
                        result["action_input"] = {}

        return result

    async def _execute_tool(self, action: str, action_input: dict, ctx: ToolContext) -> str:
        """执行工具调用"""
        tool = self.tools.get(action)
        if not tool:
            available = ", ".join(self.tools.keys())
            return f"错误：未知工具 '{action}'。可用工具：{available}"

        try:
            result = await tool.execute(ctx, **action_input)
            return self._format_observation(result)
        except Exception as e:
            logger.error(f"ConfigAgent 工具执行异常 {action}: {e}")
            return f"工具执行异常：{str(e)}"

    def _format_observation(self, result: ToolResult) -> str:
        """将 ToolResult 格式化为 Observation 字符串"""
        if not result.success:
            return f"工具执行失败：{result.error}"

        data = result.data

        # 配置工具特定格式化
        if "services" in data:
            # list_available_services
            services = data["services"]
            lines = [f"共 {data['total']} 个服务："]
            for svc in services:
                status = "已配置" if svc["is_configured"] else "未配置"
                key_info = ""
                if svc.get("requires_api_key"):
                    key_info = " [需要 API Key]"
                elif svc.get("optional_api_key"):
                    key_info = " [可选 API Key]"
                lines.append(f"- {svc['display_name']}: {status}{key_info} — {svc['description']}")
            return "\n".join(lines)

        if "statuses" in data:
            # get_service_status
            statuses = data["statuses"]
            lines = ["服务状态："]
            for name, info in statuses.items():
                status_map = {
                    "healthy": "正常",
                    "unhealthy": "异常",
                    "not_configured": "未配置",
                    "unknown": "未知",
                }
                status_text = status_map.get(info["status"], info["status"])
                lines.append(f"- {info['display_name']}: {status_text}")
            return "\n".join(lines)

        if "service" in data and "message" in data:
            # configure_service / update_api_key / validate_service
            return data["message"]

        # 默认返回 JSON
        return json.dumps(data, ensure_ascii=False)[:500]

    async def _force_summarize(self, query: str, scratchpad: list) -> str:
        """超过最大迭代次数时，强制生成总结回答"""
        if not scratchpad:
            return "抱歉，我无法在有限步骤内完成这个配置任务。"

        lines = ["基于以下操作结果，总结配置情况："]
        lines.append(f"\n用户问题：{query}\n")
        lines.append("执行过程：")

        for i, (thought, action, action_input, observation) in enumerate(scratchpad, 1):
            lines.append(f"\n步骤 {i}:")
            lines.append(f"思考：{thought}")
            lines.append(f"行动：{action}({json.dumps(action_input, ensure_ascii=False)})")
            lines.append(f"观察：{observation[:200]}...")

        lines.append("\n请基于以上信息给出配置结果总结。")

        prompt_text = "\n".join(lines)
        messages = [
            SystemMessage(content="你是 PaperChat 配置助手，擅长总结配置操作结果。"),
            HumanMessage(content=prompt_text),
        ]

        try:
            response = await llm_service.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"ConfigAgent 强制总结失败: {e}")
            last_thought = scratchpad[-1][0] if scratchpad else ""
            return f"{last_thought}\n\n（已达到最大迭代次数，部分配置任务可能未完成）"
