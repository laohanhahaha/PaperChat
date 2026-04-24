"""Zotero MCP Server — 文献库搜索、条目添加、集合管理与引用同步

实现 JSON-RPC 2.0 over stdio，与 StdioTransport 兼容。
需要环境变量:
  - ZOTERO_API_KEY: API Key
  - ZOTERO_LIBRARY_ID: 用户或群组 Library ID
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

ZOTERO_API_BASE = "https://api.zotero.org"


def _get_headers() -> dict:
    api_key = os.environ.get("ZOTERO_API_KEY", "")
    headers = {
        "Zotero-API-Version": "3",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if api_key:
        headers["Zotero-API-Key"] = api_key
    return headers


def _get_library_id() -> Optional[str]:
    return os.environ.get("ZOTERO_LIBRARY_ID")


def _build_url(path: str, library_type: str = "users") -> str:
    library_id = _get_library_id()
    if not library_id:
        return ""
    return f"{ZOTERO_API_BASE}/{library_type}/{library_id}{path}"


async def _zotero_get(session: aiohttp.ClientSession, url: str, params: Optional[dict] = None) -> Any:
    if not url:
        return {"error": "未配置 ZOTERO_LIBRARY_ID 环境变量"}
    try:
        async with session.get(url, params=params or {}, headers=_get_headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 401:
                return {"error": "Zotero API 认证失败，请检查 ZOTERO_API_KEY"}
            if resp.status == 404:
                return {"error": f"Zotero 资源未找到: {url}"}
            resp.raise_for_status()
            return await resp.json()
    except asyncio.TimeoutError:
        logger.warning("Zotero API 请求超时: %s", url)
        return {"error": "Zotero API 请求超时"}
    except aiohttp.ClientResponseError as exc:
        logger.error("Zotero API HTTP 错误 %s: %s", exc.status, exc.message)
        return {"error": f"Zotero API HTTP {exc.status}: {exc.message}"}
    except Exception as exc:
        logger.error("Zotero API 请求异常: %s", exc)
        return {"error": f"Zotero API 请求异常: {exc}"}


async def _zotero_post(session: aiohttp.ClientSession, url: str, payload: dict) -> Any:
    if not url:
        return {"error": "未配置 ZOTERO_LIBRARY_ID 环境变量"}
    try:
        async with session.post(url, json=payload, headers=_get_headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 401:
                return {"error": "Zotero API 认证失败，请检查 ZOTERO_API_KEY"}
            if resp.status == 404:
                return {"error": f"Zotero 资源未找到: {url}"}
            resp.raise_for_status()
            text = await resp.text()
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"status": resp.status, "response": text}
            return {"status": resp.status, "success": True}
    except asyncio.TimeoutError:
        logger.warning("Zotero API POST 超时: %s", url)
        return {"error": "Zotero API 请求超时"}
    except aiohttp.ClientResponseError as exc:
        logger.error("Zotero API POST HTTP 错误 %s: %s", exc.status, exc.message)
        return {"error": f"Zotero API HTTP {exc.status}: {exc.message}"}
    except Exception as exc:
        logger.error("Zotero API POST 异常: %s", exc)
        return {"error": f"Zotero API 请求异常: {exc}"}


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_library",
        "description": "搜索 Zotero 个人或群组文献库",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "library_type": {"type": "string", "default": "users", "enum": ["users", "groups"], "description": "库类型: users 或 groups"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_item",
        "description": "添加文献条目到 Zotero 库",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_data": {
                    "type": "object",
                    "description": "Zotero 条目数据对象，需包含 itemType 字段"
                },
                "library_type": {"type": "string", "default": "users", "enum": ["users", "groups"]}
            },
            "required": ["item_data"]
        }
    },
    {
        "name": "get_collections",
        "description": "获取所有集合（文件夹）列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library_type": {"type": "string", "default": "users", "enum": ["users", "groups"]}
            }
        }
    },
    {
        "name": "sync_references",
        "description": "同步指定集合中的引用条目",
        "inputSchema": {
            "type": "object",
            "properties": {
                "collection_id": {"type": "string", "description": "集合 ID"},
                "library_type": {"type": "string", "default": "users", "enum": ["users", "groups"]}
            },
            "required": ["collection_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# 工具处理函数
# ---------------------------------------------------------------------------

async def handle_search_library(arguments: dict) -> str:
    query = arguments.get("query", "").strip()
    library_type = arguments.get("library_type", "users")
    if not query:
        return json.dumps({"error": "query 参数不能为空"}, ensure_ascii=False)
    if library_type not in ("users", "groups"):
        return json.dumps({"error": "library_type 必须是 users 或 groups"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        url = _build_url("/items", library_type)
        data = await _zotero_get(session, url, {
            "q": query,
            "limit": 25,
            "sort": "dateModified",
            "direction": "desc"
        })

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({"query": query, "library_type": library_type, "items": data}, ensure_ascii=False, indent=2)


async def handle_add_item(arguments: dict) -> str:
    item_data = arguments.get("item_data", {})
    library_type = arguments.get("library_type", "users")
    if not item_data:
        return json.dumps({"error": "item_data 参数不能为空"}, ensure_ascii=False)
    if library_type not in ("users", "groups"):
        return json.dumps({"error": "library_type 必须是 users 或 groups"}, ensure_ascii=False)

    # Zotero Write API 要求提交 JSON 数组
    payload = [item_data]

    async with aiohttp.ClientSession() as session:
        url = _build_url("/items", library_type)
        data = await _zotero_post(session, url, payload)

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({"added": True, "response": data}, ensure_ascii=False, indent=2)


async def handle_get_collections(arguments: dict) -> str:
    library_type = arguments.get("library_type", "users")
    if library_type not in ("users", "groups"):
        return json.dumps({"error": "library_type 必须是 users 或 groups"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        url = _build_url("/collections", library_type)
        data = await _zotero_get(session, url, {"limit": 100})

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({"library_type": library_type, "collections": data}, ensure_ascii=False, indent=2)


async def handle_sync_references(arguments: dict) -> str:
    collection_id = arguments.get("collection_id", "").strip()
    library_type = arguments.get("library_type", "users")
    if not collection_id:
        return json.dumps({"error": "collection_id 参数不能为空"}, ensure_ascii=False)
    if library_type not in ("users", "groups"):
        return json.dumps({"error": "library_type 必须是 users 或 groups"}, ensure_ascii=False)

    async with aiohttp.ClientSession() as session:
        url = _build_url(f"/collections/{collection_id}/items", library_type)
        data = await _zotero_get(session, url, {"limit": 100, "sort": "dateModified", "direction": "desc"})

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({"collection_id": collection_id, "library_type": library_type, "items": data}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------

async def dispatch_tool(tool_name: str, arguments: dict) -> str:
    if tool_name == "search_library":
        return await handle_search_library(arguments)
    elif tool_name == "add_item":
        return await handle_add_item(arguments)
    elif tool_name == "get_collections":
        return await handle_get_collections(arguments)
    elif tool_name == "sync_references":
        return await handle_sync_references(arguments)
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
                "serverInfo": {"name": "zotero-mcp-server", "version": "1.0.0"}
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
