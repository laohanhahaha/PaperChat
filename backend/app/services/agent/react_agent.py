"""ReAct Agent - Reasoning + Acting 循环

实现 Thought → Action → Observation 循环，替代原有的 Plan-then-Execute 模式。
每轮 LLM 输出 Thought（推理）和 Action（工具调用），执行后将 Observation（结果）
反馈给 LLM，循环直到输出 Final Answer。

性能说明：
- 每轮 ReAct 循环需要 1 次 LLM 调用（约 500ms-2s，取决于模型和输出长度）
- quick 模式（max_iterations=3）：约 1-3 次 LLM 调用，总耗时 1-6s
- deep 模式（max_iterations=8）：约 3-8 次 LLM 调用，总耗时 3-16s
- 每轮工具执行时间取决于具体工具（搜索通常 100-500ms，LLM 类工具 1-3s）
"""

import asyncio
import json
import re
import logging
import time
from typing import AsyncGenerator, Optional, List
from dataclasses import dataclass, field

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service
from app.services.agent.agent_service import Tool, ToolContext, ToolResult, agent_service
from app.services.metrics.metrics_service import metrics_service
from app.prompts.agent import DEEP_RESEARCH_SYSTEM_PROMPT  # noqa: F401 — 从 app.prompts 统一导入

logger = logging.getLogger(__name__)


# DEEP_RESEARCH_SYSTEM_PROMPT 已迁移至 app.prompts.agent，此处通过顶部 import 引入


@dataclass
class ParsedAction:
    """解析出的单个 Action"""
    action: str = ""
    action_input: dict = field(default_factory=dict)


@dataclass
class ParsedResponse:
    """LLM 响应解析结果"""
    thought: str = ""
    actions: List[ParsedAction] = field(default_factory=list)
    final_answer: Optional[str] = None
    is_final: bool = False
    raw: str = ""
    
    @property
    def action(self) -> Optional[str]:
        """兼容旧代码：返回第一个 action"""
        return self.actions[0].action if self.actions else None
    
    @property
    def action_input(self) -> Optional[dict]:
        """兼容旧代码：返回第一个 action_input"""
        return self.actions[0].action_input if self.actions else None


