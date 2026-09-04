"""Company Trust 生命周期、翻译与公开 DTO 服务。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
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
from app.modules.content.services.routes import create_content_route
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
    """将 ORM 实体列序列化为 Admin 可用字典。"""
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _lifecycle(session: AsyncSession, owner_type: str, owner_id: uuid.UUID, locale: Locale, slug: str) -> None:
    """为可独立公开的 Trust 实体幂等创建统一翻译/发布/路由记录。"""
    status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == owner_id, TranslationStatus.locale_id == locale.id))
    if status is None:
        session.add(TranslationStatus(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, source_locale_id=locale.id, status="draft"))
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == owner_id, ContentPublication.locale_id == locale.id))
    if publication is None:
        session.add(ContentPublication(owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, status="draft"))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == owner_id, ContentRoute.locale_id == locale.id, ContentRoute.is_canonical.is_(True)))
    if route is None:
        await create_content_route(session, owner_type, owner_id, locale, f"/{locale.slug}/{_PATHS[owner_type]}/{slug}/")


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


async def create_trust_entity(session: AsyncSession, resource: str, payload: Any, actor_id: uuid.UUID) -> Any:
    """创建 Trust 实体、翻译及适用的统一生命周期记录。"""
    model, translation_model, owner_field, owner_type, has_route = TRUST_CONFIG[resource]
    fields = {key: value for key, value in payload.fields.items() if key in model.__table__.columns}
    entity = model(slug=payload.slug, status=payload.status, sort_order=payload.sort_order, **fields)
    session.add(entity)
    await session.flush()
    await _save_translations(session, entity, translation_model, owner_field, payload.translations)
    if has_route:
        for locale in await session.scalars(select(Locale).where(Locale.is_enabled.is_(True)).order_by(Locale.sort_order)):
            if any(item.locale_id == locale.id for item in payload.translations):
                await _lifecycle(session, owner_type, entity.id, locale, entity.slug)
    write_audit_log(session, action=f"{owner_type}.create", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    return entity


async def update_trust_entity(session: AsyncSession, resource: str, entity_id: uuid.UUID, payload: Any, actor_id: uuid.UUID) -> Any:
    """更新 Trust 主实体和翻译，保留统一生命周期记录。"""
    config = TRUST_CONFIG.get(resource)
    if config is None:
        raise AppException(404, "trust_type_not_found", "未知 Trust 类型")
    model, translation_model, owner_field, owner_type, _has_route = config
    entity = await session.get(model, entity_id)
    if entity is None:
        raise AppException(404, "trust_not_found", "Trust 实体不存在")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        if key in {"translations", "fields"}:
            continue
        if key in model.__table__.columns:
            setattr(entity, key, value)
    for key, value in payload.fields.items():
        if key in model.__table__.columns:
            setattr(entity, key, value)
    await session.flush()
    if payload.translations:
        await _save_translations(session, entity, translation_model, owner_field, payload.translations)
    write_audit_log(session, action=f"{owner_type}.update", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    return entity


async def _save_translations(session: AsyncSession, entity: Any, translation_model: type, owner_field: str, translations: list[Any]) -> None:
    """按 locale 幂等写入翻译；不覆盖未提交语言。"""
    for item in translations:
        values = {owner_field: entity.id, "locale_id": item.locale_id}
        allowed = set(translation_model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at"}
        values.update({key: value for key, value in item.fields.items() if key in allowed})
        if "name" in allowed and "name" not in values and "title" in values:
            values["name"] = values["title"]
        existing = await session.scalar(select(translation_model).where(getattr(translation_model, owner_field) == entity.id, translation_model.locale_id == item.locale_id))
        if existing is None:
            session.add(translation_model(**values))
        else:
            for key, value in values.items():
                if key not in {owner_field, "locale_id"}:
                    setattr(existing, key, value)


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
    return {"type": owner_type, "slug": entity.slug, "translation": payload, "url": f"https://junhuiscrewbarrel.com{route.path}", "schema": {"@context": "https://schema.org", "@type": "WebPage", "name": payload.get("name") or payload.get("title"), "url": f"https://junhuiscrewbarrel.com{route.path}"}}


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
