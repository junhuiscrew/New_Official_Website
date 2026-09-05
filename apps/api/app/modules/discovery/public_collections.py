"""为全局导航与首页提供严格发布的公开内容聚合。"""

from __future__ import annotations

from math import ceil
from typing import Any, NamedTuple
from urllib.parse import urlencode

from sqlalchemy import case, func, literal, literal_column, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.exceptions.handlers import AppException
from app.modules.authority.models import (
    AuthorExpert,
    AuthorExpertTranslation,
    CaseStudy,
    CaseStudyTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
    KnowledgeCategory,
    KnowledgeCategoryTranslation,
)
from app.modules.catalog.models import (
    Application,
    ApplicationTranslation,
    Material,
    MaterialTranslation,
    Product,
    ProductApplication,
    ProductCategory,
    ProductCategoryTranslation,
    ProductMaterial,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.company.models import (
    CompanyProfile,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.company.services import get_public_company_profile
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.discovery.models import SeoDocument
from app.modules.discovery.schema_generator import (
    build_breadcrumb_schema,
    build_organization_schema,
    build_webpage_schema,
    build_website_schema,
)
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation

from .public_delivery import (
    OFFICIAL_ORIGIN,
    _locale,
    _public_media,
    _public_route,
)
from .public_schemas import PublicMediaDto
from .public_specs import serialize_public_specifications_for_products


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
    "technology": _CollectionConfig(
        Technology,
        TechnologyTranslation,
        "technology_id",
        "name",
        ("definition", "process_description"),
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
    "author_expert": _CollectionConfig(
        AuthorExpert,
        AuthorExpertTranslation,
        "author_expert_id",
        "name",
        ("short_bio",),
    ),
}

_SEARCH_TYPES = (
    "product",
    "material",
    "application",
    "solution",
    "knowledge_article",
    "case_study",
)

_SEARCH_FIELDS: dict[str, tuple[str, ...]] = {
    "product": ("short_description", "description"),
    "material": (
        "definition",
        "processing_characteristics",
        "screw_impact",
        "recommendations",
    ),
    "application": ("description", "technical_requirements", "common_problems"),
    "solution": ("definition", "symptoms", "causes", "diagnosis", "solution"),
    "knowledge_article": ("summary", "body_markdown"),
    "case_study": ("summary", "problem", "analysis", "solution", "result"),
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

# 四类目录页标题属于界面导航文案，不包含材料、工艺或解决方案业务事实。
_CATALOG_LISTING_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "material": {
        "en": ("Materials", "Browse published material guidance and related engineering content."),
        "zh-cn": ("材料", "浏览已发布的材料指南及相关工程内容。"),
    },
    "technology": {
        "en": ("Technologies", "Browse published processing technologies and capability guidance."),
        "zh-cn": ("处理技术", "浏览已发布的处理技术与能力指南。"),
    },
    "application": {
        "en": (
            "Applications",
            "Browse published application requirements and processing challenges.",
        ),
        "zh-cn": ("应用", "浏览已发布的应用要求与加工挑战。"),
    },
    "solution": {
        "en": ("Solutions", "Browse published problem analysis and recommended approaches."),
        "zh-cn": ("解决方案", "浏览已发布的问题分析与建议方案。"),
    },
}

# Authority 列表标题仅描述页面用途；文章、案例与人物事实仍全部来自发布 DTO。
_AUTHORITY_LISTING_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "knowledge_article": {
        "en": ("Knowledge", "Browse published technical guidance and engineering articles."),
        "zh-cn": ("技术知识", "浏览已发布的技术指南与工程文章。"),
    },
    "case_study": {
        "en": ("Case Studies", "Browse engineering cases approved for public sharing."),
        "zh-cn": ("案例研究", "浏览已获公开许可的工程案例。"),
    },
    "author_expert": {
        "en": ("Experts", "Meet verified people with public professional profiles."),
        "zh-cn": ("专家", "查看已核验并获准公开的专业人员资料。"),
    },
}


def _public_collection_statement(
    owner_type: str,
    locale: Locale,
    *,
    require_robots_index: bool = True,
) -> Select[Any] | None:
    """
    构造复用完整发布/路由/SEO 门禁的公开集合查询。

    输入：
        owner_type: str，集合实体类型。
        locale: Locale，已启用目标语言。
        require_robots_index: bool，是否排除明确 noindex 的内容。

    输出：
        Select[Any] | None，可继续添加筛选、排序或搜索列的查询；不支持时返回 None。
    """
    config = _COLLECTION_CONFIG.get(owner_type)
    if config is None:
        return None
    model = config.model
    translation_model = config.translation_model
    statement = select(model, translation_model, ContentRoute).join(
        translation_model,
        getattr(translation_model, config.owner_field) == model.id,
    )

    # 与详情端点保持同一业务依赖门禁，避免列表产生点击后 404 的孤立卡片。
    if owner_type == "product":
        statement = statement.join(
            ProductCategory, ProductCategory.id == Product.category_id
        ).where(ProductCategory.status == "enabled")
    elif owner_type == "knowledge_article":
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
    elif owner_type == "author_expert":
        statement = statement.where(
            AuthorExpert.is_real_person_verified.is_(True),
            AuthorExpert.public_profile_enabled.is_(True),
        )

    statement = (
        statement.join(
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
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
            ),
        )
    )
    if require_robots_index:
        statement = statement.where(
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True))
        )
    return statement


