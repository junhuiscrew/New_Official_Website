"""Company Trust 生命周期、翻译与公开 DTO 服务。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import CaseProduct, CaseTechnology
from app.modules.catalog.models import ProductTechnology
from app.modules.company.models import (
    CapabilityEquipment,
    Certificate,
    CertificateTranslation,
    CompanyProfile,
    CompanyProfileTranslation,
    Equipment,
    EquipmentTranslation,
    Exhibition,
    ExhibitionTranslation,
    Honor,
    HonorTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
    Patent,
    PatentTranslation,
    TechnologyEquipment,
)
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import invalidate_publication_after_translation_edit
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import create_content_route
from app.modules.discovery.models import GeoDocument, SeoDocument
from app.modules.discovery.schema_generator import build_breadcrumb_schema, build_webpage_schema
from app.modules.localization.models import Locale

TRUST_CONFIG: dict[str, tuple[type, type, str, str, bool]] = {
    "capabilities": (ManufacturingCapability, ManufacturingCapabilityTranslation, "capability_id", "manufacturing_capability", True),
    "equipment": (Equipment, EquipmentTranslation, "equipment_id", "equipment", False),
    "certificates": (Certificate, CertificateTranslation, "certificate_id", "certificate", False),
    "patents": (Patent, PatentTranslation, "patent_id", "patent", False),
    "honors": (Honor, HonorTranslation, "honor_id", "honor", False),
    "exhibitions": (Exhibition, ExhibitionTranslation, "exhibition_id", "exhibition", True),
}

_PATHS = {"manufacturing_capability": "capabilities", "certificate": "certificates", "patent": "patents", "honor": "honors", "exhibition": "exhibitions"}

# Trust/Downloads 集合页只包含界面用途文案，不混入任何未经审核的经营事实。
_PUBLIC_PAGE_METADATA = {
    "capabilities": {
        "en": ("Manufacturing Capabilities", "Browse published manufacturing capabilities and technical evidence."),
        "zh-cn": ("制造能力", "浏览已发布的制造能力与技术证据。"),
    },
    "certificates": {
        "en": ("Certificates", "Browse certificate records currently approved for publication."),
        "zh-cn": ("证书", "浏览当前已发布的证书记录。"),
    },
    "patents": {
        "en": ("Patents", "Browse patent records currently approved for publication."),
        "zh-cn": ("专利", "浏览当前已发布的专利记录。"),
    },
    "honors": {
        "en": ("Honors", "Browse honor records currently approved for publication."),
        "zh-cn": ("荣誉", "浏览当前已发布的荣誉记录。"),
    },
    "exhibitions": {
        "en": ("Exhibitions", "Browse exhibition information currently approved for publication."),
        "zh-cn": ("展会", "浏览当前已发布的展会信息。"),
    },
    "downloads": {
        "en": ("Downloads", "Download product and technical resources currently available to the public."),
        "zh-cn": ("资料下载", "下载当前可公开访问的产品与技术资料。"),
    },
}


def serialize(entity: Any) -> dict[str, Any]:
    """将 ORM 实体已加载列序列化，避免异步环境触发隐式数据库 IO。"""
    state = inspect(entity)
    return jsonable_encoder(
        {
            column.name: state.dict[column.name]
            for column in entity.__table__.columns
            if column.name in state.dict
        }
    )


async def _ensure_public_lifecycle(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale: Locale,
    path: str,
) -> None:
    """
    幂等创建统一翻译、发布和 canonical route。

    输入：session、owner 标识、Locale 和站内绝对 path。
    输出：None；缺失记录会以 draft/inactive/noindex 建立。
    """
    await _translation_lifecycle(session, owner_type, owner_id, locale)
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == owner_id, ContentPublication.locale_id == locale.id))
    if publication is None:
        session.add(ContentPublication(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, status="draft"))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == owner_id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True)))
    if route is None:
        await create_content_route(session, owner_type, owner_id, locale, path)


async def _lifecycle(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale: Locale, slug: str) -> None:
    """为可独立公开的 Trust 实体幂等创建统一翻译/发布/路由记录。"""
    await _ensure_public_lifecycle(
        session,
        owner_type,
        owner_id,
        locale,
        f"/{locale.slug}/{_PATHS[owner_type]}/{slug}/",
    )


async def _translation_lifecycle(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale: Locale) -> TranslationStatus:
    """输入 Trust owner 与语言；输出幂等 TranslationStatus，防止草稿正文泄露。"""
    status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == owner_id, TranslationStatus.locale_id == locale.id))
    if status is None:
        status = TranslationStatus(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, source_locale_id=locale.id, status="draft")
        session.add(status)
        await session.flush()
    return status


async def upsert_company_profile(
    session: AsyncSession,
    payload: Any,
    actor_id: uuid.UUID | None,
) -> CompanyProfile:
    """
    创建或更新唯一公司档案，并接入统一内容生命周期。

    输入：session、CompanyProfileInput 与操作人 ID。
    输出：CompanyProfile；任何已发布修改都会撤回公开状态。
    """
    profile = await session.scalar(select(CompanyProfile).order_by(CompanyProfile.created_at).limit(1))
    is_new = profile is None
    if is_new:
        profile = CompanyProfile(**{key: value for key, value in payload.model_dump().items() if key != "translations"})
        session.add(profile)
    else:
        for key, value in payload.model_dump().items():
            if key != "translations":
                setattr(profile, key, value)
    await session.flush()
    saved_translations = await _save_translations(
        session,
        profile,
        CompanyProfileTranslation,
        "company_profile_id",
        payload.translations,
    )
    for translation in saved_translations:
        locale = await session.get(Locale, translation.locale_id)
        if locale is None:
            raise AppException(422, "locale_not_found", "Company Profile 翻译语言不存在")
        await _ensure_public_lifecycle(
            session,
            "company_profile",
            profile.id,
            locale,
            f"/{locale.slug}/about/",
        )
        await store_revision(
            session,
            "company_profile",
            profile.id,
            locale.id,
            {
                "master": serialize(profile),
                "translation": _translation_snapshot(
                    translation, "company_profile_id"
                ),
            },
            actor_id,
        )

    if not is_new:
        # Company Profile 主字段对所有语言均可见，因此任意更新都撤回全部已发布语言。
        publications = list(
            (
                await session.scalars(
                    select(ContentPublication).where(
                        ContentPublication.owner_type == "company_profile",
                        ContentPublication.owner_id == profile.id,
                    )
                )
            ).all()
        )
        for publication in publications:
            lifecycle_publication, translation_status, route = await _lifecycle_records(
                session, "company_profile", profile.id, publication.locale_id
            )
            await invalidate_publication_after_translation_edit(
                session,
                publication=lifecycle_publication,
                translation=translation_status,
                route=route,
                actor_id=actor_id,
            )

    if profile.status in {"disabled", "retired"}:
        publications = list(
            (
                await session.scalars(
                    select(ContentPublication).where(
                        ContentPublication.owner_type == "company_profile",
                        ContentPublication.owner_id == profile.id,
                    )
                )
            ).all()
        )
        routes = list(
            (
                await session.scalars(
                    select(ContentRoute).where(
                        ContentRoute.owner_type == "company_profile",
                        ContentRoute.owner_id == profile.id,
                    )
                )
            ).all()
        )
        for publication in publications:
            publication.status = "archived"
            publication.published_at = None
            publication.scheduled_at = None
        for route in routes:
            route.active = False
            route.indexable = False
    write_audit_log(
        session,
        action="company_profile.create" if is_new else "company_profile.update",
        target_type="company_profile",
        target_id=str(profile.id),
        user_id=actor_id,
    )
    await session.flush()
    return profile


async def create_trust_entity(session: AsyncSession, resource: str, payload: Any, actor_id: uuid.UUID | None) -> Any:
    """创建 Trust 实体、翻译及适用的统一生命周期记录。"""
    model, translation_model, owner_field, owner_type, has_route = TRUST_CONFIG[resource]
    fields = {key: value for key, value in payload.fields.items() if key in model.__table__.columns}
    entity = model(slug=payload.slug, status=payload.status, sort_order=payload.sort_order, **fields)
    session.add(entity)
    await session.flush()
    saved_translations = await _save_translations(session, entity, translation_model, owner_field, payload.translations)
    for locale in await session.scalars(select(Locale).where(Locale.is_enabled.is_(True)).order_by(Locale.sort_order)):
        if any(item.locale_id == locale.id for item in payload.translations):
            if has_route:
                await _lifecycle(session, owner_type, entity.id, locale, entity.slug)
            else:
                await _translation_lifecycle(session, owner_type, entity.id, locale)
    for translation in saved_translations:
        await store_revision(
            session,
            owner_type,
            entity.id,
            translation.locale_id,
            {"master": serialize(entity), "translation": _translation_snapshot(translation, owner_field)},
            actor_id,
        )
    write_audit_log(session, action=f"{owner_type}.create", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    return entity


async def update_trust_entity(session: AsyncSession, resource: str, entity_id: uuid.UUID, payload: Any, actor_id: uuid.UUID | None) -> Any:
    """更新 Trust，并同步翻译失效、Slug 路由和实体下线生命周期。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    model, translation_model, owner_field, owner_type, has_route = config
    entity = await session.get(model, entity_id)
    if entity is None:
        raise AppException(404, "trust_not_found", "Trust 实体不存在")
    values = payload.model_dump(exclude_unset=True)
    old_slug = entity.slug
    old_status = entity.status
    requested_slug = values.get("slug", old_slug)
    if requested_slug != old_slug and has_route:
        published = await session.scalar(
            select(ContentPublication.id).where(
                ContentPublication.owner_type == owner_type,
                ContentPublication.owner_id == entity.id,
                ContentPublication.status == "published",
            )
        )
        if published is not None:
            raise AppException(409, "published_slug_frozen", "已发布 Trust Slug 必须使用 URL Change Transaction")
    for key, value in values.items():
        if key in {"translations", "fields"}:
            continue
        if key in model.__table__.columns:
            setattr(entity, key, value)
    for key, value in payload.fields.items():
        if key in model.__table__.columns:
            setattr(entity, key, value)
    await session.flush()
    # 在后续带 populate_existing 的生命周期锁查询前固定快照，避免异步懒加载。
    master_snapshot = serialize(entity)
    saved_translations: list[Any] = []
    if payload.translations:
        saved_translations = await _save_translations(session, entity, translation_model, owner_field, payload.translations)
        for translation in saved_translations:
            translation_snapshot = _translation_snapshot(translation, owner_field)
            locale = await session.get(Locale, translation.locale_id)
            if locale is None:
                raise AppException(422, "locale_not_found", "Trust 翻译语言不存在")
            if has_route:
                await _lifecycle(session, owner_type, entity.id, locale, entity.slug)
                publication, translation_status, route = await _lifecycle_records(
                    session, owner_type, entity.id, locale.id
                )
                await invalidate_publication_after_translation_edit(
                    session,
                    publication=publication,
                    translation=translation_status,
                    route=route,
                    actor_id=actor_id,
                )
            else:
                translation_status = await _translation_lifecycle(session, owner_type, entity.id, locale)
                translation_status.status = "draft"
                translation_status.reviewed_by = None
                translation_status.published_at = None
            await store_revision(
                session,
                owner_type,
                entity.id,
                translation.locale_id,
                {"master": master_snapshot, "translation": translation_snapshot},
                actor_id,
            )
    if requested_slug != old_slug and has_route:
        routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id, ContentRoute.is_canonical.is_(True)))).all())
        for route in routes:
            locale = await session.get(Locale, route.locale_id)
            if locale is not None:
                route.path = f"/{locale.slug}/{_PATHS[owner_type]}/{entity.slug}/"
                route.active = False
                route.indexable = False
    if old_status == "enabled" and entity.status in {"disabled", "retired"} and has_route:
        publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == entity.id))).all())
        routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id))).all())
        for publication in publications:
            publication.status = "archived"
            publication.published_at = None
            publication.scheduled_at = None
        for route in routes:
            route.active = False
            route.indexable = False
    if old_status == "enabled" and entity.status in {"disabled", "retired"} and not has_route:
        statuses = list(
            (
                await session.scalars(
                    select(TranslationStatus).where(
                        TranslationStatus.owner_type == owner_type,
                        TranslationStatus.owner_id == entity.id,
                    )
                )
            ).all()
        )
        for translation_status in statuses:
            # Non-route Trust 下线后撤回翻译发布，重新启用时不得自动恢复公开。
            translation_status.status = "draft"
            translation_status.reviewed_by = None
            translation_status.published_at = None
    if not saved_translations:
        default_locale = await session.scalar(select(Locale).where(Locale.is_default.is_(True)))
        if default_locale is not None:
            await store_revision(session, owner_type, entity.id, default_locale.id, {"master": master_snapshot}, actor_id)
    write_audit_log(session, action=f"{owner_type}.update", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    return entity


async def list_public_trust(session: AsyncSession, resource: str, locale_slug: str) -> list[dict[str, Any]]:
    """
    查询 Trust 索引页可见条目，草稿、禁用、退役和不完整路由全部排除。

    输入：session、资源复数名、语言 slug。
    输出：list[dict]，只含真实数据库字段和可公开 URL。
    """
    config = TRUST_CONFIG.get(resource)
    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    if config is None or locale is None:
        return []
    model, translation_model, owner_field, owner_type, has_route = config
    statement = (
        select(model, translation_model)
        .join(translation_model, getattr(translation_model, owner_field) == model.id)
        .join(TranslationStatus, (TranslationStatus.owner_type == owner_type) & (TranslationStatus.owner_id == model.id) & (TranslationStatus.locale_id == locale.id))
        .where(model.status == "enabled", translation_model.locale_id == locale.id, TranslationStatus.status == "published")
    )
    if has_route:
        # Route-based Trust 索引与详情复用 self-canonical、robots 和发布门禁。
        statement = (
            statement.add_columns(ContentRoute)
            .join(
                ContentRoute,
                (ContentRoute.owner_type == owner_type)
                & (ContentRoute.owner_id == model.id)
                & (ContentRoute.locale_id == locale.id),
            )
            .join(
                ContentPublication,
                (ContentPublication.owner_type == ContentRoute.owner_type)
                & (ContentPublication.owner_id == ContentRoute.owner_id)
                & (ContentPublication.locale_id == ContentRoute.locale_id),
            )
            .outerjoin(
                SeoDocument,
                (SeoDocument.owner_type == ContentRoute.owner_type)
                & (SeoDocument.owner_id == ContentRoute.owner_id)
                & (SeoDocument.locale_id == ContentRoute.locale_id),
            )
            .where(
                ContentRoute.is_canonical.is_(True),
                ContentRoute.active.is_(True),
                ContentRoute.indexable.is_(True),
                ContentPublication.status == "published",
                or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
                or_(
                    SeoDocument.id.is_(None),
                    SeoDocument.canonical_override.is_(None),
                    SeoDocument.canonical_override
                    == literal("https://junhuiscrewbarrel.com") + ContentRoute.path,
                ),
            )
        )
    rows = (await session.execute(statement.order_by(model.sort_order, model.created_at))).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        entity, translation = row[0], row[1]
        route = row[2] if has_route else None
        translation_data = _translation_snapshot(translation, owner_field)
        item = {"type": owner_type, "slug": entity.slug, "title": translation_data.get("name") or translation_data.get("title"), "summary": translation_data.get("summary"), "url": route.path if route else None}
        # Non-route Trust 聚合页需要展示结构化事实，但不创建第二套详情 Route。
        if not has_route or owner_type == "exhibition":
            item["details"] = _public_trust_details(entity, owner_type)
        result.append(item)
    return result


def _public_trust_details(entity: Any, owner_type: str) -> dict[str, Any]:
    """
    按 Trust 类型提取公开结构化事实。

    输入：entity: Any，已通过公开门禁的 Trust ORM；owner_type: str，Trust 类型。
    输出：dict[str, Any]，不含内部 ID、媒体存储字段和生命周期字段的白名单事实。
    """
    field_allowlist = {
        "manufacturing_capability": ("capability_type",),
        "equipment": (
            "equipment_type",
            "manufacturer",
            "model",
            "quantity",
            "commissioning_year",
            "precision_text",
            "capacity_text",
        ),
        "certificate": (
            "certificate_type",
            "certificate_number",
            "issuer",
            "issue_date",
            "expiry_date",
        ),
        "patent": (
            "patent_number",
            "patent_type",
            "application_number",
            "filing_date",
            "grant_date",
            "jurisdiction",
            "inventor_text",
        ),
        "honor": ("issuing_organization", "award_date"),
        "exhibition": (
            "event_name",
            "country_code",
            "city",
            "start_date",
            "end_date",
            "booth_no",
        ),
    }
    return jsonable_encoder(
        {
            field: getattr(entity, field, None)
            for field in field_allowlist.get(owner_type, ())
        }
    )


def _public_trust_breadcrumb(
    locale: Locale,
    owner_type: str,
    title: str,
    canonical: str,
) -> list[dict[str, str]]:
    """
    生成与 Trust Breadcrumb Schema 完全相同的可见路径。

    输入：locale: Locale，当前语言；owner_type: str，Trust 类型；title: str，公开标题；canonical: str，详情 canonical。
    输出：list[dict[str, str]]，使用正式域名的面包屑项。
    """
    localized = locale.slug == "zh-cn"
    collection = {
        "manufacturing_capability": ("制造能力" if localized else "Capabilities", "capabilities"),
        "exhibition": ("展会" if localized else "Exhibitions", "exhibitions"),
    }[owner_type]
    return [
        {
            "name": "首页" if localized else "Home",
            "url": f"https://junhuiscrewbarrel.com/{locale.slug}/",
        },
        {
            "name": collection[0],
            "url": f"https://junhuiscrewbarrel.com/{locale.slug}/{collection[1]}/",
        },
        {"name": title, "url": canonical},
    ]


async def get_public_page_metadata(
    session: AsyncSession,
    resource: str,
    locale_slug: str,
) -> dict[str, Any]:
    """
    生成 Trust 与 Downloads 聚合页的统一 SEO、Breadcrumb 和 Schema。

    输入：session: AsyncSession，数据库会话；resource: str，公开聚合页资源名；locale_slug: str，当前语言。
    输出：dict[str, Any]，仅含后端批准的页面级元数据。
    """
    labels = _PUBLIC_PAGE_METADATA.get(resource)
    locale = await session.scalar(
        select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True))
    )
    if labels is None or locale is None:
        raise AppException(404, "public_page_not_found", "公开聚合页不存在")
    title, description = labels["zh-cn" if locale.slug == "zh-cn" else "en"]
    origin = "https://junhuiscrewbarrel.com"
    canonical = f"{origin}/{locale.slug}/{resource}/"
    locale_rows = list(
        (
            await session.scalars(
                select(Locale)
                .where(Locale.is_enabled.is_(True))
                .order_by(Locale.sort_order, Locale.code)
            )
        ).all()
    )
    hreflang = {
        item.code: f"{origin}/{item.slug}/{resource}/" for item in locale_rows
    }
    default_locale = next((item for item in locale_rows if item.is_default), None)
    if default_locale is not None:
        hreflang["x-default"] = f"{origin}/{default_locale.slug}/{resource}/"
    breadcrumb = [
        {
            "name": "首页" if locale.slug == "zh-cn" else "Home",
            "url": f"{origin}/{locale.slug}/",
        },
        {"name": title, "url": canonical},
    ]
    return {
        "seo": {
            "title": title,
            "description": description,
            "canonical": canonical,
            "robots": "index, follow",
            "hreflang": hreflang,
        },
        "breadcrumb": breadcrumb,
        "schema": [
            build_webpage_schema(
                {"name": title, "description": description, "url": canonical}
            ),
            build_breadcrumb_schema(breadcrumb),
        ],
    }


