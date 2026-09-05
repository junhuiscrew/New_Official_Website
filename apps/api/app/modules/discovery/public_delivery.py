"""Product、Case 与 Knowledge 的严格公开查询和 DTO 聚合。"""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.authority.models import (
    FAQ,
    ArticleApplication,
    ArticleCase,
    ArticleFAQ,
    ArticleMaterial,
    ArticleProduct,
    ArticleSolution,
    ArticleTechnology,
    AuthorExpert,
    AuthorExpertTranslation,
    CaseApplication,
    CaseMaterial,
    CaseProduct,
    CaseSolution,
    CaseStudy,
    CaseStudyTranslation,
    CaseTechnology,
    FAQCase,
    FAQProduct,
    FAQTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
    KnowledgeCategory,
    KnowledgeCategoryTranslation,
)
from app.modules.authority.public import serialize_public_case
from app.modules.catalog.models import (
    Application,
    ApplicationSolution,
    ApplicationTranslation,
    Material,
    MaterialSolution,
    MaterialTechnology,
    MaterialTranslation,
    Product,
    ProductApplication,
    ProductCategory,
    ProductCategoryTranslation,
    ProductMaterial,
    ProductModel,
    ProductSolution,
    ProductTechnology,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.company.models import (
    CompanyProfile,
    CompanyProfileTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.discovery.models import GeoDocument, SeoDocument, SourceCitation
from app.modules.discovery.schema_generator import (
    build_article_schema,
    build_breadcrumb_schema,
    build_faq_schema,
    build_person_schema,
    build_product_schema,
    build_webpage_schema,
)
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation

from .public_schemas import PublicMediaDto
from .public_specs import serialize_public_specifications

OFFICIAL_ORIGIN = "https://junhuiscrewbarrel.com"
PUBLIC_HANDLER_OWNER_TYPES = frozenset(
    {
        "product_category",
        "product",
        "material",
        "technology",
        "application",
        "solution",
        "case_study",
        "knowledge_article",
        "author_expert",
        "manufacturing_capability",
        "exhibition",
        "company_profile",
    }
)

CATALOG_PUBLIC_TYPES: dict[str, tuple[type, type, str, tuple[str, ...]]] = {
    "product_category": (
        ProductCategory,
        ProductCategoryTranslation,
        "category_id",
        ("short_description", "description"),
    ),
    "material": (
        Material,
        MaterialTranslation,
        "material_id",
        (
            "definition",
            "processing_characteristics",
            "screw_impact",
            "recommendations",
            "limitations",
        ),
    ),
    "technology": (
        Technology,
        TechnologyTranslation,
        "technology_id",
        ("definition", "process_description", "benefits", "limitations"),
    ),
    "application": (
        Application,
        ApplicationTranslation,
        "application_id",
        ("description", "technical_requirements", "common_problems"),
    ),
    "solution": (
        Solution,
        SolutionTranslation,
        "solution_id",
        ("definition", "symptoms", "causes", "diagnosis", "solution", "limitations"),
    ),
}

# 每类目录详情只读取既有显式关系，目标仍统一通过发布、路由与 SEO 门禁。
CATALOG_RELATION_TYPES: dict[str, tuple[tuple[str, type, str, str, str], ...]] = {
    "material": (
        ("products", ProductMaterial, "material_id", "product_id", "product"),
        ("technologies", MaterialTechnology, "material_id", "technology_id", "technology"),
        ("solutions", MaterialSolution, "material_id", "solution_id", "solution"),
        ("cases", CaseMaterial, "material_id", "case_study_id", "case_study"),
        ("knowledge", ArticleMaterial, "material_id", "article_id", "knowledge_article"),
    ),
    "technology": (
        ("products", ProductTechnology, "technology_id", "product_id", "product"),
        ("materials", MaterialTechnology, "technology_id", "material_id", "material"),
        ("cases", CaseTechnology, "technology_id", "case_study_id", "case_study"),
        ("knowledge", ArticleTechnology, "technology_id", "article_id", "knowledge_article"),
    ),
    "application": (
        ("products", ProductApplication, "application_id", "product_id", "product"),
        ("solutions", ApplicationSolution, "application_id", "solution_id", "solution"),
        ("cases", CaseApplication, "application_id", "case_study_id", "case_study"),
        ("knowledge", ArticleApplication, "application_id", "article_id", "knowledge_article"),
    ),
    "solution": (
        ("products", ProductSolution, "solution_id", "product_id", "product"),
        ("materials", MaterialSolution, "solution_id", "material_id", "material"),
        ("applications", ApplicationSolution, "solution_id", "application_id", "application"),
        ("cases", CaseSolution, "solution_id", "case_study_id", "case_study"),
        ("knowledge", ArticleSolution, "solution_id", "article_id", "knowledge_article"),
    ),
}

CATALOG_COLLECTION_LABELS: dict[str, dict[str, str]] = {
    "product_category": {"en": "Products", "zh-cn": "产品"},
    "material": {"en": "Materials", "zh-cn": "材料"},
    "technology": {"en": "Technologies", "zh-cn": "处理技术"},
    "application": {"en": "Applications", "zh-cn": "应用"},
    "solution": {"en": "Solutions", "zh-cn": "解决方案"},
}

CATALOG_COLLECTION_PATHS: dict[str, str] = {
    "product_category": "products",
    "material": "materials",
    "technology": "technologies",
    "application": "applications",
    "solution": "solutions",
}

# 单个关系分组限制公开链接数量，避免详情页响应与 SSR DOM 无界增长。
PUBLIC_RELATION_LINK_LIMIT = 12


def _columns(entity: Any) -> dict[str, Any]:
    """
    将已通过公开字段选择的 ORM 实体转为 JSON。

    输入：entity，SQLAlchemy 实体。
    输出：dict，列值字典。
    """
    return jsonable_encoder(
        {column.name: getattr(entity, column.name) for column in entity.__table__.columns}
    )


async def _locale(session: AsyncSession, locale_slug: str) -> Locale:
    """
    查找启用语言。

    输入：session 与 URL locale_slug。
    输出：Locale；不存在或停用时返回公开 404。
    """
    locale = await session.scalar(
        select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True))
    )
    if locale is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    return locale


