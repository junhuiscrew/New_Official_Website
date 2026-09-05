"""Product、Case 与 Knowledge 的严格公开查询和 DTO 聚合。"""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select
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
)
from app.modules.authority.public import serialize_public_case
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
    ProductModel,
    ProductSolution,
    ProductSpecValue,
    ProductTechnology,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
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
        ("definition", "processing_characteristics", "screw_impact", "recommendations", "limitations"),
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


def _columns(entity: Any) -> dict[str, Any]:
    """
    将已通过公开字段选择的 ORM 实体转为 JSON。

    输入：entity，SQLAlchemy 实体。
    输出：dict，列值字典。
    """
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _locale(session: AsyncSession, locale_slug: str) -> Locale:
    """
    查找启用语言。

    输入：session 与 URL locale_slug。
    输出：Locale；不存在或停用时返回公开 404。
    """
    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    if locale is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    return locale


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
    geo = await session.scalar(select(GeoDocument).where(GeoDocument.owner_type == owner_type, GeoDocument.owner_id == owner_id, GeoDocument.locale_id == locale_id))
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
        route, seo, _geo = await _public_route(
            session, owner_type, owner_id, locale.id
        )
    except AppException:
        return None
    if seo and seo.canonical_override and seo.canonical_override != OFFICIAL_ORIGIN + route.path:
        return None

    if owner_type in CATALOG_PUBLIC_TYPES:
        model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[
            owner_type
        ]
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
        if entity is None or entity.status != "enabled" or translation is None:
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
        if entity is None or entity.status != "enabled" or translation is None:
            return None
        return {
            "type": owner_type,
            "slug": entity.slug,
            "name": translation.title,
            "url": route.path,
            "summary": translation.summary or "",
        }
    return None


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
    target_ids = list(
        (
            await session.scalars(
                select(getattr(relation_model, target_column))
                .where(getattr(relation_model, relation_owner_column) == owner_id)
                .order_by(relation_model.sort_order)
            )
        ).all()
    )
    links: list[dict[str, str]] = []
    for target_id in target_ids:
        link = await _published_link(
            session, target_type, target_id, locale
        )
        if link is not None:
            links.append(link)
    return links


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
                    select(KnowledgeArticle.id).where(
                        KnowledgeArticle.author_id == owner_id
                    )
                )
            ).all()
        )
        target_pairs.extend(
            ("knowledge_article", article_id) for article_id in article_ids
        )

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
            result.append({"slug": case.slug, "title": translation.title, "summary": translation.summary or ""})
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
            result.append({"category_slug": category.slug, "slug": article.slug, "title": translation.title, "summary": translation.summary or ""})
    return result


