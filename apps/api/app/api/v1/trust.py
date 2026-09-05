"""Company Trust 与公开下载资源的最小真实管理 API。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.pagination import PaginationParams
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import get_current_user, require_csrf
from app.modules.company.models import CompanyProfile, CompanyProfileTranslation
from app.modules.company.schemas import CompanyProfileInput, TrustEntityInput
from app.modules.company.services import (
    TRUST_CONFIG,
    _lifecycle_records,
    create_trust_entity,
    serialize,
    update_trust_entity,
    upsert_company_profile,
)
from app.modules.content.enums import PublicationStatus, TranslationState
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/trust", tags=["trust"])


def _permission(user: User, code: str) -> None:
    """在 Trust 动态 API 中执行服务端原子权限检查。"""
    _roles, permissions = collect_authorization(user)
    if code not in permissions:
        raise AppException(403, "permission_denied", "没有执行此操作的权限")


async def _review_translation(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    user: User,
) -> None:
    """
    完成人工翻译审核，并把 draft/archived Publication 提交到 review。

    输入：数据库会话、owner 标识、语言 ID 与当前用户。
    输出：None；Publication 状态迁移全部复用 transition_publication()。
    """
    # Translation Review 与正文更新是不同职责；服务端必须先验证审核权限。
    _permission(user, "translation.review")
    publication, translation, route = await _lifecycle_records(
        session, owner_type, owner_id, locale_id
    )
    if publication.status == PublicationStatus.PUBLISHED.value:
        raise AppException(409, "published_translation_locked", "已发布翻译无需重复审核")
    _roles, permissions = collect_authorization(user)
    translation.status = TranslationState.HUMAN_REVIEWED.value
    translation.reviewed_by = user.id
    write_audit_log(
        session,
        action="translation.review",
        target_type=owner_type,
        target_id=str(owner_id),
        user_id=user.id,
        metadata={"locale_id": str(locale_id)},
    )
    if publication.status == PublicationStatus.ARCHIVED.value:
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.DRAFT,
            actor_permissions=set(permissions),
            actor_id=user.id,
        )
    if publication.status == PublicationStatus.DRAFT.value:
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.REVIEW,
            actor_permissions=set(permissions),
            actor_id=user.id,
        )


async def _non_route_translation_status(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> TranslationStatus:
    """
    读取并锁定不拥有独立路由的 Trust 翻译状态。

    输入：数据库会话、owner 类型/ID 与语言 ID。
    输出：TranslationStatus；记录不存在时抛出 409。
    """
    status = await session.scalar(
        select(TranslationStatus)
        .where(
            TranslationStatus.owner_type == owner_type,
            TranslationStatus.owner_id == owner_id,
            TranslationStatus.locale_id == locale_id,
        )
        .with_for_update()
    )
    if status is None:
        raise AppException(409, "translation_status_missing", "翻译状态记录不存在")
    return status


@router.get("/company-profile", response_model=ApiResponse[dict[str, Any]])
async def get_company_profile(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> ApiResponse[dict[str, Any]]:
    """返回公司档案与翻译。"""
    _permission(user, "company.read")
    profile = await session.scalar(select(CompanyProfile).order_by(CompanyProfile.created_at).limit(1))
    if profile is None:
        return success_response({"profile": None, "translations": [], "translation_statuses": [], "publications": [], "routes": []})
    translations = list((await session.scalars(select(CompanyProfileTranslation).where(CompanyProfileTranslation.company_profile_id == profile.id))).all())
    statuses = list((await session.scalars(select(TranslationStatus).where(TranslationStatus.owner_type == "company_profile", TranslationStatus.owner_id == profile.id))).all())
    publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == "company_profile", ContentPublication.owner_id == profile.id))).all())
    routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == "company_profile", ContentRoute.owner_id == profile.id))).all())
    return success_response({"profile": serialize(profile), "translations": [serialize(item) for item in translations], "translation_statuses": [serialize(item) for item in statuses], "publications": [serialize(item) for item in publications], "routes": [serialize(item) for item in routes]})


@router.put("/company-profile", response_model=ApiResponse[dict[str, Any]])
async def put_company_profile(payload: CompanyProfileInput, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建或更新唯一 Company Profile。"""
    _permission(user, "company.update")
    profile = await upsert_company_profile(session, payload, user.id)
    await session.commit()
    return success_response(serialize(profile))


