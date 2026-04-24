"""意图识别模块 — 关键词匹配 + LLM 双通道识别

性能说明：
- classify_by_keywords: 纯内存匹配，< 1ms，无 LLM 调用
- classify_by_llm: 约 500ms + 200 tokens，超时后自动 fallback 到关键词匹配
- AgentService.classify_intent: 完整 LLM 意图分类，约 500ms + 200 tokens
"""
import asyncio
import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_service import llm_service
from app.prompts.intent import (
    INTENT_CLASSIFICATION_PROMPT,
    LLM_CLASSIFY_PROMPT as _LLM_CLASSIFY_PROMPT,
    _LLM_TOOL_DESCRIPTIONS,
)  # 从 app.prompts 统一导入，保持此模块内名称不变

logger = logging.getLogger(__name__)


# ============ 意图关键词映射 ============

INTENT_KEYWORDS: dict[str, dict] = {
    "chapter_overview": {
        "keywords": ["章节概述", "概述", "章节总结", "文章结构", "目录", " outline ", "章节内容", "各章节", "章节介绍", "结构分析"],
        "intent": "chapter_overview",
        "tool": "analyze_paper"
    },
    "deep_analysis": {
        "keywords": ["深度分析", "深入分析", "详细分析", "深层分析", "分析", "研究分析", "学术分析", "critical analysis", "detailed analysis"],
        "intent": "deep_analysis",
        "tool": "deep_analyze_paper"
    },
    "key_points": {
        "keywords": ["核心知识点", "关键点", "重点", "核心要点", "主要观点", "关键概念", "核心概念", "知识点", "key points", "main points", "核心思想"],
        "intent": "key_points",
        "tool": "extract_key_points"
    },
    "compare": {
        "keywords": ["对比", "比较", "差异", "异同", "对照", "compare", "comparison", "versus", "vs "],
        "intent": "comparison",
        "tool": "compare_content"
    },
    "summary": {
        "keywords": ["摘要", "总结", "概括", "提炼", "summarize", "summary", "概括"],
        "intent": "summary",
        "tool": "summarize"
    },
    "translate": {
        "keywords": ["翻译", "译成", "translate", "中译", "英译"],
        "intent": "translate",
        "tool": "translate"
    },
    "explain": {
        "keywords": ["解释", "说明", "什么是", "含义", "定义", "explain", "definition", "definition of"],
        "intent": "explain",
        "tool": "explain_term"
    },
    "cross_doc": {
        "keywords": ["跨文档", "跨论文", "多篇论文", "多文档", "across papers", "multiple papers"],
        "intent": "cross_doc",
        "tool": "cross_doc_chat"
    },
    "quality_assessment": {
        "keywords": ["质量评估", "评估", "好不好", "优缺点", "优劣势", "assess", "quality", "评估质量"],
        "intent": "quality_assessment",
        "tool": "assess_quality"
    },
    "outline": {
        "keywords": ["提纲", "大纲", "结构", "写报告", "写综述", "outline", "structure", "报告大纲"],
        "intent": "outline",
        "tool": "generate_outline"
    },
    # 写作类
    "literature_review": {
        "keywords": ["文献综述", "综述", "写综述", "literature review"],
        "intent": "literature_review",
        "tool": "literature_review"
    },
    "cite_paper": {
        "keywords": ["引用格式", "格式化引用", "APA", "MLA", "Chicago", "citation", "cite"],
        "intent": "cite_paper",
        "tool": "cite_paper"
    },
    "polish_text": {
        "keywords": ["润色", "改写", "优化文本", "polish", "rewrite"],
        "intent": "polish_text",
        "tool": "polish_text"
    },
    # 知识库类
    "save_card": {
        "keywords": ["保存知识", "记下来", "保存卡片", "save knowledge", "save card"],
        "intent": "save_card",
        "tool": "save_card"
    },
    "search_cards": {
        "keywords": ["搜索知识", "查找笔记", "知识库搜索", "search knowledge", "search cards"],
        "intent": "search_cards",
        "tool": "search_cards"
    },
    # 论文查询类
    "recent_papers": {
        "keywords": ["最近论文", "最近读了", "论文列表", "recent papers"],
        "intent": "recent_papers",
        "tool": "recent_papers"
    },
    "search_papers": {
        "keywords": ["搜索论文", "查找论文", "找论文", "search papers"],
        "intent": "search_papers",
        "tool": "search_papers"
    },
    # 跨论文推理类
    "detect_contradiction": {
        "keywords": ["矛盾", "冲突", "不一致", "contradiction", "conflict"],
        "intent": "detect_contradiction",
        "tool": "detect_contradiction"
    },
    "trace_evolution": {
        "keywords": ["演进", "发展历程", "变化趋势", "方法演变", "evolution", "evolution of method"],
        "intent": "trace_evolution",
        "tool": "trace_evolution"
    },
    "verify_consistency": {
        "keywords": ["一致性", "验证结论", "是否一致", "consistency", "verify"],
        "intent": "verify_consistency",
        "tool": "verify_consistency"
    },
    "find_research_gaps": {
        "keywords": ["研究空白", "未解决", "局限性", "研究缺口", "research gap", "gaps"],
        "intent": "find_research_gaps",
        "tool": "find_research_gaps"
    },
    "cross_paper_reason": {
        "keywords": ["跨论文推理", "假设验证", "假设推理", "cross-paper reason", "hypothesis"],
        "intent": "cross_paper_reason",
        "tool": "cross_paper_reason"
    },
    # 多模态类
    "image_analysis": {
        "keywords": ["图片分析", "分析图片", "描述图片", "图像识别", "image analysis", "analyze image", "describe image"],
        "intent": "image_analysis",
        "tool": "analyze_chart"
    },
    "chart_extraction": {
        "keywords": ["提取图表", "图表数据", "读取图表", "表格提取", "chart data", "extract chart", "read table"],
        "intent": "chart_extraction",
        "tool": "analyze_chart"
    },
    "visual_comparison": {
        "keywords": ["图表对比", "视觉对比", "比较图表", "图像比较", "visual comparison", "compare charts", "compare figures"],
        "intent": "visual_comparison",
        "tool": "analyze_chart"
    },
    "multimodal_search": {
        "keywords": ["图片搜索", "以图搜文", "图文搜索", "视觉搜索", "image search", "visual search", "search by image"],
        "intent": "multimodal_search",
        "tool": "multimodal_search"
    },
    "cross_modal_reasoning": {
        "keywords": ["图文推理", "跨模态", "图表推理", "图像推理", "cross modal", "visual reasoning", "multimodal reasoning"],
        "intent": "cross_modal_reasoning",
        "tool": "analyze_chart"
    }
}


