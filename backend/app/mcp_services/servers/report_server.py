"""ReportGenerator MCP Server — 结构化学术报告生成服务

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
使用 aiohttp 调用 DeepSeek API（复用项目 DEEPSEEK_API_KEY 环境变量配置）。
"""

import sys
import json
import os
import asyncio
import logging
import re
import hashlib
from typing import Any, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)

# DeepSeek API 配置（从环境变量读取，复用项目配置）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# ---------------------------------------------------------------------------
# 内存缓存: 缓存键 -> 生成内容
# ---------------------------------------------------------------------------
_report_cache: dict[str, str] = {}


def _cache_key(tool_name: str, arguments: dict) -> str:
    """基于工具名和参数生成缓存键"""
    payload = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _get_cached(tool_name: str, arguments: dict) -> Optional[str]:
    key = _cache_key(tool_name, arguments)
    return _report_cache.get(key)


def _set_cached(tool_name: str, arguments: dict, content: str) -> None:
    key = _cache_key(tool_name, arguments)
    _report_cache[key] = content
    # 简单 LRU: 限制缓存条目数
    if len(_report_cache) > 100:
        oldest = next(iter(_report_cache))
        _report_cache.pop(oldest)


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "generate_literature_review",
        "description": "基于给定论文列表/主题生成结构化的文献综述",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "研究主题"},
                "papers": {
                    "type": "array",
                    "description": "论文列表，每项包含 title, authors, abstract 等",
                    "items": {"type": "object"}
                },
                "style": {"type": "string", "default": "academic", "description": "写作风格，如 academic, casual, survey"}
            },
            "required": ["topic", "papers"]
        }
    },
    {
        "name": "generate_outline",
        "description": "生成报告大纲（纯模板策略，<1s）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "报告主题"},
                "sections": {"type": "integer", "default": 5, "description": "主要章节数量"},
                "depth": {"type": "integer", "default": 2, "description": "大纲层级深度（1-3）"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "synthesize_report",
        "description": "多源信息综合生成完整报告",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "报告主题"},
                "sources": {
                    "type": "array",
                    "description": "信息源列表，每项包含 title, content, source_type 等",
                    "items": {"type": "object"}
                },
                "format": {"type": "string", "default": "markdown", "description": "输出格式: markdown, html, latex"}
            },
            "required": ["topic", "sources"]
        }
    },
    {
        "name": "format_report",
        "description": "报告格式转换（markdown ↔ html ↔ latex）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "原始报告内容"},
                "input_format": {"type": "string", "description": "输入格式"},
                "output_format": {"type": "string", "enum": ["markdown", "html", "latex"], "description": "目标输出格式"}
            },
            "required": ["content", "input_format", "output_format"]
        }
    }
]

# ---------------------------------------------------------------------------
# LLM 调用辅助（流式响应）
# ---------------------------------------------------------------------------

async def _call_llm_stream(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """调用 DeepSeek API，内部使用流式响应，返回完整文本。"""
    if not DEEPSEEK_API_KEY:
        return "[错误: 未配置 DEEPSEEK_API_KEY，无法调用 LLM]"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "temperature": 0.5,
        "max_tokens": max_tokens,
    }

    full_text = []
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{DEEPSEEK_API_BASE}/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_text.append(content)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
    except aiohttp.ClientResponseError as exc:
        logger.error("LLM API 响应错误: %s %s", exc.status, exc.message)
        return f"[错误: LLM API 响应异常 {exc.status}]"
    except asyncio.TimeoutError:
        logger.error("LLM API 请求超时")
        return "[错误: LLM API 请求超时]"
    except Exception as exc:
        logger.exception("LLM API 请求异常")
        return f"[错误: LLM API 请求异常: {exc}]"

    return "".join(full_text)


# ---------------------------------------------------------------------------
# 大纲模板生成（纯模板，无 LLM，<1s）
# ---------------------------------------------------------------------------

_OUTLINE_SECTIONS = [
    ("引言", ["研究背景", "研究意义", "研究目标与问题"]),
    ("文献综述", ["相关研究回顾", "研究空白与不足", "本章小结"]),
    ("研究方法", ["研究设计", "数据收集", "分析方法"]),
    ("实验与结果", ["实验设置", "主要发现", "结果分析"]),
    ("讨论", ["结果解释", "与已有研究对比", "研究局限性"]),
    ("结论与展望", ["主要结论", "实践意义", "未来研究方向"]),
]


