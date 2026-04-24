"""多 Agent 研究助手子 Agent 工厂函数

提供 3 个角色专用的 async generator wrapper，每个函数：
1. 限制工具集（tool_subset）
2. 注入角色系统提示词（system_prompt_override）
3. 为每个事件注入 sub_agent 字段，便于协调器和前端区分来源
"""

import logging
from typing import AsyncGenerator

from app.prompts.research import (
    RETRIEVER_SYSTEM_PROMPT,
    ANALYZER_SYSTEM_PROMPT,
    RECOMMENDER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


async def run_retriever_agent(
    react_agent,
    query: str,
    ctx,
    chat_history: str = "",
) -> AsyncGenerator[dict, None]:
    """检索专家 — 信息定位和证据收集

    工具限制: search_text, search_papers, get_paper_info, recent_papers
    每个事件注入 sub_agent="retriever"

    性能说明：quick 模式约 1-3 次 LLM 调用（1-6s），比普通 ReAct 多约 15% 开销（sub_agent 注入）。
    """
    tool_subset = ["search_text", "search_papers", "get_paper_info", "recent_papers"]
    try:
        async for event in react_agent.run(
            query=query,
            ctx=ctx,
            chat_history=chat_history,
            thinking_mode="quick",
            mode="normal",
            system_prompt_override=RETRIEVER_SYSTEM_PROMPT,
            tool_subset=tool_subset,
        ):
            event["sub_agent"] = "retriever"
            yield event
    except Exception as e:
        logger.error(f"Retriever Agent 执行失败: {e}")
        yield {
            "type": "agent_final",
            "sub_agent": "retriever",
            "content": f"检索阶段遇到错误：{str(e)}",
            "error": True,
        }


async def run_analyzer_agent(
    react_agent,
    query: str,
    ctx,
    chat_history: str = "",
) -> AsyncGenerator[dict, None]:
    """分析专家 — 论点评估和逻辑推理

    工具限制: summarize, compare_content, extract_key_points, assess_quality, explain_term
    每个事件注入 sub_agent="analyzer"

    性能说明：quick 模式约 1-3 次 LLM 调用，分析工具本身含 LLM 调用，总耗时约 3-10s。
    """
    tool_subset = ["summarize", "compare_content", "extract_key_points", "assess_quality", "explain_term"]
    try:
        async for event in react_agent.run(
            query=query,
            ctx=ctx,
            chat_history=chat_history,
            thinking_mode="quick",
            mode="normal",
            system_prompt_override=ANALYZER_SYSTEM_PROMPT,
            tool_subset=tool_subset,
        ):
            event["sub_agent"] = "analyzer"
            yield event
    except Exception as e:
        logger.error(f"Analyzer Agent 执行失败: {e}")
        yield {
            "type": "agent_final",
            "sub_agent": "analyzer",
            "content": f"分析阶段遇到错误：{str(e)}",
            "error": True,
        }


async def run_recommender_agent(
    react_agent,
    query: str,
    ctx,
    chat_history: str = "",
) -> AsyncGenerator[dict, None]:
    """推荐专家 — 研究方向和关联发现

    工具限制: search_papers, search_cards, find_research_gaps
    每个事件注入 sub_agent="recommender"

    性能说明：quick 模式约 1-3 次 LLM 调用，总耗时约 2-8s。
    """
    tool_subset = ["search_papers", "search_cards", "find_research_gaps"]
    try:
        async for event in react_agent.run(
            query=query,
            ctx=ctx,
            chat_history=chat_history,
            thinking_mode="quick",
            mode="normal",
            system_prompt_override=RECOMMENDER_SYSTEM_PROMPT,
            tool_subset=tool_subset,
        ):
            event["sub_agent"] = "recommender"
            yield event
    except Exception as e:
        logger.error(f"Recommender Agent 执行失败: {e}")
        yield {
            "type": "agent_final",
            "sub_agent": "recommender",
            "content": f"推荐阶段遇到错误：{str(e)}",
            "error": True,
        }
