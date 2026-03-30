"""Web搜索服务 - 集成DuckDuckGo"""
import asyncio
from typing import List, Dict, Any, Optional
from duckduckgo_search import DDGS
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """网络搜索服务
    
    功能：
    1. 使用 DuckDuckGo 进行网络搜索
    2. 搜索结果缓存
    3. 超时控制
    """
    
    def __init__(self):
        self.search_cache = {}
        self.max_cache_size = 100
        self.search_timeout = 15  # 搜索超时时间（秒）
        self.default_max_results = 5  # 默认最大结果数
    
    async def update_config(
        self,
        timeout: int = None,
        max_results: int = None
    ):
        """运行时更新搜索配置
        
        Args:
            timeout: 搜索超时时间（秒）
            max_results: 默认最大结果数
        """
        if timeout is not None:
            self.search_timeout = timeout
        if max_results is not None:
            self.default_max_results = max_results
    
    async def search(
        self, 
        query: str, 
        max_results: int = 5, 
        region: str = "wt-wt", 
        timelimit: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """执行网络搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数量
            region: 地区设置 (wt-wt 为全球)
            timelimit: 时间限制 (d=天, w=周, m=月, y=年)
            
        Returns:
            搜索结果列表，每个结果包含:
            - title: 标题
            - href: 链接
            - body: 摘要
        """
        # 检查缓存
        cache_key = f"{query}:{max_results}:{region}:{timelimit}"
        if cache_key in self.search_cache:
            logger.info(f"使用缓存的搜索结果: '{query}'")
            return self.search_cache[cache_key]
        
        try:
            # 在线程池中执行同步搜索
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: list(DDGS().text(
                        query, 
                        region=region, 
                        timelimit=timelimit, 
                        max_results=max_results
                    ))
                ),
                timeout=self.search_timeout
            )
            
            # 确保每个结果都有 body 字段
            for r in results:
                if "body" not in r:
                    r["body"] = ""
            
            # 缓存结果
            if len(self.search_cache) >= self.max_cache_size:
                # 移除最旧的缓存
                self.search_cache.pop(next(iter(self.search_cache)))
            self.search_cache[cache_key] = results
            
            logger.info(f"搜索完成: '{query}', 获得{len(results)}条结果")
            return results
            
        except asyncio.TimeoutError:
            logger.warning(f"搜索超时: {query}")
            return []
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return []
    
    def clear_cache(self):
        """清空搜索缓存"""
        self.search_cache.clear()
        logger.info("搜索缓存已清空")


# 全局单例
search_service = SearchService()
