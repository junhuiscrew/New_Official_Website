"""为全局导航与首页提供严格发布的公开内容聚合。"""

from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.authority.models import (
    CaseStudy,
    CaseStudyTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
)
from app.modules.catalog.models import (
    Application,
    ApplicationTranslation,
    Material,
    MaterialTranslation,
    Product,
    ProductCategory,
    ProductCategoryTranslation,
    ProductTranslation,
    Solution,
    SolutionTranslation,
)
from app.modules.company.models import (
    CompanyProfile,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.company.services import get_public_company_profile
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.discovery.models import SeoDocument
from app.modules.localization.models import Locale

from .public_delivery import OFFICIAL_ORIGIN, _locale, _public_media


class _CollectionConfig(NamedTuple):
    """描述公开集合实体、翻译外键及允许输出的文本字段。"""

    model: type
    translation_model: type
    owner_field: str
    title_field: str
    summary_fields: tuple[str, ...]


_COLLECTION_CONFIG: dict[str, _CollectionConfig] = {
    "product_category": _CollectionConfig(
        ProductCategory,
        ProductCategoryTranslation,
        "category_id",
        "name",
        ("short_description", "description"),
    ),
    "product": _CollectionConfig(
        Product,
        ProductTranslation,
        "product_id",
        "name",
        ("short_description", "description"),
    ),
    "material": _CollectionConfig(
        Material,
        MaterialTranslation,
        "material_id",
        "name",
        ("definition", "processing_characteristics"),
    ),
    "solution": _CollectionConfig(
        Solution,
        SolutionTranslation,
        "solution_id",
        "name",
        ("definition", "symptoms", "solution"),
    ),
    "application": _CollectionConfig(
        Application,
        ApplicationTranslation,
        "application_id",
        "name",
        ("description", "technical_requirements"),
    ),
    "manufacturing_capability": _CollectionConfig(
        ManufacturingCapability,
        ManufacturingCapabilityTranslation,
        "capability_id",
        "name",
        ("summary", "description"),
    ),
    "case_study": _CollectionConfig(
        CaseStudy,
        CaseStudyTranslation,
        "case_study_id",
        "title",
        ("summary",),
    ),
    "knowledge_article": _CollectionConfig(
        KnowledgeArticle,
        KnowledgeArticleTranslation,
        "article_id",
        "title",
        ("summary",),
    ),
}

_PRIMARY_NAVIGATION = (
    "products",
    "solutions",
    "materials",
    "applications",
    "capabilities",
    "case_studies",
    "knowledge",
    "about",
)


async def _published_rows(
    session: AsyncSession,
    owner_type: str,
    locale: Locale,
    limit: int,
    featured_only: bool,
) -> list[dict[str, str]]:
    """
    返回通过统一公开门禁的 canonical Link DTO 集合。

    输入：
        session: AsyncSession，数据库会话。
        owner_type: str，业务实体类型。
        locale: Locale，已启用的目标语言。
        limit: int，最多返回的有效条目数。
        featured_only: bool，是否仅返回业务层标记为推荐的实体。

    输出：
        list[dict[str, str]]，仅含类型、slug、名称、canonical 路径与摘要。
    """
    config = _COLLECTION_CONFIG.get(owner_type)
    if config is None or limit <= 0:
        return []

    model = config.model
    translation_model = config.translation_model
    statement = (
        select(model, translation_model, ContentRoute)
        .join(
            translation_model,
            getattr(translation_model, config.owner_field) == model.id,
        )
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
        .join(
            TranslationStatus,
            (TranslationStatus.owner_type == ContentRoute.owner_type)
            & (TranslationStatus.owner_id == ContentRoute.owner_id)
            & (TranslationStatus.locale_id == ContentRoute.locale_id),
        )
        .join(Locale, Locale.id == ContentRoute.locale_id)
        .outerjoin(
            SeoDocument,
            (SeoDocument.owner_type == ContentRoute.owner_type)
            & (SeoDocument.owner_id == ContentRoute.owner_id)
            & (SeoDocument.locale_id == ContentRoute.locale_id),
        )
        .where(
            model.status == "enabled",
            translation_model.locale_id == locale.id,
            Locale.id == locale.id,
            Locale.is_enabled.is_(True),
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override == "",
                SeoDocument.canonical_override
                == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
    )
    if featured_only:
        featured_column = getattr(model, "featured", None)
        if featured_column is None:
            return []
        statement = statement.where(featured_column.is_(True))

    # 数据库内一次完成公开门禁和 limit，避免对每个候选重复查询生命周期。
    order_columns = []
    if hasattr(model, "sort_order"):
        order_columns.append(model.sort_order)
    order_columns.extend((model.created_at, model.slug))
    rows = (
        await session.execute(statement.order_by(*order_columns).limit(limit))
    ).all()

    result: list[dict[str, str]] = []
    for entity, translation, route in rows:
        summary = next(
            (
                str(value)
                for field in config.summary_fields
                if (value := getattr(translation, field, None))
            ),
            "",
        )
        result.append(
            {
                "type": owner_type,
                "slug": entity.slug,
                "name": str(getattr(translation, config.title_field)),
                "url": route.path,
                "summary": summary,
            }
        )
    return result


async def _published_company(
    session: AsyncSession,
    locale: Locale,
) -> tuple[dict[str, Any], CompanyProfile] | None:
    """
    取得通过统一公开门禁的真实 Company Profile/Public DTO。

    输入：
        session: AsyncSession，数据库会话。
        locale: Locale，已启用的目标语言。

    输出：
        tuple[dict[str, Any], CompanyProfile] | None，公开 DTO 与实体；缺失时返回 None。
    """
    try:
        public_dto = await get_public_company_profile(session, locale.slug)
    except AppException:
        return None
    public_url = public_dto.get("url")
    if not isinstance(public_url, str) or not public_url.startswith(OFFICIAL_ORIGIN):
        return None

    route_path = public_url.removeprefix(OFFICIAL_ORIGIN)
    profile = await session.scalar(
        select(CompanyProfile)
        .join(
            ContentRoute,
            (ContentRoute.owner_type == "company_profile")
            & (ContentRoute.owner_id == CompanyProfile.id)
            & (ContentRoute.locale_id == locale.id),
        )
        .join(
            ContentPublication,
            (ContentPublication.owner_type == ContentRoute.owner_type)
            & (ContentPublication.owner_id == ContentRoute.owner_id)
            & (ContentPublication.locale_id == ContentRoute.locale_id),
        )
        .join(
            TranslationStatus,
            (TranslationStatus.owner_type == ContentRoute.owner_type)
            & (TranslationStatus.owner_id == ContentRoute.owner_id)
            & (TranslationStatus.locale_id == ContentRoute.locale_id),
        )
        .outerjoin(
            SeoDocument,
            (SeoDocument.owner_type == ContentRoute.owner_type)
            & (SeoDocument.owner_id == ContentRoute.owner_id)
            & (SeoDocument.locale_id == ContentRoute.locale_id),
        )
        .where(
            CompanyProfile.status == "enabled",
            ContentRoute.path == route_path,
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override == "",
                SeoDocument.canonical_override
                == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
    )
    if profile is None:
        return None
    return public_dto, profile


def _trust_summary(company: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    从真实公开 Company DTO 提取首页可信度事实摘要。

    输入：
        company: dict[str, Any] | None，已通过公开门禁的公司 DTO。

    输出：
        dict[str, Any] | None，仅保留数据库中实际存在的事实；无事实时返回 None。
    """
    if company is None:
        return None
    fact_fields = (
        "founded_year",
        "years_experience",
        "employee_count_range",
        "factory_area_sqm",
        "annual_capacity_text",
        "export_markets",
    )
    facts = {
        field: company[field] for field in fact_fields if company.get(field) not in (None, [], "")
    }
    return facts or None


async def get_public_navigation(
    session: AsyncSession,
    locale_slug: str,
) -> dict[str, Any]:
    """
    聚合 Desktop/Mobile 导航所需的公开内容与公司联系方式。

    输入：
        session: AsyncSession，数据库会话。
        locale_slug: str，URL 中的语言标识。

    输出：
        dict[str, Any]，只含静态导航键及严格发布的 canonical Link DTO。
    """
    locale = await _locale(session, locale_slug)
    product_categories = await _published_rows(session, "product_category", locale, 12, False)
    featured_products = await _published_rows(session, "product", locale, 8, True)
    featured_solutions = await _published_rows(session, "solution", locale, 8, True)
    solution_problems = await _published_rows(session, "solution", locale, 12, False)
    materials = await _published_rows(session, "material", locale, 8, True)
    applications = await _published_rows(session, "application", locale, 8, True)
    company_result = await _published_company(session, locale)
    company = company_result[0] if company_result else None

    return {
        "locale": locale.slug,
        # 这里只返回稳定键；可见标签和 index 路径由 Nuxt i18n/路由负责。
        "primary": list(_PRIMARY_NAVIGATION),
        "products": {
            "categories": product_categories,
            "featured": featured_products,
        },
        "solutions": {
            "featured": featured_solutions,
            "problems": solution_problems,
        },
        "materials": materials,
        "applications": applications,
        "company": (
            {
                "name": company["company_name"],
                "phone": company.get("phone"),
                "email": company.get("email"),
                "address": company.get("address"),
            }
            if company
            else None
        ),
    }


async def get_public_home(
    session: AsyncSession,
    locale_slug: str,
) -> dict[str, Any]:
    """
    聚合首页一次 SSR 请求所需的真实公开内容。

    输入：
        session: AsyncSession，数据库会话。
        locale_slug: str，URL 中的语言标识。

    输出：
        dict[str, Any]，缺失内容族使用空数组或 None，不构造任何业务事实。
    """
    locale = await _locale(session, locale_slug)
    company_result = await _published_company(session, locale)
    company = company_result[0] if company_result else None
    profile = company_result[1] if company_result else None
    hero_media = (
        await _public_media(
            session,
            profile.primary_factory_media_id,
            locale.id,
            company["company_name"],
            loading="eager",
        )
        if company is not None and profile is not None
        else None
    )

    return {
        "locale": locale.slug,
        "company": company,
        "hero_media": hero_media.model_dump() if hero_media else None,
        "product_categories": await _published_rows(session, "product_category", locale, 12, False),
        "featured_products": await _published_rows(session, "product", locale, 12, True),
        "materials": await _published_rows(session, "material", locale, 8, False),
        "solutions": await _published_rows(session, "solution", locale, 8, False),
        "capabilities": await _published_rows(
            session, "manufacturing_capability", locale, 8, False
        ),
        "applications": await _published_rows(session, "application", locale, 8, False),
        "cases": await _published_rows(session, "case_study", locale, 6, False),
        "knowledge": await _published_rows(session, "knowledge_article", locale, 6, False),
        "trust_summary": _trust_summary(company),
    }
