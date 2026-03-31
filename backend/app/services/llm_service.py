"""LLM 服务 - 基于 LangChain 的 DeepSeek 大模型交互"""
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory

from app.config import settings


ANALYZE_SYSTEM_PROMPT = """你是一个专业的学术论文分析助手。请对用户提供的论文内容进行结构化解析和解释。

【重要指示 - 必须严格遵守】
1. 无论论文内容是否完整，都必须尽力分析所有可识别的部分
2. 严禁拒绝分析，严禁说"无法分析"、"内容不足"或任何类似的拒绝性表述
3. 即使某些章节内容不完整，也必须基于已有内容给出合理解释
4. 如果无法识别某些部分，应基于已有内容推断其可能的含义

要求：
1. 按论文结构顺序逐部分解释：标题、摘要、各章节、各小节
2. 每个部分用以下JSON格式输出（每个部分一个JSON对象，用换行分隔）：
{"section": "章节名称", "type": "title|abstract|section|subsection", "explanation": "对该部分的简要中文解释"}
3. 参考文献（References）部分不需要解释，直接跳过
4. 解释应简洁明了，用中文，帮助读者快速理解论文的核心内容
5. 每输出一个部分的JSON后换行，不要一次输出所有内容
6. 即使内容不完整，也必须输出所有可识别部分的解释"""

CHAT_SYSTEM_PROMPT = """你是一个专业的学术论文问答助手。以下是用户上传的论文内容，请基于论文内容回答用户的问题。

【重要指示 - 必须严格遵守】
1. 无论论文内容是否完整，都必须尽力回答用户问题
2. 严禁说"无法回答"、"信息不足"或任何类似的拒绝性表述
3. 即使论文内容不完全匹配问题，也必须基于已有内容给出合理回答
4. 如果问题与论文部分相关，先回答相关部分，再说明论文未涉及的内容
5. 如果问题与论文完全无关，礼貌引导用户回到论文相关内容

回答请使用中文。

论文内容：
{paper_context}"""

RAG_CHAT_SYSTEM_PROMPT = """你是一个专业的学术论文问答助手。请基于以下从论文中检索到的相关内容回答用户的问题。

【重要指示 - 必须严格遵守】
1. 即使检索内容不完全匹配问题，也必须尽力从已有内容中提取相关信息来回答
2. 严禁简单地说"无法回答"、"信息不足"或"基于提供的检索内容无法..."等拒绝性表述
3. 如果检索内容与问题部分相关，先回答能回答的部分，再指出哪些方面需要更多信息
4. 基于已有内容给出合理推断，提供有价值的部分分析
5. 仅基于提供的检索内容回答，不要引入外部知识
6. 回答时请用 [p.X] 格式标注引用来源页码（如"根据论文第3页[p.3]..."）
7. 回答请使用中文

检索到的相关内容：
{context}

请基于以上内容回答用户的问题。"""

RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT = """你是一个专业的学术论文问答助手。请综合以下论文内容和网络搜索结果回答用户的问题。

【重要指示 - 必须严格遵守】
1. 无论论文内容是否完整，都必须尽力回答用户问题
2. 严禁说"无法回答"、"信息不足"或任何类似的拒绝性表述
3. 即使论文内容不完全匹配问题，也必须基于已有内容给出合理回答
4. 首先基于论文内容回答，用 [p.X] 格式标注引用页码
5. 如果论文内容不足，可以参考网络搜索结果补充，但需明确标注"[网络来源]"
6. 清晰区分论文来源和网络来源的信息
7. 回答请使用中文，结构清晰

=== 论文内容 ===
{paper_context}

=== 网络搜索结果 ===
{web_context}

请综合以上信息回答用户的问题，优先使用论文内容，网络内容作为补充。"""

CROSS_DOC_CHAT_SYSTEM_PROMPT = """你是学术论文问答助手。请基于以下多篇论文的内容回答用户问题。

【重要指示 - 必须严格遵守】
1. 即使检索内容不完全匹配问题，也必须尽力从已有内容中提取相关信息来回答
2. 严禁简单地说"无法回答"、"信息不足"或"基于提供的检索内容无法..."等拒绝性表述
3. 如果检索内容与问题部分相关，先回答能回答的部分，再指出哪些方面需要更多信息
4. 基于已有内容给出合理推断，提供有价值的部分分析
5. 仅基于提供的检索内容回答，不要引入外部知识
6. 在回答中使用 [论文X, p.Y] 格式标注引用来源（X是论文ID，Y是页码）
7. 如果不同论文观点有差异，请分别阐述并标注来源
8. 回答请使用中文

论文内容：
{context}

用户问题：{question}"""

