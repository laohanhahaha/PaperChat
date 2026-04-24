"""arXiv MCP Server — 通过 arXiv API 搜索论文与获取元数据

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
"""

import sys
import json
import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_PDF_URL = "https://arxiv.org/pdf"

# ---------------------------------------------------------------------------
# 内存缓存: arxiv_id -> metadata dict
# ---------------------------------------------------------------------------
_metadata_cache: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "search_arxiv",
        "description": "搜索 arXiv 论文，返回标题、作者、摘要、URL 和分类信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "default": 10, "description": "返回结果数量上限"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_paper_metadata",
        "description": "获取单篇 arXiv 论文的详细元数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "arxiv_id": {"type": "string", "description": "arXiv ID，如 2401.12345"}
            },
            "required": ["arxiv_id"]
        }
    },
    {
        "name": "get_pdf_url",
        "description": "获取 arXiv 论文的 PDF 下载链接",
        "inputSchema": {
            "type": "object",
            "properties": {
                "arxiv_id": {"type": "string", "description": "arXiv ID，如 2401.12345"}
            },
            "required": ["arxiv_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# XML 解析辅助
# ---------------------------------------------------------------------------

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _text(elem: Optional[ET.Element], tag: str, default: str = "") -> str:
    child = elem.find(tag, _ATOM_NS) if elem is not None else None
    return (child.text or default) if child is not None else default


def _parse_entry(entry: ET.Element) -> dict:
    """解析单个 Atom entry 为论文元数据 dict"""
    authors = []
    for author in entry.findall("atom:author", _ATOM_NS):
        name = author.find("atom:name", _ATOM_NS)
        if name is not None and name.text:
            authors.append(name.text)

    categories = []
    for cat in entry.findall("atom:category", _ATOM_NS):
        term = cat.get("term")
        if term:
            categories.append(term)

    arxiv_id = ""
    id_elem = entry.find("atom:id", _ATOM_NS)
    if id_elem is not None and id_elem.text:
        # id 形如 http://arxiv.org/abs/2401.12345
        arxiv_id = id_elem.text.strip().split("/")[-1]

    return {
        "title": _text(entry, "atom:title").strip(),
        "authors": authors,
        "abstract": _text(entry, "atom:summary").strip(),
        "published": _text(entry, "atom:published"),
        "updated": _text(entry, "atom:updated"),
        "arxiv_id": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
        "categories": categories,
        "primary_category": categories[0] if categories else "",
        "comment": _text(entry, "arxiv:comment"),
        "journal_ref": _text(entry, "arxiv:journal_ref"),
    }


async def _fetch_feed(session: aiohttp.ClientSession, params: dict) -> Optional[ET.Element]:
    """请求 arXiv API 并解析 Atom XML"""
    try:
        async with session.get(ARXIV_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            text = await resp.text()
            root = ET.fromstring(text.encode("utf-8"))
            return root
    except asyncio.TimeoutError:
        logger.warning("arXiv API 请求超时")
        return None
    except Exception as exc:
        logger.error("arXiv API 请求异常: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_search_arxiv(arguments: dict) -> str:
    query = arguments.get("query", "").strip()
    max_results = min(int(arguments.get("max_results", 10)), 50)
    if not query:
        return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        root = await _fetch_feed(session, {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        })
        if root is None:
            return json.dumps({"error": "arXiv API 请求失败或超时"}, ensure_ascii=False)

        results = []
        for entry in root.findall("atom:entry", _ATOM_NS):
            paper = _parse_entry(entry)
            results.append(paper)
            # 写入缓存
            if paper.get("arxiv_id"):
                _metadata_cache[paper["arxiv_id"]] = paper

    return json.dumps({"query": query, "total_results": len(results), "papers": results}, ensure_ascii=False, indent=2)


async def handle_get_paper_metadata(arguments: dict) -> str:
    arxiv_id = arguments.get("arxiv_id", "").strip()
    if not arxiv_id:
        return json.dumps({"error": "arxiv_id 参数不能为空"}, ensure_ascii=False)

    # 命中缓存
    if arxiv_id in _metadata_cache:
        return json.dumps({"cached": True, "paper": _metadata_cache[arxiv_id]}, ensure_ascii=False, indent=2)

    async with aiohttp.ClientSession() as session:
        root = await _fetch_feed(session, {
            "id_list": arxiv_id,
            "max_results": 1
        })
        if root is None:
            return json.dumps({"error": "arXiv API 请求失败或超时"}, ensure_ascii=False)

        entry = root.find("atom:entry", _ATOM_NS)
        if entry is None:
            return json.dumps({"error": f"未找到 arXiv ID: {arxiv_id}"}, ensure_ascii=False)

        paper = _parse_entry(entry)
        if paper.get("arxiv_id"):
            _metadata_cache[paper["arxiv_id"]] = paper

    return json.dumps({"cached": False, "paper": paper}, ensure_ascii=False, indent=2)


async def handle_get_pdf_url(arguments: dict) -> str:
    arxiv_id = arguments.get("arxiv_id", "").strip()
    if not arxiv_id:
        return json.dumps({"error": "arxiv_id 参数不能为空"}, ensure_ascii=False)

    pdf_url = f"{ARXIV_PDF_URL}/{arxiv_id}.pdf"
    return json.dumps({"arxiv_id": arxiv_id, "pdf_url": pdf_url}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "search_arxiv":
        return await handle_search_arxiv(arguments)
    elif tool_name == "get_paper_metadata":
        return await handle_get_paper_metadata(arguments)
    elif tool_name == "get_pdf_url":
        return await handle_get_pdf_url(arguments)
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
                "serverInfo": {"name": "arxiv-mcp-server", "version": "1.0.0"}
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

    # 尝试使用 asyncio pipe（子进程模式下可用）
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