async def _public_media(
    session: AsyncSession,
    media_id: Any,
    locale_id: Any,
    fallback_alt: str,
    *,
    loading: str = "lazy",
) -> PublicMediaDto | None:
    """
    将媒体引用解析为安全公开代理 DTO。

    输入：
        session: AsyncSession，数据库会话。
        media_id: Any，业务实体引用的媒体 ID。
        locale_id: Any，当前语言 ID。
        fallback_alt: str，对应公开实体在当前语言下的显示名称。
        loading: str，浏览器加载策略，主媒体使用 eager。

    输出：
        PublicMediaDto | None，仅 ready public-media 资产可返回。
    """
    if media_id is None:
        return None
    asset = await session.get(MediaAsset, media_id)
    if (
        asset is None
        or asset.visibility != "public"
        or asset.storage_bucket != "public-media"
        or asset.upload_status != "ready"
    ):
        return None
    translation = await session.scalar(
        select(MediaAssetTranslation).where(
            MediaAssetTranslation.media_asset_id == asset.id,
            MediaAssetTranslation.locale_id == locale_id,
        )
    )
    translated_alt = translation.alt_text.strip() if translation and translation.alt_text else ""
    alt = translated_alt or fallback_alt.strip()
    # 翻译与实体名称均无可见文本时过滤媒体，杜绝公开空 alt。
    if not alt:
        return None
    return PublicMediaDto(
        src=f"/api/v1/public/media/{asset.id}",
        type=asset.media_type,
        mime_type=asset.mime_type,
        width=asset.width,
        height=asset.height,
        alt=alt,
        caption=translation.caption if translation else None,
        loading=loading,
    )


async def _public_route(
    session: AsyncSession,
    owner_type: str,
    owner_id: Any,
    locale_id: Any,
) -> tuple[ContentRoute, SeoDocument | None, GeoDocument | None]:
    """
    强制公开页面满足发布、翻译、canonical、路由和 robots_index 条件。

    输入：session、owner 标识与 locale_id。
    输出：(route, seo, geo)；任一公开门槛不满足时返回 404。
    """
    statement = (
        select(ContentRoute, SeoDocument)
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
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == owner_id,
            ContentRoute.locale_id == locale_id,
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
        )
    )
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo = row
    geo = await session.scalar(
        select(GeoDocument).where(
            GeoDocument.owner_type == owner_type,
            GeoDocument.owner_id == owner_id,
            GeoDocument.locale_id == locale_id,
        )
    )
    return route, seo, geo


async def _published_alternates(
    session: AsyncSession,
    owner_type: str,
    owner_id: Any,
) -> dict[str, str]:
    """
    查询同一实体全部严格已发布语言，生成 reciprocal hreflang。

    输入：session、owner_type 与 owner_id。
    输出：dict，Locale code 到绝对 canonical URL，并为默认语言补 x-default。
    """
    rows = (
        await session.execute(
            select(ContentRoute, Locale)
            .join(Locale, Locale.id == ContentRoute.locale_id)
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
                ContentRoute.owner_type == owner_type,
                ContentRoute.owner_id == owner_id,
                ContentRoute.is_canonical.is_(True),
                ContentRoute.active.is_(True),
                ContentRoute.indexable.is_(True),
                ContentPublication.status == "published",
                TranslationStatus.status == "published",
                Locale.is_enabled.is_(True),
                or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
                or_(
                    SeoDocument.id.is_(None),
                    SeoDocument.canonical_override.is_(None),
                    SeoDocument.canonical_override == OFFICIAL_ORIGIN + ContentRoute.path,
                ),
            )
            .order_by(Locale.sort_order, Locale.code)
        )
    ).all()
    alternates = {locale.code: OFFICIAL_ORIGIN + route.path for route, locale in rows}
    default_row = next(((route, locale) for route, locale in rows if locale.is_default), None)
    if default_row:
        alternates["x-default"] = OFFICIAL_ORIGIN + default_row[0].path
    return alternates


async def _published_link(
    session: AsyncSession,
    owner_type: str,
    owner_id: Any,
    locale: Locale,
) -> dict[str, str] | None:
    """
    将关联目标解析为严格发布的 canonical Link DTO。

    输入：数据库会话、目标类型、目标 ID 与当前语言。
    输出：dict 或 None；不可公开、非 self-canonical 或缺少翻译时返回 None。
    """
    try:
        route, seo, _geo = await _public_route(session, owner_type, owner_id, locale.id)
    except AppException:
        return None
    if seo and seo.canonical_override and seo.canonical_override != OFFICIAL_ORIGIN + route.path:
        return None

    if owner_type in CATALOG_PUBLIC_TYPES:
        model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[owner_type]
        entity = await session.get(model, owner_id)
        translation = await session.scalar(
            select(translation_model).where(
                getattr(translation_model, foreign_key) == owner_id,
                translation_model.locale_id == locale.id,
            )
        )
        if entity is None or entity.status != "enabled" or translation is None:
            return None
        summary = next(
            (
                str(getattr(translation, field))
                for field in summary_fields
                if getattr(translation, field, None)
            ),
            "",
        )
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.name,
            "url": route.path,
            "summary": summary,
        }

    if owner_type == "product":
        entity = await session.get(Product, owner_id)
        translation = await session.scalar(
            select(ProductTranslation).where(
                ProductTranslation.product_id == owner_id,
                ProductTranslation.locale_id == locale.id,
            )
        )
        category = (
            await session.get(ProductCategory, entity.category_id) if entity is not None else None
        )
        if (
            entity is None
            or entity.status != "enabled"
            or category is None
            or category.status != "enabled"
            or translation is None
        ):
            return None
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.name,
            "url": route.path,
            "summary": translation.short_description or "",
        }

    if owner_type == "case_study":
        entity = await session.get(CaseStudy, owner_id)
        translation = await session.scalar(
            select(CaseStudyTranslation).where(
                CaseStudyTranslation.case_study_id == owner_id,
                CaseStudyTranslation.locale_id == locale.id,
            )
        )
        if entity is None or entity.status != "enabled" or translation is None:
            return None
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.title,
            "url": route.path,
            "summary": translation.summary or "",
        }

    if owner_type == "knowledge_article":
        entity = await session.get(KnowledgeArticle, owner_id)
        translation = await session.scalar(
            select(KnowledgeArticleTranslation).where(
                KnowledgeArticleTranslation.article_id == owner_id,
                KnowledgeArticleTranslation.locale_id == locale.id,
            )
        )
        category = (
            await session.get(KnowledgeCategory, entity.category_id) if entity is not None else None
        )
        author = await session.get(AuthorExpert, entity.author_id) if entity is not None else None
        author_translation = (
            await session.scalar(
                select(AuthorExpertTranslation).where(
                    AuthorExpertTranslation.author_expert_id == entity.author_id,
                    AuthorExpertTranslation.locale_id == locale.id,
                )
            )
            if entity is not None
            else None
        )
        if (
            entity is None
            or entity.status != "enabled"
            or category is None
            or category.status != "enabled"
            or author is None
            or not author.is_real_person_verified
            or author_translation is None
            or translation is None
        ):
            return None
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.title,
            "url": route.path,
            "summary": translation.summary or "",
        }
    if owner_type == "manufacturing_capability":
        entity = await session.get(ManufacturingCapability, owner_id)
        translation = await session.scalar(
            select(ManufacturingCapabilityTranslation).where(
                ManufacturingCapabilityTranslation.capability_id == owner_id,
                ManufacturingCapabilityTranslation.locale_id == locale.id,
            )
        )
        if entity is None or entity.status != "enabled" or translation is None:
            return None
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.name,
            "url": route.path,
            "summary": translation.summary or "",
        }
    return None