def _card_payload(
    owner_type: str,
    entity: Any,
    translation: Any,
    route: ContentRoute,
) -> dict[str, str]:
    """
    将已通过门禁的查询行转为无内部 ID 的 canonical Card DTO。

    输入：
        owner_type: str，卡片所属的公开实体类型。
        entity: Any，已通过公开门禁的业务实体。
        translation: Any，当前语言且已发布的翻译实体。
        route: ContentRoute，当前语言的 canonical 路由。

    输出：
        dict[str, str]，仅含类型、slug、名称、URL 与摘要。
    """
    config = _COLLECTION_CONFIG[owner_type]
    summary = next(
        (
            str(value)
            for field in config.summary_fields
            if (value := getattr(translation, field, None))
        ),
        "",
    )
    return {
        "type": owner_type,
        "slug": entity.slug,
        "name": str(getattr(translation, config.title_field)),
        "url": route.path,
        "summary": summary,
    }


async def _product_card_payloads(
    session: AsyncSession,
    locale: Locale,
    rows: list[tuple[Any, Any, ContentRoute]],
) -> list[dict[str, Any]]:
    """
    批量丰富产品列表卡片，避免逐产品查询媒体、分类和公开规格。

    输入：
        session: AsyncSession，数据库会话。
        locale: Locale，当前已启用语言。
        rows: list，已通过统一发布门禁的产品、翻译和 canonical 路由行。

    输出：
        list[dict[str, Any]]，包含公开主媒体、canonical 分类及最多四项规格的卡片。
    """
    if not rows:
        return []
    products = [row[0] for row in rows]
    product_ids = [product.id for product in products]
    specifications = await serialize_public_specifications_for_products(
        session,
        product_ids,
        locale,
    )

    category_ids = list({product.category_id for product in products})
    category_statement = _public_collection_statement("product_category", locale)
    category_rows = (
        (
            await session.execute(category_statement.where(ProductCategory.id.in_(category_ids)))
        ).all()
        if category_statement is not None
        else []
    )
    categories = {
        category.id: _card_payload("product_category", category, translation, route)
        for category, translation, route in category_rows
    }

    media_ids = [product.primary_media_id for product in products if product.primary_media_id]
    media_rows = (
        (
            await session.execute(
                select(MediaAsset, MediaAssetTranslation)
                .outerjoin(
                    MediaAssetTranslation,
                    (MediaAssetTranslation.media_asset_id == MediaAsset.id)
                    & (MediaAssetTranslation.locale_id == locale.id),
                )
                .where(
                    MediaAsset.id.in_(media_ids),
                    MediaAsset.visibility == "public",
                    MediaAsset.storage_bucket == "public-media",
                    MediaAsset.upload_status == "ready",
                )
            )
        ).all()
        if media_ids
        else []
    )
    media_by_id: dict[Any, tuple[MediaAsset, MediaAssetTranslation | None]] = {
        asset.id: (asset, translation) for asset, translation in media_rows
    }

    cards: list[dict[str, Any]] = []
    for product, translation, route in rows:
        media: dict[str, Any] | None = None
        media_row = media_by_id.get(product.primary_media_id)
        if media_row:
            asset, media_translation = media_row
            translated_alt = (
                media_translation.alt_text.strip()
                if media_translation and media_translation.alt_text
                else ""
            )
            alt = translated_alt or str(translation.name).strip()
            if alt:
                media = PublicMediaDto(
                    src=f"/api/v1/public/media/{asset.id}",
                    type=asset.media_type,
                    mime_type=asset.mime_type,
                    width=asset.width,
                    height=asset.height,
                    alt=alt,
                    caption=media_translation.caption if media_translation else None,
                    loading="lazy",
                ).model_dump()

        card: dict[str, Any] = _card_payload("product", product, translation, route)
        card.update(
            {
                "media": media,
                "category": categories.get(product.category_id),
                "specifications": [
                    item.model_dump() for item in specifications.get(product.id, [])[:4]
                ],
            }
        )
        cards.append(card)
    return cards


