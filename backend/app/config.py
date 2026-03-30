"""应用配置管理"""
import os

# 设置 HuggingFace 镜像（国内下载加速）- 必须在导入任何 huggingface 相关库之前设置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 设置 HuggingFace 模型缓存目录（项目目录下）
_hf_cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".cache")
os.makedirs(_hf_cache_path, exist_ok=True)
os.environ['HF_HOME'] = _hf_cache_path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类，从环境变量和.env文件读取配置"""
    
    # App
    APP_NAME: str = "PaperChat"
    DEBUG: bool = True
    
    # Database（开发阶段使用 SQLite）
    DATABASE_URL: str = "sqlite+aiosqlite:///./paperchat.db"
    
    # DeepSeek API
    DEEPSEEK_API_KEY: str = ""
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]
    
    # Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
