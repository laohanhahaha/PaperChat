"""MCP JSON-RPC 2.0 传输层

提供 StdioTransport 和 SseTransport 两种传输实现，均封装：
  - 请求 ID 自增管理
  - send_request(method, params) -> dict
  - close()
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# JSON-RPC 2.0 默认超时（秒）
_DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_request(req_id: int, method: str, params: Any) -> bytes:
    """序列化 JSON-RPC 2.0 请求为 UTF-8 字节（带换行符，供 stdio 使用）"""
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return (json.dumps(payload) + "\n").encode("utf-8")


def _parse_response(raw: str) -> dict:
    """解析 JSON-RPC 2.0 响应，抛出协议错误"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"无效 JSON 响应: {exc}") from exc
    if "error" in data:
        err = data["error"]
        raise RuntimeError(
            f"JSON-RPC 错误 {err.get('code', '?')}: {err.get('message', str(err))}"
        )
    return data


# ---------------------------------------------------------------------------
# StdioTransport
# ---------------------------------------------------------------------------

class StdioTransport:
    """通过子进程 stdin/stdout 进行 JSON-RPC 2.0 通信

    兼容 Windows SelectorEventLoop（uvicorn reload 模式）：
    当 asyncio.create_subprocess_exec 不可用时，自动降级为
    subprocess.Popen + 线程池异步 I/O。
    """

    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[Dict[str, str]] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._timeout = timeout
        self._process: Optional[Any] = None  # asyncio.subprocess.Process or subprocess.Popen
        self._req_id: int = 0
        self._lock = asyncio.Lock()   # 串行化请求，避免响应错位
        self._use_popen: bool = False  # 是否使用 Popen 降级模式

    # ------------------------------------------------------------------ #
    async def connect(self) -> None:
        """启动子进程"""
        if self._process is not None:
            return

        import sys
        import subprocess

        proc_env = {**os.environ}
        if self._env:
            proc_env.update(self._env)

        logger.debug("[StdioTransport] 启动子进程: %s %s", self._command, self._args)

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

        # 优先尝试 asyncio subprocess，失败则降级到 Popen
        try:
            self._process = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=proc_env,
                **(dict(creationflags=creation_flags) if creation_flags else {}),
            )
            self._use_popen = False
        except NotImplementedError:
            # Windows SelectorEventLoop 不支持 subprocess，降级到 Popen
            logger.info("[StdioTransport] asyncio subprocess 不可用，降级为 Popen 模式")
            self._process = subprocess.Popen(
                [self._command, *self._args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=proc_env,
                **(dict(creationflags=creation_flags) if creation_flags else {}),
            )
            self._use_popen = True
        except Exception as exc:
            raise ConnectionError(
                f"StdioTransport: 启动子进程失败 (cmd={self._command}): {type(exc).__name__}: {exc}"
            ) from exc

        # 检查进程是否存活
        await asyncio.sleep(0.2)
        rc = self._process.returncode if not self._use_popen else self._process.poll()
        if rc is not None:
            stderr_data = ""
            try:
                if self._use_popen:
                    stderr_data = self._process.stderr.read(2000).decode("utf-8", errors="replace")
                else:
                    raw = await asyncio.wait_for(self._process.stderr.read(2000), timeout=2)
                    stderr_data = raw.decode("utf-8", errors="replace")
            except Exception:
                pass
            raise ConnectionError(
                f"StdioTransport: 子进程立即退出 (returncode={rc}), "
                f"stderr={stderr_data[:300]}"
            )

        pid = self._process.pid
        mode = "Popen" if self._use_popen else "asyncio"
        logger.info("[StdioTransport] 子进程已启动，pid=%s, mode=%s", pid, mode)

    async def close(self) -> None:
        """关闭子进程（先 terminate，超时后 kill）"""
        if self._process is None:
            return
        proc = self._process
        self._process = None
        try:
            proc.terminate()
            if self._use_popen:
                import concurrent.futures
                loop = asyncio.get_running_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, proc.wait),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await loop.run_in_executor(None, proc.wait)
            else:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("[StdioTransport] terminate 超时，强制 kill")
                    proc.kill()
                    await proc.wait()
        except Exception as exc:
            logger.debug("[StdioTransport] 关闭子进程时出现异常（可忽略）: %s", exc)
        logger.info("[StdioTransport] 子进程已关闭")

    @property
    def is_alive(self) -> bool:
        """子进程是否存活"""
        if self._process is None:
            return False
        if self._use_popen:
            return self._process.poll() is None
        return self._process.returncode is None

    async def send_request(self, method: str, params: Any = None) -> dict:
        """发送 JSON-RPC 请求并等待响应（带超时）"""
        if self._process is None or not self.is_alive:
            raise ConnectionError("StdioTransport: 子进程未运行")

        async with self._lock:
            self._req_id += 1
            req_id = self._req_id
            data = _make_request(req_id, method, params or {})

            logger.debug("[StdioTransport] → %s (id=%d)", method, req_id)

            if self._use_popen:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._popen_write, data)
                raw = await asyncio.wait_for(
                    loop.run_in_executor(None, self._popen_read_response, req_id),
                    timeout=self._timeout,
                )
            else:
                assert self._process.stdin is not None
                assert self._process.stdout is not None
                self._process.stdin.write(data)
                await self._process.stdin.drain()
                raw = await asyncio.wait_for(
                    self._read_response_for(req_id),
                    timeout=self._timeout,
                )

        response = _parse_response(raw)
        logger.debug("[StdioTransport] ← id=%d OK", req_id)
        return response

    # --- Popen 模式同步 I/O（在线程池中执行） ---

    def _popen_write(self, data: bytes) -> None:
        """同步写入 stdin"""
        self._process.stdin.write(data)
        self._process.stdin.flush()

    def _popen_read_response(self, expected_id: int) -> str:
        """同步从 stdout 读取响应"""
        while True:
            line_bytes = self._process.stdout.readline()
            if not line_bytes:
                raise ConnectionError("StdioTransport: 子进程输出流已关闭")
            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("[StdioTransport] 忽略非 JSON 行: %s", line[:120])
                continue
            if "id" not in obj:
                continue
            if obj["id"] == expected_id:
                return line

    # --- asyncio 模式异步 I/O ---

    async def _read_response_for(self, expected_id: int) -> str:
        """持续读行直到找到 id 匹配的响应"""
        assert self._process and self._process.stdout
        while True:
            line_bytes = await self._process.stdout.readline()
            if not line_bytes:
                raise ConnectionError("StdioTransport: 子进程输出流已关闭")
            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("[StdioTransport] 忽略非 JSON 行: %s", line[:120])
                continue
            # 跳过通知（无 id 字段）
            if "id" not in obj:
                continue
            if obj["id"] == expected_id:
                return line