async def _authority_card_payloads(
    session: AsyncSession,
    owner_type: str,
    locale: Locale,
    rows: list[tuple[Any, Any, ContentRoute]],
) -> list[dict[str, Any]]:
    """
    批量补充 Knowledge 与 Expert 列表所需的公开权威元数据。

    输入：
        session: AsyncSession，数据库会话。
        owner_type: str，仅允许 knowledge_article 或 author_expert。
        locale: Locale，当前已启用语言。
        rows: list，已通过统一发布门禁的实体、翻译和 canonical 路由。

    输出：
        list[dict[str, Any]]，不包含人物 ID、分类 ID 或生命周期内部字段。
    """
    cards = [
        _card_payload(owner_type, entity, translation, route) for entity, translation, route in rows
    ]
    if not rows:
        return cards
    if owner_type == "author_expert":
        for card, (expert, _translation, _route) in zip(cards, rows, strict=True):
            card["role_type"] = expert.role_type
        return cards
    if owner_type != "knowledge_article":
        return cards

    articles = [row[0] for row in rows]
    article_ids = [article.id for article in articles]
    category_ids = list({article.category_id for article in articles})
    person_ids = list(
        {
            person_id
            for article in articles
            for person_id in (article.author_id, article.reviewer_id)
            if person_id is not None
        }
    )
    category_rows = (
        await session.execute(
            select(KnowledgeCategory, KnowledgeCategoryTranslation)
            .join(
                KnowledgeCategoryTranslation,
                (KnowledgeCategoryTranslation.category_id == KnowledgeCategory.id)
                & (KnowledgeCategoryTranslation.locale_id == locale.id),
            )
            .where(
                KnowledgeCategory.id.in_(category_ids),
                KnowledgeCategory.status == "enabled",
            )
        )
    ).all()
    categories = {
        category.id: {
            "slug": category.slug,
            "name": translation.name,
            "url": f"/{locale.slug}/knowledge/?category={category.slug}",
        }
        for category, translation in category_rows
    }
    person_rows = (
        await session.execute(
            select(AuthorExpert, AuthorExpertTranslation)
            .join(
                AuthorExpertTranslation,
                (AuthorExpertTranslation.author_expert_id == AuthorExpert.id)
                & (AuthorExpertTranslation.locale_id == locale.id),
            )
            .where(
                AuthorExpert.id.in_(person_ids),
                AuthorExpert.status == "enabled",
                AuthorExpert.is_real_person_verified.is_(True),
            )
        )
    ).all()
    people = {person.id: translation.name for person, translation in person_rows}
    publication_rows = (
        await session.execute(
            select(ContentPublication.owner_id, ContentPublication.published_at).where(
                ContentPublication.owner_type == "knowledge_article",
                ContentPublication.owner_id.in_(article_ids),
                ContentPublication.locale_id == locale.id,
                ContentPublication.status == "published",
            )
        )
    ).all()
    published_at = {row.owner_id: row.published_at for row in publication_rows}

    for card, (article, _translation, _route) in zip(cards, rows, strict=True):
        card.update(
            {
                "category": categories.get(article.category_id),
                "author": people.get(article.author_id),
                "reviewer": people.get(article.reviewer_id),
                "published_at": published_at.get(article.id),
                "updated_at": article.updated_at,
            }
        )
    await _attach_card_media(session, locale, cards, rows, "primary_media_id")
    return cards


async def _attach_card_media(
    session: AsyncSession,
    locale: Locale,
    cards: list[dict[str, Any]],
    rows: list[tuple[Any, Any, ContentRoute]],
    media_field: str,
) -> None:
    """
    批量为公开卡片附加真实 public-media，避免逐卡媒体查询。

    输入：
        session: AsyncSession，数据库会话。
        locale: Locale，当前语言。
        cards: list[dict[str, Any]]，待增强的公开卡片。
        rows: list，卡片对应的实体、翻译和路由行。
        media_field: str，实体上的媒体外键字段名。

    输出：
        None，原地写入卡片的 media 字段；不合格媒体写入 None。
    """
    media_ids = [
        media_id
        for entity, _translation, _route in rows
        if (media_id := getattr(entity, media_field, None)) is not None
    ]
    media_rows = (
        (
            await session.execute(
                select(MediaAsset, MediaAssetTranslation)
                .outerjoin(
                    MediaAssetTranslation,
                    (MediaAssetTranslation.media_asset_id == MediaAsset.id)
                    & (MediaAssetTranslation.locale_id == locale.id),
                )
                .where(
                    MediaAsset.id.in_(media_ids),
                    MediaAsset.visibility == "public",
                    MediaAsset.storage_bucket == "public-media",
                    MediaAsset.upload_status == "ready",
                )
            )
        ).all()
        if media_ids
        else []
    )
    media_by_id = {asset.id: (asset, translation) for asset, translation in media_rows}
    for card, (entity, _translation, _route) in zip(cards, rows, strict=True):
        media_row = media_by_id.get(getattr(entity, media_field, None))
        card["media"] = None
        if media_row is None:
            continue
        asset, media_translation = media_row
        translated_alt = (
            media_translation.alt_text.strip()
            if media_translation and media_translation.alt_text
            else ""
        )
        fallback_alt = str(card["name"]).strip()
        alt = translated_alt or fallback_alt
        if not alt:
            continue
        card["media"] = PublicMediaDto(
            src=f"/api/v1/public/media/{asset.id}",
            type=asset.media_type,
            mime_type=asset.mime_type,
            width=asset.width,
            height=asset.height,
            alt=alt,
            caption=media_translation.caption if media_translation else None,
            loading="lazy",
        ).model_dump()


def _listing_query_suffix(
    *,
    category: str | None,
    material: str | None,
    application: str | None,
    page: int,
    page_size: int,
    category_in_path: bool,
    type_filter: str | None = None,
) -> str:
    """
    按固定顺序生成产品集合的等价 canonical 查询字符串。

    输入：三项公开筛选、页码、每页条数，以及分类是否已表达在路径中。
    输出：str，以问号开头的规范化查询；默认值和空筛选不输出。
    """
    parameters: list[tuple[str, str | int]] = []
    if category and not category_in_path:
        parameters.append(("category", category))
    if material:
        parameters.append(("material", material))
    if application:
        parameters.append(("application", application))
    if type_filter:
        parameters.append(("type", type_filter))
    if page > 1:
        parameters.append(("page", page))
    if page_size != 24:
        parameters.append(("page_size", page_size))
    return f"?{urlencode(parameters)}" if parameters else ""


