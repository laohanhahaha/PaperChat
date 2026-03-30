"""应用启动脚本

用于启动 FastAPI 开发服务器

用法:
    python run.py

或直接使用 uvicorn:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import os

# 设置 HuggingFace 镜像（国内下载加速）- 必须在导入任何 huggingface 相关库之前设置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 设置 HuggingFace 模型缓存目录（项目目录下）
_hf_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(_hf_cache_path, exist_ok=True)
os.environ['HF_HOME'] = _hf_cache_path

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