@router.post("/company-profile/{profile_id}/translations/{locale_id}/review", response_model=ApiResponse[dict[str, str]])
async def review_company_profile_translation(
    profile_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """审核 Company Profile 翻译并将 Publication 提交审核。"""
    if await session.get(CompanyProfile, profile_id) is None:
        raise AppException(404, "company_profile_not_found", "Company Profile 不存在")
    await _review_translation(
        session,
        owner_type="company_profile",
        owner_id=profile_id,
        locale_id=locale_id,
        user=user,
    )
    await session.commit()
    return success_response({"status": "human_reviewed", "publication": "review"})


@router.post("/company-profile/{profile_id}/publications/{locale_id}/{target_status}", response_model=ApiResponse[dict[str, str]])
async def transition_company_profile_publication(
    profile_id: uuid.UUID,
    locale_id: uuid.UUID,
    target_status: PublicationStatus,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """发布或归档 Company Profile，状态切换复用统一事务服务。"""
    if target_status not in {PublicationStatus.PUBLISHED, PublicationStatus.ARCHIVED}:
        raise AppException(422, "unsupported_publication_target", "该接口只允许 published 或 archived")
    if target_status is PublicationStatus.PUBLISHED:
        # Route 内容发布会同步发布 TranslationStatus，因此必须同时具备翻译发布权限。
        _permission(user, "translation.publish")
    _permission(
        user,
        "content.publish"
        if target_status is PublicationStatus.PUBLISHED
        else "content.archive",
    )
    publication, translation, route = await _lifecycle_records(
        session, "company_profile", profile_id, locale_id
    )
    _roles, permissions = collect_authorization(user)
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=target_status,
        actor_permissions=set(permissions),
        actor_id=user.id,
    )
    await session.commit()
    return success_response({"status": target_status.value})


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
    items = []
    translation_model, owner_field = config[1], config[2]
    for row in rows:
        translations = list((await session.scalars(select(translation_model).where(getattr(translation_model, owner_field) == row.id))).all())
        item = {**serialize(row), "translations": [serialize(item) for item in translations]}
        statuses = list((await session.scalars(select(TranslationStatus).where(TranslationStatus.owner_type == config[3], TranslationStatus.owner_id == row.id))).all())
        item["translation_statuses"] = [serialize(value) for value in statuses]
        if config[4]:
            publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == config[3], ContentPublication.owner_id == row.id))).all())
            routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == config[3], ContentRoute.owner_id == row.id))).all())
            item.update({"publications": [serialize(value) for value in publications], "routes": [serialize(value) for value in routes]})
        else:
            # Non-route Trust 只拥有 TranslationStatus，明确返回空数组防止 Admin 误判。
            item.update({"publications": [], "routes": []})
        items.append(item)
    return success_response({"items": items, "page": pagination.page, "page_size": pagination.page_size, "total": total or 0})