async def _product_listing_seo(
    session: AsyncSession,
    locale: Locale,
    page: int,
    page_size: int,
    category: str | None,
    material: str | None,
    application: str | None,
    total: int,
) -> dict[str, Any]:
    """
    返回全产品集合的稳定后端 SEO DTO，不在前端复制 canonical/index 规则。

    输入：数据库会话、当前语言、分页值与三项公开筛选。
    输出：dict[str, Any]，全产品列表的 canonical、robots 与 hreflang。
    """
    path = f"/{locale.slug}/products/"
    title = "产品" if locale.slug == "zh-cn" else "Products"
    description: str | None = None
    category_in_path = False
    alternates: dict[str, str] = {}
    category_entity: ProductCategory | None = None
    category_seo: SeoDocument | None = None

    # 已发布分类使用自身 canonical 路径；分类筛选不再重复进入 query。
    if category:
        category_entity = await session.scalar(
            select(ProductCategory).where(
                ProductCategory.slug == category,
                ProductCategory.status == "enabled",
            )
        )
        if category_entity is not None:
            try:
                route, category_seo, _geo = await _public_route(
                    session,
                    "product_category",
                    category_entity.id,
                    locale.id,
                    require_robots_index=False,
                )
            except AppException:
                pass
            else:
                translation = await session.scalar(
                    select(ProductCategoryTranslation).where(
                        ProductCategoryTranslation.category_id == category_entity.id,
                        ProductCategoryTranslation.locale_id == locale.id,
                    )
                )
                if translation is not None:
                    path = route.path
                    title = (
                        category_seo.seo_title or translation.name
                        if category_seo
                        else translation.name
                    )
                    description = (
                        category_seo.meta_description
                        if category_seo and category_seo.meta_description
                        else translation.short_description or translation.description
                    )
                    category_in_path = True

    suffix = _listing_query_suffix(
        category=category,
        material=material,
        application=application,
        page=page,
        page_size=page_size,
        category_in_path=category_in_path,
    )
    temporary_view = bool(material or application or page_size != 24)
    category_allows_index = category_seo is None or category_seo.robots_index
    if not temporary_view and total > 0 and category_allows_index:
        locale_rows = list(
            (
                await session.scalars(
                    select(Locale)
                    .where(Locale.is_enabled.is_(True))
                    .order_by(Locale.sort_order, Locale.code)
                )
            ).all()
        )
        for item in locale_rows:
            other_statement = _public_collection_statement("product", item)
            if other_statement is None:
                continue
            other_path = f"/{item.slug}/products/"
            if category_entity is not None:
                try:
                    other_route, _other_seo, _other_geo = await _public_route(
                        session,
                        "product_category",
                        category_entity.id,
                        item.id,
                    )
                except AppException:
                    continue
                other_statement = other_statement.where(Product.category_id == category_entity.id)
                other_path = other_route.path
            other_total = int(
                await session.scalar(select(func.count()).select_from(other_statement.subquery()))
                or 0
            )
            if other_total <= (page - 1) * page_size:
                continue
            other_suffix = _listing_query_suffix(
                category=None,
                material=None,
                application=None,
                page=page,
                page_size=page_size,
                category_in_path=True,
            )
            alternates[item.code] = f"{OFFICIAL_ORIGIN}{other_path}{other_suffix}"
        if "zh-CN" in alternates:
            alternates["x-default"] = alternates["zh-CN"]

    canonical = f"{OFFICIAL_ORIGIN}{path}{suffix}"
    follows = category_seo is None or category_seo.robots_follow
    indexable = total > 0 and not temporary_view and category_allows_index
    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "robots": f"{'index' if indexable else 'noindex'}, {'follow' if follows else 'nofollow'}",
        "hreflang": alternates,
    }


async def _require_public_filter(
    session: AsyncSession,
    owner_type: str,
    locale: Locale,
    slug: str,
    *,
    allow_noindex: bool = False,
) -> tuple[Any, Any, ContentRoute]:
    """
    验证筛选资源本身在当前语言可公开访问。

    输入：数据库会话、筛选实体类型、语言和公开 slug。
    输出：(entity, translation, route)；不存在或未发布时抛出公开 404。
    """
    config = _COLLECTION_CONFIG[owner_type]
    statement = _public_collection_statement(
        owner_type,
        locale,
        require_robots_index=not allow_noindex,
    )
    if statement is None:
        raise AppException(404, "public_filter_not_found", "公开筛选不存在")
    row = (await session.execute(statement.where(config.model.slug == slug))).one_or_none()
    if row is None:
        raise AppException(404, "public_filter_not_found", "公开筛选不存在")
    return row


