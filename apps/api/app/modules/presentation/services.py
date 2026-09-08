"""首页配置、公开呈现、作者预览与全站模块总览服务。"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import CaseStudy, KnowledgeArticle
from app.modules.catalog.models import (
    Application,
    Material,
    Product,
    Solution,
    Technology,
)
from app.modules.company.models import (
    Certificate,
    CompanyProfile,
    Equipment,
    ManufacturingCapability,
    Patent,
)
from app.modules.content.models import SitePage, SitePageTranslation
from app.modules.content.services.revisions import store_revision
from app.modules.localization.models import Locale
from app.modules.presentation.models import HomepageLayout
from app.modules.presentation.registry import (
    HOMEPAGE_MANAGEMENT_URLS,
    HOMEPAGE_MODULE_KEYS,
    clone_homepage_config,
    default_homepage_config,
)
from app.modules.presentation.schemas import HomepageDraftUpdate

HOMEPAGE_SYSTEM_KEY = "home"
HOMEPAGE_LANGUAGES = {
    "zh-CN": {"display_name": "首页", "slug": "zh-cn"},
    "en": {"display_name": "Home", "slug": "en"},
}


def _serialize_layout(layout: HomepageLayout) -> dict[str, Any]:
    """
    将首页布局转成不含用户ID的后台安全 DTO。

    输入：
        layout: HomepageLayout，当前语言布局。
    输出：
        dict，包含草稿、应用版和修订状态。
    """
    return {
        "draft": clone_homepage_config(layout.draft_config_jsonb),
        "applied": clone_homepage_config(layout.applied_config_jsonb),
        "draft_revision": layout.draft_revision,
        "applied_revision": layout.applied_revision,
        "applied_at": layout.applied_at,
    }


async def _homepage_locales(session: AsyncSession) -> dict[str, Locale]:
    """
    读取首页支持的已启用语言。

    输入：
        session: AsyncSession，数据库会话。
    输出：
        dict，按语言代码索引的 Locale。
    """
    rows = list(
        (
            await session.scalars(
                select(Locale)
                .where(
                    Locale.code.in_(HOMEPAGE_LANGUAGES),
                    Locale.is_enabled.is_(True),
                )
                .order_by(Locale.sort_order, Locale.code)
            )
        ).all()
    )
    locales = {locale.code: locale for locale in rows}
    if set(locales) != set(HOMEPAGE_LANGUAGES):
        raise AppException(
            409,
            "homepage_locales_unavailable",
            "首页所需中英文语言未全部启用",
        )
    return locales


async def _homepage_page(
    session: AsyncSession,
    *,
    lock: bool = False,
) -> SitePage:
    """
    读取唯一固定首页身份。

    输入：
        session: AsyncSession，数据库会话。
        lock: bool，是否锁定页面记录。
    输出：
        SitePage，已验证启用的固定首页。
    """
    statement = select(SitePage).where(SitePage.system_key == HOMEPAGE_SYSTEM_KEY)
    if lock:
        statement = statement.with_for_update()
    page = await session.scalar(statement)
    if page is None:
        raise AppException(404, "homepage_not_initialized", "首页配置尚未初始化")
    if page.status != "enabled":
        raise AppException(409, "homepage_disabled", "固定首页当前未启用")
    return page


async def _homepage_layout(
    session: AsyncSession,
    *,
    locale_code: str,
    lock: bool = False,
) -> tuple[SitePage, Locale, HomepageLayout]:
    """
    读取并校验指定语言首页布局。

    输入：
        session: AsyncSession，数据库会话。
        locale_code: str，zh-CN 或 en。
        lock: bool，是否对布局加行锁。
    输出：
        tuple，固定页面、语言和布局。
    """
    if locale_code not in HOMEPAGE_LANGUAGES:
        raise AppException(404, "homepage_locale_not_found", "首页语言不存在")
    page = await _homepage_page(session, lock=lock)
    locale = await session.scalar(
        select(Locale).where(
            Locale.code == locale_code,
            Locale.is_enabled.is_(True),
        )
    )
    if locale is None:
        raise AppException(404, "homepage_locale_not_found", "首页语言不存在")
    statement = select(HomepageLayout).where(
        HomepageLayout.site_page_id == page.id,
        HomepageLayout.locale_id == locale.id,
    )
    if lock:
        statement = statement.with_for_update()
    layout = await session.scalar(statement)
    if layout is None:
        raise AppException(409, "homepage_layout_incomplete", "首页布局记录不完整")
    return page, locale, layout


async def initialize_homepage(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    幂等建立固定首页身份、双语名称和安全默认布局。

    输入：
        session: AsyncSession，数据库会话。
        actor_id: UUID | None，真实操作用户ID。
    输出：
        dict，初始化后双语详情。
    """
    locales = await _homepage_locales(session)
    page = await session.scalar(
        select(SitePage)
        .where(SitePage.system_key == HOMEPAGE_SYSTEM_KEY)
        .with_for_update()
    )
    created = False
    if page is None:
        page = SitePage(system_key=HOMEPAGE_SYSTEM_KEY, status="enabled")
        session.add(page)
        await session.flush()
        created = True
    elif page.status != "enabled":
        raise AppException(409, "homepage_conflict", "已有首页身份状态不一致")

    default_config = default_homepage_config()
    for locale_code, locale in locales.items():
        translation = await session.scalar(
            select(SitePageTranslation).where(
                SitePageTranslation.site_page_id == page.id,
                SitePageTranslation.locale_id == locale.id,
            )
        )
        if translation is None:
            session.add(
                SitePageTranslation(
                    site_page_id=page.id,
                    locale_id=locale.id,
                    display_name=HOMEPAGE_LANGUAGES[locale_code]["display_name"],
                )
            )
            created = True
        elif translation.display_name != HOMEPAGE_LANGUAGES[locale_code]["display_name"]:
            raise AppException(409, "homepage_conflict", "已有首页语言名称不一致")

        layout = await session.scalar(
            select(HomepageLayout).where(
                HomepageLayout.site_page_id == page.id,
                HomepageLayout.locale_id == locale.id,
            )
        )
        if layout is None:
            session.add(
                HomepageLayout(
                    site_page_id=page.id,
                    locale_id=locale.id,
                    draft_config_jsonb=clone_homepage_config(default_config),
                    applied_config_jsonb=clone_homepage_config(default_config),
                )
            )
            created = True

    if created:
        write_audit_log(
            session,
            action="homepage.initialize",
            target_type="homepage_layout",
            target_id=str(page.id),
            user_id=actor_id,
            metadata={"system_key": HOMEPAGE_SYSTEM_KEY},
        )
    await session.flush()
    return await get_homepage_detail(session)


