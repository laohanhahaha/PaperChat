"""LLM 服务 - 基于 LangChain 的 DeepSeek 大模型交互"""
import logging
import time
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory

from app.config import settings
from app.services.llm.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_WITH_SEARCH_SYSTEM_PROMPT,
    CROSS_DOC_CHAT_SYSTEM_PROMPT,
    EXPLAIN_TERM_PROMPT,
    SUMMARIZE_PROMPT,
    TRANSLATE_PROMPT,
    DEEP_ANALYZE_PROMPT,
    COMPARE_PAPERS_PROMPT,
    GENERATE_REVIEW_PROMPT,
    GENERATE_OUTLINE_PROMPT,
    GENERATE_DRAFT_PROMPT,
    POLISH_TEXT_PROMPT,
    CITATION_FORMAT_TEMPLATES,
    CITATION_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


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
            
            # 上下文压缩（L1 剩枝 + 必要时 L2 摘要）
            from app.services.context_compressor import context_compressor
            messages = await context_compressor.process(messages)

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
        relevant_chunks: list[dict], 
        chat_history: ChatMessageHistory, 
        user_id: int = None,
        db = None
    ) -> AsyncGenerator[str, None]:
        """基于 RAG 的智能问答，流式返回回答
        
        接收由 handler 层传入的检索结果，完成 LLM 调用
        支持记忆上下文增强
        
        Args:
            message: 用户问题
            relevant_chunks: RAG 检索结果列表，每项含 text/pages/score
            chat_history: 对话历史
            user_id: 用户 ID（用于记忆召回）
            db: 数据库会话（用于记忆召回）
            
        Yields:
            流式回答文本
        """
        try:
            from app.services.memory_middleware import enrich_context_with_memory
            
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
                    logger.warning(f"记忆召回失败（非阻塞）: {e}")
            
            # 4. 构建系统消息（使用精准上下文 + 记忆上下文）
            system_content = RAG_CHAT_SYSTEM_PROMPT.format(context=context)
            if memory_context:
                system_content += f"\n\n{memory_context}"
            
            messages = [SystemMessage(content=system_content)]
            
            # 添加历史对话
            messages.extend(chat_history.messages)
            
            # 添加当前用户消息
            messages.append(HumanMessage(content=message))
            
            # 上下文压缩（L1 剩枝 + 必要时 L2 摘要）
            from app.services.context_compressor import context_compressor
            messages = await context_compressor.process(messages)

            # 5. 流式获取回复
            start_time = time.time()
            full_response = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            
            duration_ms = round((time.time() - start_time) * 1000)
            logger.info("LLM chat_with_rag completed", extra={"duration_ms": duration_ms, "response_len": len(full_response)})
            
            # 6. 保存到历史记录
            chat_history.add_user_message(message)
            chat_history.add_ai_message(full_response)
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]"

    async def chat_cross_doc(self, message: str, relevant_chunks: list[dict], chat_history: ChatMessageHistory = None) -> AsyncGenerator[str, None]:
        """跨文档 RAG 问答，流式返回回答
        
        接收由 handler 层传入的跨文档检索结果，完成 LLM 调用
        
        Args:
            message: 用户问题
            relevant_chunks: 跨文档 RAG 检索结果列表，每项含 text/pages/paper_id/score
            chat_history: 对话历史（可选）
            
        Yields:
            流式回答文本
        """
        try:
            if not relevant_chunks:
                yield "抱歉，未能从论文中检索到相关内容。请尝试重新表述问题，或检查论文是否已完成索引。"
                return
            
            # 2. 按论文分组组装上下文，标注来源论文
            context_parts = []
            for r in relevant_chunks:
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
            
            # 上下文压缩（L1 剩枝 + 必要时 L2 摘要）
            from app.services.context_compressor import context_compressor
            messages = await context_compressor.process(messages)

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
    
    async def chat_with_rag_and_sources(self, message: str, relevant_chunks: list[dict], chat_history: ChatMessageHistory):
        """基于 RAG 的智能问答，返回回答和引用来源
        
        非流式版本，适合需要获取引用来源的场景
        接收由 handler 层传入的检索结果
        
        Args:
            message: 用户问题
            relevant_chunks: RAG 检索结果列表，每项含 text/pages/score
            chat_history: 对话历史
            
        Returns:
            dict: 包含 answer 和 sources 的字典
        """
        
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
            logger.error("关键词提取失败", exc_info=True)
            return []


# 全局单例
llm_service = LLMService()
