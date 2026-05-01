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


# ============ 论文上下文关键词 ============
# 当消息包含这些词时，说明用户在谈论论文/文档，辅助触发工具意图
_PAPER_CONTEXT_WORDS = [
    "论文", "文章", "paper", "文献", "这篇", "全文", "原文",
    "pdf", "文档", "manuscript", "article",
]


# ============ 意图关键词映射 ============
# 设计原则：
# - 强关键词（权重2）：精确的、不会出现在日常对话中的组合词
# - 弱关键词（权重1）：需要搭配论文上下文才有意义的泛用词
# - threshold 统一为 3：单个泛用词（1）+ 上下文（1）= 2 不够；
#   需要精确关键词（2）+ 上下文（1），或多个弱词组合
# - 极精确的关键词可给权重 3 直接触发

INTENT_KEYWORDS: dict[str, dict] = {
    "chapter_overview": {
        "keywords": [
            ("章节概述", 3), ("章节总结", 3), ("文章结构", 3), ("章节内容", 3),
            ("各章节", 3), ("章节介绍", 3), ("论文结构", 3), ("论文目录", 3),
            ("章节结构", 3),
            ("paper outline", 3), ("paper structure", 3),
            ("结构分析", 2),
            # 已移除："目录"、"概述" — 日常对话中太常见
        ],
        "threshold": 3,
        "intent": "chapter_overview",
        "tool": "analyze_paper"
    },
    "deep_analysis": {
        "keywords": [
            ("深度分析论文", 3), ("深入分析论文", 3), ("详细分析论文", 3),
            ("深度分析这篇", 3), ("深入分析这篇", 3),
            ("分析这篇论文", 3), ("分析这篇文章", 3),
            ("研究方法分析", 3), ("方法论分析", 3),
            ("critical analysis", 2), ("detailed analysis", 2),
            ("深度分析", 2), ("深入分析", 2), ("详细分析", 2),
            ("学术分析", 2),
            # 已移除："分析"、"分析一下"、"帮我分析" — 日常对话中极其常见
        ],
        "threshold": 3,
        "intent": "deep_analysis",
        "tool": "deep_analyze_paper"
    },
    "key_points": {
        "keywords": [
            ("核心知识点", 3), ("关键要点", 3), ("核心要点", 3),
            ("主要观点", 2), ("关键概念", 2), ("核心概念", 2), ("核心思想", 2),
            ("key points", 2), ("main points", 2),
            ("知识点", 1),
            # 已移除："重点"、"关键点" — 日常对话中太常见
        ],
        "threshold": 3,
        "intent": "key_points",
        "tool": "extract_key_points"
    },
    "compare": {
        "keywords": [
            ("对比分析论文", 3), ("比较这两篇", 3), ("论文对比", 3),
            ("对比分析", 2), ("异同点", 2), ("有何差异", 2),
            ("compare papers", 2), ("comparison", 2),
            # 已移除："对比"、"比较"、"差异"、"异同"、"对照" — 日常对话中常见
        ],
        "threshold": 3,
        "intent": "comparison",
        "tool": "compare_content"
    },
    "summary": {
        "keywords": [
            ("全文总结", 3), ("论文总结", 3), ("论文摘要", 3),
            ("总结这篇论文", 3), ("总结这篇文章", 3),
            ("概括全文", 3), ("总结全文", 3),
            ("summarize paper", 3), ("paper summary", 3),
            ("summarize", 2), ("summary", 2),
            # 已移除："总结"、"摘要"、"概括"、"提炼"、"帮我总结"、"总结一下"、"概括一下"
            # — 日常对话中极其常见
        ],
        "threshold": 3,
        "intent": "summary",
        "tool": "summarize"
    },
    "translate": {
        "keywords": [
            ("翻译论文", 3), ("翻译这篇", 3), ("翻译这段", 3),
            ("中译英", 3), ("英译中", 3),
            ("帮我翻译", 2), ("翻译", 2), ("译成", 2), ("translate", 2),
        ],
        "threshold": 3,
        "intent": "translate",
        "tool": "translate"
    },
    "explain": {
        "keywords": [
            ("名词解释", 3), ("术语解释", 3), ("概念解释", 3),
            ("是什么意思", 2), ("explain", 2), ("definition of", 2),
            ("什么是", 1), ("请解释", 1),
            # 已移除："解释"、"含义"、"定义"、"解释一下"、"帮我解释" — 日常对话中常见
        ],
        "threshold": 3,
        "intent": "explain",
        "tool": "explain_term"
    },
    "cross_doc": {
        "keywords": [
            ("跨文档", 3), ("多篇论文", 3), ("多文档", 3),
            ("跨论文对比", 3), ("跨论文分析", 3),
            ("across papers", 3), ("multiple papers", 3),
        ],
        "threshold": 3,
        "intent": "cross_doc",
        "tool": "cross_doc_chat"
    },
    "quality_assessment": {
        "keywords": [
            ("质量评估", 3), ("评估质量", 3), ("论文优缺点", 3),
            ("assess quality", 3),
            ("优缺点", 2), ("优劣势", 2),
            # 已移除："评估" — 日常对话中常见
        ],
        "threshold": 3,
        "intent": "quality_assessment",
        "tool": "assess_quality"
    },
    "outline": {
        "keywords": [
            ("写提纲", 3), ("生成大纲", 3), ("报告大纲", 3),
            ("generate outline", 3),
            ("写报告", 2),
            # 已移除："提纲"、"大纲" — 可能出现在日常对话中
        ],
        "threshold": 3,
        "intent": "outline",
        "tool": "generate_outline"
    },
    # 写作类
    "literature_review": {
        "keywords": [
            ("文献综述", 3), ("写综述", 3), ("literature review", 3),
            # 已移除："综述" — 可能出现在日常对话中
        ],
        "threshold": 3,
        "intent": "literature_review",
        "tool": "literature_review"
    },
    "cite_paper": {
        "keywords": [
            ("引用格式", 3), ("格式化引用", 3), ("citation format", 3),
            ("APA格式", 3), ("MLA格式", 3),
            # 已移除："APA"、"MLA"、"Chicago"、"citation" — 单字母缩写太容易误触发
        ],
        "threshold": 3,
        "intent": "cite_paper",
        "tool": "cite_paper"
    },
    "polish_text": {
        "keywords": [
            ("润色论文", 3), ("润色文章", 3), ("优化文本", 3),
            ("帮我润色", 3), ("帮我改写", 3),
            ("polish", 2), ("rewrite", 2), ("润色", 2),
            # 已移除："改写" — 日常对话中可能出现
        ],
        "threshold": 3,
        "intent": "polish_text",
        "tool": "polish_text"
    },
    # 知识库类
    "save_card": {
        "keywords": [
            ("保存知识", 3), ("保存卡片", 3), ("保存笔记", 3),
            ("save knowledge", 3), ("save card", 3),
            # 已移除："记下来" — 日常对话中太常见
        ],
        "threshold": 3,
        "intent": "save_card",
        "tool": "save_card"
    },
    "search_cards": {
        "keywords": [
            ("搜索知识", 3), ("查找笔记", 3), ("知识库搜索", 3),
            ("search knowledge", 3), ("search cards", 3),
        ],
        "threshold": 3,
        "intent": "search_cards",
        "tool": "search_cards"
    },
    # 论文查询类
    "recent_papers": {
        "keywords": [
            ("最近上传", 3), ("最近读的", 3), ("论文库列表", 3),
            ("列出论文", 3), ("所有论文", 3), ("论文列表", 3),
            ("最近的论文", 3), ("上传的论文", 3),
            ("recent papers", 3), ("paper list", 3), ("list papers", 3),
        ],
        "threshold": 3,
        "intent": "recent_papers",
        "tool": "recent_papers"
    },
    "search_papers": {
        "keywords": [
            ("搜索论文", 3), ("查找论文", 3), ("找论文", 3),
            ("搜索关于", 2), ("搜索有关", 2),
            ("search papers", 3), ("find papers", 3),
        ],
        "threshold": 3,
        "intent": "search_papers",
        "tool": "search_papers"
    },
    # 跨论文推理类
    "detect_contradiction": {
        "keywords": [
            ("检测矛盾", 3), ("发现冲突", 3), ("观点不一致", 3),
            ("观点矛盾", 3), ("论点冲突", 3),
            ("contradiction", 2), ("detect conflict", 2),
            # 已移除："矛盾"、"冲突"、"不一致" — 日常对话中常见
        ],
        "threshold": 3,
        "intent": "detect_contradiction",
        "tool": "detect_contradiction"
    },
    "trace_evolution": {
        "keywords": [
            ("方法演进", 3), ("发展历程", 3), ("变化趋势", 3), ("方法演变", 3),
            ("技术演进", 3),
            ("evolution of", 2), ("trace evolution", 2),
            # 已移除："演进" — 日常对话中可能出现
        ],
        "threshold": 3,
        "intent": "trace_evolution",
        "tool": "trace_evolution"
    },
    "verify_consistency": {
        "keywords": [
            ("验证一致性", 3), ("验证结论", 3), ("结论是否一致", 3),
            ("verify consistency", 3),
            # 已移除："一致性"、"是否一致" — 日常对话中可能出现
        ],
        "threshold": 3,
        "intent": "verify_consistency",
        "tool": "verify_consistency"
    },
    "find_research_gaps": {
        "keywords": [
            ("研究空白", 3), ("研究缺口", 3), ("未解决问题", 3),
            ("research gap", 3), ("find gaps", 3),
            # 已移除："局限性" — 日常对话中常见
        ],
        "threshold": 3,
        "intent": "find_research_gaps",
        "tool": "find_research_gaps"
    },
    "cross_paper_reason": {
        "keywords": [
            ("跨论文推理", 3), ("假设验证", 3), ("假设推理", 3),
            ("跨论文", 2),
            ("cross-paper reason", 3), ("cross paper reasoning", 3),
            # 已移除："hypothesis" — 日常对话中可能出现
        ],
        "threshold": 3,
        "intent": "cross_paper_reason",
        "tool": "cross_paper_reason"
    },
    # 多模态类
    "image_analysis": {
        "keywords": [
            ("图片分析", 3), ("分析图片", 3), ("描述图片", 3), ("图像识别", 3),
            ("论文的图片", 3), ("论文的图", 3), ("文章的图", 3),
            ("分析图", 2),
            ("image analysis", 3), ("analyze image", 3), ("describe image", 3),
        ],
        "threshold": 3,
        "intent": "image_analysis",
        "tool": "analyze_chart"
    },
    "chart_extraction": {
        "keywords": [
            ("提取图表", 3), ("图表数据", 3), ("读取图表", 3), ("表格提取", 3),
            ("chart data", 3), ("extract chart", 3), ("read table", 3),
        ],
        "threshold": 3,
        "intent": "chart_extraction",
        "tool": "analyze_chart"
    },
    "visual_comparison": {
        "keywords": [
            ("图表对比", 3), ("视觉对比", 3), ("比较图表", 3), ("图像比较", 3),
            ("visual comparison", 3), ("compare charts", 3), ("compare figures", 3),
        ],
        "threshold": 3,
        "intent": "visual_comparison",
        "tool": "analyze_chart"
    },
    "multimodal_search": {
        "keywords": [
            ("图片搜索", 3), ("以图搜文", 3), ("图文搜索", 3), ("视觉搜索", 3),
            ("image search", 3), ("visual search", 3), ("search by image", 3),
        ],
        "threshold": 3,
        "intent": "multimodal_search",
        "tool": "multimodal_search"
    },
    "cross_modal_reasoning": {
        "keywords": [
            ("图文推理", 3), ("跨模态推理", 3), ("图表推理", 3), ("图像推理", 3),
            ("cross modal", 3), ("visual reasoning", 3), ("multimodal reasoning", 3),
        ],
        "threshold": 3,
        "intent": "cross_modal_reasoning",
        "tool": "analyze_chart"
    }
}


