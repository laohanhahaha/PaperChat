"""工具类相关提示词（从工具文件中提取的静态模板）"""

# ============ 文献综述工具提示词 ============

LITERATURE_REVIEW_SYSTEM_PROMPT = "你是学术文献综述撰写专家，擅长系统性地梳理和总结研究领域的进展。"

LITERATURE_REVIEW_USER_TEMPLATE = """请根据以下主题生成一份结构化的文献综述。

主题：{topic}
{context_section}

要求：
1. 综述结构应包含：引言、主体（按主题或时间线组织）、总结与展望
2. 引用相关研究成果时请标注作者和年份
3. 对不同研究观点进行对比和评价
4. 指出研究空白和未来方向
5. 语言学术、严谨、客观

请直接输出文献综述内容："""

# ============ 论文质量评估工具提示词 ============

ASSESS_QUALITY_SYSTEM_PROMPT = "你是学术论文评审专家，擅长评估研究质量和方法论。"

ASSESS_QUALITY_USER_TEMPLATE = """请对以下学术论文进行质量评估：

{paper_title_line}

论文内容：
{paper_text}

请从以下维度进行评估（1-5分）：
1. 研究创新性
2. 方法论严谨性
3. 实验设计合理性
4. 数据分析充分性
5. 结论可信度
6. 写作规范性

请返回 JSON 格式：
{{
    "scores": {{
        "innovation": 分数,
        "methodology": 分数,
        "experimental_design": 分数,
        "data_analysis": 分数,
        "conclusion_validity": 分数,
        "writing_quality": 分数
    }},
    "total_score": 总分,
    "assessment": "总体评价",
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": "改进建议"
}}"""
