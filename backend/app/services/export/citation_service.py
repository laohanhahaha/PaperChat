"""引用管理服务

从数据库提取论文元数据，生成 BibTeX / APA / GB/T 7714 格式引用。
纯字符串模板生成，零 LLM 调用，单条 <1ms。
"""
import re
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_analysis import PaperAnalysisCache


class CitationService:
    """引用格式生成服务"""

    # ------------------------------------------------------------------
    # 元数据提取
    # ------------------------------------------------------------------

    async def extract_metadata(self, paper_id: int, db: AsyncSession) -> dict:
        """从数据库提取引用元数据

        返回:
            {
                "title": str,
                "authors": list[str],
                "year": int | None,
                "venue": str,
                "doi": str,
                "abstract": str,
                "paper_type": str  # article / inproceedings / misc
            }
        """
        result = await db.execute(
            select(Paper).where(Paper.id == paper_id)
        )
        paper = result.scalar_one_or_none()
        if paper is None:
            raise ValueError(f"Paper {paper_id} not found")

        # 基础字段
        title = paper.title or ""
        authors_raw = paper.authors or ""
        doi = paper.doi or ""
        abstract = paper.abstract or ""

        # 解析作者列表：支持逗号 / 分号 / "and" 分隔
        authors = self._parse_authors(authors_raw)

        # 年份：Paper 模型无 year 字段，从 created_at 推导
        year: Optional[int] = None
        if paper.created_at is not None:
            year = paper.created_at.year

        # venue & paper_type：尝试从分析缓存提取
        venue = ""
        paper_type = "article"
        try:
            cache_result = await db.execute(
                select(PaperAnalysisCache).where(
                    PaperAnalysisCache.paper_id == paper_id
                )
            )
            cache = cache_result.scalar_one_or_none()
            if cache and cache.section_analysis:
                # 尝试从 section_analysis JSON 中提取 venue / paper_type
                import json
                try:
                    section_data = json.loads(cache.section_analysis)
                    if isinstance(section_data, dict):
                        venue = section_data.get("venue", "")
                        pt = section_data.get("paper_type", "")
                        if pt in ("article", "inproceedings", "misc"):
                            paper_type = pt
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "doi": doi,
            "abstract": abstract,
            "paper_type": paper_type,
        }

    # ------------------------------------------------------------------
    # BibTeX
    # ------------------------------------------------------------------

    def generate_bibtex(self, metadata: dict) -> str:
        """生成 BibTeX 条目

        citation key 规则: 第一作者姓 + 年份 + 标题首词
        """
        authors = metadata.get("authors", [])
        year = metadata.get("year", "")
        title = metadata.get("title", "Untitled")
        venue = metadata.get("venue", "")
        doi = metadata.get("doi", "")
        paper_type = metadata.get("paper_type", "article")

        # citation key
        first_lastname = self._extract_lastname(authors[0]) if authors else "unknown"
        first_title_word = self._first_alpha_word(title)
        key = f"{first_lowercase(first_lastname)}{year}{first_title_word}"
        # 清理 key 中的特殊字符
        key = re.sub(r"[^a-zA-Z0-9_]", "", key)

        # 选择 entry type
        entry_type = {
            "article": "article",
            "inproceedings": "inproceedings",
        }.get(paper_type, "misc")

        lines = [f"@{entry_type}{{{key},"]
        lines.append(f"    title = {{{title}}},")
        if authors:
            author_str = " and ".join(authors)
            lines.append(f"    author = {{{author_str}}},")
        if year:
            lines.append(f"    year = {{{year}}},")
        if venue:
            field = "journal" if entry_type == "article" else "booktitle"
            lines.append(f"    {field} = {{{venue}}},")
        if doi:
            lines.append(f"    doi = {{{doi}}},")
        lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # APA
    # ------------------------------------------------------------------

    def generate_apa(self, metadata: dict) -> str:
        """生成 APA 7th 格式引用

        Author1, A. A., Author2, B. B. (Year). Title. Venue. https://doi.org/xxx
        """
        authors = metadata.get("authors", [])
        year = metadata.get("year", "")
        title = metadata.get("title", "Untitled")
        venue = metadata.get("venue", "")
        doi = metadata.get("doi", "")

        # 格式化作者: "Last, F." 或 "F. Last"
        formatted = []
        for a in authors:
            formatted.append(self._apa_author(a))
        author_str = self._join_apa_authors(formatted)

        parts = []
        parts.append(author_str)
        if year:
            parts.append(f"({year})")
        parts.append(f"{title}.")
        if venue:
            parts.append(f"*{venue}*.")
        if doi:
            parts.append(f"https://doi.org/{doi}")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # GB/T 7714
    # ------------------------------------------------------------------

    def generate_gbt(self, metadata: dict) -> str:
        """生成 GB/T 7714 格式引用（中国国家标准）

        [序号] 作者. 标题[J]. 期刊, 年, 卷(期): 页码.
        简化版：不含卷期页码（数据库未存储这些字段）
        """
        authors = metadata.get("authors", [])
        year = metadata.get("year", "")
        title = metadata.get("title", "Untitled")
        venue = metadata.get("venue", "")
        doi = metadata.get("doi", "")
        paper_type = metadata.get("paper_type", "article")

        # 作者格式: 姓 名首字母大写（简化处理，保持原始格式）
        if authors:
            author_str = ", ".join(authors)
        else:
            author_str = "佚名"

        # 文献类型标识
        type_code = "J" if paper_type == "article" else "C" if paper_type == "inproceedings" else "Z"

        parts = [f"{author_str}."]
        parts.append(f"{title}[{type_code}].")
        if venue:
            parts.append(f"{venue},")
        if year:
            parts.append(f"{year}.")
        if doi:
            parts.append(f"DOI:{doi}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # 批量导出
    # ------------------------------------------------------------------

    async def batch_export(
        self,
        paper_ids: list[int],
        db: AsyncSession,
        format: str = "bibtex",
    ) -> str:
        """批量导出参考文献列表

        Args:
            paper_ids: 论文 ID 列表
            db: 数据库会话
            format: bibtex | apa | gbt

        Returns:
            合并后的引用文本，条目之间用空行分隔
        """
        entries: list[str] = []
        for paper_id in paper_ids:
            try:
                meta = await self.extract_metadata(paper_id, db)
            except ValueError:
                continue  # 跳过不存在的论文

            if format == "bibtex":
                entries.append(self.generate_bibtex(meta))
            elif format == "apa":
                entries.append(self.generate_apa(meta))
            elif format == "gbt":
                entries.append(self.generate_gbt(meta))
            else:
                entries.append(self.generate_bibtex(meta))

        return "\n\n".join(entries)

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_authors(authors_raw: str) -> list[str]:
        """解析作者字符串为列表，支持逗号/分号/and 分隔"""
        if not authors_raw:
            return []
        # 优先按分号分割（最不歧义）
        if ";" in authors_raw:
            return [a.strip() for a in authors_raw.split(";") if a.strip()]
        # 按 " and " 分割
        if " and " in authors_raw:
            return [a.strip() for a in authors_raw.split(" and ") if a.strip()]
        # 按逗号分割，但注意 "Last, First" 格式
        # 启发式：如果逗号数量 == 元素数-1，可能是 "A, B, C" 列表
        parts = [p.strip() for p in authors_raw.split(",") if p.strip()]
        if len(parts) <= 1:
            return parts
        # 如果看起来像 "Last, First" 对，合并
        merged: list[str] = []
        i = 0
        while i < len(parts):
            # 简单启发式：如果下一个 token 首字母大写且较短，可能是名
            if (
                i + 1 < len(parts)
                and len(parts[i + 1]) <= 3
                and parts[i + 1][0].isupper()
            ):
                merged.append(f"{parts[i]}, {parts[i + 1]}")
                i += 2
            else:
                merged.append(parts[i])
                i += 1
        return merged

    @staticmethod
    def _extract_lastname(author: str) -> str:
        """从作者名提取姓氏"""
        if not author:
            return "unknown"
        # "Last, First" 格式
        if "," in author:
            return author.split(",")[0].strip()
        # "First Last" 格式 — 取最后一个词
        parts = author.strip().split()
        return parts[-1] if parts else "unknown"

    @staticmethod
    def _first_alpha_word(title: str) -> str:
        """取标题第一个纯字母单词（用于 citation key）"""
        for word in title.split():
            clean = re.sub(r"[^a-zA-Z]", "", word)
            if clean:
                return clean
        return "untitled"

    @staticmethod
    def _apa_author(author: str) -> str:
        """将作者名格式化为 APA: "Last, F. M." 或保持原样"""
        if not author:
            return ""
        # 已经是 "Last, First" 格式
        if "," in author:
            last_part, first_part = author.split(",", 1)
            last_part = last_part.strip()
            first_part = first_part.strip()
            # 缩写名
            initials = " ".join(
                f"{n[0].upper()}." for n in first_part.split() if n
            )
            return f"{last_part}, {initials}" if initials else last_part
        # "First Last" 格式
        parts = author.strip().split()
        if len(parts) == 1:
            return parts[0]
        last = parts[-1]
        initials = " ".join(f"{n[0].upper()}." for n in parts[:-1] if n)
        return f"{last}, {initials}"

    @staticmethod
    def _join_apa_authors(formatted: list[str]) -> str:
        """APA 作者连接: 1人直接输出，2人用 &，3+用逗号+& 最后"""
        if not formatted:
            return ""
        if len(formatted) == 1:
            return formatted[0]
        if len(formatted) == 2:
            return f"{formatted[0]} & {formatted[1]}"
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


# 单例
citation_service = CitationService()


def first_lowercase(s: str) -> str:
    """确保字符串首字母小写（用于 citation key）"""
    if not s:
        return s
    return s[0].lower() + s[1:]
