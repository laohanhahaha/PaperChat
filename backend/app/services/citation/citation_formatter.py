"""引用格式化工具

支持多种引文格式的纯字符串模板生成，不依赖 LLM。
"""
import re


class CitationFormatter:
    """支持多种引文格式的格式化器"""

    # 格式名称映射（供前端展示）
    FORMAT_LABELS = {
        "bibtex": "BibTeX",
        "ris": "RIS",
        "apa": "APA",
        "mla": "MLA",
        "chicago": "Chicago",
        "gbt7714": "GB/T 7714",
    }

    def _extract_year(self, paper_info: dict) -> str:
        """提取年份，支持多种字段名"""
        for key in ("year", "published_year", "pub_year", "date"):
            val = paper_info.get(key)
            if val:
                # 尝试从字符串中提取4位年份
                if isinstance(val, str):
                    m = re.search(r"\b(19|20)\d{2}\b", val)
                    if m:
                        return m.group(0)
                elif isinstance(val, int):
                    return str(val)
                return str(val)
        return "n.d."

    def _format_authors(self, authors: str, format_type: str) -> str:
        """根据格式类型格式化作者列表"""
        if not authors or authors == "未知作者":
            return "Unknown"

        author_list = [a.strip() for a in authors.split(",") if a.strip()]
        if not author_list:
            return authors

        if format_type == "apa":
            if len(author_list) == 1:
                return author_list[0]
            elif len(author_list) == 2:
                return f"{author_list[0]} & {author_list[1]}"
            else:
                return f"{author_list[0]} et al."

        elif format_type == "mla":
            if len(author_list) == 1:
                return author_list[0]
            elif len(author_list) == 2:
                return f"{author_list[0]}, and {author_list[1]}"
            else:
                return f"{author_list[0]}, et al"

        elif format_type == "chicago":
            if len(author_list) <= 3:
                return ", ".join(author_list)
            else:
                return f"{author_list[0]} et al."

        elif format_type == "gbt7714":
            # GB/T 7714：多个作者用逗号分隔，超过3个只列前3个加"等"
            if len(author_list) > 3:
                return ", ".join(author_list[:3]) + ", 等"
            return ", ".join(author_list)

        # bibtex / ris 默认返回原始字符串
        return " and ".join(author_list)

    def _bibtex_key(self, paper_info: dict) -> str:
        """生成 BibTeX 引用键"""
        authors = paper_info.get("authors", "")
        year = self._extract_year(paper_info)
        first_author = authors.split(",")[0].strip().split()[-1] if authors else "unknown"
        title_word = paper_info.get("title", "untitled").split()[0].lower()
        title_word = re.sub(r"[^a-z0-9]", "", title_word) or "untitled"
        return f"{first_author.lower()}{year}{title_word}"

    def format_bibtex(self, paper_info: dict) -> str:
        """生成 BibTeX 格式引用"""
        title = paper_info.get("title", "Untitled")
        authors = self._format_authors(paper_info.get("authors", ""), "bibtex")
        year = self._extract_year(paper_info)
        journal = paper_info.get("journal", paper_info.get("publisher", ""))
        doi = paper_info.get("doi", "")
        pages = paper_info.get("pages", "")
        volume = paper_info.get("volume", "")
        number = paper_info.get("number", paper_info.get("issue", ""))

        key = self._bibtex_key(paper_info)
        entry_type = "article"
        if "book" in paper_info.get("type", "").lower():
            entry_type = "book"
        elif "conference" in paper_info.get("type", "").lower():
            entry_type = "inproceedings"

        lines = [f"@{entry_type}{{{key},"]
        lines.append(f'  title   = {{{title}}},')
        if authors:
            lines.append(f'  author  = {{{authors}}},')
        if journal:
            lines.append(f'  journal = {{{journal}}},')
        if volume:
            lines.append(f'  volume  = {{{volume}}},')
        if number:
            lines.append(f'  number  = {{{number}}},')
        if pages:
            lines.append(f'  pages   = {{{pages}}},')
        lines.append(f'  year    = {{{year}}},')
        if doi:
            lines.append(f'  doi     = {{{doi}}},')
        lines.append("}")

        return "\n".join(lines)

    def format_ris(self, paper_info: dict) -> str:
        """生成 RIS 格式引用"""
        title = paper_info.get("title", "")
        authors = paper_info.get("authors", "")
        year = self._extract_year(paper_info)
        journal = paper_info.get("journal", paper_info.get("publisher", ""))
        doi = paper_info.get("doi", "")
        pages = paper_info.get("pages", "")
        volume = paper_info.get("volume", "")
        issue = paper_info.get("issue", paper_info.get("number", ""))

        # 根据类型判断 TY
        doc_type = paper_info.get("type", "").lower()
        if "book" in doc_type:
            ty = "BOOK"
        elif "conference" in doc_type or "proceeding" in doc_type:
            ty = "CONF"
        else:
            ty = "JOUR"

        lines = [f"TY  - {ty}"]
        if title:
            lines.append(f"TI  - {title}")
        if authors:
            for a in authors.split(","):
                a = a.strip()
                if a:
                    lines.append(f"AU  - {a}")
        if journal:
            lines.append(f"JO  - {journal}")
        if volume:
            lines.append(f"VL  - {volume}")
        if issue:
            lines.append(f"IS  - {issue}")
        if pages:
            lines.append(f"SP  - {pages}")
        if year and year != "n.d.":
            lines.append(f"PY  - {year}")
        if doi:
            lines.append(f"DO  - {doi}")
        lines.append("ER  - ")

        return "\n".join(lines)

    def format_apa(self, paper_info: dict) -> str:
        """APA 第7版格式"""
        authors = self._format_authors(paper_info.get("authors", ""), "apa")
        year = self._extract_year(paper_info)
        title = paper_info.get("title", "Untitled")
        journal = paper_info.get("journal", paper_info.get("publisher", "未知来源"))
        doi = paper_info.get("doi", "")

        citation = f"{authors} ({year}). {title}. {journal}."
        if doi:
            citation += f" https://doi.org/{doi}"
        return citation

    def format_mla(self, paper_info: dict) -> str:
        """MLA 第9版格式"""
        authors = self._format_authors(paper_info.get("authors", ""), "mla")
        year = self._extract_year(paper_info)
        title = paper_info.get("title", "Untitled")
        journal = paper_info.get("journal", paper_info.get("publisher", "未知来源"))

        return f'{authors}. "{title}." {journal}, {year}.'

    def format_chicago(self, paper_info: dict) -> str:
        """Chicago 第17版格式（作者-日期）"""
        authors = self._format_authors(paper_info.get("authors", ""), "chicago")
        year = self._extract_year(paper_info)
        title = paper_info.get("title", "Untitled")
        journal = paper_info.get("journal", paper_info.get("publisher", "未知来源"))
        doi = paper_info.get("doi", "")

        citation = f'{authors}. "{title}." {journal} ({year}).'
        if doi:
            citation += f" https://doi.org/{doi}"
        return citation

    def format_gbt7714(self, paper_info: dict) -> str:
        """GB/T 7714-2015 格式（中国国标）"""
        index = paper_info.get("index", "")
        authors = self._format_authors(paper_info.get("authors", ""), "gbt7714")
        title = paper_info.get("title", "未命名论文")
        journal = paper_info.get("journal", paper_info.get("publisher", "未知来源"))
        year = self._extract_year(paper_info)
        doi = paper_info.get("doi", "")

        prefix = f"[{index}] " if index else ""
        citation = f"{prefix}{authors}. {title}[J]. {journal}, {year}."
        if doi:
            citation += f" DOI:{doi}."
        return citation

    def format(self, paper_info: dict, style: str) -> str:
        """统一入口

        Args:
            paper_info: 论文信息字典
            style: 引用格式标识

        Returns:
            格式化后的引用字符串
        """
        style = style.lower().strip()
        if style == "gbt":
            style = "gbt7714"

        method = getattr(self, f"format_{style}", None)
        if method:
            return method(paper_info)
        # 未知格式回退到 APA
        return self.format_apa(paper_info)