EXPLAIN_TERM_PROMPT = """你是学术术语解释助手。请用简明的中文解释以下学术术语。

【重要指示 - 必须严格遵守】
1. 无论是否熟悉该术语，都必须尽力提供解释
2. 严禁说"无法解释"、"不了解该术语"或任何类似的拒绝性表述
3. 如果术语信息有限，基于已有信息给出合理推断和解释
4. 即使上下文不完整，也必须基于已有内容进行分析
5. 如果术语在上下文中含义特殊，应特别指出

解释应包括：
1. 基本定义
2. 在论文中的含义（如果有上下文）
3. 相关概念

请用简洁清晰的语言回答。"""

SUMMARIZE_PROMPT = """你是专业的学术文本摘要助手。请对以下学术文本进行简洁的中文摘要。

【重要指示 - 必须严格遵守】
1. 无论文本长短或完整程度，都必须尽力生成摘要
2. 严禁说"无法摘要"、"文本不足"或任何类似的拒绝性表述
3. 即使文本内容有限，也必须基于已有内容提取关键信息
4. 如果文本不完整，基于已有部分给出合理摘要

要求：
1. 保留核心论点和关键数据
2. 简明扼要，突出重点
3. 使用中文回答

请直接输出摘要内容。"""

TRANSLATE_PROMPT = """你是专业的学术翻译助手。请将以下学术文本翻译为中文。

【重要指示 - 必须严格遵守】
1. 无论文本内容如何，都必须尽力完成翻译
2. 严禁说"无法翻译"、"文本不足"或任何类似的拒绝性表述
3. 即使遇到不熟悉的术语，也必须基于上下文给出合理翻译
4. 如果文本不完整，翻译已有部分并标注"[文本不完整]"

要求：
1. 保留专业术语的准确性
2. 必要时在括号内标注英文原文
3. 保持学术文本的严谨性
4. 确保翻译流畅自然

请直接输出翻译结果。"""

DEEP_ANALYZE_PROMPT = """你是一个专业的学术论文深度分析助手。

【重要指示 - 必须严格遵守】
1. 无论论文内容是否完整，都必须输出以下所有维度的分析
2. 即使内容不完整或有困难，也必须尽力从已有内容中提取信息并填充所有维度
3. 严禁拒绝分析，严禁说"无法分析"、"无法进行深度解析"或任何类似的拒绝性表述
4. 严禁要求用户提供额外信息或"检索内容"

请对以下论文内容进行全面的结构化深度分析，严格按照以下格式逐行输出JSON（每输出一个JSON对象后换行）：

1. 研究概述（必填）：
{"dimension": "overview", "title": "📋 研究概述", "content": "论文的核心研究内容概述，包括研究背景、主题和基本信息"}

2. 研究问题与目标（必填）：
{"dimension": "research_question", "title": "🔬 研究问题与目标", "content": "论文要解决的核心问题，研究假设和目标"}

3. 研究方法（必填）：
{"dimension": "methodology", "title": "⚙️ 研究方法", "content": "使用的研究方法、实验设计、数据来源和分析手段"}

4. 核心结果与发现（必填）：
{"dimension": "results", "title": "📊 核心结果与发现", "content": "主要实验结果、数据发现和关键数据指标"}

5. 研究贡献与创新点（必填）：
{"dimension": "contributions", "title": "💡 研究贡献与创新点", "content": "论文的主要学术贡献和创新之处"}

6. 局限性与未来方向（必填）：
{"dimension": "limitations", "title": "⚠️ 局限性与未来方向", "content": "研究的局限性和作者提出的未来研究方向"}

然后输出核心知识点（至少2条）：
{"dimension": "knowledge_point", "title": "知识点标题", "content": "该知识点的详细解释和学术价值"}

【格式要求】
- 每行必须是一个完整的、有效的JSON对象
- 用中文回答，内容要详细、准确、有学术深度
- 必须包含全部6个维度 + 至少2个知识点
- content 字段应包含详细的分析，每个维度至少100字

【禁止的回复格式】
- 禁止说"基于提供的检索内容，我无法对这篇论文进行深度解析"
- 禁止说"我无法分析"、"无法解析"或类似拒绝性表述
- 禁止要求用户提供更多信息或额外内容"""