async def _public_product_options(
    session: AsyncSession,
    locale: Locale,
) -> list[dict[str, Any]]:
    """
    返回当前语言可供首页引用的严格公开产品卡。

    输入：
        session: AsyncSession，数据库会话。
        locale: Locale，目标语言。
    输出：
        list，按公开产品稳定排序的安全卡片。
    """
    from app.modules.discovery.public_collections import (
        _product_card_payloads,
        _published_row_tuples,
    )

    rows = await _published_row_tuples(session, "product", locale, 48, False)
    return await _product_card_payloads(session, locale, rows)


async def _language_detail(
    session: AsyncSession,
    page: SitePage,
    locale: Locale,
) -> dict[str, Any]:
    """
    组合后台单语言首页配置详情。

    输入：数据库会话、固定页面和语言。
    输出：dict，语言、布局和可选公开产品。
    """
    translation = await session.scalar(
        select(SitePageTranslation).where(
            SitePageTranslation.site_page_id == page.id,
            SitePageTranslation.locale_id == locale.id,
        )
    )
    layout = await session.scalar(
        select(HomepageLayout).where(
            HomepageLayout.site_page_id == page.id,
            HomepageLayout.locale_id == locale.id,
        )
    )
    if translation is None or layout is None:
        raise AppException(409, "homepage_layout_incomplete", "首页双语记录不完整")
    return {
        "locale": {
            "code": locale.code,
            "slug": locale.slug,
            "name": locale.name,
            "native_name": locale.native_name,
        },
        "translation": {"display_name": translation.display_name},
        "layout": _serialize_layout(layout),
        "products": await _public_product_options(session, locale),
    }


async def get_homepage_detail(session: AsyncSession) -> dict[str, Any]:
    """
    返回固定首页的双语后台详情。

    输入：
        session: AsyncSession，数据库会话。
    输出：
        dict，页面身份和双语布局。
    """
    page = await _homepage_page(session)
    locales = await _homepage_locales(session)
    return {
        "page": {"system_key": page.system_key, "status": page.status},
        "languages": [
            await _language_detail(session, page, locale)
            for locale in locales.values()
        ],
    }


