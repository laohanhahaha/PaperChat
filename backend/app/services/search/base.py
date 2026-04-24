"""搜索适配器抽象基类与数据模型"""
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List, Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str           # "duckduckgo" / "bing" / "tavily" / "brave" / "baidu" / "wigolo"
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)


class SearchAdapter(ABC):
    name: str = ""
    requires_api_key: bool = False

    @abstractmethod
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[SearchResult]:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查此搜索源是否可用（API Key 有效等）"""
        ...