# INTENT_CLASSIFICATION_PROMPT 、_LLM_CLASSIFY_PROMPT 、_LLM_TOOL_DESCRIPTIONS
# 已迁移至 app.prompts.intent，此处通过顶部 import 引入


# ============ 意图识别函数 ============

def _has_paper_context(message_lower: str) -> bool:
    """检测消息中是否包含论文/文档上下文词"""
    return any(w in message_lower for w in _PAPER_CONTEXT_WORDS)


def classify_by_keywords(message: str) -> dict:
    """基于关键词权重的意图识别（快速识别，用于直接功能触发）

    无 LLM 调用，< 1ms。

    关键词格式：(keyword, weight) 元组
    - 精确关键词（权重3）：非常精确的组合词，单独命中即可触发
    - 强关键词（权重2）：较精确的词，需搭配论文上下文才能触发
    - 弱关键词（权重1）：泛用词，需要多个组合或论文上下文才有意义

    论文上下文加成：当消息包含论文相关词（论文/文章/paper等）时，+1 加成。
    每个意图有 threshold=3 阈值，累计权重 >= threshold 才算匹配。

    设计原则：宁可漏掉（交给 LLM 判断），也不要误触发。

    Args:
        message: 用户消息

    Returns:
        {"matched": True, "intent": "...", "tool": "...", "confidence": "high|medium"}
        或
        {"matched": False}
    """
    message_lower = message.lower()
    has_paper_ctx = _has_paper_context(message_lower)

    best_match = None
    best_score = 0

    for intent_name, config in INTENT_KEYWORDS.items():
        score = 0
        threshold = config.get("threshold", 3)
        for kw_item in config["keywords"]:
            if isinstance(kw_item, tuple):
                keyword, weight = kw_item
            else:
                keyword, weight = kw_item, 1
            if keyword.lower() in message_lower:
                score += weight

        # 论文上下文加成：当消息包含论文相关词时 +1
        if score > 0 and has_paper_ctx:
            score += 1

        if score >= threshold and score > best_score:
            best_score = score
            best_match = {
                "intent": config["intent"],
                "tool": config["tool"],
                "confidence": "high" if score >= threshold + 2 else "medium"
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