async def get_homepage_language_detail(
    session: AsyncSession,
    locale_code: str,
) -> dict[str, Any]:
    """输入数据库会话和语言代码；输出单语言首页后台详情。"""
    page, locale, _layout = await _homepage_layout(
        session,
        locale_code=locale_code,
    )
    return await _language_detail(session, page, locale)


def _config_from_payload(payload: HomepageDraftUpdate) -> dict[str, Any]:
    """
    把 Pydantic 输入转换为稳定 JSON 配置。

    输入：
        payload: HomepageDraftUpdate，完整白名单输入。
    输出：
        dict，schema_version=1 的配置。
    """
    return {
        "schema_version": 1,
        "modules": [
            module.model_dump(mode="json") for module in payload.modules
        ],
    }


async def _validate_product_references(
    session: AsyncSession,
    locale: Locale,
    config: dict[str, Any],
) -> None:
    """
    确保首页只引用当前语言严格公开的产品 slug。

    输入：数据库会话、语言和待保存配置。
    输出：None；引用草稿、禁用或不存在产品时抛出 409。
    """
    requested = {
        slug
        for module in config["modules"]
        for slug in module.get("product_slugs", [])
    }
    if not requested:
        return
    available = {
        product["slug"] for product in await _public_product_options(session, locale)
    }
    missing = sorted(requested - available)
    if missing:
        raise AppException(
            409,
            "homepage_product_reference_unavailable",
            "首页产品引用必须是当前语言已发布内容",
            details={"slugs": missing},
        )


