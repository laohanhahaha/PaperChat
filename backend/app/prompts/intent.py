"""意图识别相关提示词"""

# ============ LLM 意图识别所用常量 ============

_LLM_TOOL_DESCRIPTIONS = """- analyze_paper: 章节概述、文章结构分析
- deep_analyze_paper: 深度分析、详细分析、学术分析
- extract_key_points: 提取核心知识点、关键概念
- compare_content: 对比、比较、差异、异同
- summarize: 摘要、总结、概括
- translate: 翻译、译成
- explain_term: 解释术语、说明概念、定义
- cross_doc_chat: 跨文档、跨论文、多篇论文问答
- assess_quality: 质量评估、评估论文
- generate_outline: 生成提纲、大纲、报告结构
- literature_review: 文献综述、综述
- cite_paper: 引用格式化（APA/MLA/Chicago）
- polish_text: 润色、改写、优化文本
- save_card: 保存知识卡片
- search_cards: 搜索知识库
- recent_papers: 查询最近论文列表
- search_papers: 搜索论文
- detect_contradiction: 检测多篇论文间矛盾、冲突
- trace_evolution: 追踪方法演进、发展历程
- verify_consistency: 验证多篇论文结论一致性
- find_research_gaps: 发现研究空白、未解决问题
- cross_paper_reason: 跨论文假设推理、假设验证
- rag_chat: 论文问答（默认，无法匹配其他工具时使用）"""

LLM_CLASSIFY_PROMPT = """你是意图识别专家。根据用户消息判断应调用哪个工具。

可用工具：
{tool_descriptions}

用户消息：{message}

返回 JSON（不要其他内容）：
{{"intent": "意图名", "tool": "工具名", "confidence": "high|medium|low"}}

无法匹配时 tool 填 rag_chat。"""

# 保持旧名称的向后兼容
_LLM_CLASSIFY_PROMPT = LLM_CLASSIFY_PROMPT

# 完整意图分类 Prompt（classify_intent 方法使用）
INTENT_CLASSIFICATION_PROMPT = """你是用户意图识别专家。请分析用户的请求，判断其意图类型和复杂度。

用户请求：{message}

请分析并返回 JSON 格式：
{{
    "intent": "simple_qa|analysis|comparison|search|writing|multi_step",
    "requires_tools": ["需要的工具名称列表"],
    "complexity": "low|medium|high",
    "reasoning": "简要说明判断理由"
}}

意图类型说明：
- simple_qa: 简单问答，可直接用 RAG 回答
- analysis: 分析类请求（总结、解释、评估）
- comparison: 对比多篇论文
- search: 搜索特定信息
- writing: 生成内容（提纲、综述）
- multi_step: 复杂多步任务

工具列表：
- search_text: 搜索论文文本
- summarize: 摘要生成
- explain_term: 术语解释
- translate: 翻译
- extract_key_points: 提取知识点
- compare_content: 对比内容
- generate_outline: 生成提纲
- assess_quality: 质量评估
- get_paper_info: 获取论文信息
- literature_review: 生成文献综述
- cite_paper: 格式化引用
- polish_text: 润色文本
- save_card: 保存知识卡片
- search_cards: 搜索知识卡片
- recent_papers: 查询最近论文
- search_papers: 搜索论文
- detect_contradiction: 检测多篇论文间矛盾主张
- trace_evolution: 追踪方法演进时间线
- verify_consistency: 验证多篇论文结论一致性
- find_research_gaps: 发现研究空白
- cross_paper_reason: 跨论文假设生成与推理"""