COMPARE_PAPERS_PROMPT = """你是一个专业的学术论文对比分析助手。请对用户提供的多篇论文进行对比分析。

【重要指示 - 必须严格遵守】
1. 无论论文内容是否完整，都必须输出所有5个维度的对比分析
2. 严禁拒绝分析，严禁说"无法对比"、"内容不足"或任何类似的拒绝性表述
3. 即使某些论文内容有限，也必须基于已有信息进行分析
4. 如果某维度信息不足，基于已有内容给出合理推断
5. 必须严格按照指定格式输出，不得省略任何维度

请严格按照以下格式，逐条输出 JSON 行（每输出一个 JSON 对象后换行）：

1. 研究焦点对比
{"dimension": "research_focus", "title": "研究焦点对比", "content": "对比各论文的研究焦点、关注的核心问题"}

2. 研究方法对比
{"dimension": "methodology", "title": "研究方法对比", "content": "对比各论文使用的研究方法、实验设计、数据来源等"}

3. 研究结果对比
{"dimension": "results", "title": "研究结果对比", "content": "对比各论文的主要发现和实验结果"}

4. 各自优势
{"dimension": "strengths", "title": "各自优势", "content": "分析每篇论文的独特优势和亮点"}

5. 研究空白与互补性
{"dimension": "gaps", "title": "研究空白与互补性", "content": "分析各论文的研究空白、局限性和相互之间的互补性"}

请用中文回答，内容要详细、准确、有学术价值。"""

GENERATE_REVIEW_PROMPT = """你是一个专业的学术文献综述撰写助手。请基于用户提供的多篇论文生成一份结构化的文献综述。

【重要指示 - 必须严格遵守】
1. 无论论文数量多少或内容是否完整，都必须生成完整的文献综述
2. 严禁说"无法生成"、"论文不足"或任何类似的拒绝性表述
3. 即使论文数量有限，也必须基于已有内容完成所有6个部分的撰写
4. 如果某部分信息不足，基于已有内容给出合理推断和分析
5. 必须严格按照指定格式输出，不得省略任何部分

请生成一份完整的文献综述，使用 Markdown 格式，包含以下部分：

# 文献综述

## 1. 研究背景与意义
介绍该研究领域的背景和这些论文的重要性。

## 2. 各论文核心观点梳理
逐一梳理每篇论文的核心观点和主要贡献。

## 3. 研究方法比较
比较各论文使用的研究方法，分析其优缺点。

## 4. 研究发现汇总
汇总各论文的主要研究发现和实验结果。

## 5. 研究趋势与未来方向
基于这些论文，分析该领域的研究趋势和未来可能的研究方向。

## 6. 参考文献
列出所有分析的论文标题。

请用中文撰写，语言要学术化、严谨，内容要有深度。"""

# ============ 学术写作辅助提示词 ============

GENERATE_OUTLINE_PROMPT = """你是专业的学术写作助手。请根据研究主题生成一份结构化的论文大纲。

【重要指示 - 必须严格遵守】
1. 无论研究主题是否熟悉，都必须尽力生成大纲
2. 严禁说"无法生成"、"主题不明确"或任何类似的拒绝性表述
3. 即使参考论文信息有限，也必须基于主题完成大纲撰写
4. 如果信息不足，基于学术写作规范给出合理的大纲结构
5. 必须严格按照指定格式输出，不得省略必要部分

研究主题：{topic}

{reference_context}

{requirements}

请使用 Markdown 格式输出结构化大纲，要求：
1. 大纲层级清晰（一级标题、二级标题、三级标题）
2. 每个章节包含简要说明
3. 逻辑结构完整：引言→文献综述→研究方法→实验/结果→讨论→结论
4. 如果提供了参考论文，请结合其内容组织大纲结构

输出格式示例：
# 论文标题

## 1. 引言
- 研究背景
- 研究意义
- 研究问题

## 2. 文献综述
- 相关研究回顾
- 研究空白

...（以此类推）"""