# INTENT_CLASSIFICATION_PROMPT 、_LLM_CLASSIFY_PROMPT 、_LLM_TOOL_DESCRIPTIONS
# 已迁移至 app.prompts.intent，此处通过顶部 import 引入


# ============ 意图识别函数 ============

def classify_by_keywords(message: str) -> dict:
    """基于关键词的意图识别（快速识别，用于直接功能触发）

    无 LLM 调用，< 1ms。

    Args:
        message: 用户消息

    Returns:
        {"matched": True, "intent": "...", "tool": "...", "confidence": "high|medium"}
        或
        {"matched": False}
    """
    message_lower = message.lower()

    best_match = None
    best_score = 0

    for intent_name, config in INTENT_KEYWORDS.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword.lower() in message_lower:
                score += 1

        if score > 0 and score > best_score:
            best_score = score
            best_match = {
                "intent": config["intent"],
                "tool": config["tool"],
                "confidence": "high" if score >= 2 else "medium"
            }

    if best_match:
        return {"matched": True, **best_match}

    return {"matched": False}


async def classify_by_llm(message: str, timeout_seconds: float = 2.0) -> dict:
    """基于 LLM 的意图识别（自然语言理解，更准确）

    性能：约 500ms + 200 tokens。超时后自动 fallback 到关键词匹配（< 1ms）。

    Args:
        message: 用户消息
        timeout_seconds: 超时时间（默认 2.0s），超时后 fallback 到关键词匹配

    Returns:
        {"matched": True, "intent": "...", "tool": "...", "confidence": "high|medium|low"}
        或
        {"matched": False}
    """
    try:
        prompt = _LLM_CLASSIFY_PROMPT.format(
            tool_descriptions=_LLM_TOOL_DESCRIPTIONS,
            message=message
        )
        messages = [
            SystemMessage(content="你是意图识别专家，只返回 JSON。"),
            HumanMessage(content=prompt)
        ]

        # 带 timeout 的 LLM 调用
        response = await asyncio.wait_for(
            llm_service.llm.ainvoke(messages),
            timeout=timeout_seconds
        )

        # 解析 JSON
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        tool = result.get("tool", "")
        confidence = result.get("confidence", "low")
        intent = result.get("intent", "")

        # 如果 LLM 返回 rag_chat，视为未匹配特定工具
        if tool == "rag_chat" or not tool:
            return {"matched": False}

        return {
            "matched": True,
            "intent": intent,
            "tool": tool,
            "confidence": confidence
        }

    except asyncio.TimeoutError:
        logger.warning("LLM 意图识别超时，fallback 到关键词匹配")
        return classify_by_keywords(message)
    except Exception as e:
        logger.warning(f"LLM 意图识别失败，fallback 到关键词匹配: {e}")
        return classify_by_keywords(message)


async def classify_intent_full(user_message: str) -> dict:
    """完整 LLM 意图分类（AgentService.classify_intent 的独立实现）

    性能：约 500ms + 200 tokens。

    Returns:
        {
            "intent": "simple_qa|analysis|comparison|search|writing|multi_step",
            "requires_tools": [...],
            "complexity": "low|medium|high",
            "reasoning": "..."
        }
    """
    prompt = INTENT_CLASSIFICATION_PROMPT.format(message=user_message)

    messages_payload = [
        SystemMessage(content="你是用户意图识别专家。"),
        HumanMessage(content=prompt)
    ]

    response = await llm_service.llm.ainvoke(messages_payload)

    try:
        content = response.content
        # 提取 JSON 部分
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())
    except Exception as e:
        # 解析失败返回默认意图
        return {
            "intent": "simple_qa",
            "requires_tools": ["search_text"],
            "complexity": "low",
            "reasoning": f"解析失败，使用默认意图: {str(e)}"
        }
