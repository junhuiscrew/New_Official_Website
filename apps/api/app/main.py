"""FastAPI 应用工厂与默认 ASGI 应用。"""

from fastapi import FastAPI

from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    """
    创建配置完整的 FastAPI 应用实例。

    输入：无。

    输出：FastAPI，已注册 v1 路由与统一异常处理器的 ASGI 应用。
    """
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
    )
    register_exception_handlers(application)
    application.include_router(api_v1_router)
    return application


app = create_app()