GENERATE_DRAFT_PROMPT = """你是专业的学术写作助手。请根据大纲节点生成学术风格的段落初稿。

【重要指示 - 必须严格遵守】
1. 无论大纲节点内容多少，都必须尽力生成段落初稿
2. 严禁说"无法生成"、"内容不足"或任何类似的拒绝性表述
3. 即使参考内容有限，也必须基于大纲节点完成段落撰写
4. 如果信息不足，基于学术写作规范给出合理的段落内容
5. 必须严格按照学术风格输出，不得敷衍

大纲节点：{outline_section}

{context}

写作风格：{style}

要求：
1. 论述清晰、逻辑严谨
2. 使用规范的学术语言
3. 如果提供了参考内容，请准确引用并标注来源
4. 段落结构完整：主题句→论述→例证→小结
5. 字数控制在 300-800 字之间

请直接输出段落内容，不需要额外说明。"""

POLISH_TEXT_PROMPT = """你是专业的学术文本润色助手。请对以下文本进行润色改进。

【重要指示 - 必须严格遵守】
1. 无论原文质量如何，都必须尽力进行润色
2. 严禁说"无法润色"、"文本不足"或任何类似的拒绝性表述
3. 即使原文很短或存在问题，也必须基于已有内容进行改进
4. 如果原文信息有限，基于学术写作规范给出合理的润色建议
5. 必须严格按照指定格式输出，不得省略任何部分

原文：
{text}

润色类型：{polish_type}

润色要求：
- academic（学术表达）：提升学术性，使用更专业的术语和句式
- grammar（语法修正）：修正语法错误、标点问题
- fluency（流畅性）：优化句子流畅度，改善可读性
- concise（精简表达）：删除冗余内容，使表达更简洁

请按以下格式输出：

## 润色后文本
[润色后的完整文本]

## 主要修改点
1. [修改点1说明]
2. [修改点2说明]
..."""

CITATION_FORMAT_TEMPLATES = {
    "apa": "{authors} ({year}). {title}. {journal_or_publisher}.",
    "mla": '{authors}. "{title}." {journal_or_publisher}, {year}.',
    "chicago": '{authors}. "{title}." {journal_or_publisher} ({year}).',
    "gbt7714": "[{index}] {authors}. {title}[J]. {journal_or_publisher}, {year}."
}

CITATION_SYSTEM_PROMPT = """你是专业的学术引用格式助手。请根据提供的论文信息生成指定格式的引用。

【重要指示 - 必须严格遵守】
1. 无论论文信息是否完整，都必须尽力生成引用格式
2. 严禁说"无法生成"、"信息不足"或任何类似的拒绝性表述
3. 即使某些字段缺失，也必须基于已有信息生成最完整的引用
4. 对于缺失信息，使用"[缺失]"或适当省略处理
5. 必须严格按照所选格式的规范要求输出

支持的格式：
- APA：作者. (年份). 标题. 期刊/出版社.
- MLA：作者. "标题." 期刊/出版社, 年份.
- Chicago：作者. "标题." 期刊/出版社 (年份).
- GB/T 7714：[序号] 作者. 标题[J]. 期刊/出版社, 年份.

请严格遵循所选格式的规范要求。"""