def _translation_snapshot(translation: Any, owner_field: str) -> dict[str, Any]:
    """输入翻译 ORM 与 owner 字段；输出适合不可变 Revision 的业务字段快照。"""
    return {
        key: value
        for key, value in serialize(translation).items()
        if key not in {"id", owner_field, "locale_id", "created_at", "updated_at"}
    }


async def _lifecycle_records(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale_id: uuid.UUID) -> tuple[ContentPublication, TranslationStatus, ContentRoute]:
    """输入 owner 与 locale；输出完整发布、翻译状态和 canonical route 三元组。"""
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == owner_id, ContentPublication.locale_id == locale_id))
    translation = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == owner_id, TranslationStatus.locale_id == locale_id))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == owner_id, ContentRoute.locale_id == locale_id, ContentRoute.is_canonical.is_(True)))
    if publication is None or translation is None or route is None:
        raise AppException(409, "trust_lifecycle_incomplete", "Trust 生命周期记录不完整")
    return publication, translation, route


async def _save_translations(session: AsyncSession, entity: Any, translation_model: type, owner_field: str, translations: list[Any]) -> list[Any]:
    """输入实体和翻译；输出本次创建或更新的翻译 ORM，不覆盖未提交语言。"""
    saved: list[Any] = []
    for item in translations:
        values = {owner_field: entity.id, "locale_id": item.locale_id}
        allowed = set(translation_model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at"}
        values.update({key: value for key, value in item.fields.items() if key in allowed})
        if "name" in allowed and "name" not in values and "title" in values:
            values["name"] = values["title"]
        existing = await session.scalar(select(translation_model).where(getattr(translation_model, owner_field) == entity.id, translation_model.locale_id == item.locale_id))
        if existing is None:
            existing = translation_model(**values)
            session.add(existing)
        else:
            for key, value in values.items():
                if key not in {owner_field, "locale_id"}:
                    setattr(existing, key, value)
        await session.flush()
        saved.append(existing)
    return saved


async def _public_capability_equipment(
    session: AsyncSession,
    capability_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    查询能力页面可见的设备结构化模块。

    输入：数据库会话、制造能力 ID 与语言 ID。
    输出：list[dict]；仅返回 enabled 且 TranslationStatus=published 的关联设备。
    """
    rows = (
        await session.execute(
            select(CapabilityEquipment, Equipment, EquipmentTranslation)
            .join(Equipment, CapabilityEquipment.equipment_id == Equipment.id)
            .join(
                EquipmentTranslation,
                (EquipmentTranslation.equipment_id == Equipment.id)
                & (EquipmentTranslation.locale_id == locale_id),
            )
            .join(
                TranslationStatus,
                (TranslationStatus.owner_type == "equipment")
                & (TranslationStatus.owner_id == Equipment.id)
                & (TranslationStatus.locale_id == locale_id),
            )
            .where(
                CapabilityEquipment.capability_id == capability_id,
                Equipment.status == "enabled",
                TranslationStatus.status == "published",
            )
            .order_by(
                CapabilityEquipment.sort_order,
                Equipment.sort_order,
                Equipment.created_at,
            )
        )
    ).all()
    result: list[dict[str, Any]] = []
    for _relation, equipment, translation in rows:
        result.append(
            {
                "slug": equipment.slug,
                "equipment_type": equipment.equipment_type,
                "manufacturer": equipment.manufacturer,
                "model": equipment.model,
                "quantity": equipment.quantity,
                "commissioning_year": equipment.commissioning_year,
                "precision_text": equipment.precision_text,
                "capacity_text": equipment.capacity_text,
                "featured": equipment.featured,
                "translation": _translation_snapshot(
                    translation,
                    "equipment_id",
                ),
            }
        )
    return result


async def _public_capability_relations(
    session: AsyncSession,
    capability_id: uuid.UUID,
    locale: Locale,
) -> dict[str, list[dict[str, str]]]:
    """
    沿既有显式 Equipment/Technology/Product/Case 关系返回公开 canonical links。

    输入：session: AsyncSession，数据库会话；capability_id: UUID，能力 ID；locale: Locale，当前语言。
    输出：dict[str, list[dict[str, str]]]，目标均再次通过统一发布与 canonical 门禁。
    """
    technology_ids = list(
        (
            await session.scalars(
                select(TechnologyEquipment.technology_id)
                .join(
                    CapabilityEquipment,
                    CapabilityEquipment.equipment_id == TechnologyEquipment.equipment_id,
                )
                .join(Equipment, Equipment.id == TechnologyEquipment.equipment_id)
                .join(
                    TranslationStatus,
                    (TranslationStatus.owner_type == "equipment")
                    & (TranslationStatus.owner_id == Equipment.id)
                    & (TranslationStatus.locale_id == locale.id),
                )
                .where(
                    CapabilityEquipment.capability_id == capability_id,
                    Equipment.status == "enabled",
                    TranslationStatus.status == "published",
                )
                .order_by(TechnologyEquipment.sort_order)
            )
        ).all()
    )
    product_ids = (
        list(
            (
                await session.scalars(
                    select(ProductTechnology.product_id)
                    .where(ProductTechnology.technology_id.in_(technology_ids))
                    .order_by(ProductTechnology.sort_order)
                )
            ).all()
        )
        if technology_ids
        else []
    )
    case_ids = []
    if technology_ids:
        case_ids.extend(
            (
                await session.scalars(
                    select(CaseTechnology.case_study_id)
                    .where(CaseTechnology.technology_id.in_(technology_ids))
                    .order_by(CaseTechnology.sort_order)
                )
            ).all()
        )
    if product_ids:
        case_ids.extend(
            (
                await session.scalars(
                    select(CaseProduct.case_study_id)
                    .where(CaseProduct.product_id.in_(product_ids))
                    .order_by(CaseProduct.sort_order)
                )
            ).all()
        )

    from app.modules.discovery.public_delivery import _published_links_for_ids

    return {
        "technologies": await _published_links_for_ids(
            session, "technology", technology_ids, locale
        ),
        "products": await _published_links_for_ids(
            session, "product", product_ids, locale
        ),
        "cases": await _published_links_for_ids(
            session, "case_study", case_ids, locale
        ),
    }


async def get_public_trust(session: AsyncSession, owner_type: str, locale_slug: str, slug: str) -> dict[str, Any]:
    """按统一发布门槛返回公开 Trust DTO；Equipment 不允许独立公开页。"""
    if owner_type == "equipment":
        raise AppException(404, "public_content_not_found", "设备仅作为能力页面结构化模块")
    resource = next((key for key, value in TRUST_CONFIG.items() if value[3] == owner_type), None)
    if resource is None:
        raise AppException(404, "public_content_not_found", "公开 Trust 内容不存在")
    model, translation_model, owner_field, _owner, _route = TRUST_CONFIG[resource]
    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    entity = await session.scalar(select(model).where(model.slug == slug, model.status == "enabled"))
    if locale is None or entity is None:
        raise AppException(404, "public_content_not_found", "公开 Trust 内容不存在")
    from app.modules.discovery.public_delivery import _public_route

    route, seo, geo = await _public_route(session, owner_type, entity.id, locale.id)
    if (
        seo
        and seo.canonical_override
        and seo.canonical_override != f"https://junhuiscrewbarrel.com{route.path}"
    ):
        raise AppException(404, "public_content_not_found", "公开 Trust canonical 不可索引")
    translation = await session.scalar(select(translation_model).where(getattr(translation_model, owner_field) == entity.id, translation_model.locale_id == locale.id))
    if not translation:
        raise AppException(404, "public_content_not_found", "公开 Trust 内容不存在")
    payload = {key: value for key, value in serialize(translation).items() if key not in {"id", owner_field, "locale_id", "created_at", "updated_at"}}
    canonical = seo.canonical_override if seo and seo.canonical_override else f"https://junhuiscrewbarrel.com{route.path}"
    # 与 Product/Case/Knowledge 共用同一严格规则，避免 Trust 产生第二套 hreflang 判定。
    from app.modules.discovery.public_delivery import _published_alternates

    published_alternates = await _published_alternates(session, owner_type, entity.id)
    alternates = [
        {"hreflang": hreflang, "url": url}
        for hreflang, url in published_alternates.items()
    ]
    equipment = (
        await _public_capability_equipment(session, entity.id, locale.id)
        if owner_type == "manufacturing_capability"
        else None
    )
    title = payload.get("name") or payload.get("title")
    breadcrumb = _public_trust_breadcrumb(locale, owner_type, title, canonical)
    # 媒体仍经统一 public-media 状态白名单解析，不向前端暴露媒体 ID 或存储路径。
    from app.modules.discovery.public_delivery import _public_media

    primary_media = await _public_media(
        session,
        getattr(entity, "primary_media_id", None),
        locale.id,
        title,
        loading="eager",
    )
    relations = (
        await _public_capability_relations(session, entity.id, locale)
        if owner_type == "manufacturing_capability"
        else None
    )
    return {
        "type": owner_type,
        "slug": entity.slug,
        "translation": payload,
        "url": f"https://junhuiscrewbarrel.com{route.path}",
        "details": _public_trust_details(entity, owner_type),
        "seo": {"title": seo.seo_title if seo else None, "description": seo.meta_description if seo else None, "canonical": canonical, "robots_index": bool(seo.robots_index) if seo else True, "robots_follow": bool(seo.robots_follow) if seo else True, "hreflang": alternates},
        "geo": {"direct_answer": geo.direct_answer, "key_facts": geo.key_facts_json or [], "evidence": geo.evidence_json or [], "related_questions": geo.related_questions_json or [], "last_reviewed_at": geo.last_reviewed_at} if geo else None,
        "breadcrumb": breadcrumb,
        "schema": [
            build_webpage_schema({"name": title, "description": payload.get("summary"), "url": canonical}),
            build_breadcrumb_schema(breadcrumb),
        ],
        "primary_media": primary_media.model_dump() if primary_media else None,
        "media": [primary_media.model_dump()] if primary_media else [],
        **({"relations": relations} if relations is not None else {}),
        **({"equipment": equipment} if equipment is not None else {}),
    }


async def get_public_company_profile(session: AsyncSession, locale_slug: str) -> dict[str, Any]:
    """
    从正式发布的 Company Profile 生成 About/Organization 公开 DTO。

    输入：session 与语言 slug。
    输出：包含 SEO/GEO、严格 hreflang 和 Organization Schema 的公开 DTO。
    """
    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    profile = await session.scalar(select(CompanyProfile).where(CompanyProfile.status == "enabled").order_by(CompanyProfile.created_at).limit(1))
    if locale is None or profile is None:
        raise AppException(404, "public_content_not_found", "公司公开档案不存在")
    translation = await session.scalar(select(CompanyProfileTranslation).where(CompanyProfileTranslation.company_profile_id == profile.id, CompanyProfileTranslation.locale_id == locale.id))
    status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == "company_profile", TranslationStatus.owner_id == profile.id, TranslationStatus.locale_id == locale.id, TranslationStatus.status == "published"))
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == "company_profile", ContentPublication.owner_id == profile.id, ContentPublication.locale_id == locale.id, ContentPublication.status == "published"))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == "company_profile", ContentRoute.owner_id == profile.id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True), ContentRoute.active.is_(True), ContentRoute.indexable.is_(True)))
    if translation is None or status is None or publication is None or route is None:
        raise AppException(404, "public_content_not_found", "公司公开档案尚未正式发布")
    seo = await session.scalar(select(SeoDocument).where(SeoDocument.owner_type == "company_profile", SeoDocument.owner_id == profile.id, SeoDocument.locale_id == locale.id))
    geo = await session.scalar(select(GeoDocument).where(GeoDocument.owner_type == "company_profile", GeoDocument.owner_id == profile.id, GeoDocument.locale_id == locale.id))
    canonical = seo.canonical_override if seo and seo.canonical_override else f"https://junhuiscrewbarrel.com{route.path}"
    from app.modules.discovery.public_delivery import _published_alternates

    published_alternates = await _published_alternates(
        session, "company_profile", profile.id
    )
    alternates = [
        {"hreflang": hreflang, "url": url}
        for hreflang, url in published_alternates.items()
    ]
    public = {"company_name": translation.company_name, "short_intro": translation.short_intro, "full_intro": translation.full_intro, "mission": translation.mission, "advantages": translation.advantages_json, "founded_year": profile.founded_year, "years_experience": profile.years_experience, "employee_count_range": profile.employee_count_range, "factory_area_sqm": profile.factory_area_sqm, "annual_capacity_text": profile.annual_capacity_text, "export_markets": profile.export_markets_json, "phone": profile.public_phone, "email": profile.public_email, "address": profile.public_address, "url": f"https://junhuiscrewbarrel.com{route.path}"}
    localized = locale.slug == "zh-cn"
    breadcrumb = [
        {
            "name": "首页" if localized else "Home",
            "url": f"https://junhuiscrewbarrel.com/{locale.slug}/",
        },
        {"name": translation.company_name, "url": canonical},
    ]
    organization_schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": translation.company_name,
        "url": "https://junhuiscrewbarrel.com/",
        **(
            {
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": profile.public_address,
                }
            }
            if profile.public_address
            else {}
        ),
        **({"telephone": profile.public_phone} if profile.public_phone else {}),
        **({"email": profile.public_email} if profile.public_email else {}),
        "mainEntityOfPage": canonical,
    }
    return {
        **public,
        "seo": {
            "title": seo.seo_title if seo else None,
            "description": seo.meta_description if seo else None,
            "canonical": canonical,
            "robots_index": bool(seo.robots_index) if seo else True,
            "robots_follow": bool(seo.robots_follow) if seo else True,
            "hreflang": alternates,
        },
        "geo": {"direct_answer": geo.direct_answer, "key_facts": geo.key_facts_json or [], "evidence": geo.evidence_json or [], "related_questions": geo.related_questions_json or [], "last_reviewed_at": geo.last_reviewed_at} if geo else None,
        "breadcrumb": breadcrumb,
        "schema": [organization_schema, build_breadcrumb_schema(breadcrumb)],
    }