class ReActAgent:
    """ReAct Agent 主类
    
    实现 Thought-Action-Observation 循环，支持流式事件输出。
    """
    
    # ReAct System Prompt 模板（中文，适配 DeepSeek/Qwen）
    REACT_SYSTEM_PROMPT = """你是 PaperChat 学术研究助手。你通过 Thought（思考）和 Action（行动）循环来解决用户问题。

可用工具：
{tools_description}

回答格式（严格遵守）：

如果需要使用工具：
Thought: [你的推理过程，分析用户需求，决定下一步行动]
Action: [工具名称]
Action Input: [JSON 格式的参数]

如果已经有足够信息回答用户：
Thought: [总结推理过程]
Final Answer: [最终回答]

规则：
1. 每次只能调用一个工具
2. Action Input 必须是合法的 JSON
3. 根据 Observation 结果决定下一步
4. 工具执行失败时，尝试换一种方式
5. 最多执行 {max_iterations} 轮
6. 使用中文进行思考和回答"""

    # User Prompt 模板
    REACT_USER_PROMPT = """{chat_history}

用户问题：{query}

{scratchpad}
请继续推理。"""

    def __init__(self, tools: dict[str, Tool], max_iterations: int = 5):
        self.tools = tools
        self.max_iterations = max_iterations
    
    async def run(self, query: str, ctx: ToolContext, 
                  chat_history: str = "",
                  thinking_mode: str = "quick",
                  mode: str = "normal") -> AsyncGenerator[dict, None]:
        """ReAct 主循环
        
        Args:
            query: 用户问题
            ctx: 工具执行上下文
            chat_history: 格式化后的对话历史（来自 context_service）
            thinking_mode: "quick"(max_iterations=3) 或 "deep"(max_iterations=8)
            mode: "normal" 或 "deep_research"（深度研究模式，强制 max_iterations=8）
            
        Yields:
            事件字典：
            - {"type": "agent_thought", "step": N, "content": "思考内容"}
            - {"type": "agent_action", "step": N, "tool": "工具名", "input": {...}}
            - {"type": "agent_observation", "step": N, "content": "工具结果"}
            - {"type": "agent_reflection", "content": "反思内容"}
            - {"type": "agent_final", "content": "最终回答"}
        """
        # 指标采集初始化
        start_time = time.perf_counter()
        tool_call_records = []
        llm_call_count = 0
        cache_hit_count = 0
        error_message = None
        iteration = 0
        
        # 根据 thinking_mode 和 mode 调整 max_iterations
        if mode == "deep_research":
            max_iter = 8
        else:
            max_iter = 8 if thinking_mode == "deep" else min(self.max_iterations, 3)
        
        scratchpad = []  # list of (thought, action, action_input, observation)
        consecutive_failures = 0
        verification_done = False
        
        try:
            for i in range(max_iter):
                iteration = i + 1
                # 改动2: deep_research 模式结果复核（还剩 2 轮时插入验证步骤）
                if mode == "deep_research" and i == max_iter - 2 and not verification_done:
                    verification_prompt = self._build_verification_prompt(query, scratchpad, chat_history)
                    yield {"type": "agent_reflection", "content": "正在验证推理过程的一致性..."}
                    try:
                        verification_response = await self._call_llm(verification_prompt)
                        scratchpad.append(("_verification_reflection", None, None, verification_response))
                    except Exception as e:
                        logger.error(f"验证步骤调用 LLM 失败: {e}")
                    verification_done = True
                
                # 1. 构建 prompt
                prompt = self._build_prompt(query, scratchpad, chat_history, max_iter, mode=mode)
                
                # 2. 调用 LLM（非流式，需要完整解析）
                response = await self._call_llm(prompt)
                llm_call_count += 1
                parsed = self._parse_response(response)
                
                # 3. yield thought
                if parsed.thought:
                    yield {"type": "agent_thought", "step": i + 1, "content": parsed.thought}
                
                # 4. 检查是否是 Final Answer
                if parsed.is_final:
                    # 改动3: 最终答案一致性检查
                    final_answer = self._check_answer_consistency(parsed.final_answer, scratchpad)
                    yield {"type": "agent_final", "content": final_answer}
                    return
                
                # 5. 如果没有 action，强制结束
                if not parsed.actions:
                    yield {"type": "agent_final", "content": parsed.thought or "抱歉，我无法处理这个请求。"}
                    return
                
                # 6. yield action(s)
                for idx, act in enumerate(parsed.actions):
                    yield {
                        "type": "agent_action", 
                        "step": i + 1,
                        "tool": act.action, 
                        "input": act.action_input or {}
                    }
                
                # 7. 执行工具（支持并行）
                if len(parsed.actions) > 1:
                    # 并行执行多个工具
                    observations = await self._execute_tools_parallel(parsed.actions, ctx, tool_call_records)
                    
                    # yield 每个 observation 事件
                    for obs in observations:
                        yield {"type": "agent_observation", "step": i + 1, "content": obs}
                    
                    # 检查失败
                    has_failure = any(obs.startswith("[ERROR]") or 
                                      obs.startswith("错误") or 
                                      obs.startswith("工具执行失败") or 
                                      obs.startswith("工具执行异常") 
                                      for obs in observations)
                    
                    if has_failure:
                        consecutive_failures += 1
                        if consecutive_failures >= 2:
                            system_instruction = "[SYSTEM] 连续失败过多，请跳过当前工具，尝试其他方法或直接总结已有信息。"
                            scratchpad.append(("_system_instruction", None, None, system_instruction))
                    else:
                        consecutive_failures = 0
                    
                    # 记录到 scratchpad（使用第一个 action 代表本轮）
                    combined_obs = "\n".join([f"[{act.action}] {obs}" for act, obs in zip(parsed.actions, observations)])
                    scratchpad.append((parsed.thought, parsed.actions[0].action, parsed.actions[0].action_input, combined_obs))
                else:
                    # 单个 Action，保持原有串行逻辑
                    observation = await self._execute_tool(parsed.actions[0].action, parsed.actions[0].action_input or {}, ctx, tool_call_records)
                    
                    # 改动1: 工具失败自动恢复
                    is_failure = (observation.startswith("错误") or 
                                 observation.startswith("工具执行失败") or 
                                 observation.startswith("工具执行异常"))
                    
                    if is_failure:
                        consecutive_failures += 1
                        error_msg = observation
                        observation = f"[ERROR] {observation}"
                        
                        # yield observation（带 [ERROR] 标记）
                        yield {"type": "agent_observation", "step": i + 1, "content": observation}
                        
                        # 记录到 scratchpad
                        scratchpad.append((parsed.thought, parsed.actions[0].action, parsed.actions[0].action_input, observation))
                        
                        # 追加反思提示
                        reflection_text = f"上一步工具调用失败（{error_msg}），我需要换一种策略或使用其他工具。"
                        scratchpad.append(("_reflection", None, None, reflection_text))
                        yield {"type": "agent_reflection", "content": "工具调用失败，正在调整策略..."}
                        
                        # 连续失败 >= 2 次时，添加强制指令
                        if consecutive_failures >= 2:
                            system_instruction = "[SYSTEM] 连续失败过多，请跳过当前工具，尝试其他方法或直接总结已有信息。"
                            scratchpad.append(("_system_instruction", None, None, system_instruction))
                    else:
                        consecutive_failures = 0
                        
                        # yield observation
                        yield {"type": "agent_observation", "step": i + 1, "content": observation}
                        
                        # 记录到 scratchpad
                        scratchpad.append((parsed.thought, parsed.actions[0].action, parsed.actions[0].action_input, observation))
            
            # 超过最大轮次，强制总结
            summary = await self._force_summarize(query, scratchpad)
            yield {"type": "agent_final", "content": summary}
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Agent run failed: {e}")
            yield {"type": "agent_final", "content": f"抱歉，处理请求时发生错误：{error_message}"}
            raise
        finally:
            # 记录指标（失败不应影响 Agent 返回结果）
            try:
                total_duration = (time.perf_counter() - start_time) * 1000
                await metrics_service.record_agent_run(
                    db=ctx.db, session_id=ctx.session_id, user_id=ctx.user_id,
                    agent_mode=mode, total_steps=iteration,
                    total_duration_ms=total_duration, tool_calls=tool_call_records,
                    llm_calls=llm_call_count, cache_hits=cache_hit_count,
                    success=not bool(error_message), error_message=error_message
                )
            except Exception as e:
                logger.error(f"Failed to record metrics: {e}")
    
    def _build_prompt(self, query: str, scratchpad: list, chat_history: str, max_iterations: int, mode: str = "normal") -> list:
        """构建 ReAct Prompt
        
        Args:
            query: 用户问题
            scratchpad: 历史步骤列表
            chat_history: 格式化后的对话历史
            max_iterations: 最大迭代次数
            mode: "normal" 或 "deep_research"
            
        Returns:
            LangChain Message 列表
        """
        # 获取工具描述
        tools_description = agent_service.get_tools_description()
        
        # 构建 System Prompt
        if mode == "deep_research":
            format_instructions = """如果需要使用工具：
Thought: [阶段标签] [你的推理过程，分析用户需求，决定下一步行动]
Action: [工具名称]
Action Input: [JSON 格式的参数]

如果已经有足够信息回答用户：
Thought: [总结推理过程]
Final Answer: [最终回答]"""
            system_content = DEEP_RESEARCH_SYSTEM_PROMPT.format(
                tools_description=tools_description,
                format_instructions=format_instructions
            )
        else:
            system_content = self.REACT_SYSTEM_PROMPT.format(
                tools_description=tools_description,
                max_iterations=max_iterations
            )
        
        # 构建 Scratchpad 文本
        scratchpad_text = ""
        if scratchpad:
            lines = []
            for thought, action, action_input, observation in scratchpad:
                # 处理特殊条目（反思、系统指令、验证）
                if action is None and thought is not None and thought.startswith("_"):
                    if thought == "_reflection":
                        lines.append(f"Reflection: {observation}")
                    elif thought == "_system_instruction":
                        lines.append(observation)
                    elif thought == "_verification_reflection":
                        lines.append(f"Verification Reflection: {observation}")
                    lines.append("")
                    continue
                lines.append(f"Thought: {thought}")
                lines.append(f"Action: {action}")
                lines.append(f"Action Input: {json.dumps(action_input, ensure_ascii=False)}")
                lines.append(f"Observation: {observation}")
                lines.append("")
            scratchpad_text = "\n".join(lines)
        
        # 构建 User Prompt
        user_content = self.REACT_USER_PROMPT.format(
            chat_history=chat_history if chat_history else "",
            query=query,
            scratchpad=scratchpad_text
        )
        
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=user_content)
        ]
    
    async def _call_llm(self, messages: list) -> str:
        """调用 LLM 获取响应
        
        Args:
            messages: LangChain Message 列表
            
        Returns:
            LLM 响应文本
        """
        try:
            response = await llm_service.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return f"Thought: 调用语言模型时出错\nFinal Answer: 抱歉，系统暂时无法处理您的请求，请稍后重试。"
    
    def _parse_response(self, response: str) -> ParsedResponse:
        """解析 LLM 响应，提取 Thought/Action/Final Answer
        
        支持解析多个 Action（格式：多个 Action/Action Input 块）
        
        Args:
            response: LLM 原始响应文本
            
        Returns:
            ParsedResponse 对象
        """
        parsed = ParsedResponse(raw=response)
        
        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\n(?:Action|Final Answer):|$)', response, re.DOTALL | re.IGNORECASE)
        if thought_match:
            parsed.thought = thought_match.group(1).strip()
        
        # 检查是否有 Final Answer
        final_match = re.search(r'Final Answer:\s*(.+)', response, re.DOTALL | re.IGNORECASE)
        if final_match:
            parsed.final_answer = final_match.group(1).strip()
            parsed.is_final = True
            return parsed
        
        # 提取多个 Action（支持分号或换行分隔的多个 Action）
        # 首先尝试匹配多个 Action/Action Input 对
        action_blocks = re.findall(
            r'Action:\s*(\w+)\s*\n+Action Input:\s*(\{.*?\})',
            response, 
            re.DOTALL | re.IGNORECASE
        )
        
        if action_blocks:
            for action_name, action_input_str in action_blocks:
                try:
                    action_input = json.loads(action_input_str)
                except json.JSONDecodeError:
                    try:
                        action_input = json.loads(action_input_str.strip())
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析 Action Input JSON: {action_input_str}")
                        action_input = {}
                parsed.actions.append(ParsedAction(action=action_name.strip(), action_input=action_input))
        else:
            # 回退到单个 Action 匹配
            action_match = re.search(r'Action:\s*(\w+)', response, re.IGNORECASE)
            if action_match:
                action_name = action_match.group(1).strip()
                action_input_match = re.search(r'Action Input:\s*(\{.*?\})', response, re.DOTALL | re.IGNORECASE)
                action_input = {}
                if action_input_match:
                    try:
                        action_input = json.loads(action_input_match.group(1))
                    except json.JSONDecodeError:
                        try:
                            action_input = json.loads(action_input_match.group(1).strip())
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析 Action Input JSON: {action_input_match.group(1)}")
                parsed.actions.append(ParsedAction(action=action_name, action_input=action_input))
        
        return parsed
    
    async def _execute_tool(self, action: str, action_input: dict, ctx: ToolContext, 
                            tool_call_records: List[dict] = None) -> str:
        """执行工具调用（带缓存支持）
        
        Args:
            action: 工具名称
            action_input: 工具参数
            ctx: 工具执行上下文
            tool_call_records: 工具调用记录列表（用于指标采集）
            
        Returns:
            工具执行结果字符串（用于 Observation）
        """
        # 1. 先查缓存
        from app.services.core.tool_cache import tool_cache
        params_str = json.dumps(action_input, ensure_ascii=False, sort_keys=True)
        cached = tool_cache.get(action, params_str)
        if cached:
            logger.debug(f"Cache hit for tool: {action}")
            # 记录缓存命中
            if tool_call_records is not None:
                tool_call_records.append({
                    "tool_name": action,
                    "duration_ms": 0.0,
                    "success": True,
                    "cached": True
                })
            return cached
        
        # 2. 执行工具
        tool = self.tools.get(action)
        if not tool:
            available = ", ".join(self.tools.keys())
            error_msg = f"错误：未知工具 '{action}'。可用工具：{available}"
            if tool_call_records is not None:
                tool_call_records.append({
                    "tool_name": action,
                    "duration_ms": 0.0,
                    "success": False,
                    "cached": False
                })
            return error_msg
        
        tool_start = time.perf_counter()
        try:
            result = await tool.execute(ctx, **action_input)
            observation = self._format_observation(result)
            tool_duration = (time.perf_counter() - tool_start) * 1000
            
            # 3. 缓存成功结果（非错误结果）
            if observation and not observation.startswith("[ERROR]") and not observation.startswith("错误") and not observation.startswith("工具执行失败"):
                tool_cache.set(action, params_str, observation)
            
            # 记录工具调用
            if tool_call_records is not None:
                tool_call_records.append({
                    "tool_name": action,
                    "duration_ms": round(tool_duration, 2),
                    "success": not (observation.startswith("[ERROR]") or observation.startswith("错误") or observation.startswith("工具执行失败")),
                    "cached": False
                })
            
            return observation
        except Exception as e:
            tool_duration = (time.perf_counter() - tool_start) * 1000
            logger.error(f"工具执行异常 {action}: {e}")
            error_msg = f"工具执行异常：{str(e)}"
            
            # 记录失败的工具调用
            if tool_call_records is not None:
                tool_call_records.append({
                    "tool_name": action,
                    "duration_ms": round(tool_duration, 2),
                    "success": False,
                    "cached": False
                })
            
            return error_msg
    
    async def _execute_tools_parallel(self, actions: List[ParsedAction], ctx: ToolContext,
                                      tool_call_records: List[dict] = None) -> List[str]:
        """串行执行多个工具调用（避免 AsyncSession 并发访问问题）
        
        Args:
            actions: Action 列表
            ctx: 工具执行上下文
            tool_call_records: 工具调用记录列表（用于指标采集）
            
        Returns:
            各工具执行结果字符串列表
        """
        observations = []
        for act in actions:
            try:
                obs = await self._execute_tool(act.action, act.action_input or {}, ctx, tool_call_records)
            except Exception as e:
                logger.error(f"工具并行执行异常 {act.action}: {e}")
                obs = f"[ERROR] 工具执行异常：{str(e)}"
                # 记录失败的工具调用
                if tool_call_records is not None:
                    tool_call_records.append({
                        "tool_name": act.action,
                        "duration_ms": 0.0,
                        "success": False,
                        "cached": False
                    })
            observations.append(obs)
        return observations
    
    def _format_observation(self, result: ToolResult) -> str:
        """将 ToolResult 格式化为 Observation 字符串
        
        Args:
            result: 工具执行结果
            
        Returns:
            简洁的观察结果字符串
        """
        if not result.success:
            return f"工具执行失败：{result.error}"
        
        data = result.data
        
        # 根据结果类型返回简洁描述
        if "summary" in data:
            return f"摘要结果：{data['summary'][:300]}..."
        if "translation" in data:
            return f"翻译结果：{data['translation'][:300]}..."
        if "explanation" in data:
            return f"解释：{data['explanation'][:300]}..."
        if "results" in data and isinstance(data["results"], list):
            count = len(data["results"])
            # 提取前几条结果的摘要
            previews = []
            for i, r in enumerate(data["results"][:3]):
                if isinstance(r, dict):
                    text = r.get("text", r.get("content", str(r)))[:100]
                    previews.append(f"[{i+1}] {text}...")
            return f"检索到 {count} 条结果：\n" + "\n".join(previews)
        if "points" in data and isinstance(data["points"], list):
            count = len(data["points"])
            points_preview = []
            for p in data["points"][:3]:
                if isinstance(p, dict):
                    concept = p.get("concept", str(p))
                    points_preview.append(f"- {concept}")
            return f"提取了 {count} 个知识点：\n" + "\n".join(points_preview)
        if "comparison" in data:
            return f"对比结果：{data['comparison'][:300]}..."
        if "outline" in data:
            return f"生成提纲：\n{data['outline'][:400]}..."
        if "assessment" in data:
            return f"质量评估：{data['assessment'][:300]}..."
        if "review" in data:
            return f"文献综述：{data['review'][:300]}..."
        if "citation" in data:
            return f"引用格式：{data['citation']}"
        if "polished_text" in data:
            return f"润色结果：{data['polished_text'][:300]}..."
        if "cards" in data and isinstance(data.get("cards"), list):
            count = len(data["cards"])
            return f"找到 {count} 张知识卡片"
        if "papers" in data and isinstance(data.get("papers"), list):
            count = len(data["papers"])
            papers_preview = []
            for p in data["papers"][:3]:
                if isinstance(p, dict):
                    title = p.get("title", "未知标题")
                    papers_preview.append(f"- {title}")
            return f"找到 {count} 篇论文：\n" + "\n".join(papers_preview)
        if "paper" in data or ("title" in data and "authors" in data):
            # 单篇论文信息
            title = data.get("title", "未知标题")
            authors = data.get("authors", "未知作者")
            return f"论文信息：{title} - {authors}"
        if "card_id" in data:
            return f"知识卡片已保存（ID: {data['card_id']}）"
        
        # 默认返回 JSON 摘要
        return json.dumps(data, ensure_ascii=False)[:500]
    
    def _build_verification_prompt(self, query: str, scratchpad: list, chat_history: str) -> list:
        """构建验证 prompt（deep_research 模式结果复核）
        
        Args:
            query: 用户问题
            scratchpad: 历史步骤列表
            chat_history: 格式化后的对话历史
            
        Returns:
            LangChain Message 列表
        """
        # 构建 Scratchpad 文本
        scratchpad_text = ""
        if scratchpad:
            lines = []
            for thought, action, action_input, observation in scratchpad:
                if action is None and thought is not None and thought.startswith("_"):
                    if thought == "_reflection":
                        lines.append(f"Reflection: {observation}")
                    elif thought == "_system_instruction":
                        lines.append(observation)
                    elif thought == "_verification_reflection":
                        lines.append(f"Verification Reflection: {observation}")
                    lines.append("")
                    continue
                lines.append(f"Thought: {thought}")
                lines.append(f"Action: {action}")
                lines.append(f"Action Input: {json.dumps(action_input, ensure_ascii=False)}")
                lines.append(f"Observation: {observation}")
                lines.append("")
            scratchpad_text = "\n".join(lines)
        
        verification_content = f"""基于你到目前为止的分析，请进行自我检查：
1. 你的结论之间是否存在矛盾？
2. 每个关键论据是否有来自论文的证据支持？
3. 是否遗漏了重要的分析维度？

如果发现问题，请在下一步中修正。如果一切一致，请继续生成最终答案。

以下是你到目前为止的分析过程：
{scratchpad_text}

用户问题：{query}"""
        
        return [
            SystemMessage(content="你是 PaperChat 深度研究助手，正在进行自我验证。"),
            HumanMessage(content=verification_content)
        ]
    
    def _check_answer_consistency(self, final_answer: str, scratchpad: list) -> str:
        """最终答案一致性检查，检测可能的幻觉
        
        通过纯文本匹配检查 Final Answer 中的实体是否在 Observations 中出现。
        不调用 LLM，开销极小。
        
        Args:
            final_answer: 最终答案文本
            scratchpad: 历史步骤列表
            
        Returns:
            可能追加幻觉警告的最终答案
        """
        # 收集所有 observation 文本（排除特殊条目）
        observation_texts = []
        for thought, action, action_input, observation in scratchpad:
            if observation and not (thought is not None and thought.startswith("_")):
                observation_texts.append(observation)
        observation_combined = " ".join(observation_texts)
        
        # 中文停用词
        _CHINESE_STOPWORDS = {
            '这个', '那个', '这些', '那些', '什么', '怎么', '如何', '为什么',
            '可以', '可能', '应该', '需要', '已经', '正在', '通过', '进行',
            '使用', '包括', '以及', '或者', '但是', '然而', '因此', '所以',
            '如果', '虽然', '不仅', '而且', '同时', '其中', '基于', '关于',
            '对于', '根据', '来自', '之间', '以上', '以下', '之后', '之前',
            '本文', '该文', '论文', '研究', '方法', '结果', '分析', '提出',
            '问题', '方面', '角度', '观点', '认为', '表明', '说明', '显示',
            '一些', '一种', '一个', '没有', '不是', '而是', '的话',
        }
        # 英文停用词
        _ENGLISH_STOPWORDS = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been',
            'from', 'this', 'that', 'with', 'they', 'will', 'each', 'make',
            'like', 'been', 'long', 'very', 'after', 'also', 'just', 'than',
            'more', 'other', 'into', 'could', 'would', 'about', 'which',
            'their', 'there', 'these', 'those', 'being', 'some', 'when',
        }
        
        def extract_entities(text: str) -> set:
            """提取文本中的关键实体词"""
            entities = set()
            # 提取中文词组（2+个连续汉字）
            for match in re.findall(r'[\u4e00-\u9fff]{2,}', text):
                if match not in _CHINESE_STOPWORDS:
                    entities.add(match)
            # 提取英文词组（3+个连续英文字母）
            for match in re.findall(r'[a-zA-Z]{3,}', text):
                if match.lower() not in _ENGLISH_STOPWORDS:
                    entities.add(match.lower())
            return entities
        
        obs_entities = extract_entities(observation_combined)
        answer_entities = extract_entities(final_answer)
        
        # 找出 Final Answer 中但不在 Observations 中的实体
        novel_entities = answer_entities - obs_entities
        
        # 如果有多个在 Final Answer 中出现但完全不在 Observation 中的关键实体，标记为可能幻觉
        if len(novel_entities) >= 3:
            # 进一步过滤：只计算看起来像"关键实体"的（较长的中文词或英文大写词）
            key_novel = [e for e in novel_entities 
                        if len(e) >= 4 or (e.isascii() and any(c.isupper() for c in e))]
            if len(key_novel) >= 2:
                logger.info(f"一致性检查：检测到可能的幻觉，新增关键实体: {key_novel}")
                return final_answer + "\n\n> 注意：部分内容可能基于推断而非直接证据，请结合原文验证。"
        
        return final_answer

    async def _force_summarize(self, query: str, scratchpad: list) -> str:
        """超过最大迭代次数时，强制生成总结回答
        
        Args:
            query: 原始用户问题
            scratchpad: 历史步骤列表
            
        Returns:
            总结回答
        """
        if not scratchpad:
            return "抱歉，我无法在有限步骤内完成这个任务。"
        
        # 构建总结 prompt
        lines = ["基于以下思考和观察结果，回答用户问题："]
        lines.append(f"\n用户问题：{query}\n")
        lines.append("执行过程：")
        
        for i, (thought, action, action_input, observation) in enumerate(scratchpad, 1):
            # 处理特殊条目
            if action is None and thought is not None and thought.startswith("_"):
                lines.append(f"\n{observation[:200]}...")
                continue
            lines.append(f"\n步骤 {i}:")
            lines.append(f"思考：{thought}")
            lines.append(f"行动：{action}({json.dumps(action_input, ensure_ascii=False)})")
            lines.append(f"观察：{observation[:200]}...")
        
        lines.append("\n请基于以上信息给出最终回答。如果信息不足，请说明。")
        
        prompt_text = "\n".join(lines)
        
        messages = [
            SystemMessage(content="你是学术问答专家，擅长基于已有信息整合回答。"),
            HumanMessage(content=prompt_text)
        ]
        
        try:
            response = await llm_service.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"强制总结失败: {e}")
            # 返回最后一步的思考作为 fallback
            last_thought = scratchpad[-1][0] if scratchpad else ""
            return f"{last_thought}\n\n（已达到最大迭代次数，部分任务可能未完成）"


# 全局 ReAct Agent 实例
react_agent = ReActAgent(tools=agent_service.tools)
