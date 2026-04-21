import hashlib
import json
import time
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)


class ToolCache:
    """工具调用结果 LRU 缓存"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def _make_key(self, tool_name: str, params: str) -> str:
        """生成缓存 key（工具名+参数哈希）"""
        param_hash = hashlib.md5(params.encode()).hexdigest()[:12]
        return f"{tool_name}:{param_hash}"
    
    def get(self, tool_name: str, params: str) -> Optional[str]:
        """获取缓存结果，未命中返回 None"""
        key = self._make_key(tool_name, params)
        if key not in self._cache:
            return None
        # 检查 TTL
        if time.time() - self._timestamps[key] > self.ttl_seconds:
            del self._cache[key]
            del self._timestamps[key]
            return None
        # LRU: 移到末尾
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit: {tool_name}")
        return self._cache[key]
    
    def set(self, tool_name: str, params: str, result: str):
        """缓存结果"""
        key = self._make_key(tool_name, params)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._timestamps.pop(oldest_key, None)
        self._cache[key] = result
        self._timestamps[key] = time.time()
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._timestamps.clear()


tool_cache = ToolCache()
