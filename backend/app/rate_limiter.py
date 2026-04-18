"""请求限流配置

独立模块，避免循环导入。
路由文件可从此处导入 limiter 实例。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 请求限流器（基于客户端 IP 地址限流）
limiter = Limiter(key_func=get_remote_address)