# ---------------------------------------------------------------------------
# SseTransport
# ---------------------------------------------------------------------------

class SseTransport:
    """通过 HTTP SSE 进行 JSON-RPC 2.0 通信

    MCP over SSE 模式：
      - GET {url}  → SSE 事件流（server-sent events）
      - 从 SSE 流中读取 endpoint 事件，获取 POST URL
      - POST {post_url} 发送 JSON-RPC 请求
      - 响应通过 SSE 流推送回来
    """

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._session: Optional[Any] = None   # aiohttp.ClientSession
        self._post_url: Optional[str] = None  # 从 SSE endpoint 事件获取
        self._sse_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._req_id: int = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """建立 SSE 连接，等待 endpoint 事件"""
        try:
            import aiohttp  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "SSE 传输需要 aiohttp 库，请运行: pip install aiohttp"
            ) from exc

        headers: Dict[str, str] = {"Accept": "text/event-stream"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, connect=10)
        )
        # 等待 SSE 流建立并获取 endpoint
        endpoint_event = asyncio.get_event_loop().create_future()
        self._sse_task = asyncio.create_task(
            self._listen_sse(headers, endpoint_event)
        )
        try:
            self._post_url = await asyncio.wait_for(
                endpoint_event, timeout=10.0
            )
            logger.info("[SseTransport] SSE 连接成功，POST URL: %s", self._post_url)
        except asyncio.TimeoutError as exc:
            await self.close()
            raise ConnectionError("SseTransport: 等待 endpoint 事件超时") from exc

    async def _listen_sse(
        self,
        headers: Dict[str, str],
        endpoint_future: asyncio.Future,
    ) -> None:
        """持续监听 SSE 流，分发响应到 pending futures"""
        assert self._session is not None
        try:
            async with self._session.get(self._url, headers=headers) as resp:
                resp.raise_for_status()
                event_type = ""
                data_lines: list[str] = []

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").rstrip("\n\r")

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                    elif line == "":
                        # 事件结束
                        data = "\n".join(data_lines)
                        data_lines = []

                        if event_type == "endpoint":
                            # 获取消息 POST URL
                            post_url = data.strip()
                            if not post_url.startswith("http"):
                                # 相对路径
                                from urllib.parse import urljoin
                                post_url = urljoin(self._url + "/", post_url)
                            if not endpoint_future.done():
                                endpoint_future.set_result(post_url)

                        elif event_type == "message":
                            # JSON-RPC 响应
                            try:
                                obj = json.loads(data)
                                msg_id = obj.get("id")
                                if msg_id is not None and msg_id in self._pending:
                                    fut = self._pending.pop(msg_id)
                                    if not fut.done():
                                        fut.set_result(obj)
                            except json.JSONDecodeError:
                                logger.debug("[SseTransport] 忽略非 JSON SSE 数据")

                        event_type = ""
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("[SseTransport] SSE 流异常: %s", exc)
            # 让所有 pending 请求失败
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(exc)
            self._pending.clear()
            if not endpoint_future.done():
                endpoint_future.set_exception(exc)

    async def close(self) -> None:
        """关闭 SSE 连接"""
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("[SseTransport] SSE 连接已关闭")

    @property
    def is_alive(self) -> bool:
        return (
            self._session is not None
            and self._sse_task is not None
            and not self._sse_task.done()
        )

    async def send_request(self, method: str, params: Any = None) -> dict:
        """发送 JSON-RPC POST 请求，响应通过 SSE 流返回"""
        if not self.is_alive or self._post_url is None:
            raise ConnectionError("SseTransport: 连接未就绪")

        try:
            import aiohttp  # type: ignore
        except ImportError as exc:
            raise ImportError("SSE 传输需要 aiohttp 库") from exc

        async with self._lock:
            self._req_id += 1
            req_id = self._req_id

        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        assert self._session is not None
        try:
            async with self._session.post(
                self._post_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                resp.raise_for_status()
                logger.debug("[SseTransport] → %s (id=%d) 已提交", method, req_id)
        except Exception as exc:
            self._pending.pop(req_id, None)
            raise

        # 等待 SSE 流推送响应
        try:
            response = await asyncio.wait_for(fut, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise

        if "error" in response:
            err = response["error"]
            raise RuntimeError(
                f"JSON-RPC 错误 {err.get('code', '?')}: {err.get('message', str(err))}"
            )
        logger.debug("[SseTransport] ← id=%d OK", req_id)
        return response


# ---------------------------------------------------------------------------
# StreamableHttpTransport（简化版，直接 POST）
# ---------------------------------------------------------------------------

class StreamableHttpTransport:
    """MCP over HTTP — 直接 POST JSON-RPC，同步响应"""

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._url = url.rstrip("/") + "/messages"
        self._api_key = api_key
        self._timeout = timeout
        self._session: Optional[Any] = None
        self._req_id: int = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            import aiohttp  # type: ignore
        except ImportError as exc:
            raise ImportError("HTTP 传输需要 aiohttp 库") from exc
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout)
        )
        logger.info("[HttpTransport] 已初始化 session: %s", self._url)

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def is_alive(self) -> bool:
        return self._session is not None

    async def send_request(self, method: str, params: Any = None) -> dict:
        if self._session is None:
            raise ConnectionError("HttpTransport: 未连接")

        async with self._lock:
            self._req_id += 1
            req_id = self._req_id

        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        assert self._session is not None
        async with self._session.post(self._url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"JSON-RPC 错误 {err.get('code', '?')}: {err.get('message', str(err))}"
            )
        return data
