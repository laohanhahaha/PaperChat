"""全局异常处理中间件

统一处理应用中的各种异常，返回标准化的错误响应
"""
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: ValidationError):
    """处理 Pydantic 验证错误"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": {"errors": errors}
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """处理数据库异常"""
    # 记录详细错误日志（生产环境应该使用日志框架）
    logger.error(f"Database error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "数据库操作失败",
            "data": None
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """处理所有其他未捕获的异常"""
    # 记录详细错误日志
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None
        }
    )


def setup_error_handlers(app: FastAPI):
    """
    为 FastAPI 应用设置全局异常处理器
    
    用法:
        app = FastAPI()
        setup_error_handlers(app)
    """
    # Pydantic 验证错误
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # HTTP 异常
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    # 数据库异常
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    
    # 通用异常（捕获所有其他异常）
    app.add_exception_handler(Exception, general_exception_handler)