def _generate_outline_template(topic: str, sections: int, depth: int) -> str:
    """基于模板生成结构化大纲。"""
    sections = max(1, min(sections, 8))
    depth = max(1, min(depth, 3))

    lines = [f"# {topic}", ""]

    available = _OUTLINE_SECTIONS[:sections]
    for i, (sec_title, sub_items) in enumerate(available, 1):
        lines.append(f"## {i}. {sec_title}")
        if depth >= 2:
            for sub in sub_items:
                lines.append(f"- {sub}")
                if depth >= 3:
                    lines.append(f"  - 详细说明...")
        lines.append("")

    lines.append("## 附录")
    lines.append("- 参考文献")
    lines.append("- 致谢")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 格式转换器（纯字符串模板）
# ---------------------------------------------------------------------------

def _markdown_to_html(md: str) -> str:
    """简易 Markdown → HTML 转换器。"""
    html = md

    # 代码块
    def _code_block_repl(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = m.group(2)
        return f'<pre><code class="language-{lang}">{code}</code></pre>'

    html = re.sub(r'```(\w+)?\n(.*?)```', _code_block_repl, html, flags=re.DOTALL)

    # 行内代码
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # 标题
    html = re.sub(r'^###### (.*)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
    html = re.sub(r'^##### (.*)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.*)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # 粗体/斜体
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # 列表
    lines = html.split('\n')
    out_lines = []
    in_ul = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            content = stripped[2:]
            indent = len(line) - len(stripped)
            if not in_ul:
                out_lines.append('<ul>')
                in_ul = True
            out_lines.append(f'<li>{content}</li>')
        else:
            if in_ul:
                out_lines.append('</ul>')
                in_ul = False
            out_lines.append(line)
    if in_ul:
        out_lines.append('</ul>')
    html = '\n'.join(out_lines)

    # 段落
    paragraphs = html.split('\n\n')
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<') and not p.startswith('<li>'):
            wrapped.append(p)
        else:
            wrapped.append(f'<p>{p}</p>')
    html = '\n\n'.join(wrapped)

    return html


def _markdown_to_latex(md: str) -> str:
    """简易 Markdown → LaTeX 转换器。"""
    latex = md

    # 代码块
    def _code_block_repl(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = m.group(2)
        return f"\\begin{{lstlisting}}[language={lang}]\n{code}\n\\end{{lstlisting}}"

    latex = re.sub(r'```(\w+)?\n(.*?)```', _code_block_repl, latex, flags=re.DOTALL)

    # 行内代码
    latex = re.sub(r'`([^`]+)`', r'\\texttt{\1}', latex)

    # 标题
    latex = re.sub(r'^# (.*)$', r'\\section{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^## (.*)$', r'\\subsection{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^### (.*)$', r'\\subsubsection{\1}', latex, flags=re.MULTILINE)
    latex = re.sub(r'^#### (.*)$', r'\\paragraph{\1}', latex, flags=re.MULTILINE)

    # 粗体/斜体
    latex = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', latex)
    latex = re.sub(r'\*(.+?)\*', r'\\textit{\1}', latex)

    # 列表
    lines = latex.split('\n')
    out_lines = []
    in_list = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            content = stripped[2:]
            if not in_list:
                out_lines.append('\\begin{itemize}')
                in_list = True
            out_lines.append(f'  \\item {content}')
        else:
            if in_list:
                out_lines.append('\\end{itemize}')
                in_list = False
            out_lines.append(line)
    if in_list:
        out_lines.append('\\end{itemize}')
    latex = '\n'.join(out_lines)

    return latex


def _convert_format(content: str, input_format: str, output_format: str) -> str:
    """在 markdown / html / latex 之间转换。"""
    input_fmt = input_format.lower().strip()
    output_fmt = output_format.lower().strip()

    if input_fmt == output_fmt:
        return content

    # 统一先转为 markdown 作为中间态
    md = content
    if input_fmt == "html":
        # html -> markdown: 简化处理
        md = re.sub(r'<h1>(.*?)</h1>', r'# \1', md)
        md = re.sub(r'<h2>(.*?)</h2>', r'## \1', md)
        md = re.sub(r'<h3>(.*?)</h3>', r'### \1', md)
        md = re.sub(r'<p>(.*?)</p>', r'\1\n\n', md)
        md = re.sub(r'<strong>(.*?)</strong>', r'**\1**', md)
        md = re.sub(r'<em>(.*?)</em>', r'*\1*', md)
        md = re.sub(r'<code>(.*?)</code>', r'`\1`', md)
        md = re.sub(r'<li>(.*?)</li>', r'- \1', md)
        md = re.sub(r'<ul>|</ul>', r'', md)
        md = re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```', md, flags=re.DOTALL)
    elif input_fmt == "latex":
        # latex -> markdown: 简化处理
        md = re.sub(r'\\section\{(.*?)\}', r'# \1', md)
        md = re.sub(r'\\subsection\{(.*?)\}', r'## \1', md)
        md = re.sub(r'\\subsubsection\{(.*?)\}', r'### \1', md)
        md = re.sub(r'\\textbf\{(.*?)\}', r'**\1**', md)
        md = re.sub(r'\\textit\{(.*?)\}', r'*\1*', md)
        md = re.sub(r'\\texttt\{(.*?)\}', r'`\1`', md)
        md = re.sub(r'\\item ', r'- ', md)
        md = re.sub(r'\\begin\{lstlisting\}[^\n]*\n', r'```\n', md)
        md = re.sub(r'\\end\{lstlisting\}', r'```', md)
        md = re.sub(r'\\begin\{itemize\}|\\end\{itemize\}', r'', md)

    if output_fmt == "markdown":
        return md.strip()
    elif output_fmt == "html":
        return _markdown_to_html(md)
    elif output_fmt == "latex":
        return _markdown_to_latex(md)
    else:
        return content


# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_generate_literature_review(arguments: dict) -> str:
    topic = arguments.get("topic", "").strip()
    papers = arguments.get("papers", [])
    style = arguments.get("style", "academic").strip()

    if not topic:
        return json.dumps({"error": "topic 参数不能为空"}, ensure_ascii=False)
    if not papers or not isinstance(papers, list):
        return json.dumps({"error": "papers 参数必须为非空列表"}, ensure_ascii=False)

    # 检查缓存
    cached = _get_cached("generate_literature_review", arguments)
    if cached:
        return json.dumps({"cached": True, "topic": topic, "review": cached}, ensure_ascii=False)

    # 构建论文摘要文本
    paper_texts = []
    for i, p in enumerate(papers, 1):
        title = p.get("title", "未知标题")
        authors = ", ".join(p.get("authors", [])) if isinstance(p.get("authors"), list) else p.get("authors", "未知作者")
        abstract = p.get("abstract", "")
        paper_texts.append(f"论文 {i}:\n标题: {title}\n作者: {authors}\n摘要: {abstract}\n")

    papers_block = "\n".join(paper_texts)

    system_prompt = (
        "你是一个专业的学术文献综述撰写助手。请基于用户提供的多篇论文生成一份结构化的文献综述。\n\n"
        "【重要指示 - 必须严格遵守】\n"
        "1. 无论论文数量多少或内容是否完整，都必须生成完整的文献综述\n"
        "2. 严禁说'无法生成'、'论文不足'或任何类似的拒绝性表述\n"
        "3. 即使论文数量有限，也必须基于已有内容完成所有部分的撰写\n"
        "4. 如果某部分信息不足，基于已有内容给出合理推断和分析\n"
        "5. 必须严格按照指定格式输出，不得省略任何部分\n\n"
        f"写作风格: {style}\n"
        "请用中文撰写，语言要学术化、严谨，内容要有深度。"
    )

    user_prompt = (
        f"研究主题: {topic}\n\n"
        f"以下是需要综述的论文:\n\n{papers_block}\n\n"
        "请生成一份完整的文献综述，使用 Markdown 格式，包含以下部分：\n"
        "# 文献综述\n\n"
        "## 1. 研究背景与意义\n"
        "## 2. 各论文核心观点梳理\n"
        "## 3. 研究方法比较\n"
        "## 4. 研究发现汇总\n"
        "## 5. 研究趋势与未来方向\n"
        "## 6. 参考文献\n"
    )

    review = await _call_llm_stream(system_prompt, user_prompt, max_tokens=4096)
    if review.startswith("[错误:"):
        return json.dumps({"error": review}, ensure_ascii=False)

    _set_cached("generate_literature_review", arguments, review)
    return json.dumps({"cached": False, "topic": topic, "review": review}, ensure_ascii=False)


async def handle_generate_outline(arguments: dict) -> str:
    topic = arguments.get("topic", "").strip()
    sections = int(arguments.get("sections", 5))
    depth = int(arguments.get("depth", 2))

    if not topic:
        return json.dumps({"error": "topic 参数不能为空"}, ensure_ascii=False)

    # 检查缓存
    cached = _get_cached("generate_outline", arguments)
    if cached:
        return json.dumps({"cached": True, "topic": topic, "outline": cached}, ensure_ascii=False)

    outline = _generate_outline_template(topic, sections, depth)
    _set_cached("generate_outline", arguments, outline)

    return json.dumps({"cached": False, "topic": topic, "outline": outline}, ensure_ascii=False)


async def handle_synthesize_report(arguments: dict) -> str:
    topic = arguments.get("topic", "").strip()
    sources = arguments.get("sources", [])
    fmt = arguments.get("format", "markdown").strip().lower()

    if not topic:
        return json.dumps({"error": "topic 参数不能为空"}, ensure_ascii=False)
    if not sources or not isinstance(sources, list):
        return json.dumps({"error": "sources 参数必须为非空列表"}, ensure_ascii=False)

    # 检查缓存
    cached = _get_cached("synthesize_report", arguments)
    if cached:
        return json.dumps({"cached": True, "topic": topic, "report": cached}, ensure_ascii=False)

    source_texts = []
    for i, s in enumerate(sources, 1):
        title = s.get("title", f"来源 {i}")
        content = s.get("content", "")
        source_type = s.get("source_type", "未知")
        source_texts.append(f"【来源 {i} | 类型: {source_type} | 标题: {title}】\n{content}\n")

    sources_block = "\n".join(source_texts)

    system_prompt = (
        "你是一个专业的学术报告撰写助手。请基于多源信息综合生成一份完整的结构化报告。\n\n"
        "【重要指示 - 必须严格遵守】\n"
        "1. 必须综合所有来源的信息，生成一份连贯、完整的报告\n"
        "2. 严禁说'无法生成'、'信息不足'或任何类似的拒绝性表述\n"
        "3. 如果信息存在矛盾，请客观呈现不同观点并分析\n"
        "4. 报告结构必须完整，包含摘要、正文和结论\n"
        "5. 请用中文撰写，语言学术化、严谨"
    )

    user_prompt = (
        f"报告主题: {topic}\n"
        f"输出格式: {fmt}\n\n"
        f"以下是需要综合的信息来源:\n\n{sources_block}\n\n"
        "请生成一份完整的报告，包含以下结构:\n"
        "# 摘要\n"
        "# 1. 引言\n"
        "# 2. 主体分析\n"
        "# 3. 综合讨论\n"
        "# 4. 结论与建议\n"
    )

    report = await _call_llm_stream(system_prompt, user_prompt, max_tokens=4096)
    if report.startswith("[错误:"):
        return json.dumps({"error": report}, ensure_ascii=False)

    # 如需格式转换
    if fmt == "html":
        report = _markdown_to_html(report)
    elif fmt == "latex":
        report = _markdown_to_latex(report)

    _set_cached("synthesize_report", arguments, report)
    return json.dumps({"cached": False, "topic": topic, "format": fmt, "report": report}, ensure_ascii=False)


async def handle_format_report(arguments: dict) -> str:
    content = arguments.get("content", "")
    input_format = arguments.get("input_format", "markdown").strip()
    output_format = arguments.get("output_format", "markdown").strip()

    if not content:
        return json.dumps({"error": "content 参数不能为空"}, ensure_ascii=False)

    if output_format not in ("markdown", "html", "latex"):
        return json.dumps({"error": "output_format 必须是 markdown、html 或 latex"}, ensure_ascii=False)

    converted = _convert_format(content, input_format, output_format)
    return json.dumps(
        {"input_format": input_format, "output_format": output_format, "content": converted},
        ensure_ascii=False
    )


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "generate_literature_review":
        return await handle_generate_literature_review(arguments)
    elif tool_name == "generate_outline":
        return await handle_generate_outline(arguments)
    elif tool_name == "synthesize_report":
        return await handle_synthesize_report(arguments)
    elif tool_name == "format_report":
        return await handle_format_report(arguments)
    else:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# JSON-RPC 处理
# ---------------------------------------------------------------------------

async def handle_request(request: dict) -> Optional[dict]:
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "report-generator-mcp-server", "version": "1.0.0"}
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        tool_name = request.get("params", {}).get("name", "")
        arguments = request.get("params", {}).get("arguments", {})
        result = await dispatch_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result}],
                "isError": False
            }
        }
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


# ---------------------------------------------------------------------------
# 主循环 — 兼容 pipe 和直接运行
# ---------------------------------------------------------------------------

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    loop = asyncio.get_event_loop()

    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY 未设置，LLM 相关工具将返回错误")

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
        except Exception as exc:
            logger.error("读取 stdin 异常: %s", exc)
            break

        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("忽略非 JSON 行: %s", exc)
            continue

        try:
            response = await handle_request(request)
        except Exception as exc:
            logger.exception("处理请求异常")
            req_id = request.get("id") if isinstance(request, dict) else None
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal error: {exc}"}
            }

        if response is not None:
            data = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
            sys.stdout.buffer.write(data)
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