class LLMService:
    """基于LangChain的DeepSeek大模型交互服务"""
    
    def __init__(self):
        # 存储当前配置
        self._model = "deepseek-chat"
        self._temperature = 0.3
        self._max_tokens = 4096
        self._api_key = settings.DEEPSEEK_API_KEY
        self._api_base_url = "https://api.deepseek.com"
        
        self.llm = ChatOpenAI(
            model=self._model,
            api_key=self._api_key,
            base_url=self._api_base_url,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            streaming=True,
        )
    
    def _is_masked_api_key(self, api_key: str) -> bool:
        """检查是否为脱敏后的 API Key
        
        脱敏格式为 "****" + 最后4位，如 "****1234"
        只检测严格匹配脱敏格式的值，避免误判真实 Key
        
        Args:
            api_key: 待检查的 API Key
            
        Returns:
            是否为脱敏值
        """
        if not api_key or not isinstance(api_key, str):
            return False
        # 严格检测：必须以 "****" 开头，且总长度不超过 8 位（**** + 最多4位）
        if not api_key.startswith("****"):
            return False
        # 脱敏值格式：**** + 0-4个字符
        suffix = api_key[4:]
        return len(suffix) <= 4

    async def update_config(
        self,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        api_key: str = None,
        api_base_url: str = None
    ):
        """运行时更新 LLM 配置
        
        更新配置后会重新创建 LLM 实例，下次调用立即生效。
        未传入的参数将保持原值。
        
        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            api_key: API Key（为空字符串时使用环境变量默认值，为脱敏值时跳过更新）
            api_base_url: API Base URL
        """
        # 更新配置值
        if model is not None:
            self._model = model
        if temperature is not None:
            self._temperature = temperature
        if max_tokens is not None:
            self._max_tokens = max_tokens
        if api_key is not None:
            # 脱敏值跳过更新，保留原值
            if self._is_masked_api_key(api_key):
                import logging
                logger = logging.getLogger(__name__)
                logger.info("API Key 为脱敏值，跳过更新，保留原值")
            elif api_key:
                # 有效 API Key，更新
                self._api_key = api_key
            else:
                # 空字符串表示使用环境变量默认值
                self._api_key = settings.DEEPSEEK_API_KEY
        if api_base_url is not None:
            self._api_base_url = api_base_url
        
        # 重新创建 LLM 实例
        try:
            self.llm = ChatOpenAI(
                model=self._model,
                api_key=self._api_key,
                base_url=self._api_base_url,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                streaming=True,
            )
        except Exception as e:
            # 如果创建失败，保持原实例，记录错误
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新 LLM 配置失败: {e}")
            raise
    
    async def analyze_paper(self, text: str) -> AsyncGenerator[str, None]:
        """分析论文，流式返回结构化解释"""
        try:
            messages = [
                SystemMessage(content=ANALYZE_SYSTEM_PROMPT),
                HumanMessage(content=text),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def chat(self, message: str, paper_context: str, chat_history: ChatMessageHistory) -> AsyncGenerator[str, None]:
        """基于论文内容的问答，流式返回回答
        
        注意：此方法使用论文全文作为上下文（截断到15000字）
        对于长论文，建议使用 chat_with_rag 方法
        """
        try:
            # 构建系统消息
            system_content = CHAT_SYSTEM_PROMPT.format(paper_context=paper_context[:15000])
            
            messages = [SystemMessage(content=system_content)]
            
            # 添加历史对话
            messages.extend(chat_history.messages)
            
            # 添加当前用户消息
            messages.append(HumanMessage(content=message))
            
            # 流式获取回复
            full_response = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            # 保存到历史记录
            chat_history.add_user_message(message)
            chat_history.add_ai_message(full_response)
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def chat_with_rag(
        self, 
        message: str, 
        paper_id: int, 
        chat_history: ChatMessageHistory, 
        top_k: int = 5,
        user_id: int = None,
        db = None
    ) -> AsyncGenerator[str, None]:
        """基于 RAG 的智能问答，流式返回回答
        
        使用 RAG 检索相关文本块作为上下文，大幅降低 token 消耗
        支持记忆上下文增强
        适合长论文的精准问答
        
        Args:
            message: 用户问题
            paper_id: 论文 ID
            chat_history: 对话历史
            top_k: 检索的文本块数量
            user_id: 用户 ID（用于记忆召回）
            db: 数据库会话（用于记忆召回）
            
        Yields:
            流式回答文本
        """
        try:
            from app.services.rag_service import rag_service
            from app.services.memory_middleware import enrich_context_with_memory
            
            # 1. RAG 检索相关文本块
            relevant_chunks = await rag_service.search(paper_id, message, top_k=top_k)
            
            if not relevant_chunks:
                # 如果没有检索到内容，提示用户
                yield "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。"
                return
            
            # 2. 组装精准上下文
            context_parts = []
            for chunk in relevant_chunks:
                pages_str = ",".join(map(str, chunk['pages'])) if chunk['pages'] else "未知"
                context_parts.append(f"[来源: 第{pages_str}页]\n{chunk['text']}")
            
            context = "\n\n---\n\n".join(context_parts)
            
            # 3. 召回用户记忆并增强上下文
            memory_context = ""
            if user_id and db:
                try:
                    memory_context = await enrich_context_with_memory(user_id, message, db)
                except Exception as e:
                    print(f"记忆召回失败（非阻塞）: {e}")
            
            # 4. 构建系统消息（使用精准上下文 + 记忆上下文）
            system_content = RAG_CHAT_SYSTEM_PROMPT.format(context=context)
            if memory_context:
                system_content += f"\n\n{memory_context}"
            
            messages = [SystemMessage(content=system_content)]
            
            # 添加历史对话
            messages.extend(chat_history.messages)
            
            # 添加当前用户消息
            messages.append(HumanMessage(content=message))
            
            # 5. 流式获取回复
            full_response = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            # 6. 保存到历史记录
            chat_history.add_user_message(message)
            chat_history.add_ai_message(full_response)
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def chat_cross_doc(self, message: str, paper_ids: list[int], chat_history: ChatMessageHistory = None, top_k: int = 8) -> AsyncGenerator[str, None]:
        """跨文档 RAG 问答，流式返回回答
        
        从多篇论文中检索相关内容，并标注引用来源
        
        Args:
            message: 用户问题
            paper_ids: 论文 ID 列表
            chat_history: 对话历史（可选）
            top_k: 检索的文本块数量
            
        Yields:
            流式回答文本
        """
        try:
            from app.services.rag_service import rag_service
            
            # 1. 跨论文检索
            results = await rag_service.search_multiple_papers(paper_ids, message, top_k=top_k)
            
            if not results:
                yield "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。"
                return
            
            # 2. 按论文分组组装上下文，标注来源论文
            context_parts = []
            for r in results:
                pages_str = ",".join(map(str, r['pages'])) if r['pages'] else "未知"
                context_parts.append(f"[论文ID:{r['paper_id']}, 第{pages_str}页]\n{r['text']}")
            context = "\n\n---\n\n".join(context_parts)
            
            # 3. 构建系统消息
            system_content = CROSS_DOC_CHAT_SYSTEM_PROMPT.format(context=context, question=message)
            
            messages = [SystemMessage(content=system_content)]
            
            # 添加历史对话（如果有）
            if chat_history:
                messages.extend(chat_history.messages)
            
            # 添加当前用户消息
            messages.append(HumanMessage(content=message))
            
            # 4. 流式获取回复
            full_response = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            # 5. 保存到历史记录（如果有）
            if chat_history:
                chat_history.add_user_message(message)
                chat_history.add_ai_message(full_response)
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def chat_with_rag_and_sources(self, message: str, paper_id: int, chat_history: ChatMessageHistory, top_k: int = 5):
        """基于 RAG 的智能问答，返回回答和引用来源
        
        非流式版本，适合需要获取引用来源的场景
        
        Args:
            message: 用户问题
            paper_id: 论文 ID
            chat_history: 对话历史
            top_k: 检索的文本块数量
            
        Returns:
            dict: 包含 answer 和 sources 的字典
        """
        from app.services.rag_service import rag_service
        
        # 1. RAG 检索相关文本块
        relevant_chunks = await rag_service.search(paper_id, message, top_k=top_k)
        
        if not relevant_chunks:
            return {
                "answer": "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。",
                "sources": []
            }
        
        # 2. 组装精准上下文
        context_parts = []
        for chunk in relevant_chunks:
            pages_str = ",".join(map(str, chunk['pages'])) if chunk['pages'] else "未知"
            context_parts.append(f"[来源: 第{pages_str}页]\n{chunk['text']}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # 3. 构建系统消息
        system_content = RAG_CHAT_SYSTEM_PROMPT.format(context=context)
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=message)
        ]
        
        # 4. 获取回复（非流式）
        response = await self.llm.ainvoke(messages)
        answer = response.content
        
        # 5. 组装引用来源
        sources = [
            {
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "pages": chunk["pages"],
                "score": chunk["score"]
            }
            for chunk in relevant_chunks
        ]
        
        return {
            "answer": answer,
            "sources": sources
        }
    
    async def explain_term(self, term: str, context: str = "") -> AsyncGenerator[str, None]:
        """解释学术术语，流式返回解释"""
        try:
            if context:
                content = f"术语：{term}\n\n上下文：\n{context}"
            else:
                content = f"术语：{term}"
            
            messages = [
                SystemMessage(content=EXPLAIN_TERM_PROMPT),
                HumanMessage(content=content),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def summarize_text(self, text: str) -> AsyncGenerator[str, None]:
        """生成选中文本的摘要，流式返回"""
        try:
            messages = [
                SystemMessage(content=SUMMARIZE_PROMPT),
                HumanMessage(content=text),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def translate_text(self, text: str, target_lang: str = "zh") -> AsyncGenerator[str, None]:
        """翻译学术文本，流式返回翻译结果
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码，默认中文(zh)
        """
        try:
            # 目前仅支持中文翻译，后续可扩展
            messages = [
                SystemMessage(content=TRANSLATE_PROMPT),
                HumanMessage(content=text),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"
    
    async def deep_analyze_paper(self, text: str) -> AsyncGenerator[str, None]:
        """6维度深度分析论文，流式返回结构化分析结果"""
        try:
            # 文本预处理：清理多余空白
            text = ' '.join(text.split())
            
            # 检查文本长度
            if len(text) < 50:
                yield "[错误: 论文内容过短，无法进行深度分析。请确保上传的论文包含足够的文本内容。]"
                return
            
            # 限制文本长度防止超出 token 限制（约 80000 字符）
            MAX_TEXT_LENGTH = 80000
            if len(text) > MAX_TEXT_LENGTH:
                text = text[:MAX_TEXT_LENGTH] + "\n\n[内容已截断...]"
            
            messages = [
                SystemMessage(content=DEEP_ANALYZE_PROMPT),
                HumanMessage(content=text),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def compare_papers(self, papers_text: list[dict]) -> AsyncGenerator[str, None]:
        """多论文对比分析
        papers_text: [{"title": "论文标题", "text": "论文全文或摘要"}, ...]
        """
        try:
            # 构建论文内容文本
            papers_content = []
            for i, paper in enumerate(papers_text, 1):
                papers_content.append(f"【论文 {i}】{paper['title']}\n{paper['text']}\n")
            
            full_content = "\n".join(papers_content)
            
            messages = [
                SystemMessage(content=COMPARE_PAPERS_PROMPT),
                HumanMessage(content=f"请对以下论文进行对比分析：\n\n{full_content}"),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def generate_review(self, papers_text: list[dict]) -> AsyncGenerator[str, None]:
        """生成结构化文献综述
        papers_text: [{"title": "论文标题", "text": "论文全文或摘要"}, ...]
        """
        try:
            # 构建论文内容文本
            papers_content = []
            for i, paper in enumerate(papers_text, 1):
                papers_content.append(f"【论文 {i}】{paper['title']}\n{paper['text']}\n")
            
            full_content = "\n".join(papers_content)
            
            messages = [
                SystemMessage(content=GENERATE_REVIEW_PROMPT),
                HumanMessage(content=f"请基于以下论文生成文献综述：\n\n{full_content}"),
            ]
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"


    async def generate_outline(self, topic: str, paper_ids: list[int] = None, requirements: str = "", reference_papers: list[dict] = None) -> AsyncGenerator[str, None]:
        """生成论文大纲
        
        Args:
            topic: 研究主题
            paper_ids: 参考论文ID列表（可选）
            requirements: 额外要求（可选）
            reference_papers: 参考论文信息列表，包含title和abstract（可选）
            
        Yields:
            流式生成的大纲内容
        """
        try:
            # 构建参考论文上下文
            reference_context = ""
            if reference_papers:
                reference_context = "\n\n参考论文信息：\n"
                for i, paper in enumerate(reference_papers, 1):
                    reference_context += f"\n【论文{i}】{paper.get('title', '未命名')}\n"
                    if paper.get('abstract'):
                        reference_context += f"摘要：{paper['abstract'][:500]}...\n"
            
            # 构建额外要求
            requirements_text = ""
            if requirements:
                requirements_text = f"\n\n额外要求：{requirements}"
            
            # 构建提示词
            prompt = GENERATE_OUTLINE_PROMPT.format(
                topic=topic,
                reference_context=reference_context,
                requirements=requirements_text
            )
            
            messages = [
                SystemMessage(content="你是专业的学术写作助手，擅长生成结构清晰的论文大纲。"),
                HumanMessage(content=prompt),
            ]
            
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def generate_draft(self, outline_section: str, context: str = "", style: str = "academic") -> AsyncGenerator[str, None]:
        """生成段落初稿
        
        Args:
            outline_section: 大纲节点文本
            context: 参考内容/上下文（可选）
            style: 写作风格（academic/formal/concise）
            
        Yields:
            流式生成的段落内容
        """
        try:
            # 构建上下文文本
            context_text = ""
            if context:
                context_text = f"\n参考内容：\n{context[:3000]}"
            
            # 风格映射
            style_map = {
                "academic": "学术风格（严谨、专业、客观）",
                "formal": "正式风格（规范、礼貌、清晰）",
                "concise": "简洁风格（精炼、直接、高效）"
            }
            style_desc = style_map.get(style, style_map["academic"])
            
            # 构建提示词
            prompt = GENERATE_DRAFT_PROMPT.format(
                outline_section=outline_section,
                context=context_text,
                style=style_desc
            )
            
            messages = [
                SystemMessage(content="你是专业的学术写作助手，擅长撰写高质量的学术段落。"),
                HumanMessage(content=prompt),
            ]
            
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def polish_text(self, text: str, polish_type: str = "academic") -> AsyncGenerator[str, None]:
        """学术润色
        
        Args:
            text: 待润色的文本
            polish_type: 润色类型（academic/grammar/fluency/concise）
            
        Yields:
            流式生成的润色结果
        """
        try:
            # 类型映射
            type_map = {
                "academic": "学术表达优化",
                "grammar": "语法修正",
                "fluency": "流畅性提升",
                "concise": "精简表达"
            }
            type_desc = type_map.get(polish_type, type_map["academic"])
            
            # 构建提示词
            prompt = POLISH_TEXT_PROMPT.format(
                text=text,
                polish_type=type_desc
            )
            
            messages = [
                SystemMessage(content="你是专业的学术文本润色专家，擅长提升文本质量。"),
                HumanMessage(content=prompt),
            ]
            
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def generate_citation(self, paper_info: dict, format: str = "apa") -> str:
        """生成引用格式（非流式，直接返回）
        
        Args:
            paper_info: 论文信息字典，包含title, authors, year, journal等
            format: 引用格式（apa/mla/chicago/gbt7714）
            
        Returns:
            格式化后的引用字符串
        """
        format = format.lower()
        
        # 使用规则模板直接生成（不依赖LLM，更高效）
        if format in CITATION_FORMAT_TEMPLATES:
            template = CITATION_FORMAT_TEMPLATES[format]
            
            # 提取信息
            title = paper_info.get('title', '未命名论文')
            authors = paper_info.get('authors', '未知作者')
            year = paper_info.get('year', paper_info.get('published_year', 'n.d.'))
            journal = paper_info.get('journal', paper_info.get('publisher', ''))
            index = paper_info.get('index', '')
            
            # 格式化作者
            if authors and authors != '未知作者':
                # 简单处理：如果作者太多，只显示前3个
                author_list = authors.split(',') if ',' in authors else [authors]
                if len(author_list) > 3:
                    if format == 'apa':
                        authors = f"{author_list[0].strip()} et al."
                    else:
                        authors = f"{author_list[0].strip()} 等"
            
            # 构建引用
            citation = template.format(
                authors=authors,
                title=title,
                year=year,
                journal_or_publisher=journal or '未知来源',
                index=index
            )
            
            return citation
        else:
            # 不支持的格式，使用LLM生成
            prompt = f"""请将以下论文信息转换为{format}格式的引用：

论文标题：{paper_info.get('title', '')}
作者：{paper_info.get('authors', '')}
年份：{paper_info.get('year', paper_info.get('published_year', ''))}
期刊/出版社：{paper_info.get('journal', paper_info.get('publisher', ''))}

请只输出引用格式，不要其他内容。"""
            
            messages = [
                SystemMessage(content=CITATION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()


    async def extract_keywords(self, text: str, title: str = "", max_keywords: int = 5) -> list:
        """从论文文本中提取关键词
        
        Args:
            text: 论文文本内容
            title: 论文标题
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        prompt = f"""请从以下学术论文内容中提取最重要的3-5个关键词。

【重要指示 - 必须严格遵守】
1. 无论论文内容长短，都必须尽力提取关键词
2. 严禁说"无法提取"、"内容不足"或任何类似的拒绝性表述
3. 即使内容有限，也必须基于已有信息提取最相关的关键词
4. 如果内容不足，基于标题和已有文本进行合理推断

论文标题：{title}

论文内容：
{text[:2000]}

要求：
1. 每行一个关键词，不要编号
2. 关键词应准确概括论文核心研究主题
3. 优先提取专业术语和方法名称
4. 避免通用词汇如"研究"、"方法"、"分析"
5. 只返回关键词，不要其他内容"""

        messages = [
            SystemMessage(content="你是学术关键词提取专家。只返回关键词列表，每行一个。"),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            keywords = [kw.strip().lstrip('0123456789.-•· ') for kw in response.content.strip().split('\n') if kw.strip()]
            keywords = [kw for kw in keywords if kw and len(kw) > 1]
            return keywords[:max_keywords]
        except Exception as e:
            print(f"关键词提取失败: {e}")
            return []


# 全局单例
llm_service = LLMService()
