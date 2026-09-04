"""聚合 API v1 的各模块路由。"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.authority import router as authority_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.locales import router as locales_router
from app.api.v1.public import router as public_router
from app.api.v1.rbac import router as rbac_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(locales_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(rbac_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(authority_router)
api_v1_router.include_router(discovery_router)
api_v1_router.include_router(public_router)
