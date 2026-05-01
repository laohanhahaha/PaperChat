"""论文查询与提纲工具集 — 查询最近论文、搜索论文、生成提纲

工具列表：
- RecentPapersTool: 按上传时间倒序查询论文列表（无 LLM，快速）
- SearchPapersTool: 按关键词搜索论文（LLM 提取关键词 + 本地搜索 + 联网降级）
- GenerateOutlineTool: 用 LLM 生成研究报告或文献综述提纲（约 1 次 LLM 调用）
"""
import asyncio
import json
import logging
import re

from langchain_core.messages import SystemMessage, HumanMessage

from app.tools.base import Tool, ToolContext, ToolResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class RecentPapersTool(Tool):
    """查询最近论文"""
    name = "recent_papers"
    description = "查询最近上传的论文列表"
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10, "description": "返回论文数量"}
        },
        "required": []
    }

    async def execute(self, ctx: ToolContext, limit: int = 10, **kwargs) -> ToolResult:
        """查询 Paper 表，按上传时间倒序"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        from sqlalchemy import select
        from app.models.paper import Paper

        query = select(Paper)
        if ctx.user_id:
            query = query.where(Paper.user_id == ctx.user_id)
        query = query.order_by(Paper.created_at.desc()).limit(limit)

        result = await db.execute(query)
        papers = result.scalars().all()

        paper_list = []
        for p in papers:
            paper_list.append({
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "category": p.category,
                "reading_status": p.reading_status,
                "page_count": p.page_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return ToolResult(data={
            "papers": paper_list,
            "count": len(paper_list),
            "type": "papers"
        })


class SearchPapersTool(Tool):
    """搜索论文（LLM 关键词提取 + 本地搜索 + 联网降级）"""
    name = "search_papers"
    description = "按关键词搜索论文，支持智能关键词提取和联网搜索降级"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "top_k": {"type": "integer", "default": 10, "description": "返回结果数量"}
        },
        "required": ["query"]
    }

    # ------------------------------------------------------------------ #
    #  主入口
    # ------------------------------------------------------------------ #

    async def execute(self, ctx: ToolContext, query: str, top_k: int = 10, **kwargs) -> ToolResult:
        """搜索论文：LLM 提取关键词 → 本地搜索(相关性过滤) → 联网补充 → 去重合并"""
        db = ctx.db
        if db is None:
            return ToolResult(success=False, error="需要提供数据库会话")

        if not query:
            return ToolResult(success=False, error="需要提供搜索关键词")

        chat_history = kwargs.get("chat_history", "")
        mcp_manager = kwargs.get("mcp_manager", None)
        logger.info(f"[SearchPapersTool] execute called: query={query!r}, mcp_manager={type(mcp_manager).__name__ if mcp_manager else None}, has_clients={bool(mcp_manager._clients) if mcp_manager and hasattr(mcp_manager, '_clients') else 'N/A'}")

        # 1. LLM 提取关键词（强制英文）
        keywords = await self._extract_search_keywords(query, chat_history)
        logger.info(f"搜索关键词提取: {keywords}")

        # 2. 本地数据库搜索（多关键词 OR 匹配 + 原始查询直接匹配）
        local_results = await self._search_local(db, ctx.user_id, keywords, top_k, raw_query=query)

        # 3. 对本地结果进行相关性过滤
        relevant_local = self._filter_by_relevance(local_results, keywords)
        logger.info(f"[SearchPapersTool] 本地结果: {len(local_results)}, 相关结果: {len(relevant_local)}")

        # 4. 联网搜索逻辑
        enable_web_search = getattr(ctx, 'enable_search', False) and mcp_manager is not None
        if enable_web_search:
            # 强制联网搜索，无论本地结果多少
            logger.info(f"[SearchPapersTool] 联网搜索已启用，强制联网搜索，keywords={keywords}")
            online_results = await self._search_online(keywords, mcp_manager)
            # 合并本地+联网结果，去重
            all_results = self._merge_and_deduplicate(relevant_local, online_results)
            source = "local+web" if relevant_local and online_results else ("web" if online_results else "local")
            if all_results:
                return ToolResult(data={
                    "papers": all_results[:top_k],
                    "count": len(all_results[:top_k]),
                    "query": query,
                    "keywords": keywords,
                    "source": source,
                    "type": "papers",
                })
        elif relevant_local:
            logger.info(f"[SearchPapersTool] 用户未开启联网搜索，仅返回本地结果")
            return ToolResult(data={
                "papers": relevant_local[:top_k],
                "count": len(relevant_local[:top_k]),
                "query": query,
                "keywords": keywords,
                "source": "local",
                "type": "papers",
            })

        # 5. 完全无结果
        return ToolResult(data={
            "papers": [],
            "count": 0,
            "query": query,
            "keywords": keywords,
            "source": "none",
            "message": f"未找到与 {', '.join(keywords)} 相关的论文",
            "type": "papers",
        })

    # ------------------------------------------------------------------ #
    #  LLM 关键词提取
    # ------------------------------------------------------------------ #

    async def _extract_search_keywords(self, query: str, chat_history: str = "") -> list[str]:
        """使用 LLM 从用户消息和对话历史中提取英文学术搜索关键词"""
        prompt = f"""Extract 3-5 English academic search keywords from the user's query and conversation history.
