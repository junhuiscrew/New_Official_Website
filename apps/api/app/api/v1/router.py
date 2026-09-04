"""聚合 API v1 的各模块路由。"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.locales import router as locales_router
from app.api.v1.rbac import router as rbac_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(locales_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(rbac_router)
