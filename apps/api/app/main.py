"""FastAPI 应用工厂与默认 ASGI 应用。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    # Cookie 认证只向显式 allowlist Origin 开放，禁止通配 Origin 与凭据组合。
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type", "X-CSRF-Token"],
    )
    register_exception_handlers(application)
    application.include_router(api_v1_router)
    return application


app = create_app()
