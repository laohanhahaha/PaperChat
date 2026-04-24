"""Semantic Scholar MCP Server — 论文搜索、引用、参考文献与作者查询

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
API Key 通过环境变量 S2_API_KEY 传入（可选，用于提升限额）。
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"


def _get_headers() -> dict:
    headers = {"Accept": "application/json"}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


async def _s2_get(session: aiohttp.ClientSession, endpoint: str, params: Optional[dict] = None) -> Any:
    """发送 GET 请求到 S2 API，返回 JSON 或 None"""
    url = f"{S2_API_BASE}/{endpoint}"
    try:
        async with session.get(url, params=params or {}, headers=_get_headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 404:
                return {"error": f"资源未找到: {endpoint}"}
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError:
        logger.warning("S2 API 请求超时: %s", endpoint)
        return {"error": "Semantic Scholar API 请求超时"}
    except aiohttp.ClientResponseError as exc:
        logger.error("S2 API HTTP 错误 %s: %s", exc.status, exc.message)
        return {"error": f"Semantic Scholar API HTTP {exc.status}: {exc.message}"}
    except Exception as exc:
        logger.error("S2 API 请求异常: %s", exc)
        return {"error": f"Semantic Scholar API 请求异常: {exc}"}


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_papers",
        "description": "在 Semantic Scholar 搜索论文",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "default": 10, "description": "返回数量上限（最大 100）"},
                "fields": {"type": "string", "default": "title,abstract,authors,year,citationCount", "description": "返回字段列表"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_citations",
        "description": "获取引用指定论文的论文列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_id": {"type": "string", "description": "Semantic Scholar Paper ID 或 DOI/ArXiv ID（前缀如 DOI:xxx）"},
                "limit": {"type": "integer", "default": 20, "description": "返回数量上限"}
            },
            "required": ["paper_id"]
        }
    },
    {
        "name": "get_references",
        "description": "获取指定论文引用的参考文献列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_id": {"type": "string", "description": "Semantic Scholar Paper ID 或 DOI/ArXiv ID（前缀如 DOI:xxx）"},
                "limit": {"type": "integer", "default": 20, "description": "返回数量上限"}
            },
            "required": ["paper_id"]
        }
    },
    {
        "name": "get_author",
        "description": "获取作者信息和论文列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "Semantic Scholar Author ID"}
            },
            "required": ["author_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_search_papers(arguments: dict) -> str:
    query = arguments.get("query", "").strip()
    limit = min(int(arguments.get("limit", 10)), 100)
    fields = arguments.get("fields", "title,abstract,authors,year,citationCount")
    if not query:
        return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _s2_get(session, "paper/search", {
            "query": query,
            "limit": limit,
            "fields": fields
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    papers = data.get("data", []) if isinstance(data, dict) else []
    total = data.get("total", 0) if isinstance(data, dict) else len(papers)
    return json.dumps({"query": query, "total": total, "papers": papers}, ensure_ascii=False, indent=2)


async def handle_get_citations(arguments: dict) -> str:
    paper_id = arguments.get("paper_id", "").strip()
    limit = min(int(arguments.get("limit", 20)), 100)
    if not paper_id:
        return json.dumps({"error": "paper_id 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _s2_get(session, f"paper/{paper_id}/citations", {
            "limit": limit,
            "fields": "title,authors,year,citationCount,venue"
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    citations = data.get("data", []) if isinstance(data, dict) else []
    return json.dumps({"paper_id": paper_id, "citations": citations}, ensure_ascii=False, indent=2)


async def handle_get_references(arguments: dict) -> str:
    paper_id = arguments.get("paper_id", "").strip()
    limit = min(int(arguments.get("limit", 20)), 100)
    if not paper_id:
        return json.dumps({"error": "paper_id 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _s2_get(session, f"paper/{paper_id}/references", {
            "limit": limit,
            "fields": "title,authors,year,citationCount,venue"
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    references = data.get("data", []) if isinstance(data, dict) else []
    return json.dumps({"paper_id": paper_id, "references": references}, ensure_ascii=False, indent=2)


async def handle_get_author(arguments: dict) -> str:
    author_id = arguments.get("author_id", "").strip()
    if not author_id:
        return json.dumps({"error": "author_id 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _s2_get(session, f"author/{author_id}", {
            "fields": "name,hIndex,citationCount,paperCount,papers.title,papers.year,papers.abstract"
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({"author": data}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "search_papers":
        return await handle_search_papers(arguments)
    elif tool_name == "get_citations":
        return await handle_get_citations(arguments)
    elif tool_name == "get_references":
        return await handle_get_references(arguments)
    elif tool_name == "get_author":
        return await handle_get_author(arguments)
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
                "serverInfo": {"name": "semantic-scholar-mcp-server", "version": "1.0.0"}
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
# 主循环
# ---------------------------------------------------------------------------

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    loop = asyncio.get_event_loop()

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
