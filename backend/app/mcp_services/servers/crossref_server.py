"""CrossRef MCP Server — DOI 解析、学术作品搜索与资助机构信息查询

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
建议设置 User-Agent 包含 mailto 以提升 API 优先级。
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org"


def _get_headers() -> dict:
    mailto = os.environ.get("CROSSREF_MAILTO", "chatpdf@example.com")
    return {
        "User-Agent": f"ChatPDF-MCP/1.0 (mailto:{mailto})",
        "Accept": "application/json"
    }


async def _crossref_get(session: aiohttp.ClientSession, endpoint: str, params: Optional[dict] = None) -> Any:
    """发送 GET 请求到 CrossRef API，返回 JSON 或 None"""
    url = f"{CROSSREF_API_BASE}/{endpoint}"
    try:
        async with session.get(url, params=params or {}, headers=_get_headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 404:
                return {"error": f"资源未找到: {endpoint}"}
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError:
        logger.warning("CrossRef API 请求超时: %s", endpoint)
        return {"error": "CrossRef API 请求超时"}
    except aiohttp.ClientResponseError as exc:
        logger.error("CrossRef API HTTP 错误 %s: %s", exc.status, exc.message)
        return {"error": f"CrossRef API HTTP {exc.status}: {exc.message}"}
    except Exception as exc:
        logger.error("CrossRef API 请求异常: %s", exc)
        return {"error": f"CrossRef API 请求异常: {exc}"}


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "resolve_doi",
        "description": "通过 DOI 获取作品的完整元数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doi": {"type": "string", "description": "DOI，如 10.1038/s41586-021-03819-2"}
            },
            "required": ["doi"]
        }
    },
    {
        "name": "search_works",
        "description": "在 CrossRef 搜索学术作品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "rows": {"type": "integer", "default": 10, "description": "返回数量上限（最大 100）"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_funder_info",
        "description": "获取资助机构信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "funder_id": {"type": "string", "description": "CrossRef Funder ID，如 10.13039/501100001659"}
            },
            "required": ["funder_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_resolve_doi(arguments: dict) -> str:
    doi = arguments.get("doi", "").strip()
    if not doi:
        return json.dumps({"error": "doi 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _crossref_get(session, f"works/{doi}")

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    work = data.get("message", {}) if isinstance(data, dict) else {}
    return json.dumps({"doi": doi, "work": work}, ensure_ascii=False, indent=2)


async def handle_search_works(arguments: dict) -> str:
    query = arguments.get("query", "").strip()
    rows = min(int(arguments.get("rows", 10)), 100)
    if not query:
        return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _crossref_get(session, "works", {
            "query": query,
            "rows": rows,
            "sort": "relevance",
            "order": "desc"
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    message = data.get("message", {}) if isinstance(data, dict) else {}
    items = message.get("items", [])
    total_results = message.get("total-results", 0)
    return json.dumps({"query": query, "total_results": total_results, "works": items}, ensure_ascii=False, indent=2)


async def handle_get_funder_info(arguments: dict) -> str:
    funder_id = arguments.get("funder_id", "").strip()
    if not funder_id:
        return json.dumps({"error": "funder_id 参数不能为空"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        data = await _crossref_get(session, f"funders/{funder_id}")

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    message = data.get("message", {}) if isinstance(data, dict) else {}
    return json.dumps({"funder_id": funder_id, "funder": message}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "resolve_doi":
        return await handle_resolve_doi(arguments)
    elif tool_name == "search_works":
        return await handle_search_works(arguments)
    elif tool_name == "get_funder_info":
        return await handle_get_funder_info(arguments)
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
                "serverInfo": {"name": "crossref-mcp-server", "version": "1.0.0"}
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
