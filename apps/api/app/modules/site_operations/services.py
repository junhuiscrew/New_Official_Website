"""品牌、导航页脚与受控重定向的保存、应用、恢复和公开读取服务。"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.models import AuditLog
from app.modules.audit.service import write_audit_log
from app.modules.company.models import CompanyProfile, CompanyProfileTranslation
from app.modules.content.models import ContentRoute
from app.modules.content.services.revisions import store_revision
from app.modules.discovery.models import RedirectRule
from app.modules.discovery.redirects import ALLOWED_SOURCE_HOSTS, OFFICIAL_HOST, RedirectEdge
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset
from app.modules.site_operations.models import SiteBrandSetting, SiteNavigationSetting
from app.modules.site_operations.redirects import validate_managed_redirect
from app.modules.site_operations.registry import (
    SITE_TARGET_LABELS,
    SITE_TARGET_PATHS,
    default_brand_config,
    default_navigation_config,
)
from app.modules.site_operations.schemas import (
    BrandDraftUpdate,
    ManagedRedirectInput,
    ManagedRedirectUpdate,
    NavigationDraftUpdate,
)

SUPPORTED_LOCALES = ("zh-CN", "en")
ALWAYS_AVAILABLE_TARGETS = frozenset(
    {
        "home",
        "products",
        "solutions",
        "materials",
        "applications",
        "technologies",
        "capabilities",
        "case_studies",
        "knowledge",
        "about",
        "contact",
        "request_a_quote",
        "downloads",
        "search",
    }
)


async def _enabled_locales(session: AsyncSession) -> dict[str, Locale]:
    """
    读取站点运营所需中英文语言。

    输入：session: AsyncSession，数据库会话。
    输出：dict[str, Locale]，按语言代码索引的启用语言。
    """
    rows = list(
        (
            await session.scalars(
                select(Locale).where(
                    Locale.code.in_(SUPPORTED_LOCALES),
                    Locale.is_enabled.is_(True),
                )
            )
        ).all()
    )
    locales = {row.code: row for row in rows}
    if set(locales) != set(SUPPORTED_LOCALES):
        raise AppException(
            409, "site_operations_locales_unavailable", "站点运营所需中英文语言未全部启用"
        )
    return locales


async def _current_brand_config(
    session: AsyncSession,
    locales: dict[str, Locale],
) -> dict[str, Any]:
    """
    用当前启用公司档案初始化品牌展示名，避免建立矛盾的公司名称副本。

    输入：
        session: AsyncSession，数据库会话。
        locales: dict[str, Locale]，已启用的中英文语言。

    输出：
        dict[str, Any]，以现有公司名称覆盖默认展示名后的完整品牌配置。
    """
    config = default_brand_config()
    profile = await session.scalar(
        select(CompanyProfile)
        .where(CompanyProfile.status == "enabled")
        .order_by(CompanyProfile.created_at)
        .limit(1)
    )
    if profile is None:
        return config
    translations = list(
        (
            await session.scalars(
                select(CompanyProfileTranslation).where(
                    CompanyProfileTranslation.company_profile_id == profile.id,
                    CompanyProfileTranslation.locale_id.in_(
                        [locale.id for locale in locales.values()]
                    ),
                )
            )
        ).all()
    )
    names_by_locale_id = {
        translation.locale_id: translation.company_name for translation in translations
    }
    for locale_code, locale in locales.items():
        if company_name := names_by_locale_id.get(locale.id):
            # 只同步展示名称；法定资料仍由 Company Profile 单一来源负责。
            config["translations"][locale_code]["display_name"] = company_name
    return config


async def _brand_setting(session: AsyncSession, *, lock: bool = False) -> SiteBrandSetting:
    """
    读取唯一品牌设置。

    输入：session: AsyncSession；lock: bool，是否加行锁。
    输出：SiteBrandSetting，存在的唯一品牌记录。
    """
    statement = select(SiteBrandSetting).where(SiteBrandSetting.singleton_key == "primary")
    if lock:
        statement = statement.with_for_update()
    setting = await session.scalar(statement)
    if setting is None:
        raise AppException(409, "site_brand_not_initialized", "站点品牌尚未初始化")
    return setting


async def _navigation_setting(
    session: AsyncSession,
    locale_code: str,
    *,
    lock: bool = False,
) -> tuple[Locale, SiteNavigationSetting]:
    """
    读取指定语言导航设置。

    输入：session、locale_code 和 lock。
    输出：tuple[Locale, SiteNavigationSetting]，语言与配置记录。
    """
    if locale_code not in SUPPORTED_LOCALES:
        raise AppException(404, "site_navigation_locale_not_found", "导航语言不存在")
    locale = await session.scalar(
        select(Locale).where(Locale.code == locale_code, Locale.is_enabled.is_(True))
    )
    if locale is None:
        raise AppException(404, "site_navigation_locale_not_found", "导航语言不存在")
    statement = select(SiteNavigationSetting).where(SiteNavigationSetting.locale_id == locale.id)
    if lock:
        statement = statement.with_for_update()
    setting = await session.scalar(statement)
    if setting is None:
        raise AppException(409, "site_navigation_not_initialized", "导航与页脚尚未初始化")
    return locale, setting


def _media_dto(asset: MediaAsset | None) -> dict[str, Any] | None:
    """
    将品牌媒体转成不暴露存储信息的安全 DTO。

    输入：asset: MediaAsset | None，媒体记录。
    输出：dict | None，包含ID、文件名和公开交付地址。
    """
    if asset is None:
        return None
    return {
        "id": str(asset.id),
        "filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "url": f"/api/v1/public/media/{asset.id}",
    }


async def _brand_media_map(
    session: AsyncSession,
    setting: SiteBrandSetting,
    *,
    applied: bool,
) -> dict[str, dict[str, Any] | None]:
    """
    批量读取草稿或应用版品牌媒体。

    输入：session、setting 和 applied 版本选择。
    输出：dict，三种使用位置对应的安全媒体 DTO。
    """
    prefix = "applied" if applied else "draft"
    ids = {
        "header_logo": getattr(setting, f"{prefix}_header_logo_media_id"),
        "mobile_logo": getattr(setting, f"{prefix}_mobile_logo_media_id"),
        "favicon": getattr(setting, f"{prefix}_favicon_media_id"),
    }
    existing_ids = {media_id for media_id in ids.values() if media_id is not None}
    assets = (
        {
            asset.id: asset
            for asset in (
                await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(existing_ids)))
            ).all()
        }
        if existing_ids
        else {}
    )
    return {key: _media_dto(assets.get(media_id)) for key, media_id in ids.items()}


async def _validate_brand_media(
    session: AsyncSession,
    media_ids: list[uuid.UUID | None],
) -> None:
    """
    校验品牌只引用公开、就绪且可作为图片交付的媒体。

    输入：session 和三个可选媒体ID。
    输出：None；任一媒体不合格时抛出 AppException。
    """
    requested = {media_id for media_id in media_ids if media_id is not None}
    if not requested:
        return
    assets = list(
        (await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(requested)))).all()
    )
    if len(assets) != len(requested):
        raise AppException(422, "brand_media_not_found", "所选品牌媒体不存在")
    for asset in assets:
        if (
            asset.visibility != "public"
            or asset.upload_status != "ready"
            or asset.media_type != "image"
            or not asset.mime_type.startswith("image/")
        ):
            raise AppException(
                422, "brand_media_not_public_ready_image", "品牌只能使用公开、就绪的图片媒体"
            )


async def _serialize_brand(session: AsyncSession, setting: SiteBrandSetting) -> dict[str, Any]:
    """输入数据库会话和品牌记录；输出不含用户ID的草稿/应用版详情。"""
    return {
        "draft": {
            **deepcopy(setting.draft_config_jsonb),
            "media": await _brand_media_map(session, setting, applied=False),
        },
        "applied": {
            **deepcopy(setting.applied_config_jsonb),
            "media": await _brand_media_map(session, setting, applied=True),
        },
        "draft_revision": setting.draft_revision,
        "applied_revision": setting.applied_revision,
        "applied_at": setting.applied_at,
    }


def _serialize_navigation(setting: SiteNavigationSetting, locale: Locale) -> dict[str, Any]:
    """输入导航记录和语言；输出安全草稿/应用版及修订状态。"""
    return {
        "locale": {"code": locale.code, "slug": locale.slug, "native_name": locale.native_name},
        "draft": deepcopy(setting.draft_config_jsonb),
        "applied": deepcopy(setting.applied_config_jsonb),
        "draft_revision": setting.draft_revision,
        "applied_revision": setting.applied_revision,
        "applied_at": setting.applied_at,
    }


async def initialize_site_operations(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    幂等建立当前品牌与菜单的等值设置，不覆盖已有草稿。

    输入：session 和 actor_id。
    输出：dict，初始化后的品牌与双语导航详情。
    """
    locales = await _enabled_locales(session)
    brand = await session.scalar(
        select(SiteBrandSetting).where(SiteBrandSetting.singleton_key == "primary")
    )
    if brand is None:
        default_brand = await _current_brand_config(session, locales)
        brand = SiteBrandSetting(
            singleton_key="primary",
            draft_config_jsonb=deepcopy(default_brand),
            applied_config_jsonb=deepcopy(default_brand),
            updated_by=actor_id,
        )
        session.add(brand)
        await session.flush()
        write_audit_log(
            session,
            action="site_brand.initialize",
            target_type="site_brand_setting",
            target_id=str(brand.id),
            user_id=actor_id,
        )
    for locale_code, locale in locales.items():
        setting = await session.scalar(
            select(SiteNavigationSetting).where(SiteNavigationSetting.locale_id == locale.id)
        )
        if setting is None:
            default_config = default_navigation_config(locale_code)
            setting = SiteNavigationSetting(
                locale_id=locale.id,
                draft_config_jsonb=deepcopy(default_config),
                applied_config_jsonb=deepcopy(default_config),
                updated_by=actor_id,
            )
            session.add(setting)
            await session.flush()
            write_audit_log(
                session,
                action="site_navigation.initialize",
                target_type="site_navigation_setting",
                target_id=str(setting.id),
                user_id=actor_id,
                metadata={"locale": locale_code},
            )
    return await get_site_operations_detail(session)