async def _published_capability_links(
    session: AsyncSession,
    locale: Locale,
) -> list[dict[str, str]]:
    """
    返回经过统一发布与 canonical 门禁的全局制造能力链接。

    输入：session: AsyncSession，数据库会话；locale: Locale，当前语言。
    输出：list[dict[str, str]]，最多八项公开制造能力链接。
    """
    capability_ids = list(
        (
            await session.scalars(
                select(ManufacturingCapability.id)
                .join(
                    ManufacturingCapabilityTranslation,
                    ManufacturingCapabilityTranslation.capability_id == ManufacturingCapability.id,
                )
                .join(
                    ContentRoute,
                    (ContentRoute.owner_type == "manufacturing_capability")
                    & (ContentRoute.owner_id == ManufacturingCapability.id)
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
                    ManufacturingCapability.status == "enabled",
                    ManufacturingCapabilityTranslation.locale_id == locale.id,
                    ContentRoute.is_canonical.is_(True),
                    ContentRoute.active.is_(True),
                    ContentRoute.indexable.is_(True),
                    ContentPublication.status == "published",
                    TranslationStatus.status == "published",
                    or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
                    or_(
                        SeoDocument.id.is_(None),
                        SeoDocument.canonical_override.is_(None),
                        SeoDocument.canonical_override
                        == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
                    ),
                )
                .order_by(
                    ManufacturingCapability.sort_order,
                    ManufacturingCapability.created_at,
                )
                .limit(8)
            )
        ).all()
    )
    links: list[dict[str, str]] = []
    for capability_id in capability_ids:
        link = await _published_link(
            session,
            "manufacturing_capability",
            capability_id,
            locale,
        )
        if link is not None:
            links.append(link)
    return links


async def _published_trust_summary(
    session: AsyncSession,
    locale: Locale,
) -> dict[str, Any] | None:
    """
    返回已发布公司档案中的公开可信度事实，不推导或补造数值。

    输入：session: AsyncSession，数据库会话；locale: Locale，当前语言。
    输出：dict[str, Any] | None，公开事实白名单；档案未发布时返回 None。
    """
    profile = await session.scalar(
        select(CompanyProfile)
        .join(
            CompanyProfileTranslation,
            CompanyProfileTranslation.company_profile_id == CompanyProfile.id,
        )
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
            CompanyProfileTranslation.locale_id == locale.id,
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
        .order_by(CompanyProfile.created_at)
        .limit(1)
    )
    if profile is None:
        return None
    try:
        await _public_route(session, "company_profile", profile.id, locale.id)
    except AppException:
        return None
    fact_fields = (
        "founded_year",
        "years_experience",
        "employee_count_range",
        "factory_area_sqm",
        "annual_capacity_text",
        "export_markets_json",
    )
    summary = {
        ("export_markets" if field == "export_markets_json" else field): getattr(profile, field)
        for field in fact_fields
        if getattr(profile, field) not in (None, [], "")
    }
    return summary or None


