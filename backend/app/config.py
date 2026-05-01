# -*- coding: utf-8 -*-
"""应用配置管理

配置优先级（低 → 高）:
  1. 代码默认值（Settings 类字段默认值）
  2. .env 文件（pydantic-settings 自动加载）
  3. 项目配置文件（paperchat.yaml）
  4. 用户 DB 设置（运行时通过 ConfigService.set 写入）

不修改现有 Settings 类，通过 ConfigService 包装实现多层覆盖链。
"""
import os
import logging
from typing import Any, Callable

# 设置 HuggingFace 镜像（国内下载加速）- 必须在导入任何 huggingface 相关库之前设置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 设置 HuggingFace 模型缓存目录（项目目录下）
_hf_cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".cache")
os.makedirs(_hf_cache_path, exist_ok=True)
os.environ['HF_HOME'] = _hf_cache_path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用配置类，从环境变量和.env文件读取配置"""
    
    # App
    APP_NAME: str = "PaperChat"
    DEBUG: bool = True

    # Default User（单用户模式下使用的默认用户 ID）
    DEFAULT_USER_ID: int = 1
    
    # Database（开发阶段使用 SQLite）
    DATABASE_URL: str = "sqlite+aiosqlite:///./paperchat.db"
    
    # DeepSeek API
    DEEPSEEK_API_KEY: str = ""

    # 默认 LLM 模型配置
    DEFAULT_LLM_MODEL: str = "deepseek-v4-flash"
    DEFAULT_LLM_BASE_URL: str = "https://api.deepseek.com"
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # 图片处理
    MAX_IMAGE_SIZE_MB: int = 10
    IMAGE_CACHE_ENABLED: bool = True

    # RAG 增强
    RAG_RERANKER_ENABLED: bool = True
    RAG_RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RAG_HYDE_ENABLED: bool = False  # 默认关闭，增加 500-1000ms 延迟
    RAG_RERANKER_TOP_K: int = 5

    # 预缓存
    PRECACHE_ENABLED: bool = False  # 默认关闭
    PRECACHE_INTERVAL_HOURS: int = 1  # 预缓存检查间隔
    PRECACHE_TTL_HOURS: int = 24  # 预缓存有效期
    PRECACHE_DEFAULT_TOPICS: str = "cs.AI,cs.CL,cs.CV"  # 默认关注领域


    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    
    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 52428800  # 50MB

    # 智能路由
    MODEL_ROUTE_MODE: str = "smart_route"  # local_only | smart_route | cloud_only
    MODEL_BUDGET_LIMIT: float = 10.0  # 月度预算上限（元）
    MODEL_CONFIRM_THRESHOLD: float = 0.5  # 单次费用确认阈值（元）
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


# ---------------------------------------------------------------------------
# Layer 3: ProjectConfig — 从 paperchat.yaml 加载项目级配置
# ---------------------------------------------------------------------------

class ProjectConfig:
    """从 paperchat.yaml 加载项目级配置（Layer 3）

    yaml 文件是可选的；若不存在，则静默忽略，不影响启动。
    推荐格式::

        rag:
          chunk_size: 512
          top_k: 5
        llm:
          temperature: 0.7
    """

    def __init__(self, yaml_path: str | None = None):
        self._data: dict = {}
        self._path = yaml_path or self._default_path()
        self._load()

    @staticmethod
    def _default_path() -> str:
        """默认在 backend/ 目录下寻找 paperchat.yaml"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "paperchat.yaml",
        )

    def _load(self) -> None:
        """尝试加载 yaml 配置文件，失败则静默回退"""
        if not os.path.isfile(self._path):
            logger.debug("ProjectConfig: %s 不存在，跳过加载", self._path)
            return
        try:
            import yaml  # type: ignore
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            self._data = self._flatten(loaded)
            logger.info("ProjectConfig: 已加载 %s (%d 项)", self._path, len(self._data))
        except ImportError:
            logger.warning("ProjectConfig: 未安装 PyYAML，跳过 paperchat.yaml 加载")
        except Exception as exc:
            logger.warning("ProjectConfig: 加载失败 (%s)，跳过", exc)

    @staticmethod
    def _flatten(d: dict, prefix: str = "") -> dict:
        """将嵌套 dict 展开为点号分隔的扁平 dict，方便 get(key) 查找"""
        items: dict = {}
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(ProjectConfig._flatten(v, full_key))
            else:
                items[full_key] = v
        return items

    def get(self, key: str, default: Any = None) -> Any:
        """查询配置值（支持点号路径，如 'rag.chunk_size'）"""
        return self._data.get(key, default)


