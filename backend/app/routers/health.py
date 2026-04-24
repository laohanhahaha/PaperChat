"""健康监控路由

提供服务健康状态的查询和手动触发检查的 API 端点。
"""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/services")
async def get_service_health(request: Request):
    """返回所有服务健康状态（读取缓存，不发起新检查）

    返回格式:
        {
            "database": {
                "status": "healthy",
                "latency_ms": 1.2,
                "message": "数据库连接正常",
                "last_checked": 1714032000.0
            },
            ...
        }
    """
    health_service = request.app.state.health_service
    results = health_service.get_cached_status()

    return {
        name: {
            "status": h.status.value,
            "latency_ms": h.latency_ms,
            "message": h.message,
            "last_checked": h.last_checked,
            "details": h.details,
        }
        for name, h in results.items()
    }


@router.post("/check")
async def trigger_health_check(request: Request):
    """手动触发健康检查（并行检查所有服务）

    返回格式同 GET /services，但会发起新的检查请求。
    注意：此操作会并行发起多个 HTTP 请求，总延迟 = 最慢的服务（≤5s）。
    """
    health_service = request.app.state.health_service
    results = await health_service.check_all()

    return {
        name: {
            "status": h.status.value,
            "latency_ms": h.latency_ms,
            "message": h.message,
            "last_checked": h.last_checked,
            "details": h.details,
        }
        for name, h in results.items()
    }
