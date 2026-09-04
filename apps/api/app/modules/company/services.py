"""Company Trust 生命周期、翻译与公开 DTO 服务。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.company.models import (
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
)
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import invalidate_publication_after_translation_edit
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import create_content_route
from app.modules.discovery.models import GeoDocument, SeoDocument
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


async def _lifecycle(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale: Locale, slug: str) -> None:
    """为可独立公开的 Trust 实体幂等创建统一翻译/发布/路由记录。"""
    await _translation_lifecycle(session, owner_type, owner_id, locale)
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == owner_id, ContentPublication.locale_id == locale.id))
    if publication is None:
        session.add(ContentPublication(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, status="draft"))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == owner_id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True)))
    if route is None:
        await create_content_route(session, owner_type, owner_id, locale, f"/{locale.slug}/{_PATHS[owner_type]}/{slug}/")


async def _translation_lifecycle(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale: Locale) -> TranslationStatus:
    """输入 Trust owner 与语言；输出幂等 TranslationStatus，防止草稿正文泄露。"""
    status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == owner_id, TranslationStatus.locale_id == locale.id))
    if status is None:
        status = TranslationStatus(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, source_locale_id=locale.id, status="draft")
        session.add(status)
        await session.flush()
    return status


async def upsert_company_profile(session: AsyncSession, payload: Any, actor_id: uuid.UUID) -> CompanyProfile:
    """创建或更新唯一公司档案，并保存真实翻译。"""
    profile = await session.scalar(select(CompanyProfile).order_by(CompanyProfile.created_at).limit(1))
    if profile is None:
        profile = CompanyProfile(**{key: value for key, value in payload.model_dump().items() if key != "translations"})
        session.add(profile)
    else:
        for key, value in payload.model_dump().items():
            if key != "translations":
                setattr(profile, key, value)
    await session.flush()
    await _save_translations(session, profile, CompanyProfileTranslation, "company_profile_id", payload.translations)
    write_audit_log(session, action="company_profile.update", target_type="company_profile", target_id=str(profile.id), user_id=actor_id)
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
    rows = (await session.execute(
        select(model, translation_model)
        .join(translation_model, getattr(translation_model, owner_field) == model.id)
        .join(TranslationStatus, (TranslationStatus.owner_type == owner_type) & (TranslationStatus.owner_id == model.id) & (TranslationStatus.locale_id == locale.id))
        .where(model.status == "enabled", translation_model.locale_id == locale.id, TranslationStatus.status == "published")
        .order_by(model.sort_order, model.created_at)
    )).all()
    result: list[dict[str, Any]] = []
    for entity, translation in rows:
        route = None
        if has_route:
            route = await session.scalar(select(ContentRoute).join(ContentPublication, (ContentPublication.owner_type == ContentRoute.owner_type) & (ContentPublication.owner_id == ContentRoute.owner_id) & (ContentPublication.locale_id == ContentRoute.locale_id)).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True), ContentRoute.active.is_(True), ContentRoute.indexable.is_(True), ContentPublication.status == "published"))
            if route is None:
                continue
        translation_data = _translation_snapshot(translation, owner_field)
        result.append({"type": owner_type, "slug": entity.slug, "title": translation_data.get("name") or translation_data.get("title"), "summary": translation_data.get("summary"), "url": route.path if route else None})
    return result


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
    status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == entity.id, TranslationStatus.locale_id == locale.id, TranslationStatus.status == "published"))
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == entity.id, ContentPublication.locale_id == locale.id, ContentPublication.status == "published"))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True), ContentRoute.active.is_(True), ContentRoute.indexable.is_(True)))
    translation = await session.scalar(select(translation_model).where(getattr(translation_model, owner_field) == entity.id, translation_model.locale_id == locale.id))
    if not status or not publication or not route or not translation:
        raise AppException(404, "public_content_not_found", "公开 Trust 内容不存在")
    payload = {key: value for key, value in serialize(translation).items() if key not in {"id", owner_field, "locale_id", "created_at", "updated_at"}}
    seo = await session.scalar(select(SeoDocument).where(SeoDocument.owner_type == owner_type, SeoDocument.owner_id == entity.id, SeoDocument.locale_id == locale.id))
    geo = await session.scalar(select(GeoDocument).where(GeoDocument.owner_type == owner_type, GeoDocument.owner_id == entity.id, GeoDocument.locale_id == locale.id))
    canonical = seo.canonical_override if seo and seo.canonical_override else f"https://junhuiscrewbarrel.com{route.path}"
    alternates = []
    alternate_routes = (await session.execute(select(ContentRoute, Locale).join(Locale, Locale.id == ContentRoute.locale_id).join(ContentPublication, (ContentPublication.owner_type == ContentRoute.owner_type) & (ContentPublication.owner_id == ContentRoute.owner_id) & (ContentPublication.locale_id == ContentRoute.locale_id)).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id, ContentRoute.is_canonical.is_(True), ContentRoute.active.is_(True), ContentRoute.indexable.is_(True), ContentPublication.status == "published", Locale.is_enabled.is_(True)))).all()
    for alternate_route, alternate_locale in alternate_routes:
        alternate_seo = await session.scalar(select(SeoDocument).where(SeoDocument.owner_type == owner_type, SeoDocument.owner_id == entity.id, SeoDocument.locale_id == alternate_locale.id))
        if not alternate_seo or not alternate_seo.canonical_override:
            alternates.append({"hreflang": alternate_locale.code, "url": f"https://junhuiscrewbarrel.com{alternate_route.path}"})
    return {
        "type": owner_type,
        "slug": entity.slug,
        "translation": payload,
        "url": f"https://junhuiscrewbarrel.com{route.path}",
        "seo": {"title": seo.seo_title if seo else None, "description": seo.meta_description if seo else None, "canonical": canonical, "robots_index": bool(seo.robots_index) if seo else True, "hreflang": alternates},
        "geo": {"direct_answer": geo.direct_answer, "key_facts": geo.key_facts_json, "evidence": geo.evidence_json} if geo else None,
        "schema": {"@context": "https://schema.org", "@type": "WebPage", "name": payload.get("name") or payload.get("title"), "url": canonical},
    }


async def get_public_company_profile(session: AsyncSession, locale_slug: str) -> dict[str, Any]:
    """从真实 Company Profile 生成 About/Organization 公开 DTO。"""
    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    profile = await session.scalar(select(CompanyProfile).where(CompanyProfile.status == "enabled").order_by(CompanyProfile.created_at).limit(1))
    if locale is None or profile is None:
        raise AppException(404, "public_content_not_found", "公司公开档案不存在")
    translation = await session.scalar(select(CompanyProfileTranslation).where(CompanyProfileTranslation.company_profile_id == profile.id, CompanyProfileTranslation.locale_id == locale.id))
    if translation is None:
        raise AppException(404, "public_content_not_found", "公司公开档案翻译不存在")
    public = {"company_name": translation.company_name, "short_intro": translation.short_intro, "full_intro": translation.full_intro, "mission": translation.mission, "advantages": translation.advantages_json, "founded_year": profile.founded_year, "years_experience": profile.years_experience, "employee_count_range": profile.employee_count_range, "factory_area_sqm": profile.factory_area_sqm, "annual_capacity_text": profile.annual_capacity_text, "export_markets": profile.export_markets_json, "phone": profile.public_phone, "email": profile.public_email, "address": profile.public_address, "url": "https://junhuiscrewbarrel.com/"}
    return {**public, "schema": {"@context": "https://schema.org", "@type": "Organization", "name": translation.company_name, "url": "https://junhuiscrewbarrel.com/", **({"address": {"@type": "PostalAddress", "streetAddress": profile.public_address}} if profile.public_address else {}), **({"telephone": profile.public_phone} if profile.public_phone else {}), **({"email": profile.public_email} if profile.public_email else {})}}