project_config = ProjectConfig()


# ---------------------------------------------------------------------------
# ConfigService — 四层覆盖链统一访问入口
# ---------------------------------------------------------------------------

class ConfigService:
    """四层配置覆盖链服务

    查找优先级（高 → 低）:
      Layer 4 user_db  > Layer 3 yaml  > Layer 2 .env  > Layer 1 defaults

    公共 API:
      get(key, default)         — 按优先级查找配置值
      set(key, value, layer)    — 写入指定层（默认 user 层，内存）
      on_change(key, callback)  — 注册配置变更回调（为 WebSocket 推送预留）

    注意:
      - set() 当前仅操作内存层（user_db）；重启后失效。
        如需持久化，请将写入逻辑扩展到数据库。
      - 推理速度影响：get() 为纯内存 dict 查找，O(1)，无额外开销。
        on_change 回调同步触发，回调函数本身的耗时由调用方控制。
    """

    def __init__(
        self,
        base_settings: Settings,
        project_cfg: ProjectConfig,
    ):
        self._settings = base_settings
        self._project_cfg = project_cfg
        # Layer 4: 用户/运行时覆盖（内存，按 layer 标签分桶）
        self._user_layer: dict[str, Any] = {}
        # 变更回调注册表
        self._callbacks: dict[str, list[Callable]] = {}

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """按优先级查找配置值。

        查找顺序: user_db → paperchat.yaml → Settings（含 .env）→ default

        Args:
            key: 配置键名（对 Settings 字段使用大写，如 'DEBUG'；
                 yaml 层使用点号路径，如 'rag.chunk_size'）
            default: 所有层均未找到时的回退值

        Returns:
            找到的第一个值，或 default
        """
        # Layer 4: user_db 内存层
        if key in self._user_layer:
            return self._user_layer[key]

        # Layer 3: paperchat.yaml
        yaml_val = self._project_cfg.get(key)
        if yaml_val is not None:
            return yaml_val

        # Layer 2+1: Settings（.env + 代码默认值）
        settings_val = getattr(self._settings, key, None)
        if settings_val is not None:
            return settings_val

        return default

    def set(self, key: str, value: Any, layer: str = "user") -> None:
        """设置配置值（当前写入内存 user 层）。

        Args:
            key: 配置键名
            value: 配置值
            layer: 目标层标识（预留扩展，当前统一写内存）
        """
        old_value = self._user_layer.get(key)
        self._user_layer[key] = value
        logger.debug("ConfigService.set: key=%s layer=%s value=%r", key, layer, value)

        # 触发变更回调
        if key in self._callbacks and old_value != value:
            for cb in self._callbacks[key]:
                try:
                    cb(key, value)
                except Exception as exc:
                    logger.warning("ConfigService: 变更回调异常 key=%s err=%s", key, exc)

    def on_change(self, key: str, callback: Callable) -> None:
        """注册配置变更回调（为 WebSocket 实时推送预留接口）。

        当 set(key, ...) 修改配置且值发生变化时，所有已注册回调将被同步触发。
        回调签名: callback(key: str, new_value: Any) -> None

        注意: 回调在 set() 调用线程中同步执行，请避免阻塞操作。

        Args:
            key: 监听的配置键名
            callback: 回调函数
        """
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)
        logger.debug("ConfigService.on_change: 注册回调 key=%s", key)


# 全局单例（在 app/main.py 的 lifespan 中注册到 app.state）
config_service = ConfigService(
    base_settings=settings,
    project_cfg=project_config,
)