async def _catalog_listing_metadata(
    session: AsyncSession,
    locale: Locale,
    owner_type: str,
    page: int,
    page_size: int,
    category: str | None = None,
    type_filter: str | None = None,
    total: int = 0,
) -> dict[str, Any] | None:
    """
    为 Catalog 与 Authority 集合生成稳定的后端 SEO、Breadcrumb 与 Schema。

    输入：
        session: AsyncSession，数据库会话。
        locale: Locale，当前已启用语言。
        owner_type: str，受支持的 Catalog 或 Authority 内容族。
        page: int，当前页码。
        page_size: int，每页条数。
        category: str | None，Knowledge 分类筛选。
        type_filter: str | None，Expert 人物类型筛选。

    输出：
        dict[str, Any] | None，列表元数据；不支持的内容族返回 None。
    """
    locale_labels = _CATALOG_LISTING_LABELS.get(owner_type) or _AUTHORITY_LISTING_LABELS.get(
        owner_type
    )
    if locale_labels is None:
        return None
    resource = {
        "material": "materials",
        "technology": "technologies",
        "application": "applications",
        "solution": "solutions",
        "knowledge_article": "knowledge",
        "case_study": "case-studies",
        "author_expert": "experts",
    }[owner_type]
    labels = locale_labels["zh-cn" if locale.slug == "zh-cn" else "en"]
    title, description = labels
    suffix = _listing_query_suffix(
        category=category if owner_type == "knowledge_article" else None,
        material=None,
        application=None,
        page=page,
        page_size=page_size,
        category_in_path=False,
        type_filter=type_filter if owner_type == "author_expert" else None,
    )
    canonical = f"{OFFICIAL_ORIGIN}/{locale.slug}/{resource}/{suffix}"
    temporary_view = bool(category or type_filter or page_size != 24)
    hreflang: dict[str, str] = {}
    if total > 0 and not temporary_view:
        locale_rows = list(
            (
                await session.scalars(
                    select(Locale)
                    .where(Locale.is_enabled.is_(True))
                    .order_by(Locale.sort_order, Locale.code)
                )
            ).all()
        )
        for item in locale_rows:
            candidate_statement = _public_collection_statement(owner_type, item)
            if candidate_statement is None:
                continue
            candidate_total = int(
                await session.scalar(
                    select(func.count()).select_from(candidate_statement.subquery())
                )
                or 0
            )
            if candidate_total <= (page - 1) * page_size:
                continue
            candidate_suffix = _listing_query_suffix(
                category=None,
                material=None,
                application=None,
                page=page,
                page_size=page_size,
                category_in_path=False,
            )
            hreflang[item.code] = f"{OFFICIAL_ORIGIN}/{item.slug}/{resource}/{candidate_suffix}"
        if "zh-CN" in hreflang:
            hreflang["x-default"] = hreflang["zh-CN"]
    home_name = "首页" if locale.slug == "zh-cn" else "Home"
    breadcrumb = [
        {"name": home_name, "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": title, "url": canonical},
    ]
    seo = {
        "title": title,
        "description": description,
        "canonical": canonical,
        "robots": "index, follow" if total > 0 and not temporary_view else "noindex, follow",
        "hreflang": hreflang,
    }
    return {
        "seo": seo,
        "breadcrumb": breadcrumb,
        "schema": [
            build_webpage_schema({"name": title, "description": description, "url": canonical}),
            build_breadcrumb_schema(breadcrumb),
        ],
    }


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
    rows = await _published_row_tuples(session, owner_type, locale, limit, featured_only)

    return [
        _card_payload(owner_type, entity, translation, route) for entity, translation, route in rows
    ]


async def _published_row_tuples(
    session: AsyncSession,
    owner_type: str,
    locale: Locale,
    limit: int,
    featured_only: bool,
) -> list[tuple[Any, Any, ContentRoute]]:
    """
    一次查询返回通过公开门禁的实体、翻译和 canonical 路由行。

    输入：数据库会话、公开实体类型、语言、上限及推荐过滤标记。
    输出：list，供基础 Link DTO 和完整卡片 serializer 共同复用。
    """
    config = _COLLECTION_CONFIG.get(owner_type)
    if config is None or limit <= 0:
        return []
    model = config.model
    statement = _public_collection_statement(owner_type, locale)
    if statement is None:
        return []
    if featured_only:
        featured_column = getattr(model, "featured", None)
        if featured_column is None:
            return []
        statement = statement.where(featured_column.is_(True))
    order_columns = []
    if hasattr(model, "sort_order"):
        order_columns.append(model.sort_order)
    order_columns.extend((model.created_at, model.slug))
    return list((await session.execute(statement.order_by(*order_columns).limit(limit))).all())


async def _home_locale_is_eligible(session: AsyncSession, locale: Locale) -> bool:
    """
    判断语言首页是否存在至少一项严格公开的实质内容。

    输入：session 数据库会话；locale 已启用语言。
    输出：bool，公司或任一首页内容族通过完整公开门禁时为 True。
    """
    if await _published_company(session, locale) is not None:
        return True
    for owner_type in (
        "product_category",
        "product",
        "material",
        "solution",
        "manufacturing_capability",
        "application",
        "case_study",
        "knowledge_article",
    ):
        if await _published_row_tuples(session, owner_type, locale, 1, False):
            return True
    return False