async def save_homepage_draft(
    session: AsyncSession,
    *,
    locale_code: str,
    payload: HomepageDraftUpdate,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    以乐观锁保存完整首页草稿并写 Revision/Audit。

    输入：数据库会话、语言、草稿输入和操作用户ID。
    输出：dict，保存后单语言真实详情。
    """
    _page, locale, layout = await _homepage_layout(
        session,
        locale_code=locale_code,
        lock=True,
    )
    if layout.draft_revision != payload.expected_revision:
        raise AppException(
            409,
            "homepage_revision_conflict",
            "首页草稿已被其他操作更新",
            details={"current_revision": layout.draft_revision},
        )
    config = _config_from_payload(payload)
    await _validate_product_references(session, locale, config)
    if layout.draft_config_jsonb == config:
        return await get_homepage_language_detail(session, locale_code)

    layout.draft_config_jsonb = clone_homepage_config(config)
    layout.draft_revision += 1
    layout.updated_by = actor_id
    await store_revision(
        session,
        "homepage_layout",
        layout.id,
        locale.id,
        jsonable_encoder(
            {
                "event": "draft.save",
                "draft_revision": layout.draft_revision,
                "config": config,
            }
        ),
        actor_id,
    )
    write_audit_log(
        session,
        action="homepage.draft.save",
        target_type="homepage_layout",
        target_id=str(layout.id),
        user_id=actor_id,
        metadata={
            "locale_code": locale.code,
            "draft_revision": layout.draft_revision,
        },
    )
    await session.flush()
    return await get_homepage_language_detail(session, locale_code)


async def apply_homepage_layout(
    session: AsyncSession,
    *,
    locale_code: str,
    expected_revision: int,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    把当前草稿原子应用到普通首页。

    输入：数据库会话、语言、期望草稿修订号和操作用户ID。
    输出：dict，应用后单语言真实详情。
    """
    _page, locale, layout = await _homepage_layout(
        session,
        locale_code=locale_code,
        lock=True,
    )
    if layout.draft_revision != expected_revision:
        raise AppException(
            409,
            "homepage_revision_conflict",
            "首页草稿修订号不一致",
            details={"current_revision": layout.draft_revision},
        )
    await _validate_product_references(
        session,
        locale,
        layout.draft_config_jsonb,
    )
    if layout.applied_config_jsonb == layout.draft_config_jsonb:
        return await get_homepage_language_detail(session, locale_code)

    layout.applied_config_jsonb = clone_homepage_config(layout.draft_config_jsonb)
    layout.applied_revision += 1
    layout.applied_by = actor_id
    layout.applied_at = datetime.now(UTC)
    await store_revision(
        session,
        "homepage_layout",
        layout.id,
        locale.id,
        jsonable_encoder(
            {
                "event": "layout.apply",
                "draft_revision": layout.draft_revision,
                "applied_revision": layout.applied_revision,
                "config": layout.applied_config_jsonb,
            }
        ),
        actor_id,
    )
    write_audit_log(
        session,
        action="homepage.layout.apply",
        target_type="homepage_layout",
        target_id=str(layout.id),
        user_id=actor_id,
        metadata={
            "locale_code": locale.code,
            "draft_revision": layout.draft_revision,
            "applied_revision": layout.applied_revision,
        },
    )
    await session.flush()
    return await get_homepage_language_detail(session, locale_code)


async def restore_homepage_draft(
    session: AsyncSession,
    *,
    locale_code: str,
    expected_revision: int,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    """
    把当前应用版恢复为新草稿，不直接改变普通首页。

    输入：数据库会话、语言、期望草稿修订号和操作用户ID。
    输出：dict，恢复后单语言真实详情。
    """
    _page, locale, layout = await _homepage_layout(
        session,
        locale_code=locale_code,
        lock=True,
    )
    if layout.draft_revision != expected_revision:
        raise AppException(
            409,
            "homepage_revision_conflict",
            "首页草稿修订号不一致",
            details={"current_revision": layout.draft_revision},
        )
    if layout.draft_config_jsonb == layout.applied_config_jsonb:
        return await get_homepage_language_detail(session, locale_code)

    layout.draft_config_jsonb = clone_homepage_config(layout.applied_config_jsonb)
    layout.draft_revision += 1
    layout.updated_by = actor_id
    await store_revision(
        session,
        "homepage_layout",
        layout.id,
        locale.id,
        jsonable_encoder(
            {
                "event": "draft.restore",
                "draft_revision": layout.draft_revision,
                "config": layout.draft_config_jsonb,
            }
        ),
        actor_id,
    )
    write_audit_log(
        session,
        action="homepage.draft.restore",
        target_type="homepage_layout",
        target_id=str(layout.id),
        user_id=actor_id,
        metadata={
            "locale_code": locale.code,
            "draft_revision": layout.draft_revision,
        },
    )
    await session.flush()
    return await get_homepage_language_detail(session, locale_code)


async def get_homepage_configuration(
    session: AsyncSession,
    *,
    locale_id: uuid.UUID,
    use_draft: bool,
) -> tuple[dict[str, Any], int]:
    """
    读取公开应用版或认证作者草稿配置；未初始化时使用安全默认。

    输入：数据库会话、语言ID和是否读取草稿。
    输出：tuple，配置及对应修订号。
    """
    page = await session.scalar(
        select(SitePage).where(
            SitePage.system_key == HOMEPAGE_SYSTEM_KEY,
            SitePage.status == "enabled",
        )
    )
    if page is None:
        return default_homepage_config(), 0
    layout = await session.scalar(
        select(HomepageLayout).where(
            HomepageLayout.site_page_id == page.id,
            HomepageLayout.locale_id == locale_id,
        )
    )
    if layout is None:
        return default_homepage_config(), 0
    if use_draft:
        return clone_homepage_config(layout.draft_config_jsonb), layout.draft_revision
    return clone_homepage_config(layout.applied_config_jsonb), layout.applied_revision


def _module_content_state(
    key: str,
    home: dict[str, Any],
) -> tuple[str, str | None]:
    """
    根据真实公开 DTO 判断模块内容状态。

    输入：模块键和首页公开数据。
    输出：tuple，available/missing 与缺件原因。
    """
    company = home.get("company")
    availability = {
        "hero": bool(company),
        "core_product_families": bool(
            home.get("product_categories") or home.get("homepage_products")
        ),
        "materials": bool(home.get("materials")),
        "special_applications": bool(home.get("applications")),
        "technologies": bool(home.get("technologies")),
        "manufacturing_capability": bool(home.get("capabilities")),
        "why_junhui": bool(
            company
            and (
                company.get("full_intro")
                or company.get("short_intro")
                or company.get("advantages")
            )
        ),
        "factory_equipment": bool(
            home.get("equipment") or home.get("factory_media")
        ),
        "solutions": bool(home.get("solutions")),
        "case_studies": bool(home.get("cases")),
        "technical_knowledge": bool(home.get("knowledge")),
        "certificates_patents": bool(
            home.get("certificates") or home.get("patents")
        ),
        "global_markets": bool(
            company and company.get("export_markets")
        ),
        "rfq_cta": True,
    }
    if availability[key]:
        return "available", None
    return "missing", "尚无符合公开门禁的内容"


def attach_homepage_presentation(
    home: dict[str, Any],
    *,
    config: dict[str, Any],
    revision: int,
    preview: bool,
) -> dict[str, Any]:
    """
    给首页公开数据附加排序、显示、状态和管理入口。

    输入：首页数据、已验证配置、修订号和预览标志。
    输出：dict，带安全 presentation DTO 的首页数据。
    """
    modules = []
    for module in config["modules"]:
        key = module["key"]
        content_status, missing_reason = _module_content_state(key, home)
        modules.append(
            {
                **deepcopy(module),
                "content_status": content_status,
                "missing_reason": missing_reason,
                "management_url": HOMEPAGE_MANAGEMENT_URLS[key],
            }
        )
    home["presentation"] = {
        "revision": revision,
        "modules": modules,
    }
    home["preview"] = preview
    return home


async def get_homepage_preview(
    session: AsyncSession,
    locale_code: str,
) -> dict[str, Any]:
    """
    为已认证作者读取草稿布局和严格公开内容。

    输入：数据库会话和语言代码。
    输出：dict，preview=true 的完整首页 DTO。
    """
    from app.modules.discovery.public_collections import get_public_home

    locale = await session.scalar(
        select(Locale).where(
            Locale.code == locale_code,
            Locale.is_enabled.is_(True),
        )
    )
    if locale is None:
        raise AppException(404, "homepage_locale_not_found", "首页语言不存在")
    return await get_public_home(
        session,
        locale.slug,
        use_draft_layout=True,
        preview=True,
    )


async def _count(session: AsyncSession, model: type[Any]) -> int:
    """输入数据库会话和ORM模型；输出真实记录总数。"""
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def get_site_overview(
    session: AsyncSession,
    locale_code: str,
) -> dict[str, Any]:
    """
    生成全站模块的实际实现、数据、导航和隐藏原因总览。

    输入：数据库会话和语言代码。
    输出：dict，供 Admin 只读总览使用。
    """
    from app.modules.discovery.public_collections import (
        get_public_home,
        get_public_navigation,
    )

    locale = await session.scalar(
        select(Locale).where(
            Locale.code == locale_code,
            Locale.is_enabled.is_(True),
        )
    )
    if locale is None:
        raise AppException(404, "homepage_locale_not_found", "首页语言不存在")
    home = await get_public_home(session, locale.slug)
    navigation = await get_public_navigation(session, locale.slug)
    public_counts = {
        "hero": 1 if home.get("company") else 0,
        "core_product_families": len(home.get("homepage_products", [])),
        "materials": len(home.get("materials", [])),
        "special_applications": len(home.get("applications", [])),
        "technologies": len(home.get("technologies", [])),
        "manufacturing_capability": len(home.get("capabilities", [])),
        "why_junhui": 1 if home.get("company") else 0,
        "factory_equipment": len(home.get("equipment", [])),
        "solutions": len(home.get("solutions", [])),
        "case_studies": len(home.get("cases", [])),
        "technical_knowledge": len(home.get("knowledge", [])),
        "certificates_patents": len(home.get("certificates", []))
        + len(home.get("patents", [])),
        "global_markets": len(
            (home.get("company") or {}).get("export_markets") or []
        ),
        "rfq_cta": 1,
    }
    actual_counts = {
        "hero": await _count(session, CompanyProfile),
        "core_product_families": await _count(session, Product),
        "materials": await _count(session, Material),
        "special_applications": await _count(session, Application),
        "technologies": await _count(session, Technology),
        "manufacturing_capability": await _count(
            session, ManufacturingCapability
        ),
        "why_junhui": await _count(session, CompanyProfile),
        "factory_equipment": await _count(session, Equipment),
        "solutions": await _count(session, Solution),
        "case_studies": await _count(session, CaseStudy),
        "technical_knowledge": await _count(session, KnowledgeArticle),
        "certificates_patents": await _count(session, Certificate)
        + await _count(session, Patent),
        "global_markets": await _count(session, CompanyProfile),
        "rfq_cta": 1,
    }
    frontend_paths = {
        "hero": f"/{locale.slug}/",
        "core_product_families": f"/{locale.slug}/products/",
        "materials": f"/{locale.slug}/materials/",
        "special_applications": f"/{locale.slug}/applications/",
        "technologies": f"/{locale.slug}/technologies/",
        "manufacturing_capability": f"/{locale.slug}/capabilities/",
        "why_junhui": f"/{locale.slug}/about/",
        "factory_equipment": f"/{locale.slug}/capabilities/",
        "solutions": f"/{locale.slug}/solutions/",
        "case_studies": f"/{locale.slug}/case-studies/",
        "technical_knowledge": f"/{locale.slug}/knowledge/",
        "certificates_patents": f"/{locale.slug}/certificates/",
        "global_markets": f"/{locale.slug}/about/",
        "rfq_cta": f"/{locale.slug}/request-a-quote/",
    }
    primary = set(navigation["primary"])
    navigation_keys = {
        "core_product_families": "products",
        "materials": "materials",
        "special_applications": "applications",
        "manufacturing_capability": "capabilities",
        "solutions": "solutions",
        "case_studies": "case_studies",
        "technical_knowledge": "knowledge",
        "why_junhui": "about",
    }
    items = []
    for key in HOMEPAGE_MODULE_KEYS:
        navigation_key = navigation_keys.get(key)
        if key == "technologies":
            navigation_status = "not_in_primary_registry"
        elif navigation_key is None:
            navigation_status = "not_primary_navigation"
        else:
            navigation_status = (
                "visible" if navigation_key in primary else "hidden_no_public_content"
            )
        items.append(
            {
                "key": key,
                "frontend_url": frontend_paths[key],
                "admin_url": HOMEPAGE_MANAGEMENT_URLS[key],
                "actual_count": actual_counts[key],
                "public_count": public_counts[key],
                "navigation_status": navigation_status,
                "implementation": "homepage_renderer_and_source",
                "hidden_reason": (
                    None
                    if public_counts[key]
                    else "当前语言没有符合公开门禁的内容"
                ),
            }
        )
    items.extend(
        [
            {
                "key": "products",
                "frontend_url": f"/{locale.slug}/products/",
                "admin_url": "/catalog/products",
                "actual_count": await _count(session, Product),
                "public_count": len(home.get("homepage_products", [])),
                "navigation_status": (
                    "visible" if "products" in primary else "hidden_no_public_content"
                ),
                "implementation": "frontend_and_admin",
                "hidden_reason": None,
            },
            {
                "key": "about",
                "frontend_url": f"/{locale.slug}/about/",
                "admin_url": "/trust/company",
                "actual_count": await _count(session, CompanyProfile),
                "public_count": 1 if home.get("company") else 0,
                "navigation_status": (
                    "visible" if "about" in primary else "hidden_no_public_content"
                ),
                "implementation": "frontend_and_admin",
                "hidden_reason": None,
            },
            {
                "key": "search",
                "frontend_url": f"/{locale.slug}/search/",
                "admin_url": None,
                "actual_count": 0,
                "public_count": 0,
                "navigation_status": "utility_navigation",
                "implementation": "public_search_service",
                "hidden_reason": None,
            },
            {
                "key": "privacy",
                "frontend_url": f"/{locale.slug}/privacy/",
                "admin_url": "/privacy",
                "actual_count": 0,
                "public_count": 0,
                "navigation_status": "footer_when_published",
                "implementation": "private_draft_current_empty",
                "hidden_reason": "正式政策未批准发布",
            },
            {
                "key": "contact",
                "frontend_url": f"/{locale.slug}/request-a-quote/",
                "admin_url": "/trust/company",
                "actual_count": await _count(session, CompanyProfile),
                "public_count": 1
                if home.get("company")
                and any(
                    home["company"].get(field)
                    for field in ("phone", "email", "address")
                )
                else 0,
                "navigation_status": "footer_or_rfq_entry",
                "implementation": "contact_entry_only",
                "hidden_reason": (
                    None
                    if home.get("company")
                    and any(
                        home["company"].get(field)
                        for field in ("phone", "email", "address")
                    )
                    else "当前公开公司资料没有联系方式"
                ),
            },
        ]
    )
    return {
        "locale": locale.code,
        "items": items,
        "summary": {
            "homepage_components": len(HOMEPAGE_MODULE_KEYS),
            "homepage_with_public_content": sum(
                1 for key in HOMEPAGE_MODULE_KEYS if public_counts[key] > 0
            ),
            "homepage_missing_content": sum(
                1 for key in HOMEPAGE_MODULE_KEYS if public_counts[key] == 0
            ),
        },
    }
