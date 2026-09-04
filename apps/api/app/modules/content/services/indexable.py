"""提供 SEO/GEO 使用的已发布、可索引 Content Route 查询。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute
from app.modules.localization.models import Locale

# 只有具备结构化主实体的路由才允许进入公开索引源。
INDEXABLE_OWNER_TYPES = frozenset(
    {
        "product_category",
        "product",
        "product_model",
        "material",
        "technology",
        "application",
        "solution",
    }
)


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
        .join(Locale, Locale.id == ContentRoute.locale_id)
        .where(
            ContentRoute.owner_type.in_(INDEXABLE_OWNER_TYPES),
            ContentRoute.is_canonical.is_(True),
            ContentRoute.indexable.is_(True),
            ContentRoute.active.is_(True),
            ContentPublication.status == PublicationStatus.PUBLISHED.value,
            Locale.is_enabled.is_(True),
        )
        .order_by(ContentRoute.path.asc())
    )
    return list((await session.scalars(statement)).all())