Rules:
- Keywords MUST be in English only (for arXiv/Google Scholar search)
- Focus on academic terms, paper titles, method names, research topics
- Do NOT include any Chinese words or characters
- If the user uses pronouns like "这样的" or "类似的", infer the specific research topic from conversation history
- Return as comma-separated list, nothing else

Conversation history:
{chat_history[-2000:] if chat_history else 'None'}

User query: {query}
Keywords:"""

        try:
            messages = [
                SystemMessage(content="You are an expert at extracting academic search keywords. Output ONLY English keywords separated by commas. Never output Chinese."),
                HumanMessage(content=prompt),
            ]
            response = await asyncio.wait_for(
                llm_service.llm.ainvoke(messages),
                timeout=5.0,
            )
            raw = response.content.strip()
            keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
            # 过滤掉可能残留的中文关键词
            keywords = [kw for kw in keywords if not re.search(r'[\u4e00-\u9fff]', kw)]
            return keywords[:5] if keywords else self._fallback_extract_keywords(query)
        except Exception as e:
            logger.warning(f"LLM 关键词提取失败: {e}")
            return self._fallback_extract_keywords(query)

    def _fallback_extract_keywords(self, query: str) -> list[str]:
        """回退关键词提取：仅提取英文单词（用于学术搜索引擎）"""
        # 提取英文单词（2 个字符以上，保留 AI、NLP 等缩写）
        en_words = re.findall(r'[a-zA-Z]{2,}', query)
        # 过滤常见停用词
        stop_en = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was",
            "have", "has", "had", "not", "but", "can", "will", "about", "some",
            "what", "how", "which", "their", "there", "been", "would", "could",
        }
        en_words = [w for w in en_words if w.lower() not in stop_en]
        return en_words if en_words else [query]  # 兜底：直接用原始 query

    # ------------------------------------------------------------------ #
    #  相关性评分与去重
    # ------------------------------------------------------------------ #

    def _filter_by_relevance(self, papers: list, keywords: list[str]) -> list:
        """基于关键词匹配度过滤论文，返回有相关性的论文（按得分排序）"""
        scored_papers = []
        keywords_lower = [kw.lower() for kw in keywords]

        for paper in papers:
            title = (paper.get("title", "") or "").lower()
            abstract = (paper.get("abstract", "") or "").lower()
            score = 0
            for kw in keywords_lower:
                # 支持多词关键词（如 "transformer variants"）
                kw_parts = kw.split()
                for part in kw_parts:
                    if part in title:
                        score += 3  # 标题匹配权重高
                    if part in abstract:
                        score += 1  # 摘要匹配
                # 完整短语匹配额外加分
                if len(kw_parts) > 1 and kw in title:
                    score += 5
                if len(kw_parts) > 1 and kw in abstract:
                    score += 2
            if score > 0:
                paper["_relevance_score"] = score
                scored_papers.append(paper)

        # 按相关性排序
        scored_papers.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)
        return scored_papers

    def _merge_and_deduplicate(self, local: list, online: list) -> list:
        """合并本地和联网结果，按标题去重（跳过无效条目）"""
        seen_titles = set()
        merged = []

        # 本地结果优先
        for paper in local + online:
            if not isinstance(paper, dict) or not paper.get("title"):
                continue
            title = (paper.get("title", "") or "").strip().lower()
            # 标题去重（忽略末尾标点）
            title_clean = title.rstrip(".:;, ")
            if title_clean and title_clean not in seen_titles:
                seen_titles.add(title_clean)
                # 清理内部评分字段
                paper.pop("_relevance_score", None)
                merged.append(paper)

        return merged

    # ------------------------------------------------------------------ #
    #  本地数据库搜索
    # ------------------------------------------------------------------ #

    async def _search_local(self, db, user_id, keywords: list[str], top_k: int, raw_query: str = "") -> list[dict]:
        """多关键词 OR 匹配搜索本地 Paper 表（title + abstract + tags），无结果时降级到 text_blocks"""
        from sqlalchemy import select, or_
        from app.models.paper import Paper

        # 合并关键词：LLM 提取的关键词 + 原始查询中有意义的片段
        all_search_terms = list(keywords)
        if raw_query and raw_query not in all_search_terms:
            all_search_terms.append(raw_query)

        conditions = []
        for kw in all_search_terms:
            pattern = f"%{kw}%"
            conditions.append(Paper.title.ilike(pattern))
            conditions.append(Paper.abstract.ilike(pattern))
            conditions.append(Paper.tags.ilike(pattern))

        if not conditions:
            return []

        sql_query = select(Paper).where(or_(*conditions))
        if user_id:
            sql_query = sql_query.where(Paper.user_id == user_id)
        sql_query = sql_query.order_by(Paper.created_at.desc()).limit(top_k)

        result = await db.execute(sql_query)
        papers = result.scalars().all()

        # 主表搜索无结果，尝试从 text_blocks 中搜索
        if not papers:
            papers = await self._search_text_blocks(db, user_id, all_search_terms, top_k)

        paper_list = []
        for p in papers:
            paper_list.append({
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract[:200] + "..." if p.abstract and len(p.abstract) > 200 else p.abstract,
                "category": p.category,
                "reading_status": p.reading_status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "source": "local",
            })
        return paper_list

    async def _search_text_blocks(self, db, user_id, keywords: list[str], top_k: int) -> list:
        """从 text_blocks 表中搜索论文（降级搜索）"""
        from sqlalchemy import select, or_
        from app.models.paper import Paper, PaperTextBlock

        text_conditions = []
        for kw in keywords:
            text_conditions.append(PaperTextBlock.text.ilike(f"%{kw}%"))

        if not text_conditions:
            return []

        try:
            sql_query = (
                select(Paper)
                .join(PaperTextBlock, Paper.id == PaperTextBlock.paper_id)
                .where(or_(*text_conditions))
            )
            if user_id:
                sql_query = sql_query.where(Paper.user_id == user_id)
            sql_query = sql_query.distinct().order_by(Paper.created_at.desc()).limit(top_k)

            result = await db.execute(sql_query)
            return result.scalars().all()
        except Exception as e:
            logger.warning(f"text_blocks 搜索失败: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  联网搜索降级
    # ------------------------------------------------------------------ #

    async def _search_online(self, keywords: list[str], mcp_manager) -> list[dict]:
        """多源并行搜索，汇总所有可用源的结果（带 45s 总超时保护）"""
        try:
            return await asyncio.wait_for(
                self._search_online_impl(keywords, mcp_manager),
                timeout=45.0,  # 多源并行总超时（单源最长20s）
            )
        except asyncio.TimeoutError:
            logger.warning("[SearchPapersTool] 联网搜索总超时")
            return []
        except Exception as e:
            logger.warning(f"[SearchPapersTool] 联网搜索异常: {e}")
            return []
    
    # 构建查询时需要过滤的停用词
    _STOP_WORDS = {
        'the', 'a', 'an', 'of', 'in', 'on', 'for', 'with', 'and', 'or',
        'to', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'that', 'this', 'these', 'those', 'it', 'its', 'at', 'as',
        'into', 'about', 'between', 'through', 'during', 'before', 'after',
        'above', 'below', 'up', 'down', 'over', 'under', 'again', 'further',
        'then', 'once', 'using', 'based', 'via', 'towards', 'toward',
        'have', 'has', 'had', 'more', 'also', 'than', 'such', 'very',
        'their', 'each', 'which', 'other', 'some', 'what', 'when', 'where',
        'will', 'does', 'only', 'most', 'both', 'same', 'while',
        'paper', 'approach', 'method', 'proposed', 'recent', 'novel',
    }

    # 纯数字年份正则：匹配 2000-2099 的纯数字字符串
    _YEAR_PATTERN = re.compile(r'^\d{4}$')
    
    @classmethod
    def _is_stopword_or_year(cls, kw: str) -> bool:
        """判断单个关键词是否应被过滤：单词停用词 或 纯数字年份"""
        stripped = kw.strip().lower()
        # 纯数字年份（如 2023, 2024）不应作为 ti/abs 搜索词
        if cls._YEAR_PATTERN.match(stripped):
            return True
        # 单个词且为停用词
        words = stripped.split()
        if len(words) == 1 and stripped in cls._STOP_WORDS:
            return True
        return False
    
    @classmethod
    def _build_arxiv_query(cls, keywords: list[str]) -> str:
        """构建 arXiv 搜索查询，保持短语完整性。
    
        策略（核心 AND 辅助 OR）：
        - 第1个关键词为核心必选项
        - 第2-5个关键词之间用 OR 连接作为辅助
        - 核心 AND 辅助 的结构，确保结果必须包含核心主题
        - 仅1个关键词时直接返回，不加 AND
        - 过滤后关键词不足2个时，只用 OR 连接，不加 AND 约束
    
        过滤规则：
        - 跳过单个停用词（如 of, the, in 等）
        - 跳过纯数字年份（如 2023, 2024）
    
        短语处理：
        - 短短语（1-3词）：直接用双引号包裹
        - 长短语（4+词）：提取核心实义词（去停用词），取前3个组成短语
        - 同时搜标题和摘要：(ti:"phrase" OR abs:"phrase")
    
        示例:
            ['Large Language Model', 'LLM', 'language model', 'transformer', 'NLP']
            → (ti:"large language model" OR abs:"large language model") AND
              ((ti:"llm" OR abs:"llm") OR (ti:"language model" OR abs:"language model") OR
               (ti:"transformer" OR abs:"transformer") OR (ti:"nlp" OR abs:"nlp"))
        """
        if not keywords:
            return ""
    
        # 先过滤掉停用词和年份
        filtered_keywords = [kw for kw in keywords if not cls._is_stopword_or_year(kw)]
        if not filtered_keywords:
            # 所有关键词都被过滤了，降级使用原始列表中最长的关键词
            filtered_keywords = sorted(keywords, key=len, reverse=True)[:1]
        logger.debug(f"[SearchPapersTool] 关键词过滤: {keywords} -> {filtered_keywords}")
    
        def _kw_to_part(kw: str) -> str | None:
            phrase = kw.strip().lower()
            words = phrase.split()
            if not words:
                return None
            if len(words) <= 3:
                quoted = f'"{phrase}"'
            else:
                meaningful = [w for w in words if w not in cls._STOP_WORDS and len(w) > 1]
                if len(meaningful) > 3:
                    short_phrase = " ".join(meaningful[:3])
                else:
                    short_phrase = " ".join(meaningful) if meaningful else phrase
                quoted = f'"{short_phrase}"'
            return f'(ti:{quoted} OR abs:{quoted})'
    
        parts = [p for kw in filtered_keywords[:5] if (p := _kw_to_part(kw)) is not None]
        if not parts:
            return ""
    
        if len(parts) == 1:
            arxiv_query = parts[0]
        elif len(parts) == 2:
            # 只剩2个关键词时，放宽为 OR 连接，避免过于严格
            arxiv_query = " OR ".join(parts)
        else:
            core = parts[0]
            auxiliary = " OR ".join(parts[1:])
            arxiv_query = f"{core} AND ({auxiliary})"
    
        logger.info(f"[SearchPapersTool] arXiv 查询: {arxiv_query}")
        return arxiv_query

    @classmethod
    def _build_text_query(cls, keywords: list[str], max_words: int = 5) -> str:
        """为 Google Scholar / Semantic Scholar 构建文本查询，保持短语完整性。"""
        phrases = []
        for kw in keywords[:3]:  # 最多3个关键词
            phrase = kw.strip()
            words = phrase.split()
            if len(words) >= 2:
                phrases.append(f'"{phrase}"')
            else:
                phrases.append(phrase)
        return " ".join(phrases) if phrases else " ".join(keywords[:3])
    
    async def _search_online_impl(self, keywords: list[str], mcp_manager) -> list[dict]:
        """多源并行搜索，汇总所有可用源的结果"""
        all_papers = []
        text_query = self._build_text_query(keywords, max_words=5)
        arxiv_query = self._build_arxiv_query(keywords)
    
        # 定义搜索任务: (searcher名, 查询字符串, max_results, 超时秒数)
        search_tasks = [
            ("arxiv", arxiv_query or text_query, 10, 10.0),       # arXiv 响应快，保持10s
            ("google_scholar", text_query, 10, 20.0),             # Google Scholar 需要更长超时
            ("semantic", text_query, 10, 20.0),                   # Semantic Scholar 需要更长超时
        ]
    
        async def _search_single(searcher: str, query: str, max_results: int, timeout: float = 10.0) -> list[dict]:
            try:
                raw = await asyncio.wait_for(
                    mcp_manager.call_tool(
                        server_name="academic_mcp",
                        tool_name="paper_search",
                        arguments={"query_list": [{"searcher": searcher, "query": query, "max_results": max_results}]},
                    ),
                    timeout=timeout,
                )
                papers = self._parse_academic_mcp_result(raw)
                logger.info(f"[SearchPapersTool] {searcher} 返回 {len(papers)} 篇论文")
                return papers
            except asyncio.TimeoutError:
                logger.warning(f"[SearchPapersTool] {searcher} 搜索超时({timeout}s)")
                return []
            except Exception as e:
                logger.warning(f"[SearchPapersTool] {searcher} 搜索失败: {e}")
                return []
    
        # 并发执行所有学术搜索源
        results = await asyncio.gather(*[
            _search_single(s, q, m, t) for s, q, m, t in search_tasks
        ])
    
        for papers in results:
            all_papers.extend(papers)
    
        # 也尝试 open_websearch 补充
        try:
            web_raw = await asyncio.wait_for(
                mcp_manager.call_tool(
                    server_name="open_websearch",
                    tool_name="search",
                    arguments={"query": text_query + " research paper", "limit": 5},
                ),
                timeout=8.0,
            )
            web_papers = self._parse_websearch_result(web_raw)
            all_papers.extend(web_papers)
            logger.info(f"[SearchPapersTool] open_websearch 返回 {len(web_papers)} 条结果")
        except Exception as e:
            logger.warning(f"[SearchPapersTool] open_websearch 搜索失败: {e}")
    
        # 去重（跳过 None 或非 dict 的无效条目）
        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            if not isinstance(p, dict):
                continue
            title = (p.get("title", "") or "").strip().lower().rstrip(".:;, ")
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_papers.append(p)
    
        logger.info(f"[SearchPapersTool] 多源搜索汇总: 总计 {len(all_papers)} 篇, 去重后 {len(unique_papers)} 篇")
        return unique_papers

    # ------------------------------------------------------------------ #
    #  结果解析
    # ------------------------------------------------------------------ #

    def _parse_academic_mcp_result(self, raw) -> list[dict]:
        """解析 academic-mcp paper_search 返回的文本格式结果"""
        if raw is None:
            return []

        # 如果是列表/字典等非字符串类型，尝试安全转换
        try:
            text = raw if isinstance(raw, str) else str(raw)
        except Exception:
            return []
        if text.strip() == "No papers found.":
            return []

        papers = []
        # paper_search 返回的格式是多段文本，每段之间用两个换行分隔
        blocks = text.split("\n\n")
        for block in blocks:
            if not block.strip():
                continue
            paper = {"source": "web"}
            for line in block.strip().split("\n"):
                line = line.strip()
                if line.startswith("Source:"):
                    paper["source"] = line.split(":", 1)[1].strip().strip("'")
                elif line.startswith("Title:"):
                    paper["title"] = line.split(":", 1)[1].strip()
                elif line.startswith("Authors:"):
                    paper["authors"] = line.split(":", 1)[1].strip()
                elif line.startswith("Abstract:"):
                    abstract = line.split(":", 1)[1].strip()
                    paper["abstract"] = abstract[:200] + "..." if len(abstract) > 200 else abstract
                elif line.startswith("Published Date:"):
                    date_str = line.split(":", 1)[1].strip()
                    # 尝试提取年份
                    year_match = re.search(r'(\d{4})', date_str)
                    if year_match:
                        paper["year"] = year_match.group(1)
                elif line.startswith("URL:"):
                    paper["url"] = line.split("URL:", 1)[1].strip()
                elif line.startswith("DOI:"):
                    paper["doi"] = line.split("DOI:", 1)[1].strip()
            # 映射 source 为前端期望的显示名称
            _SOURCE_DISPLAY_MAP = {
                "arxiv": "arXiv",
                "google_scholar": "Google Scholar",
                "semantic": "Semantic Scholar",
            }
            paper["source"] = _SOURCE_DISPLAY_MAP.get(paper["source"], paper["source"])
            if paper.get("title"):
                papers.append(paper)
        return papers

    def _parse_websearch_result(self, raw) -> list[dict]:
        """解析 open-webSearch 返回的 JSON 结果"""
        if raw is None:
            return []

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return []

        if not isinstance(data, dict):
            return []

        results_list = data.get("results", [])
        if not isinstance(results_list, list):
            return []

        papers = []
        for r in results_list:
            if not isinstance(r, dict):
                continue
            title = r.get("title") or "未知标题"
            papers.append({
                "title": title,
                "authors": "",
                "year": "",
                "url": r.get("url", ""),
                "abstract": r.get("description", ""),
                "source": "Web",
            })
        return papers


class GenerateOutlineTool(Tool):
    """生成提纲"""
    name = "generate_outline"
    description = "基于论文内容生成研究报告或文献综述的提纲"
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "报告主题"},
            "context": {"type": "string", "description": "相关上下文内容（可选）"},
            "paper_ids": {"type": "array", "items": {"type": "integer"}, "description": "相关论文ID列表（可选）"}
        },
        "required": ["topic"]
    }

    async def execute(self, ctx: ToolContext, topic: str, context: str = "", paper_ids: list[int] = None, **kwargs) -> ToolResult:
        """使用 LLM 生成提纲"""
        # 优先使用传入的paper_ids，否则从ctx获取
        pids = paper_ids if paper_ids is not None else ctx.paper_ids

        prompt = f"""请为以下主题生成一份详细的研究报告提纲：

主题：{topic}

{f"相关论文内容：\n{context[:5000]}" if context else ""}

要求：
1. 提纲结构清晰，层级分明
2. 包含引言、主体章节、结论
3. 每个章节提供简要说明
4. 适合作为研究报告或文献综述的框架

请直接输出提纲内容。"""

        messages = [
            SystemMessage(content="你是学术研究专家，擅长构建清晰的研究报告结构。"),
            HumanMessage(content=prompt)
        ]

        response = await llm_service.llm.ainvoke(messages)

        return ToolResult(data={
            "topic": topic,
            "outline": response.content,
            "paper_count": len(pids) if pids else 0
        })