async def _published_relation_links(
    session: AsyncSession,
    relation_model: type,
    relation_owner_column: str,
    owner_id: Any,
    target_column: str,
    target_type: str,
    locale: Locale,
) -> list[dict[str, str]]:
    """
    按关系顺序聚合严格公开目标，统一过滤草稿、停用和 noindex 页面。

    输入：会话、关系模型、来源字段/ID、目标字段/类型与语言。
    输出：list[dict[str, str]]，canonical Link DTO 列表。
    """
    if target_type in CATALOG_PUBLIC_TYPES:
        model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[target_type]
        title_field = "name"
    elif target_type == "product":
        model, translation_model, foreign_key = Product, ProductTranslation, "product_id"
        title_field, summary_fields = "name", ("short_description",)
    elif target_type == "case_study":
        model, translation_model, foreign_key = CaseStudy, CaseStudyTranslation, "case_study_id"
        title_field, summary_fields = "title", ("summary",)
    elif target_type == "knowledge_article":
        model = KnowledgeArticle
        translation_model = KnowledgeArticleTranslation
        foreign_key = "article_id"
        title_field, summary_fields = "title", ("summary",)
    else:
        return []

    # 一次联表查询完成业务状态、翻译、发布、canonical 路由与 robots 门禁。
    statement = (
        select(model, translation_model, ContentRoute)
        .select_from(relation_model)
        .join(model, model.id == getattr(relation_model, target_column))
        .join(
            translation_model,
            (getattr(translation_model, foreign_key) == model.id)
            & (translation_model.locale_id == locale.id),
        )
        .join(
            ContentRoute,
            (ContentRoute.owner_type == target_type)
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
        .outerjoin(
            SeoDocument,
            (SeoDocument.owner_type == ContentRoute.owner_type)
            & (SeoDocument.owner_id == ContentRoute.owner_id)
            & (SeoDocument.locale_id == ContentRoute.locale_id),
        )
        .where(
            getattr(relation_model, relation_owner_column) == owner_id,
            model.status == "enabled",
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
    )
    # Product 与 Knowledge 的依赖实体也必须满足详情端点的业务可见性门槛。
    if target_type == "product":
        statement = statement.join(
            ProductCategory, ProductCategory.id == Product.category_id
        ).where(ProductCategory.status == "enabled")
    elif target_type == "knowledge_article":
        statement = (
            statement.join(
                KnowledgeCategory,
                KnowledgeCategory.id == KnowledgeArticle.category_id,
            )
            .join(AuthorExpert, AuthorExpert.id == KnowledgeArticle.author_id)
            .join(
                AuthorExpertTranslation,
                (AuthorExpertTranslation.author_expert_id == KnowledgeArticle.author_id)
                & (AuthorExpertTranslation.locale_id == locale.id),
            )
            .where(
                KnowledgeCategory.status == "enabled",
                AuthorExpert.status == "enabled",
                AuthorExpert.is_real_person_verified.is_(True),
            )
        )

    rows = (
        await session.execute(
            statement.order_by(relation_model.sort_order, model.slug).limit(
                PUBLIC_RELATION_LINK_LIMIT
            )
        )
    ).all()
    return [
        {
            "type": target_type,
            "slug": entity.slug,
            "name": str(getattr(translation, title_field)),
            "url": route.path,
            "summary": next(
                (
                    str(getattr(translation, field))
                    for field in summary_fields
                    if getattr(translation, field, None)
                ),
                "",
            ),
        }
        for entity, translation, route in rows
    ]


async def _published_links_for_ids(
    session: AsyncSession,
    target_type: str,
    target_ids: list[Any],
    locale: Locale,
) -> list[dict[str, str]]:
    """
    批量解析一组关系目标，避免逐项执行公开门禁产生 N+1 查询。

    输入：session: AsyncSession，数据库会话；target_type: str，目标类型；target_ids: list[Any]，按业务顺序排列的目标 ID；locale: Locale，当前语言。
    输出：list[dict[str, str]]，保持输入顺序且仅含严格 published/self-canonical/robots 可见链接。
    """
    ordered_ids = list(dict.fromkeys(target_ids))
    if not ordered_ids:
        return []
    if target_type in CATALOG_PUBLIC_TYPES:
        model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[target_type]
        title_field = "name"
    elif target_type == "product":
        model, translation_model, foreign_key = Product, ProductTranslation, "product_id"
        title_field, summary_fields = "name", ("short_description",)
    elif target_type == "case_study":
        model, translation_model, foreign_key = CaseStudy, CaseStudyTranslation, "case_study_id"
        title_field, summary_fields = "title", ("summary",)
    else:
        return []

    statement = (
        select(model, translation_model, ContentRoute)
        .join(
            translation_model,
            (getattr(translation_model, foreign_key) == model.id)
            & (translation_model.locale_id == locale.id),
        )
        .join(
            ContentRoute,
            (ContentRoute.owner_type == target_type)
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
        .outerjoin(
            SeoDocument,
            (SeoDocument.owner_type == ContentRoute.owner_type)
            & (SeoDocument.owner_id == ContentRoute.owner_id)
            & (SeoDocument.locale_id == ContentRoute.locale_id),
        )
        .where(
            model.id.in_(ordered_ids),
            model.status == "enabled",
            ContentRoute.is_canonical.is_(True),
            ContentRoute.active.is_(True),
            ContentRoute.indexable.is_(True),
            ContentPublication.status == "published",
            TranslationStatus.status == "published",
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override
                == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
    )
    if target_type == "product":
        statement = statement.join(
            ProductCategory,
            ProductCategory.id == Product.category_id,
        ).where(ProductCategory.status == "enabled")

    rows = (await session.execute(statement)).all()
    links_by_id = {
        entity.id: {
            "type": target_type,
            "slug": entity.slug,
            "name": str(getattr(translation, title_field)),
            "url": route.path,
            "summary": next(
                (
                    str(getattr(translation, field))
                    for field in summary_fields
                    if getattr(translation, field, None)
                ),
                "",
            ),
        }
        for entity, translation, route in rows
    }
    return [links_by_id[target_id] for target_id in ordered_ids if target_id in links_by_id]


async def get_relation_health(
    session: AsyncSession,
    owner_type: str,
    owner_id: Any,
    locale_id: Any,
) -> tuple[int, bool]:
    """
    统计结构化关系中可公开链接数量，并识别不可解析目标。

    输入：数据库会话、来源类型/ID 与语言 ID。
    输出：(公开链接数, 是否存在断裂目标)，供 SEO health checks 使用。
    """
    locale = await session.get(Locale, locale_id)
    if locale is None or not locale.is_enabled:
        return 0, False
    relation_specs: dict[str, list[tuple[type, str, str, str]]] = {
        "product": [
            (ProductMaterial, "product_id", "material_id", "material"),
            (ProductTechnology, "product_id", "technology_id", "technology"),
            (ProductApplication, "product_id", "application_id", "application"),
            (ProductSolution, "product_id", "solution_id", "solution"),
            (CaseProduct, "product_id", "case_study_id", "case_study"),
            (ArticleProduct, "product_id", "article_id", "knowledge_article"),
        ],
        "case_study": [
            (CaseProduct, "case_study_id", "product_id", "product"),
            (CaseMaterial, "case_study_id", "material_id", "material"),
            (CaseTechnology, "case_study_id", "technology_id", "technology"),
            (CaseApplication, "case_study_id", "application_id", "application"),
            (CaseSolution, "case_study_id", "solution_id", "solution"),
            (ArticleCase, "case_study_id", "article_id", "knowledge_article"),
        ],
        "knowledge_article": [
            (ArticleProduct, "article_id", "product_id", "product"),
            (ArticleMaterial, "article_id", "material_id", "material"),
            (ArticleTechnology, "article_id", "technology_id", "technology"),
            (ArticleApplication, "article_id", "application_id", "application"),
            (ArticleSolution, "article_id", "solution_id", "solution"),
            (ArticleCase, "article_id", "case_study_id", "case_study"),
        ],
    }
    target_pairs: list[tuple[str, Any]] = []
    for relation_model, source_column, target_column, target_type in relation_specs.get(
        owner_type, []
    ):
        target_ids = list(
            (
                await session.scalars(
                    select(getattr(relation_model, target_column)).where(
                        getattr(relation_model, source_column) == owner_id
                    )
                )
            ).all()
        )
        target_pairs.extend((target_type, target_id) for target_id in target_ids)
    if owner_type == "author_expert":
        article_ids = list(
            (
                await session.scalars(
                    select(KnowledgeArticle.id).where(KnowledgeArticle.author_id == owner_id)
                )
            ).all()
        )
        target_pairs.extend(("knowledge_article", article_id) for article_id in article_ids)

    valid_count = 0
    for target_type, target_id in target_pairs:
        if await _published_link(session, target_type, target_id, locale):
            valid_count += 1
    return valid_count, valid_count != len(target_pairs)


async def _published_faqs(
    session: AsyncSession,
    relation_model: type,
    relation_owner_column: str,
    owner_id: Any,
    locale_id: Any,
) -> list[dict[str, str]]:
    """
    查询关联且翻译已发布的可见 FAQ。

    输入：session、关系模型/字段、owner_id 和 locale_id。
    输出：list，按关系与 FAQ 排序的问题答案。
    """
    rows = (
        await session.execute(
            select(FAQTranslation.question, FAQTranslation.answer)
            .join(FAQ, FAQ.id == FAQTranslation.faq_id)
            .join(relation_model, relation_model.faq_id == FAQ.id)
            .join(
                TranslationStatus,
                (TranslationStatus.owner_type == "faq")
                & (TranslationStatus.owner_id == FAQ.id)
                & (TranslationStatus.locale_id == FAQTranslation.locale_id),
            )
            .where(
                getattr(relation_model, relation_owner_column) == owner_id,
                FAQTranslation.locale_id == locale_id,
                FAQ.status == "enabled",
                TranslationStatus.status == "published",
            )
            .order_by(relation_model.sort_order, FAQ.sort_order)
        )
    ).all()
    return [{"question": row.question, "answer": row.answer} for row in rows]


async def _published_related_cases(
    session: AsyncSession,
    relation_model: type,
    relation_owner_column: str,
    owner_id: Any,
    locale: Locale,
) -> list[dict[str, str]]:
    """
    查询关联且严格已发布的 Case 摘要，不暴露客户内部身份。

    输入：session、关系模型/owner 字段、owner_id 与 locale。
    输出：list，仅包含 slug、title、summary 的公开白名单。
    """
    case_ids = list(
        (
            await session.scalars(
                select(relation_model.case_study_id)
                .where(getattr(relation_model, relation_owner_column) == owner_id)
                .order_by(relation_model.sort_order)
            )
        ).all()
    )
    result: list[dict[str, str]] = []
    for case_id in case_ids:
        case = await session.get(CaseStudy, case_id)
        if case is None or case.status != "enabled":
            continue
        try:
            await _public_route(session, "case_study", case.id, locale.id)
        except AppException:
            continue
        translation = await session.scalar(
            select(CaseStudyTranslation).where(
                CaseStudyTranslation.case_study_id == case.id,
                CaseStudyTranslation.locale_id == locale.id,
            )
        )
        if translation:
            result.append(
                {
                    "slug": case.slug,
                    "title": translation.title,
                    "summary": translation.summary or "",
                }
            )
    return result


async def _published_related_articles(
    session: AsyncSession,
    relation_model: type,
    relation_owner_column: str,
    owner_id: Any,
    locale: Locale,
) -> list[dict[str, str]]:
    """
    查询关联且严格已发布的 Knowledge Article 摘要。

    输入：session、关系模型/owner 字段、owner_id 与 locale。
    输出：list，包含 category_slug、slug、title 和 summary。
    """
    article_ids = list(
        (
            await session.scalars(
                select(relation_model.article_id)
                .where(getattr(relation_model, relation_owner_column) == owner_id)
                .order_by(relation_model.sort_order)
            )
        ).all()
    )
    result: list[dict[str, str]] = []
    for article_id in article_ids:
        article = await session.get(KnowledgeArticle, article_id)
        if article is None or article.status != "enabled":
            continue
        try:
            await _public_route(session, "knowledge_article", article.id, locale.id)
        except AppException:
            continue
        category = await session.get(KnowledgeCategory, article.category_id)
        translation = await session.scalar(
            select(KnowledgeArticleTranslation).where(
                KnowledgeArticleTranslation.article_id == article.id,
                KnowledgeArticleTranslation.locale_id == locale.id,
            )
        )
        if category and translation:
            result.append(
                {
                    "category_slug": category.slug,
                    "slug": article.slug,
                    "title": translation.title,
                    "summary": translation.summary or "",
                }
            )
    return result


def _seo_payload(
    seo: SeoDocument | None,
    route: ContentRoute,
    fallback_title: str,
    fallback_description: str | None,
) -> dict[str, Any]:
    """
    构造公开 SEO meta，默认 canonical 来自 ContentRoute。

    输入：seo、route 与正文回退标题/描述。
    输出：dict，SSR 可直接消费的 SEO 字段。
    """
    return {
        "title": seo.seo_title if seo and seo.seo_title else fallback_title,
        "description": seo.meta_description
        if seo and seo.meta_description
        else fallback_description,
        "canonical": seo.canonical_override
        if seo and seo.canonical_override
        else OFFICIAL_ORIGIN + route.path,
        "robots": "index, follow",
        "og_title": seo.og_title if seo else None,
        "og_description": seo.og_description if seo else None,
    }


def _geo_payload(geo: GeoDocument | None) -> dict[str, Any] | None:
    """输入可选 GeoDocument，输出页面可见 GEO 模块字段或 None。"""
    if geo is None:
        return None
    return {
        "direct_answer": geo.direct_answer,
        "key_facts": geo.key_facts_json,
        "evidence": geo.evidence_json,
        "related_questions": geo.related_questions_json,
        "last_reviewed_at": geo.last_reviewed_at,
    }


def _page_schemas(
    primary_schema: dict[str, Any],
    breadcrumb: list[dict[str, str]],
    faqs: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    组合页面基础 Schema 与受功能开关控制的 FAQPage。

    输入：主 Schema、可见面包屑与已发布可见 FAQ。
    输出：list[dict[str, Any]]，与页面正文一致的 JSON-LD 列表。
    """
    schemas = [primary_schema, build_breadcrumb_schema(breadcrumb)]
    faq_schema = build_faq_schema(faqs, enabled=get_settings().faq_schema_enabled)
    if faq_schema:
        schemas.append(faq_schema)
    return schemas


async def get_public_product(
    session: AsyncSession,
    locale_slug: str,
    category_slug: str,
    slug: str,
) -> dict[str, Any]:
    """
    聚合严格已发布的 Product SSR DTO。

    输入：session、语言、分类 slug 和产品 slug。
    输出：dict，正文、型号、规格、关系、Case/FAQ/Knowledge、SEO/GEO 与 Schema。
    """
    locale = await _locale(session, locale_slug)
    product = await session.scalar(
        select(Product)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(
            Product.slug == slug,
            Product.status == "enabled",
            ProductCategory.slug == category_slug,
            ProductCategory.status == "enabled",
        )
    )
    if product is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "product", product.id, locale.id)
    translation = await session.scalar(
        select(ProductTranslation).where(
            ProductTranslation.product_id == product.id, ProductTranslation.locale_id == locale.id
        )
    )
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    models = list(
        (
            await session.scalars(
                select(ProductModel)
                .where(ProductModel.product_id == product.id, ProductModel.status == "enabled")
                .order_by(ProductModel.sort_order)
            )
        ).all()
    )
    specifications = await serialize_public_specifications(session, product.id, locale)
    primary_media = await _public_media(
        session,
        product.primary_media_id,
        locale.id,
        translation.name,
        loading="eager",
    )
    relations: dict[str, list[dict[str, str]]] = {}
    for field_name, relation_model, target_column, target_type in (
        ("materials", ProductMaterial, "material_id", "material"),
        ("technologies", ProductTechnology, "technology_id", "technology"),
        ("applications", ProductApplication, "application_id", "application"),
        ("solutions", ProductSolution, "solution_id", "solution"),
    ):
        relations[field_name] = await _published_relation_links(
            session,
            relation_model,
            "product_id",
            product.id,
            target_column,
            target_type,
            locale,
        )
    faqs = await _published_faqs(session, FAQProduct, "product_id", product.id, locale.id)
    cases = await _published_relation_links(
        session,
        CaseProduct,
        "product_id",
        product.id,
        "case_study_id",
        "case_study",
        locale,
    )
    knowledge = await _published_relation_links(
        session,
        ArticleProduct,
        "product_id",
        product.id,
        "article_id",
        "knowledge_article",
        locale,
    )
    relations["cases"] = cases
    relations["knowledge"] = knowledge
    relations["capabilities"] = await _published_capability_links(session, locale)
    url = OFFICIAL_ORIGIN + route.path
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Products", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/products/"},
        {"name": translation.name, "url": url},
    ]
    product_schema = build_product_schema(
        {
            "name": translation.name,
            "description": translation.description or translation.short_description,
            "url": url,
        }
    )
    return {
        "slug": product.slug,
        "category_slug": category_slug,
        "translation": {
            "name": translation.name,
            "short_description": translation.short_description,
            "description": translation.description,
            "highlights": translation.highlights_jsonb,
        },
        "models": [
            {"model_code": item.model_code, "sort_order": item.sort_order} for item in models
        ],
        "specifications": [item.model_dump() for item in specifications],
        "media": [primary_media.model_dump()] if primary_media else [],
        "primary_media": primary_media.model_dump() if primary_media else None,
        "relations": relations,
        "faqs": faqs,
        "cases": cases,
        "knowledge": knowledge,
        "trust_summary": await _published_trust_summary(session, locale),
        "seo": _seo_payload(seo, route, translation.name, translation.short_description),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": _page_schemas(product_schema, breadcrumb, faqs),
        "alternates": await _published_alternates(session, "product", product.id),
    }


async def get_public_case(session: AsyncSession, locale_slug: str, slug: str) -> dict[str, Any]:
    """
    聚合客户隐私白名单保护的 Case SSR DTO。

    输入：session、语言 slug 与案例 slug。
    输出：dict，公开案例、关系、FAQ、SEO/GEO 与无敏感信息 Schema。
    """
    locale = await _locale(session, locale_slug)
    case = await session.scalar(
        select(CaseStudy).where(CaseStudy.slug == slug, CaseStudy.status == "enabled")
    )
    if case is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "case_study", case.id, locale.id)
    translation = await session.scalar(
        select(CaseStudyTranslation).where(
            CaseStudyTranslation.case_study_id == case.id,
            CaseStudyTranslation.locale_id == locale.id,
        )
    )
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    public_case = serialize_public_case(case, _columns(translation))
    # Serializer 的许可判断是唯一身份门禁；此处把放行值重组为 SSR 专用嵌套 DTO。
    allowed_name = public_case.pop("client_name", None)
    allowed_address = public_case.pop("client_address", None)
    allowed_logo_id = public_case.pop("client_logo_media_id", None)
    public_case.pop("primary_media_id", None)
    primary_media = await _public_media(
        session,
        case.primary_media_id,
        locale.id,
        translation.title,
        loading="eager",
    )
    customer_logo = await _public_media(
        session,
        case.client_logo_media_id if allowed_logo_id else None,
        locale.id,
        allowed_name or translation.title,
    )
    customer_identity = (
        {
            "name": allowed_name,
            "address": allowed_address,
            "logo": customer_logo.model_dump() if customer_logo else None,
        }
        if allowed_name or allowed_address or customer_logo
        else None
    )
    relations: dict[str, list[dict[str, str]]] = {}
    for field_name, relation_model, target_column, target_type in (
        ("products", CaseProduct, "product_id", "product"),
        ("materials", CaseMaterial, "material_id", "material"),
        ("technologies", CaseTechnology, "technology_id", "technology"),
        ("applications", CaseApplication, "application_id", "application"),
        ("solutions", CaseSolution, "solution_id", "solution"),
    ):
        relations[field_name] = await _published_relation_links(
            session,
            relation_model,
            "case_study_id",
            case.id,
            target_column,
            target_type,
            locale,
        )
    faqs = await _published_faqs(session, FAQCase, "case_study_id", case.id, locale.id)
    knowledge = await _published_relation_links(
        session,
        ArticleCase,
        "case_study_id",
        case.id,
        "article_id",
        "knowledge_article",
        locale,
    )
    relations["knowledge"] = knowledge
    url = OFFICIAL_ORIGIN + route.path
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Case Studies", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/case-studies/"},
        {"name": translation.title, "url": url},
    ]
    public_case.update(
        media=primary_media.model_dump() if primary_media else None,
        customer_identity=customer_identity,
        relations=relations,
        faqs=faqs,
        knowledge=knowledge,
        seo=_seo_payload(seo, route, translation.title, translation.summary),
        geo=_geo_payload(geo),
        breadcrumb=breadcrumb,
        schema=_page_schemas(
            build_webpage_schema(
                {"name": translation.title, "description": translation.summary, "url": url}
            ),
            breadcrumb,
            faqs,
        ),
        alternates=await _published_alternates(session, "case_study", case.id),
    )
    return public_case


async def get_public_knowledge(
    session: AsyncSession,
    locale_slug: str,
    category_slug: str,
    slug: str,
) -> dict[str, Any]:
    """
    聚合带真实作者、来源和结构化关系的 Knowledge SSR DTO。

    输入：session、语言、分类 slug 和文章 slug。
    输出：dict，文章、作者/审核人、来源、关系、FAQ、SEO/GEO 与 Schema。
    """
    locale = await _locale(session, locale_slug)
    article = await session.scalar(
        select(KnowledgeArticle)
        .join(KnowledgeCategory, KnowledgeCategory.id == KnowledgeArticle.category_id)
        .where(
            KnowledgeArticle.slug == slug,
            KnowledgeArticle.status == "enabled",
            KnowledgeCategory.slug == category_slug,
            KnowledgeCategory.status == "enabled",
        )
    )
    if article is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "knowledge_article", article.id, locale.id)
    translation = await session.scalar(
        select(KnowledgeArticleTranslation).where(
            KnowledgeArticleTranslation.article_id == article.id,
            KnowledgeArticleTranslation.locale_id == locale.id,
        )
    )
    author = await session.get(AuthorExpert, article.author_id)
    author_translation = await session.scalar(
        select(AuthorExpertTranslation).where(
            AuthorExpertTranslation.author_expert_id == article.author_id,
            AuthorExpertTranslation.locale_id == locale.id,
        )
    )
    if (
        translation is None
        or author is None
        or author_translation is None
        or not author.is_real_person_verified
    ):
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    category = await session.get(KnowledgeCategory, article.category_id)
    category_translation = await session.scalar(
        select(KnowledgeCategoryTranslation).where(
            KnowledgeCategoryTranslation.category_id == article.category_id,
            KnowledgeCategoryTranslation.locale_id == locale.id,
        )
    )
    if category is None or category_translation is None or category.status != "enabled":
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    publication = await session.scalar(
        select(ContentPublication).where(
            ContentPublication.owner_type == "knowledge_article",
            ContentPublication.owner_id == article.id,
            ContentPublication.locale_id == locale.id,
            ContentPublication.status == "published",
        )
    )
    if publication is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    reviewer = None
    if article.reviewer_id:
        reviewer_model = await session.get(AuthorExpert, article.reviewer_id)
        reviewer_translation = await session.scalar(
            select(AuthorExpertTranslation).where(
                AuthorExpertTranslation.author_expert_id == article.reviewer_id,
                AuthorExpertTranslation.locale_id == locale.id,
            )
        )
        if reviewer_model and reviewer_model.is_real_person_verified and reviewer_translation:
            reviewer = {
                "name": reviewer_translation.name,
                "job_title": reviewer_translation.job_title,
            }
    source_conditions = [SourceCitation.article_id == article.id]
    if geo is not None:
        source_conditions.append(SourceCitation.geo_document_id == geo.id)
    sources = list(
        (
            await session.scalars(
                select(SourceCitation)
                .where(or_(*source_conditions))
                .order_by(SourceCitation.sort_order)
            )
        ).all()
    )
    relations: dict[str, list[dict[str, str]]] = {}
    for field_name, relation_model, target_column, target_type in (
        ("products", ArticleProduct, "product_id", "product"),
        ("materials", ArticleMaterial, "material_id", "material"),
        ("technologies", ArticleTechnology, "technology_id", "technology"),
        ("applications", ArticleApplication, "application_id", "application"),
        ("solutions", ArticleSolution, "solution_id", "solution"),
        ("cases", ArticleCase, "case_study_id", "case_study"),
    ):
        relations[field_name] = await _published_relation_links(
            session,
            relation_model,
            "article_id",
            article.id,
            target_column,
            target_type,
            locale,
        )
    faqs = await _published_faqs(session, ArticleFAQ, "article_id", article.id, locale.id)
    url = OFFICIAL_ORIGIN + route.path
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Knowledge", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/knowledge/"},
        {"name": translation.title, "url": url},
    ]
    author_payload = {
        "name": author_translation.name,
        "job_title": author_translation.job_title,
        "short_bio": author_translation.short_bio,
        "is_real_person_verified": True,
    }
    article_schema = build_article_schema(
        {
            "headline": translation.title,
            "description": translation.summary,
            "url": url,
            "date_modified": article.updated_at.isoformat(),
        },
        author_payload,
    )
    return {
        "slug": article.slug,
        "category_slug": category_slug,
        "category": {
            "slug": category.slug,
            "name": category_translation.name,
            "url": f"/{locale.slug}/knowledge/?category={category.slug}",
        },
        "translation": {
            "title": translation.title,
            "summary": translation.summary,
            "body_markdown": translation.body_markdown,
        },
        "author": author_payload,
        "reviewer": reviewer,
        "published_at": publication.published_at,
        "updated_at": article.updated_at,
        "last_reviewed_at": article.last_reviewed_at,
        "sources": [
            {
                "title": item.title,
                "url": item.url,
                "publisher": item.publisher,
                "publication_date": item.publication_date,
                "source_type": item.source_type,
            }
            for item in sources
        ],
        "relations": relations,
        "faqs": faqs,
        "seo": _seo_payload(seo, route, translation.title, translation.summary),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": _page_schemas(article_schema, breadcrumb, faqs),
        "alternates": await _published_alternates(session, "knowledge_article", article.id),
    }


async def get_public_expert(
    session: AsyncSession,
    locale_slug: str,
    slug: str,
) -> dict[str, Any]:
    """
    聚合已核验且允许公开的人物资料、Person Schema 与已发布文章。

    输入：数据库会话、语言 slug 与人物 slug。
    输出：dict，供 Expert Nuxt SSR 使用的严格公开 DTO。
    """
    locale = await _locale(session, locale_slug)
    expert = await session.scalar(
        select(AuthorExpert).where(
            AuthorExpert.slug == slug,
            AuthorExpert.status == "enabled",
            AuthorExpert.is_real_person_verified.is_(True),
            AuthorExpert.public_profile_enabled.is_(True),
        )
    )
    if expert is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "author_expert", expert.id, locale.id)
    translation = await session.scalar(
        select(AuthorExpertTranslation).where(
            AuthorExpertTranslation.author_expert_id == expert.id,
            AuthorExpertTranslation.locale_id == locale.id,
        )
    )
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")

    article_ids = list(
        (
            await session.scalars(
                select(KnowledgeArticle.id)
                .where(KnowledgeArticle.author_id == expert.id)
                .order_by(KnowledgeArticle.sort_order, KnowledgeArticle.id)
            )
        ).all()
    )
    authored_knowledge: list[dict[str, str]] = []
    for article_id in article_ids:
        link = await _published_link(session, "knowledge_article", article_id, locale)
        if link:
            authored_knowledge.append(link)

    url = OFFICIAL_ORIGIN + route.path
    person = {
        "slug": expert.slug,
        "name": translation.name,
        "job_title": translation.job_title,
        "short_bio": translation.short_bio,
        "expertise": translation.expertise_json,
        "role_type": expert.role_type,
        "years_experience": expert.years_experience,
        "linkedin_url": expert.linkedin_url,
        "public_email": expert.public_email,
        "is_real_person_verified": True,
        "url": url,
    }
    profile_media = await _public_media(
        session,
        expert.profile_media_id,
        locale.id,
        translation.name,
        loading="eager",
    )
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Experts", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/experts/"},
        {"name": translation.name, "url": url},
    ]
    return {
        **person,
        "profile_media": profile_media.model_dump() if profile_media else None,
        "authored_knowledge": authored_knowledge,
        "seo": _seo_payload(seo, route, translation.name, translation.short_bio),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": [build_person_schema(person), build_breadcrumb_schema(breadcrumb)],
        "alternates": await _published_alternates(session, "author_expert", expert.id),
    }


async def get_public_catalog_entity(
    session: AsyncSession,
    owner_type: str,
    locale_slug: str,
    slug: str,
) -> dict[str, Any]:
    """
    为 Sitemap 中的分类、材料、技术、应用和方案提供最小公开 DTO。

    输入：数据库会话、受支持 owner_type、语言 slug 与实体 slug。
    输出：dict，正文、SEO/GEO、breadcrumb、Schema 与 alternate。
    """
    if owner_type not in CATALOG_PUBLIC_TYPES:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    locale = await _locale(session, locale_slug)
    model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[owner_type]
    entity = await session.scalar(
        select(model).where(model.slug == slug, model.status == "enabled")
    )
    if entity is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, owner_type, entity.id, locale.id)
    translation = await session.scalar(
        select(translation_model).where(
            getattr(translation_model, foreign_key) == entity.id,
            translation_model.locale_id == locale.id,
        )
    )
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    # Catalog 公开翻译使用显式字段白名单，未来新增 ORM 列不会被自动暴露。
    translation_payload = {
        field: getattr(translation, field, None) for field in ("name", *summary_fields)
    }
    summary = next(
        (
            str(getattr(translation, field))
            for field in summary_fields
            if getattr(translation, field, None)
        ),
        None,
    )
    url = OFFICIAL_ORIGIN + route.path
    resource = CATALOG_COLLECTION_PATHS[owner_type]
    collection_name = CATALOG_COLLECTION_LABELS[owner_type][
        "zh-cn" if locale.slug == "zh-cn" else "en"
    ]
    breadcrumb = [
        {
            "name": "首页" if locale.slug == "zh-cn" else "Home",
            "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/",
        },
        {"name": collection_name, "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/{resource}/"},
        {"name": translation.name, "url": url},
    ]
    relations: dict[str, list[dict[str, str]]] = {}
    for (
        group,
        relation_model,
        owner_column,
        target_column,
        target_type,
    ) in CATALOG_RELATION_TYPES.get(owner_type, ()):
        relations[group] = await _published_relation_links(
            session,
            relation_model,
            owner_column,
            entity.id,
            target_column,
            target_type,
            locale,
        )
    return {
        "type": owner_type,
        "slug": entity.slug,
        "translation": translation_payload,
        "relations": relations,
        "seo": _seo_payload(seo, route, translation.name, summary),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": [
            build_webpage_schema({"name": translation.name, "description": summary, "url": url}),
            build_breadcrumb_schema(breadcrumb),
        ],
        "alternates": await _published_alternates(session, owner_type, entity.id),
    }