async def _home_metadata(
    session: AsyncSession,
    locale: Locale,
    company: dict[str, Any] | None,
    has_content: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    生成首页自引用 SEO 和适用 JSON-LD，不借用 About 生命周期。

    输入：数据库会话、当前语言、已发布公司 DTO 与首页实质内容标记。
    输出：(seo, schema)，空首页保持 200 但 noindex 且不生成事实 Schema。
    """
    is_zh = locale.slug == "zh-cn"
    canonical = f"{OFFICIAL_ORIGIN}/{locale.slug}/"
    title = "骏辉螺杆" if is_zh else "Junhui Screw"
    fallback_description = (
        "浏览骏辉已发布的螺杆机筒产品、材料、应用与制造知识。"
        if is_zh
        else "Explore Junhui's published screw and barrel products, materials, applications, and manufacturing knowledge."
    )
    description = str(company.get("short_intro") or "").strip() if company else ""
    locale_rows = list(
        (
            await session.scalars(
                select(Locale)
                .where(Locale.is_enabled.is_(True))
                .order_by(Locale.sort_order, Locale.code)
            )
        ).all()
    )
    eligible: dict[str, str] = {}
    for candidate in locale_rows:
        candidate_has_content = (
            has_content
            if candidate.id == locale.id
            else await _home_locale_is_eligible(session, candidate)
        )
        if candidate_has_content:
            eligible[candidate.code] = f"{OFFICIAL_ORIGIN}/{candidate.slug}/"
    if "zh-CN" in eligible:
        eligible["x-default"] = eligible["zh-CN"]
    seo = {
        "title": title,
        "description": description or fallback_description,
        "canonical": canonical,
        "robots": "index, follow" if has_content else "noindex, follow",
        "hreflang": eligible if has_content else {},
    }
    schema: list[dict[str, Any]] = []
    if has_content:
        schema.append(
            build_webpage_schema(
                {"name": title, "description": seo["description"], "url": canonical}
            )
        )
        # WebSite generator 带 Organization publisher；只有真实 Company Profile 已发布时才输出。
        if company:
            schema.extend((build_website_schema(), build_organization_schema()))
    return seo, schema


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
                SeoDocument.canonical_override == literal(OFFICIAL_ORIGIN) + ContentRoute.path,
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

    category_rows = await _published_row_tuples(session, "product_category", locale, 12, False)
    product_rows = await _published_row_tuples(session, "product", locale, 12, True)
    capability_rows = await _published_row_tuples(
        session, "manufacturing_capability", locale, 8, False
    )
    case_rows = await _published_row_tuples(session, "case_study", locale, 6, False)
    knowledge_rows = await _published_row_tuples(session, "knowledge_article", locale, 6, False)
    product_categories = [
        _card_payload("product_category", entity, translation, route)
        for entity, translation, route in category_rows
    ]
    capabilities = [
        _card_payload("manufacturing_capability", entity, translation, route)
        for entity, translation, route in capability_rows
    ]
    cases = [
        _card_payload("case_study", entity, translation, route)
        for entity, translation, route in case_rows
    ]
    await _attach_card_media(session, locale, product_categories, category_rows, "cover_media_id")
    await _attach_card_media(session, locale, capabilities, capability_rows, "primary_media_id")
    await _attach_card_media(session, locale, cases, case_rows, "primary_media_id")
    featured_products = await _product_card_payloads(session, locale, product_rows)
    knowledge = await _authority_card_payloads(session, "knowledge_article", locale, knowledge_rows)
    materials = await _published_rows(session, "material", locale, 8, False)
    solutions = await _published_rows(session, "solution", locale, 8, False)
    applications = await _published_rows(session, "application", locale, 8, False)
    has_content = bool(
        company
        or product_categories
        or featured_products
        or materials
        or solutions
        or capabilities
        or applications
        or cases
        or knowledge
    )
    seo, schema = await _home_metadata(session, locale, company, has_content)

    return {
        "locale": locale.slug,
        "company": company,
        "hero_media": hero_media.model_dump() if hero_media else None,
        "product_categories": product_categories,
        "featured_products": featured_products,
        "materials": materials,
        "solutions": solutions,
        "capabilities": capabilities,
        "applications": applications,
        "cases": cases,
        "knowledge": knowledge,
        "trust_summary": _trust_summary(company),
        "seo": seo,
        "schema": schema,
    }


async def get_public_listing(
    session: AsyncSession,
    owner_type: str,
    locale_slug: str,
    page: int,
    page_size: int,
    *,
    category: str | None = None,
    material: str | None = None,
    application: str | None = None,
    type_filter: str | None = None,
) -> dict[str, Any]:
    """
    返回统一分页 envelope 的严格公开卡片列表。

    输入：
        session: AsyncSession，数据库会话。
        owner_type: str，受支持的公开实体类型。
        locale_slug: str，目标语言 slug。
        page: int，从 1 开始的页码。
        page_size: int，每页条数，API 层限制为 1 到 48。
        category: str | None，产品分类 slug 白名单筛选。
        material: str | None，产品材料关系 slug 白名单筛选。
        application: str | None，产品应用关系 slug 白名单筛选。
        type_filter: str | None，Expert 的公开人物类型白名单筛选。

    输出：
        dict[str, Any]，包含 items、分页元数据和适用于当前集合的白名单筛选回显。
    """
    locale = await _locale(session, locale_slug)
    config = _COLLECTION_CONFIG.get(owner_type)
    statement = _public_collection_statement(owner_type, locale)
    if config is None or statement is None:
        raise AppException(404, "public_content_not_found", "公开集合不存在")

    model = config.model
    category_row: tuple[Any, Any, ContentRoute] | None = None
    if owner_type == "product":
        if category:
            category_row = await _require_public_filter(
                session,
                "product_category",
                locale,
                category,
                allow_noindex=True,
            )
            statement = statement.where(ProductCategory.slug == category)
        if material:
            await _require_public_filter(session, "material", locale, material)
            statement = (
                statement.join(ProductMaterial, ProductMaterial.product_id == Product.id)
                .join(Material, Material.id == ProductMaterial.material_id)
                .where(Material.slug == material, Material.status == "enabled")
            )
        if application:
            await _require_public_filter(session, "application", locale, application)
            statement = (
                statement.join(
                    ProductApplication,
                    ProductApplication.product_id == Product.id,
                )
                .join(
                    Application,
                    Application.id == ProductApplication.application_id,
                )
                .where(
                    Application.slug == application,
                    Application.status == "enabled",
                )
            )
    elif owner_type == "knowledge_article" and category:
        category_exists = await session.scalar(
            select(KnowledgeCategory.id)
            .join(
                KnowledgeCategoryTranslation,
                KnowledgeCategoryTranslation.category_id == KnowledgeCategory.id,
            )
            .where(
                KnowledgeCategory.slug == category,
                KnowledgeCategory.status == "enabled",
                KnowledgeCategoryTranslation.locale_id == locale.id,
            )
        )
        if category_exists is None:
            raise AppException(404, "public_filter_not_found", "公开筛选不存在")
        statement = statement.where(KnowledgeCategory.slug == category)
    elif owner_type == "author_expert" and type_filter:
        statement = statement.where(AuthorExpert.role_type == type_filter)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(await session.scalar(count_statement) or 0)
    real_pages = ceil(total / page_size) if total else 0
    if page > 1 and (real_pages == 0 or page > real_pages):
        raise AppException(404, "public_page_not_found", "公开分页不存在")
    if owner_type == "product" and total == 0 and (category or material or application):
        category_description = ""
        if category_row is not None:
            category_translation = category_row[1]
            category_description = str(
                getattr(category_translation, "short_description", None)
                or getattr(category_translation, "description", None)
                or ""
            ).strip()
        # 已发布且有独立说明的分类落地页可在无产品时保留 200；其他零结果组合均为 404。
        if material or application or not category_description:
            raise AppException(404, "public_filter_empty", "公开筛选没有匹配内容")
    if (
        owner_type in {"knowledge_article", "author_expert"}
        and total == 0
        and (category or type_filter)
    ):
        raise AppException(404, "public_filter_empty", "公开筛选没有匹配内容")
    order_columns = []
    if hasattr(model, "sort_order"):
        order_columns.append(model.sort_order)
    order_columns.extend((model.created_at, model.slug))
    rows = (
        await session.execute(
            statement.order_by(*order_columns).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    if owner_type == "product":
        items = await _product_card_payloads(session, locale, rows)
    elif owner_type in {"knowledge_article", "author_expert"}:
        items = await _authority_card_payloads(session, owner_type, locale, rows)
    else:
        items = [
            _card_payload(owner_type, entity, translation, route)
            for entity, translation, route in rows
        ]
    filters = {
        "category": category,
        "material": material,
        "application": application,
    }
    if owner_type == "author_expert":
        filters["type"] = type_filter
    payload: dict[str, Any] = {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, ceil(total / page_size)),
        "filters": filters,
    }
    if owner_type == "product":
        seo = await _product_listing_seo(
            session,
            locale,
            page,
            page_size,
            category,
            material,
            application,
            total,
        )
        products_name = "产品" if locale.slug == "zh-cn" else "Products"
        breadcrumb = [
            {
                "name": "首页" if locale.slug == "zh-cn" else "Home",
                "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/",
            }
        ]
        category_in_path = bool(
            category
            and seo["canonical"].split("?", maxsplit=1)[0].endswith(f"/products/{category}/")
        )
        if category_in_path:
            breadcrumb.append(
                {
                    "name": products_name,
                    "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/products/",
                }
            )
        breadcrumb.append({"name": seo["title"], "url": seo["canonical"]})
        payload["seo"] = seo
        payload["breadcrumb"] = breadcrumb
        payload["schema"] = [
            build_webpage_schema(
                {
                    "name": seo["title"],
                    "description": seo["description"],
                    "url": seo["canonical"],
                }
            ),
            build_breadcrumb_schema(breadcrumb),
        ]
    else:
        catalog_metadata = await _catalog_listing_metadata(
            session,
            locale,
            owner_type,
            page,
            page_size,
            category,
            type_filter,
            total,
        )
        if catalog_metadata is not None:
            payload.update(catalog_metadata)
    return payload


def _combined_text(columns: list[Any]) -> Any:
    """
    将可空搜索字段组合为跨 PostgreSQL/SQLite 可用的文本表达式。

    输入：columns: list[Any]，SQLAlchemy 文本列列表。
    输出：Any，空值已归一化且字段间带空格的 SQL 表达式。
    """
    combined = func.coalesce(columns[0], "")
    for column in columns[1:]:
        combined = combined + literal(" ") + func.coalesce(column, "")
    return combined


def _search_select(
    owner_type: str,
    locale: Locale,
    query: str,
    dialect_name: str,
) -> Select[Any]:
    """
    构造单个批准内容族的标准化搜索 select，供统一 UNION 使用。

    输入：
        owner_type: str，六个批准搜索内容族之一。
        locale: Locale，已启用的目标语言。
        query: str，已经 API 校验的用户搜索词。
        dialect_name: str，当前数据库方言名称。

    输出：
        Select[Any]，列固定为 Card DTO 字段加内部相关性分值。
    """
    config = _COLLECTION_CONFIG[owner_type]
    statement = _public_collection_statement(owner_type, locale)
    if statement is None:  # pragma: no cover - 调用方已使用固定白名单
        raise AppException(404, "public_content_not_found", "公开集合不存在")
    model = config.model
    translation_model = config.translation_model
    title = getattr(translation_model, config.title_field)
    body_columns = [getattr(translation_model, field) for field in _SEARCH_FIELDS[owner_type]]
    body_text = _combined_text(body_columns)
    card_summary = func.coalesce(getattr(translation_model, config.summary_fields[0]), "")

    if dialect_name == "postgresql":
        # 标题使用 A 权重、正文使用 B 权重；trigram 仅作为标题拼写容错后备。
        weighted_vector = func.setweight(
            func.to_tsvector("simple", func.coalesce(title, "")),
            literal_column("'A'"),
        ).op("||")(func.setweight(func.to_tsvector("simple", body_text), literal_column("'B'")))
        ts_query = func.websearch_to_tsquery("simple", query)
        match_condition = or_(
            weighted_vector.op("@@")(ts_query),
            title.op("%")(query),
        )
        score = (
            func.ts_rank_cd(weighted_vector, ts_query) * 100 + func.similarity(title, query) * 10
        )
    else:
        # SQLite 单测按精确、前缀、标题包含、正文包含给固定分值，结果可重复。
        normalized_query = query.casefold()
        lowered_title = func.lower(title)
        lowered_body = func.lower(body_text)
        contains_pattern = f"%{normalized_query}%"
        match_condition = or_(
            lowered_title.like(contains_pattern),
            lowered_body.like(contains_pattern),
        )
        score = case(
            (lowered_title == normalized_query, 400.0),
            (lowered_title.like(f"{normalized_query}%"), 300.0),
            (lowered_title.like(contains_pattern), 200.0),
            (lowered_body.like(contains_pattern), 100.0),
            else_=0.0,
        )

    return statement.where(match_condition).with_only_columns(
        literal(owner_type).label("type"),
        model.slug.label("slug"),
        title.label("name"),
        ContentRoute.path.label("url"),
        card_summary.label("summary"),
        score.label("score"),
    )


async def search_public_content(
    session: AsyncSession,
    locale_slug: str,
    query: str,
    content_types: tuple[str, ...] | list[str] | None = None,
    limit_per_type: int = 10,
) -> dict[str, Any]:
    """
    搜索六个批准内容族并按类型返回 canonical Card DTO。

    输入：
        session: AsyncSession，数据库会话。
        locale_slug: str，目标语言 slug。
        query: str，已在 API 层校验长度的搜索词。
        content_types: tuple[str, ...] | list[str] | None，可选类型白名单子集。
        limit_per_type: int，每个类型最多返回的卡片数。

    输出：
        dict[str, Any]，包含原查询词和按批准类型分组的公开卡片。
    """
    locale = await _locale(session, locale_slug)
    requested_types = tuple(content_types or _SEARCH_TYPES)
    if not requested_types or any(item not in _SEARCH_TYPES for item in requested_types):
        raise AppException(422, "invalid_search_type", "搜索类型不受支持")
    # 去重但保留 API 请求顺序，使分组合同稳定。
    selected_types = tuple(dict.fromkeys(requested_types))
    bind = session.get_bind()
    dialect_name = bind.dialect.name
    selects = [
        _search_select(owner_type, locale, query, dialect_name) for owner_type in selected_types
    ]
    search_union = selects[0].subquery() if len(selects) == 1 else union_all(*selects).subquery()
    ranked = select(
        search_union,
        func.row_number()
        .over(
            partition_by=search_union.c.type,
            order_by=(
                search_union.c.score.desc(),
                search_union.c.name,
                search_union.c.slug,
            ),
        )
        .label("type_rank"),
    ).subquery()
    rows = (
        await session.execute(
            select(ranked)
            .where(ranked.c.type_rank <= limit_per_type)
            .order_by(ranked.c.type, ranked.c.type_rank)
        )
    ).mappings()
    groups: dict[str, list[dict[str, str]]] = {owner_type: [] for owner_type in selected_types}
    for row in rows:
        groups[row["type"]].append(
            {
                "type": row["type"],
                "slug": row["slug"],
                "name": row["name"],
                "url": row["url"],
                "summary": row["summary"],
            }
        )
    return {"query": query, "groups": groups}
