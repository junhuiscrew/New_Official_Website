"""Company Trust 与公开下载资源的最小真实管理 API。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.pagination import PaginationParams
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import get_current_user, require_csrf
from app.modules.company.models import CompanyProfile, CompanyProfileTranslation
from app.modules.company.schemas import CompanyProfileInput, TrustEntityInput
from app.modules.company.services import (
    TRUST_CONFIG,
    create_trust_entity,
    serialize,
    update_trust_entity,
    upsert_company_profile,
)
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/trust", tags=["trust"])


def _permission(user: User, code: str) -> None:
    """在 Trust 动态 API 中执行服务端原子权限检查。"""
    _roles, permissions = collect_authorization(user)
    if code not in permissions:
        raise AppException(403, "permission_denied", "没有执行此操作的权限")


@router.get("/company-profile", response_model=ApiResponse[dict[str, Any]])
async def get_company_profile(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> ApiResponse[dict[str, Any]]:
    """返回公司档案与翻译。"""
    _permission(user, "company.read")
    profile = await session.scalar(select(CompanyProfile).order_by(CompanyProfile.created_at).limit(1))
    if profile is None:
        return success_response({"profile": None, "translations": []})
    translations = list((await session.scalars(select(CompanyProfileTranslation).where(CompanyProfileTranslation.company_profile_id == profile.id))).all())
    return success_response({"profile": serialize(profile), "translations": [serialize(item) for item in translations]})


@router.put("/company-profile", response_model=ApiResponse[dict[str, Any]])
async def put_company_profile(payload: CompanyProfileInput, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建或更新唯一 Company Profile。"""
    _permission(user, "company.update")
    profile = await upsert_company_profile(session, payload, user.id)
    await session.commit()
    return success_response(serialize(profile))


@router.get("/{resource}", response_model=ApiResponse[dict[str, Any]])
async def list_trust(resource: str, pagination: PaginationParams = Depends(), session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> ApiResponse[dict[str, Any]]:
    """按 Trust 类型分页读取真实记录。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    _permission(user, f"{config[3].replace('manufacturing_capability', 'capability')}.read")
    model = config[0]
    rows = list((await session.scalars(select(model).order_by(model.sort_order, model.id).offset(pagination.offset).limit(pagination.page_size))).all())
    total = await session.scalar(select(func.count()).select_from(model))
    return success_response({"items": [serialize(row) for row in rows], "page": pagination.page, "page_size": pagination.page_size, "total": total or 0})


@router.post("/{resource}", response_model=ApiResponse[dict[str, Any]], status_code=201)
async def create_trust(resource: str, payload: TrustEntityInput, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建能力、设备、证书、专利、荣誉或展会。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    _permission(user, f"{config[3].replace('manufacturing_capability', 'capability')}.create")
    entity = await create_trust_entity(session, resource, payload, user.id)
    await session.commit()
    return success_response(serialize(entity))


@router.patch("/{resource}/{entity_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_trust(resource: str, entity_id: uuid.UUID, payload: TrustEntityInput, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """更新 Trust 实体，权限仅由后端决定。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    _permission(user, f"{config[3].replace('manufacturing_capability', 'capability')}.update")
    entity = await update_trust_entity(session, resource, entity_id, payload, user.id)
    await session.commit()
    return success_response(serialize(entity))
