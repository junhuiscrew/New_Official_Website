"""提供 SEO/GEO 使用的已发布、可索引 Content Route 查询。"""

from __future__ import annotations

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
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.discovery.models import SeoDocument
from app.modules.localization.models import Locale

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
}


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
