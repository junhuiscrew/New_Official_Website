"""聚合 API v1 的各模块路由。"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.authority import router as authority_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.downloads import router as downloads_router
from app.api.v1.health import router as health_router
from app.api.v1.locales import router as locales_router
from app.api.v1.media import public_router as public_media_router
from app.api.v1.media import router as media_router
from app.api.v1.presentation import router as presentation_router
from app.api.v1.privacy import public_router as public_privacy_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.public import router as public_router
from app.api.v1.rbac import router as rbac_router
from app.api.v1.rfq import public_router as public_rfq_router
from app.api.v1.rfq import router as rfq_router
from app.api.v1.trust import router as trust_router
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
api_v1_router.include_router(downloads_router)
api_v1_router.include_router(public_router)
api_v1_router.include_router(privacy_router)
api_v1_router.include_router(public_privacy_router)
api_v1_router.include_router(presentation_router)
api_v1_router.include_router(trust_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(public_media_router)
api_v1_router.include_router(rfq_router)
api_v1_router.include_router(public_rfq_router)
