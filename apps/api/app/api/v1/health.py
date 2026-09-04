"""API 健康检查端点。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.responses import ApiResponse, success_response

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    """健康检查业务数据。"""

    status: str
    service: str
    version: str


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
