"""DBLP MCP Server — 出版物搜索、作者发表查询与期刊/会议信息

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
DBLP API 免费无需 Key，返回 JSON 格式。
"""

import sys
import json
import asyncio
import logging
import urllib.parse
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

DBLP_API_BASE = "https://dblp.org/search/publ/api"
DBLP_AUTHOR_API = "https://dblp.org/search/author/api"
DBLP_VENUE_API = "https://dblp.org/search/venue/api"


async def _dblp_get(session: aiohttp.ClientSession, url: str, params: Optional[dict] = None) -> Any:
    """发送 GET 请求到 DBLP API，返回 JSON 或 None"""
    try:
        async with session.get(url, params=params or {}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 404:
                return {"error": f"资源未找到: {url}"}
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError:
        logger.warning("DBLP API 请求超时: %s", url)
        return {"error": "DBLP API 请求超时"}
    except aiohttp.ClientResponseError as exc:
        logger.error("DBLP API HTTP 错误 %s: %s", exc.status, exc.message)
        return {"error": f"DBLP API HTTP {exc.status}: {exc.message}"}
    except Exception as exc:
        logger.error("DBLP API 请求异常: %s", exc)
        return {"error": f"DBLP API 请求异常: {exc}"}


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_publications",
        "description": "在 DBLP 搜索出版物",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "default": 10, "description": "返回数量上限（最大 100）"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_author_publications",
        "description": "获取指定作者的所有发表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "author_name": {"type": "string", "description": "作者姓名"}
            },
            "required": ["author_name"]
        }
    },
    {
        "name": "get_venue_info",
        "description": "获取期刊或会议的信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "venue": {"type": "string", "description": "期刊/会议名称或缩写"}
            },
            "required": ["venue"]
        }
    }
]

# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_search_publications(arguments: dict) -> str:
    query = arguments.get("query", "").strip()
    max_results = min(int(arguments.get("max_results", 10)), 100)
    if not query:
        return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _dblp_get(session, DBLP_API_BASE, {
            "q": query,
            "format": "json",
            "h": max_results
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    result = data.get("result", {}) if isinstance(data, dict) else {}
    hits = result.get("hits", {}) if isinstance(result, dict) else {}
    items = hits.get("hit", []) if isinstance(hits, dict) else []
    total = hits.get("@total", 0) if isinstance(hits, dict) else 0

    papers = []
    for item in items:
        info = item.get("info", {}) if isinstance(item, dict) else {}
        if info:
            papers.append(info)

    return json.dumps({"query": query, "total": total, "papers": papers}, ensure_ascii=False, indent=2)


async def handle_get_author_publications(arguments: dict) -> str:
    author_name = arguments.get("author_name", "").strip()
    if not author_name:
        return json.dumps({"error": "author_name 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _dblp_get(session, DBLP_API_BASE, {
            "q": f"author:{author_name}",
            "format": "json",
            "h": 100
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    result = data.get("result", {}) if isinstance(data, dict) else {}
    hits = result.get("hits", {}) if isinstance(result, dict) else {}
    items = hits.get("hit", []) if isinstance(hits, dict) else []
    total = hits.get("@total", 0) if isinstance(hits, dict) else 0

    papers = []
    for item in items:
        info = item.get("info", {}) if isinstance(item, dict) else {}
        if info:
            papers.append(info)

    return json.dumps({"author_name": author_name, "total": total, "papers": papers}, ensure_ascii=False, indent=2)


async def handle_get_venue_info(arguments: dict) -> str:
    venue = arguments.get("venue", "").strip()
    if not venue:
        return json.dumps({"error": "venue 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _dblp_get(session, DBLP_VENUE_API, {
            "q": venue,
            "format": "json",
            "h": 10
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    result = data.get("result", {}) if isinstance(data, dict) else {}
    hits = result.get("hits", {}) if isinstance(result, dict) else {}
    items = hits.get("hit", []) if isinstance(hits, dict) else []

    venues = []
    for item in items:
        info = item.get("info", {}) if isinstance(item, dict) else {}
        if info:
            venues.append(info)

    return json.dumps({"venue_query": venue, "venues": venues}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "search_publications":
        return await handle_search_publications(arguments)
    elif tool_name == "get_author_publications":
        return await handle_get_author_publications(arguments)
    elif tool_name == "get_venue_info":
        return await handle_get_venue_info(arguments)
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
                "serverInfo": {"name": "dblp-mcp-server", "version": "1.0.0"}
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
