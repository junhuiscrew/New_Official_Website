"""API 健康检查端点。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.responses import ApiResponse, success_response

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    """健康检查业务数据。"""

    status: str
    service: str
    version: str


class ReadinessData(HealthData):
    """依赖就绪状态业务数据。"""

    dependencies: dict[str, str]


@router.get("/health", response_model=ApiResponse[HealthData])
async def get_health() -> ApiResponse[HealthData]:
    """
    返回 API 进程的基础存活状态。

    输入：无。

    输出：ApiResponse[HealthData]，包含状态、服务名和版本。
    """
    settings = get_settings()
    return success_response(
        HealthData(status="healthy", service=settings.app_name, version=settings.app_version)
    )


@router.get("/health/live", response_model=ApiResponse[HealthData])
async def get_liveness() -> ApiResponse[HealthData]:
    """
    返回仅代表 API 进程存活的健康状态。

    输入：无。

    输出：ApiResponse[HealthData]，不访问外部依赖的存活响应。
    """
    return await get_health()


async def _check_redis(redis_url: str) -> bool:
    """
    创建短生命周期 Redis 客户端并执行 PING。

    输入：
        redis_url: str，Redis 连接 URL。

    输出：bool，PING 成功返回 true，连接失败返回 false。
    """
    client = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/health/ready", response_model=ApiResponse[ReadinessData])
async def get_readiness(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[ReadinessData]:
    """
    检查 API 对请求处理至关重要的 PostgreSQL 与 Redis。

    输入：
        session: AsyncSession，请求作用域数据库 session。

    输出：ApiResponse[ReadinessData]，全部关键依赖可用时返回 ready。
    """
    dependencies = {"postgresql": "unavailable", "redis": "unavailable"}
    try:
        await session.execute(text("SELECT 1"))
        dependencies["postgresql"] = "ready"
    except Exception:
        pass
    if await _check_redis(get_settings().redis_url):
        dependencies["redis"] = "ready"
    if "unavailable" in dependencies.values():
        raise AppException(
            503,
            "service_not_ready",
            "关键依赖尚未就绪",
            details={"dependencies": dependencies},
        )
    settings = get_settings()
    return success_response(
        ReadinessData(
            status="ready",
            service=settings.app_name,
            version=settings.app_version,
            dependencies=dependencies,
        )
    )
