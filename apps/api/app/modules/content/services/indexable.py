"""提供 SEO/GEO 使用的已发布、可索引 Content Route 查询。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.authority.models import AuthorExpert, CaseStudy, KnowledgeArticle
from app.modules.catalog.models import (
    Application,
    Material,
    Product,
    ProductCategory,
    Solution,
    Technology,
)
from app.modules.company.models import CompanyProfile, Exhibition, ManufacturingCapability
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.discovery.models import SeoDocument
from app.modules.localization.models import Locale

OFFICIAL_ORIGIN = "https://junhuiscrewbarrel.com"

# 只有具备结构化主实体的路由才允许进入公开索引源。
INDEXABLE_OWNER_TYPES = frozenset(
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

_BUSINESS_MODELS = {
    "product_category": ProductCategory,
    "product": Product,
    "material": Material,
    "technology": Technology,
    "application": Application,
    "solution": Solution,
    "case_study": CaseStudy,
    "knowledge_article": KnowledgeArticle,
    "author_expert": AuthorExpert,
    "manufacturing_capability": ManufacturingCapability,
    "exhibition": Exhibition,
    "company_profile": CompanyProfile,
}

_HOME_AGGREGATE_OWNER_TYPES = frozenset(
    {
        "company_profile",
        "product_category",
        "product",
        "material",
        "solution",
        "manufacturing_capability",
        "application",
        "case_study",
        "knowledge_article",
    }
)


@dataclass(frozen=True)
class SitemapCandidate:
    """Sitemap 候选站内路径及可证实的最近公开路由更新时间。"""

    path: str
    updated_at: datetime


async def list_indexable_routes(session: AsyncSession) -> list[ContentRoute]:
    """
    查询当前可被搜索引擎和 GEO 抓取的规范路由。

    输入：
        session: AsyncSession，数据库异步会话。

    输出：
        list[ContentRoute]，仅包含已发布、启用语言、规范且可索引的路由，按路径稳定排序。
    """
    statement = (
        select(ContentRoute)
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
            ContentRoute.owner_type.in_(INDEXABLE_OWNER_TYPES),
            ContentRoute.is_canonical.is_(True),
            ContentRoute.indexable.is_(True),
            ContentRoute.active.is_(True),
            ContentPublication.status == PublicationStatus.PUBLISHED.value,
            TranslationStatus.status == "published",
            Locale.is_enabled.is_(True),
            or_(SeoDocument.id.is_(None), SeoDocument.robots_index.is_(True)),
            or_(
                SeoDocument.id.is_(None),
                SeoDocument.canonical_override.is_(None),
                SeoDocument.canonical_override
                == OFFICIAL_ORIGIN + ContentRoute.path,
            ),
        )
        .order_by(ContentRoute.path.asc())
    )
    candidates = list((await session.scalars(statement)).all())
    enabled_ids: dict[str, set] = {}
    for owner_type, model in _BUSINESS_MODELS.items():
        owner_ids = {route.owner_id for route in candidates if route.owner_type == owner_type}
        if not owner_ids:
            enabled_ids[owner_type] = set()
            continue
        enabled_statement = select(model.id).where(
            model.id.in_(owner_ids), model.status == "enabled"
        )
        if owner_type == "author_expert":
            enabled_statement = enabled_statement.where(
                AuthorExpert.is_real_person_verified.is_(True),
                AuthorExpert.public_profile_enabled.is_(True),
            )
        enabled_ids[owner_type] = set((await session.scalars(enabled_statement)).all())
    return [
        route
        for route in candidates
        if route.owner_id in enabled_ids.get(route.owner_type, set())
    ]


async def list_sitemap_candidates(session: AsyncSession) -> list[SitemapCandidate]:
    """
    生成 owner 路由与合格聚合页共用的 Sitemap 候选集合。

    输入：
        session: AsyncSession，数据库异步会话。

    输出：
        list[SitemapCandidate]，包含严格公开 owner 路由，以及由同一批路由证明有实质内容的首页和产品总列表。
    """
    routes = await list_indexable_routes(session)
    candidates = {
        route.path: SitemapCandidate(path=route.path, updated_at=route.updated_at)
        for route in routes
    }
    locales = list(
        (
            await session.scalars(
                select(Locale).where(Locale.is_enabled.is_(True)).order_by(Locale.sort_order)
            )
        ).all()
    )
    for locale in locales:
        locale_routes = [route for route in routes if route.locale_id == locale.id]
        home_routes = [
            route for route in locale_routes if route.owner_type in _HOME_AGGREGATE_OWNER_TYPES
        ]
        product_routes = [route for route in locale_routes if route.owner_type == "product"]
        if home_routes:
            candidates[f"/{locale.slug}/"] = SitemapCandidate(
                path=f"/{locale.slug}/",
                updated_at=max(route.updated_at for route in home_routes),
            )
        if product_routes:
            candidates[f"/{locale.slug}/products/"] = SitemapCandidate(
                path=f"/{locale.slug}/products/",
                updated_at=max(route.updated_at for route in product_routes),
            )
    return [candidates[path] for path in sorted(candidates)]