def _seo_payload(seo: SeoDocument | None, route: ContentRoute, fallback_title: str, fallback_description: str | None) -> dict[str, Any]:
    """
    构造公开 SEO meta，默认 canonical 来自 ContentRoute。

    输入：seo、route 与正文回退标题/描述。
    输出：dict，SSR 可直接消费的 SEO 字段。
    """
    return {
        "title": seo.seo_title if seo and seo.seo_title else fallback_title,
        "description": seo.meta_description if seo and seo.meta_description else fallback_description,
        "canonical": seo.canonical_override if seo and seo.canonical_override else OFFICIAL_ORIGIN + route.path,
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
        .where(Product.slug == slug, Product.status == "enabled", ProductCategory.slug == category_slug, ProductCategory.status == "enabled")
    )
    if product is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "product", product.id, locale.id)
    translation = await session.scalar(select(ProductTranslation).where(ProductTranslation.product_id == product.id, ProductTranslation.locale_id == locale.id))
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    models = list((await session.scalars(select(ProductModel).where(ProductModel.product_id == product.id, ProductModel.status == "enabled").order_by(ProductModel.sort_order))).all())
    specifications = list((await session.scalars(select(ProductSpecValue).where(ProductSpecValue.product_id == product.id, ProductSpecValue.is_public.is_(True)).order_by(ProductSpecValue.sort_order))).all())
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
    url = OFFICIAL_ORIGIN + route.path
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Products", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/products/"},
        {"name": translation.name, "url": url},
    ]
    product_schema = build_product_schema({"name": translation.name, "description": translation.description or translation.short_description, "url": url})
    return {
        "slug": product.slug,
        "category_slug": category_slug,
        "translation": {"name": translation.name, "short_description": translation.short_description, "description": translation.description, "highlights": translation.highlights_jsonb},
        "models": [{"model_code": item.model_code, "sort_order": item.sort_order} for item in models],
        "specifications": [_columns(item) for item in specifications],
        "relations": relations,
        "faqs": faqs,
        "cases": cases,
        "knowledge": knowledge,
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
    case = await session.scalar(select(CaseStudy).where(CaseStudy.slug == slug, CaseStudy.status == "enabled"))
    if case is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "case_study", case.id, locale.id)
    translation = await session.scalar(select(CaseStudyTranslation).where(CaseStudyTranslation.case_study_id == case.id, CaseStudyTranslation.locale_id == locale.id))
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    public_case = serialize_public_case(case, _columns(translation))
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
        .where(KnowledgeArticle.slug == slug, KnowledgeArticle.status == "enabled", KnowledgeCategory.slug == category_slug, KnowledgeCategory.status == "enabled")
    )
    if article is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(session, "knowledge_article", article.id, locale.id)
    translation = await session.scalar(select(KnowledgeArticleTranslation).where(KnowledgeArticleTranslation.article_id == article.id, KnowledgeArticleTranslation.locale_id == locale.id))
    author = await session.get(AuthorExpert, article.author_id)
    author_translation = await session.scalar(select(AuthorExpertTranslation).where(AuthorExpertTranslation.author_expert_id == article.author_id, AuthorExpertTranslation.locale_id == locale.id))
    if translation is None or author is None or author_translation is None or not author.is_real_person_verified:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    reviewer = None
    if article.reviewer_id:
        reviewer_model = await session.get(AuthorExpert, article.reviewer_id)
        reviewer_translation = await session.scalar(select(AuthorExpertTranslation).where(AuthorExpertTranslation.author_expert_id == article.reviewer_id, AuthorExpertTranslation.locale_id == locale.id))
        if reviewer_model and reviewer_model.is_real_person_verified and reviewer_translation:
            reviewer = {"name": reviewer_translation.name, "job_title": reviewer_translation.job_title}
    source_conditions = [SourceCitation.article_id == article.id]
    if geo is not None:
        source_conditions.append(SourceCitation.geo_document_id == geo.id)
    sources = list((await session.scalars(select(SourceCitation).where(or_(*source_conditions)).order_by(SourceCitation.sort_order))).all())
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
    author_payload = {"name": author_translation.name, "job_title": author_translation.job_title, "short_bio": author_translation.short_bio, "is_real_person_verified": True}
    article_schema = build_article_schema({"headline": translation.title, "description": translation.summary, "url": url, "date_modified": article.updated_at.isoformat()}, author_payload)
    return {
        "slug": article.slug,
        "category_slug": category_slug,
        "translation": {"title": translation.title, "summary": translation.summary, "body_markdown": translation.body_markdown},
        "author": author_payload,
        "reviewer": reviewer,
        "sources": [{"title": item.title, "url": item.url, "publisher": item.publisher, "publication_date": item.publication_date, "source_type": item.source_type} for item in sources],
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
    route, seo, geo = await _public_route(
        session, "author_expert", expert.id, locale.id
    )
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
        link = await _published_link(
            session, "knowledge_article", article_id, locale
        )
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
        "is_real_person_verified": True,
        "url": url,
    }
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": "Experts", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/experts/"},
        {"name": translation.name, "url": url},
    ]
    return {
        **person,
        "authored_knowledge": authored_knowledge,
        "seo": _seo_payload(seo, route, translation.name, translation.short_bio),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": [build_person_schema(person), build_breadcrumb_schema(breadcrumb)],
        "alternates": await _published_alternates(
            session, "author_expert", expert.id
        ),
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
    model, translation_model, foreign_key, summary_fields = CATALOG_PUBLIC_TYPES[
        owner_type
    ]
    entity = await session.scalar(
        select(model).where(model.slug == slug, model.status == "enabled")
    )
    if entity is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    route, seo, geo = await _public_route(
        session, owner_type, entity.id, locale.id
    )
    translation = await session.scalar(
        select(translation_model).where(
            getattr(translation_model, foreign_key) == entity.id,
            translation_model.locale_id == locale.id,
        )
    )
    if translation is None:
        raise AppException(404, "public_content_not_found", "公开内容不存在")
    translation_payload = {
        field: value
        for field, value in _columns(translation).items()
        if field
        not in {"id", foreign_key, "locale_id", "created_at", "updated_at"}
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
    breadcrumb = [
        {"name": "Home", "url": f"{OFFICIAL_ORIGIN}/{locale.slug}/"},
        {"name": translation.name, "url": url},
    ]
    return {
        "type": owner_type,
        "slug": entity.slug,
        "translation": translation_payload,
        "seo": _seo_payload(seo, route, translation.name, summary),
        "geo": _geo_payload(geo),
        "breadcrumb": breadcrumb,
        "schema": [
            build_webpage_schema(
                {"name": translation.name, "description": summary, "url": url}
            ),
            build_breadcrumb_schema(breadcrumb),
        ],
        "alternates": await _published_alternates(
            session, owner_type, entity.id
        ),
    }