async def get_site_operations_detail(session: AsyncSession) -> dict[str, Any]:
    """输入数据库会话；输出品牌、双语导航和安全目标选择列表。"""
    brand = await _brand_setting(session)
    navigation = []
    for locale_code in SUPPORTED_LOCALES:
        locale, setting = await _navigation_setting(session, locale_code)
        navigation.append(_serialize_navigation(setting, locale))
    return {"brand": await _serialize_brand(session, brand), "navigation": navigation}


async def get_brand_detail(session: AsyncSession) -> dict[str, Any]:
    """输入数据库会话；输出品牌草稿和应用版详情。"""
    return await _serialize_brand(session, await _brand_setting(session))


async def save_brand_draft(
    session: AsyncSession,
    *,
    payload: BrandDraftUpdate,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """
    保存完整双语品牌草稿并追加两种语言修订。

    输入：session、payload 和 actor_id。
    输出：dict，fresh-read 品牌详情。
    """
    setting = await _brand_setting(session, lock=True)
    if setting.draft_revision != payload.expected_revision:
        raise AppException(
            409, "site_brand_revision_conflict", "品牌草稿已被其他操作更新，请刷新后重试"
        )
    await _validate_brand_media(
        session,
        [payload.header_logo_media_id, payload.mobile_logo_media_id, payload.favicon_media_id],
    )
    locales = await _enabled_locales(session)
    config = {"translations": jsonable_encoder(payload.translations)}
    next_revision = setting.draft_revision + 1
    setting.draft_config_jsonb = deepcopy(config)
    setting.draft_header_logo_media_id = payload.header_logo_media_id
    setting.draft_mobile_logo_media_id = payload.mobile_logo_media_id
    setting.draft_favicon_media_id = payload.favicon_media_id
    setting.draft_revision = next_revision
    setting.updated_by = actor_id
    for locale_code, locale in locales.items():
        await store_revision(
            session,
            "site_brand_setting",
            setting.id,
            locale.id,
            {
                "revision": next_revision,
                "translation": config["translations"][locale_code],
                "media_ids": {
                    "header_logo": str(payload.header_logo_media_id)
                    if payload.header_logo_media_id
                    else None,
                    "mobile_logo": str(payload.mobile_logo_media_id)
                    if payload.mobile_logo_media_id
                    else None,
                    "favicon": str(payload.favicon_media_id) if payload.favicon_media_id else None,
                },
            },
            actor_id,
        )
    write_audit_log(
        session,
        action="site_brand.draft.save",
        target_type="site_brand_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"revision": next_revision},
    )
    await session.flush()
    return await _serialize_brand(session, setting)


async def apply_brand(
    session: AsyncSession,
    *,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入会话、草稿修订号和用户；输出确认应用后的品牌详情。"""
    setting = await _brand_setting(session, lock=True)
    if setting.draft_revision != expected_revision:
        raise AppException(409, "site_brand_revision_conflict", "品牌草稿版本不一致，请刷新后重试")
    await _validate_brand_media(
        session,
        [
            setting.draft_header_logo_media_id,
            setting.draft_mobile_logo_media_id,
            setting.draft_favicon_media_id,
        ],
    )
    setting.applied_config_jsonb = deepcopy(setting.draft_config_jsonb)
    setting.applied_header_logo_media_id = setting.draft_header_logo_media_id
    setting.applied_mobile_logo_media_id = setting.draft_mobile_logo_media_id
    setting.applied_favicon_media_id = setting.draft_favicon_media_id
    setting.applied_revision = setting.draft_revision
    setting.applied_by = actor_id
    setting.applied_at = datetime.now(UTC)
    write_audit_log(
        session,
        action="site_brand.apply",
        target_type="site_brand_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"revision": setting.applied_revision},
    )
    await session.flush()
    return await _serialize_brand(session, setting)


async def restore_brand_draft(
    session: AsyncSession,
    *,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入会话、修订号和用户；输出由应用版生成的新草稿版本。"""
    setting = await _brand_setting(session, lock=True)
    if setting.draft_revision != expected_revision:
        raise AppException(409, "site_brand_revision_conflict", "品牌草稿版本不一致，请刷新后重试")
    setting.draft_config_jsonb = deepcopy(setting.applied_config_jsonb)
    setting.draft_header_logo_media_id = setting.applied_header_logo_media_id
    setting.draft_mobile_logo_media_id = setting.applied_mobile_logo_media_id
    setting.draft_favicon_media_id = setting.applied_favicon_media_id
    setting.draft_revision += 1
    setting.updated_by = actor_id
    write_audit_log(
        session,
        action="site_brand.restore",
        target_type="site_brand_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"revision": setting.draft_revision},
    )
    await session.flush()
    return await _serialize_brand(session, setting)


async def get_navigation_detail(session: AsyncSession, locale_code: str) -> dict[str, Any]:
    """输入会话和语言；输出该语言导航草稿、应用版与目标选项。"""
    locale, setting = await _navigation_setting(session, locale_code)
    return {
        **_serialize_navigation(setting, locale),
        "target_options": await get_target_options(session, locale_code),
    }


async def save_navigation_draft(
    session: AsyncSession,
    *,
    locale_code: str,
    payload: NavigationDraftUpdate,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入完整单语言导航草稿；输出保存后的 fresh-read 详情。"""
    locale, setting = await _navigation_setting(session, locale_code, lock=True)
    if setting.draft_revision != payload.expected_revision:
        raise AppException(409, "site_navigation_revision_conflict", "导航草稿已更新，请刷新后重试")
    config = jsonable_encoder(payload, exclude={"expected_revision"})
    setting.draft_revision += 1
    setting.draft_config_jsonb = deepcopy(config)
    setting.updated_by = actor_id
    await store_revision(
        session,
        "site_navigation_setting",
        setting.id,
        locale.id,
        {"revision": setting.draft_revision, **config},
        actor_id,
    )
    write_audit_log(
        session,
        action="site_navigation.draft.save",
        target_type="site_navigation_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"locale": locale_code, "revision": setting.draft_revision},
    )
    await session.flush()
    return await get_navigation_detail(session, locale_code)


async def apply_navigation(
    session: AsyncSession,
    *,
    locale_code: str,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入语言、修订号和用户；输出确认应用后的导航详情。"""
    _locale, setting = await _navigation_setting(session, locale_code, lock=True)
    if setting.draft_revision != expected_revision:
        raise AppException(
            409, "site_navigation_revision_conflict", "导航草稿版本不一致，请刷新后重试"
        )
    # 应用前重新由严格 Schema 校验持久化 JSON，防止旧数据绕过白名单。
    NavigationDraftUpdate.model_validate(
        {"expected_revision": expected_revision, **setting.draft_config_jsonb}
    )
    setting.applied_config_jsonb = deepcopy(setting.draft_config_jsonb)
    setting.applied_revision = setting.draft_revision
    setting.applied_by = actor_id
    setting.applied_at = datetime.now(UTC)
    write_audit_log(
        session,
        action="site_navigation.apply",
        target_type="site_navigation_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"locale": locale_code, "revision": setting.applied_revision},
    )
    await session.flush()
    return await get_navigation_detail(session, locale_code)


async def restore_navigation_draft(
    session: AsyncSession,
    *,
    locale_code: str,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入语言、修订号和用户；输出由应用版恢复出的新草稿。"""
    _locale, setting = await _navigation_setting(session, locale_code, lock=True)
    if setting.draft_revision != expected_revision:
        raise AppException(
            409, "site_navigation_revision_conflict", "导航草稿版本不一致，请刷新后重试"
        )
    setting.draft_config_jsonb = deepcopy(setting.applied_config_jsonb)
    setting.draft_revision += 1
    setting.updated_by = actor_id
    write_audit_log(
        session,
        action="site_navigation.restore",
        target_type="site_navigation_setting",
        target_id=str(setting.id),
        user_id=actor_id,
        metadata={"locale": locale_code, "revision": setting.draft_revision},
    )
    await session.flush()
    return await get_navigation_detail(session, locale_code)


async def get_target_options(session: AsyncSession, locale_code: str) -> list[dict[str, Any]]:
    """
    返回后台安全目标选择器的服务端选项。

    输入：session 和 locale_code。
    输出：list[dict]，每项含稳定键、标签、路径与当前可用性。
    """
    if locale_code not in SUPPORTED_LOCALES:
        raise AppException(404, "site_navigation_locale_not_found", "导航语言不存在")
    locale = await session.scalar(
        select(Locale).where(Locale.code == locale_code, Locale.is_enabled.is_(True))
    )
    if locale is None:
        raise AppException(404, "site_navigation_locale_not_found", "导航语言不存在")
    active_paths = set(
        (
            await session.scalars(
                select(ContentRoute.path).where(
                    ContentRoute.locale_id == locale.id,
                    ContentRoute.active.is_(True),
                )
            )
        ).all()
    )
    options = []
    for key, paths in SITE_TARGET_PATHS.items():
        path = paths[locale_code]
        available = key in ALWAYS_AVAILABLE_TARGETS or path in active_paths
        options.append(
            {
                "key": key,
                "label": SITE_TARGET_LABELS[key][locale_code],
                "path": path,
                "available": available,
                "reason": None if available else "页面尚未批准公开",
            }
        )
    return options


async def get_public_site_operations(
    session: AsyncSession, locale_slug: str
) -> dict[str, Any] | None:
    """
    返回普通前台可读的唯一应用版品牌和导航。

    输入：session 和 locale_slug。
    输出：dict | None，未初始化时返回 None 供前台保持旧配置。
    """
    locale = await session.scalar(
        select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True))
    )
    if locale is None:
        return None
    brand = await session.scalar(
        select(SiteBrandSetting).where(SiteBrandSetting.singleton_key == "primary")
    )
    navigation = await session.scalar(
        select(SiteNavigationSetting).where(SiteNavigationSetting.locale_id == locale.id)
    )
    if brand is None or navigation is None:
        return None
    raw_brand_media = await _brand_media_map(session, brand, applied=True)
    brand_media = {
        key: ({field: value for field, value in media.items() if field != "id"} if media else None)
        for key, media in raw_brand_media.items()
    }
    brand_translation = deepcopy(
        brand.applied_config_jsonb.get("translations", {}).get(locale.code, {})
    )
    options = {item["key"]: item for item in await get_target_options(session, locale.code)}

    def public_item(item: dict[str, Any]) -> dict[str, Any] | None:
        """输入持久化菜单项；输出可公开的路径 DTO 或 None。"""
        option = options.get(str(item.get("target_key")))
        if not item.get("enabled") or option is None or not option["available"]:
            return None
        return {"label": item["label"], "target_key": item["target_key"], "path": option["path"]}

    header_items = [
        result
        for item in navigation.applied_config_jsonb.get("header_items", [])
        if (result := public_item(item))
    ]
    footer_groups = []
    for group in navigation.applied_config_jsonb.get("footer_groups", []):
        if not group.get("enabled"):
            continue
        items = [result for item in group.get("items", []) if (result := public_item(item))]
        if items:
            footer_groups.append({"title": group["title"], "items": items})
    return {
        "brand": {**brand_translation, "media": brand_media},
        "header_items": header_items,
        "footer_groups": footer_groups,
    }


def _redirect_dto(rule: RedirectRule) -> dict[str, Any]:
    """输入重定向实体；输出后台可读且不暴露用户ID的工作流 DTO。"""
    return {
        "id": str(rule.id),
        "source_host": rule.draft_source_host or rule.source_host,
        "source_path": rule.draft_source_path or rule.source_path,
        "target_url": rule.draft_target_url or rule.target_url,
        "target_path": (rule.draft_target_url or rule.target_url).removeprefix(
            f"https://{OFFICIAL_HOST}"
        ),
        "status_code": rule.draft_status_code or rule.status_code,
        "notes": rule.draft_notes if rule.draft_notes is not None else rule.notes,
        "workflow_status": rule.workflow_status,
        "revision": rule.revision,
        "checked_revision": rule.checked_revision,
        "enabled": rule.enabled,
        "hit_count": rule.hit_count,
        "last_hit_at": rule.last_hit_at,
        "confirmed_at": rule.confirmed_at,
        "updated_at": rule.updated_at,
    }


async def list_managed_redirects(
    session: AsyncSession, query: str | None = None
) -> list[dict[str, Any]]:
    """输入会话和可选搜索词；输出按更新时间倒序的受控重定向列表。"""
    statement = select(RedirectRule)
    if query and query.strip():
        token = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                RedirectRule.source_host.ilike(token),
                RedirectRule.source_path.ilike(token),
                RedirectRule.target_url.ilike(token),
                RedirectRule.notes.ilike(token),
            )
        )
    rows = list((await session.scalars(statement.order_by(RedirectRule.updated_at.desc()))).all())
    return [_redirect_dto(row) for row in rows]


async def _redirect_conflict_inputs(
    session: AsyncSession,
    *,
    exclude_id: uuid.UUID | None = None,
) -> tuple[list[RedirectEdge], set[str]]:
    """输入会话和排除ID；输出冲突图边及当前有效内容路径。"""
    statement = select(RedirectRule)
    if exclude_id is not None:
        statement = statement.where(RedirectRule.id != exclude_id)
    rules = list((await session.scalars(statement)).all())
    edges = [
        RedirectEdge(
            source_host=row.draft_source_host or row.source_host,
            source_path=row.draft_source_path or row.source_path,
            target_url=row.draft_target_url or row.target_url,
        )
        for row in rules
    ]
    active_paths = set(
        (
            await session.scalars(select(ContentRoute.path).where(ContentRoute.active.is_(True)))
        ).all()
    )
    return edges, active_paths


async def create_managed_redirect(
    session: AsyncSession,
    *,
    payload: ManagedRedirectInput,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入重定向表单和用户；输出保存但未启用的新草稿。"""
    target_url = f"https://{OFFICIAL_HOST}{payload.target_path}"
    edges, active_paths = await _redirect_conflict_inputs(session)
    normalized = validate_managed_redirect(
        source_host=payload.source_host,
        source_path=payload.source_path,
        target_url=target_url,
        existing_rules=edges,
        active_paths=active_paths,
    )
    rule = RedirectRule(
        source_host=payload.source_host,
        source_path=payload.source_path,
        target_url=normalized,
        status_code=payload.status_code,
        enabled=False,
        notes=payload.notes,
        created_by=actor_id,
        draft_source_host=payload.source_host,
        draft_source_path=payload.source_path,
        draft_target_url=normalized,
        draft_status_code=payload.status_code,
        draft_notes=payload.notes,
        workflow_status="draft",
        revision=0,
        updated_by=actor_id,
    )
    session.add(rule)
    await session.flush()
    write_audit_log(
        session,
        action="redirect.draft.create",
        target_type="redirect_rule",
        target_id=str(rule.id),
        user_id=actor_id,
        metadata={"revision": 0},
    )
    await session.refresh(rule)
    return _redirect_dto(rule)


async def update_managed_redirect(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    payload: ManagedRedirectUpdate,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入规则ID、表单和用户；输出更新后重新待检查的草稿。"""
    rule = await session.scalar(
        select(RedirectRule).where(RedirectRule.id == rule_id).with_for_update()
    )
    if rule is None:
        raise AppException(404, "redirect_not_found", "重定向规则不存在")
    if rule.revision != payload.expected_revision:
        raise AppException(409, "redirect_revision_conflict", "重定向草稿已更新，请刷新后重试")
    target_url = f"https://{OFFICIAL_HOST}{payload.target_path}"
    edges, active_paths = await _redirect_conflict_inputs(session, exclude_id=rule.id)
    normalized = validate_managed_redirect(
        source_host=payload.source_host,
        source_path=payload.source_path,
        target_url=target_url,
        existing_rules=edges,
        active_paths=active_paths,
    )
    rule.draft_source_host = payload.source_host
    rule.draft_source_path = payload.source_path
    rule.draft_target_url = normalized
    rule.draft_status_code = payload.status_code
    rule.draft_notes = payload.notes
    rule.revision += 1
    rule.checked_revision = None
    rule.workflow_status = "draft"
    rule.updated_by = actor_id
    write_audit_log(
        session,
        action="redirect.draft.update",
        target_type="redirect_rule",
        target_id=str(rule.id),
        user_id=actor_id,
        metadata={"revision": rule.revision},
    )
    await session.flush()
    await session.refresh(rule)
    return _redirect_dto(rule)


async def check_managed_redirect(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入规则和修订号；输出纯本地冲突检查通过的草稿状态。"""
    rule = await session.scalar(
        select(RedirectRule).where(RedirectRule.id == rule_id).with_for_update()
    )
    if rule is None:
        raise AppException(404, "redirect_not_found", "重定向规则不存在")
    if rule.revision != expected_revision:
        raise AppException(409, "redirect_revision_conflict", "重定向草稿版本不一致")
    edges, active_paths = await _redirect_conflict_inputs(session, exclude_id=rule.id)
    validate_managed_redirect(
        source_host=rule.draft_source_host or rule.source_host,
        source_path=rule.draft_source_path or rule.source_path,
        target_url=rule.draft_target_url or rule.target_url,
        existing_rules=edges,
        active_paths=active_paths,
    )
    rule.checked_revision = rule.revision
    rule.workflow_status = "checked"
    rule.updated_by = actor_id
    write_audit_log(
        session,
        action="redirect.check",
        target_type="redirect_rule",
        target_id=str(rule.id),
        user_id=actor_id,
        metadata={"revision": rule.revision, "network_access": False},
    )
    await session.flush()
    await session.refresh(rule)
    return _redirect_dto(rule)


async def confirm_managed_redirect(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入已检查规则、修订号和用户；输出确认启用后的有效规则。"""
    rule = await session.scalar(
        select(RedirectRule).where(RedirectRule.id == rule_id).with_for_update()
    )
    if rule is None:
        raise AppException(404, "redirect_not_found", "重定向规则不存在")
    if (
        rule.revision != expected_revision
        or rule.checked_revision != expected_revision
        or rule.workflow_status != "checked"
    ):
        raise AppException(409, "redirect_check_required", "必须先检查当前修订后才能确认启用")
    edges, active_paths = await _redirect_conflict_inputs(session, exclude_id=rule.id)
    normalized = validate_managed_redirect(
        source_host=rule.draft_source_host or rule.source_host,
        source_path=rule.draft_source_path or rule.source_path,
        target_url=rule.draft_target_url or rule.target_url,
        existing_rules=edges,
        active_paths=active_paths,
    )
    rule.source_host = rule.draft_source_host or rule.source_host
    rule.source_path = rule.draft_source_path or rule.source_path
    rule.target_url = normalized
    rule.status_code = rule.draft_status_code or rule.status_code
    rule.notes = rule.draft_notes
    rule.enabled = True
    rule.workflow_status = "confirmed"
    rule.confirmed_by = actor_id
    rule.confirmed_at = datetime.now(UTC)
    write_audit_log(
        session,
        action="redirect.confirm",
        target_type="redirect_rule",
        target_id=str(rule.id),
        user_id=actor_id,
        metadata={"revision": rule.revision, "status_code": rule.status_code},
    )
    await session.flush()
    await session.refresh(rule)
    return _redirect_dto(rule)


async def disable_managed_redirect(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    expected_revision: int,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """输入规则、修订号和用户；输出已停用但保留历史的规则。"""
    rule = await session.scalar(
        select(RedirectRule).where(RedirectRule.id == rule_id).with_for_update()
    )
    if rule is None:
        raise AppException(404, "redirect_not_found", "重定向规则不存在")
    if rule.revision != expected_revision:
        raise AppException(409, "redirect_revision_conflict", "重定向规则版本不一致")
    rule.enabled = False
    rule.revision += 1
    rule.checked_revision = None
    rule.workflow_status = "draft"
    rule.updated_by = actor_id
    write_audit_log(
        session,
        action="redirect.disable",
        target_type="redirect_rule",
        target_id=str(rule.id),
        user_id=actor_id,
        metadata={"revision": rule.revision},
    )
    await session.flush()
    await session.refresh(rule)
    return _redirect_dto(rule)


async def get_redirect_history(session: AsyncSession, rule_id: uuid.UUID) -> list[dict[str, Any]]:
    """输入规则ID；输出脱敏审计历史，不返回用户ID或请求凭据。"""
    rows = list(
        (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.target_type == "redirect_rule", AuditLog.target_id == str(rule_id))
                .order_by(AuditLog.created_at.desc())
            )
        ).all()
    )
    return [
        {
            "action": row.action,
            "metadata": deepcopy(row.metadata_json),
            "created_at": row.created_at,
        }
        for row in rows
    ]


def managed_redirect_hosts() -> list[str]:
    """输入无；输出后台来源主机下拉框允许值。"""
    return sorted(ALLOWED_SOURCE_HOSTS)