@router.get("/{resource}/{entity_id}", response_model=ApiResponse[dict[str, Any]])
async def get_trust_detail(resource: str, entity_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> ApiResponse[dict[str, Any]]:
    """读取单个 Trust 主实体、翻译与统一生命周期状态。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    _permission(user, f"{config[3].replace('manufacturing_capability', 'capability')}.read")
    model, translation_model, owner_field, owner_type, _has_route = config
    entity = await session.get(model, entity_id)
    if entity is None:
        raise AppException(404, "trust_not_found", "Trust 实体不存在")
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus

    translations = list((await session.scalars(select(translation_model).where(getattr(translation_model, owner_field) == entity.id))).all())
    statuses = list((await session.scalars(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == entity.id))).all())
    publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == entity.id))).all())
    routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id))).all())
    return success_response({"entity": serialize(entity), "translations": [serialize(item) for item in translations], "translation_statuses": [serialize(item) for item in statuses], "publications": [serialize(item) for item in publications], "routes": [serialize(item) for item in routes]})


@router.post("/{resource}/{entity_id}/translations/{locale_id}/review", response_model=ApiResponse[dict[str, str]])
async def review_trust_translation(
    resource: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """审核 Trust 翻译；独立页面同时把 Publication 提交 review。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    entity = await session.get(config[0], entity_id)
    if entity is None:
        raise AppException(404, "trust_not_found", "Trust 实体不存在")
    if config[4]:
        await _review_translation(
            session,
            owner_type=config[3],
            owner_id=entity_id,
            locale_id=locale_id,
            user=user,
        )
        response = {"status": "human_reviewed", "publication": "review"}
    else:
        _permission(user, "translation.review")
        status = await _non_route_translation_status(
            session,
            owner_type=config[3],
            owner_id=entity_id,
            locale_id=locale_id,
        )
        if status.status != TranslationState.DRAFT.value:
            raise AppException(
                409,
                "translation_not_reviewable",
                "只有 draft 翻译可以人工审核",
            )
        status.status = TranslationState.HUMAN_REVIEWED.value
        status.reviewed_by = user.id
        status.published_at = None
        write_audit_log(
            session,
            action="translation.review",
            target_type=config[3],
            target_id=str(entity_id),
            user_id=user.id,
            metadata={"locale_id": str(locale_id)},
        )
        response = {"status": "human_reviewed"}
    await session.commit()
    return success_response(response)


@router.post("/{resource}/{entity_id}/translations/{locale_id}/publish", response_model=ApiResponse[dict[str, str]])
async def publish_trust_translation(
    resource: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    发布无独立 Route/Publication 的 Trust 翻译。

    输入：Trust 资源、实体/语言 ID、数据库会话与当前用户。
    输出：ApiResponse；仅 human_reviewed 且 enabled 的翻译可发布。
    """
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    if config[4]:
        raise AppException(409, "publication_required", "独立页面必须通过统一 Publication 发布")
    _permission(user, "translation.publish")
    entity = await session.get(config[0], entity_id)
    if entity is None:
        raise AppException(404, "trust_not_found", "Trust 实体不存在")
    if entity.status != "enabled":
        raise AppException(409, "trust_not_enabled", "禁用或退役 Trust 不能发布")
    status = await _non_route_translation_status(
        session,
        owner_type=config[3],
        owner_id=entity_id,
        locale_id=locale_id,
    )
    if status.status != TranslationState.HUMAN_REVIEWED.value:
        raise AppException(
            409,
            "translation_not_reviewed",
            "翻译完成人工审核后才能发布",
        )
    status.status = TranslationState.PUBLISHED.value
    status.published_at = datetime.now(UTC)
    write_audit_log(
        session,
        action="translation.publish",
        target_type=config[3],
        target_id=str(entity_id),
        user_id=user.id,
        metadata={"locale_id": str(locale_id)},
    )
    await session.commit()
    return success_response({"status": "published"})


@router.post("/{resource}/{entity_id}/publications/{locale_id}/{target_status}", response_model=ApiResponse[dict[str, str]])
async def transition_trust_publication(
    resource: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    target_status: PublicationStatus,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """发布或归档可独立公开 Trust，复用统一发布事务。"""
    config = TRUST_CONFIG.get(resource)
    if config is None or not config[4]:
        raise AppException(409, "trust_not_publishable", "该 Trust 类型没有独立公开页面")
    if target_status not in {PublicationStatus.PUBLISHED, PublicationStatus.ARCHIVED}:
        raise AppException(422, "unsupported_publication_target", "该接口只允许 published 或 archived")
    if target_status is PublicationStatus.PUBLISHED:
        # 独立 Trust 页面沿用统一事务，并同时验证翻译与内容发布职责。
        _permission(user, "translation.publish")
    _permission(
        user,
        "content.publish"
        if target_status is PublicationStatus.PUBLISHED
        else "content.archive",
    )
    publication, translation, route = await _lifecycle_records(
        session, config[3], entity_id, locale_id
    )
    _roles, permissions = collect_authorization(user)
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=target_status,
        actor_permissions=set(permissions),
        actor_id=user.id,
    )
    await session.commit()
    return success_response({"status": target_status.value})


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
