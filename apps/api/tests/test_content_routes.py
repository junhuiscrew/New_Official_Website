"""Content Route 路径和唯一性服务测试。"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog.models import Product, ProductCategory
from app.modules.content import models as content_models  # noqa: F401
from app.modules.content.models import ContentPublication, TranslationStatus
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.content.services.routes import create_content_route, validate_content_path
from app.modules.localization.models import Locale
from app.modules.users import models as user_models  # noqa: F401


@pytest.fixture
async def route_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建含英文 Locale 的路由测试数据库。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add(
            Locale(
                code="en",
                slug="en",
                name="English",
                native_name="English",
                is_default=True,
                is_enabled=True,
            )
        )
    yield factory
    await engine.dispose()


@pytest.mark.parametrize("path", ["/EN/About/", "/en/about_us/", "/about/", "/en//about/"])
def test_route_path_requires_locale_prefix_lowercase_and_kebab_case(path: str) -> None:
    """验证公开路径满足稳定多语言 URL 规则。"""
    with pytest.raises(ValueError):
        validate_content_path(path, "en")


async def test_duplicate_content_path_is_rejected(
    route_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 route registry 不允许两个实体占用相同 URL。"""
    async with route_session_factory() as session:
        locale = await session.scalar(__import__("sqlalchemy").select(Locale))
        async with session.begin_nested():
            await create_content_route(session, "page", uuid.uuid4(), locale, "/en/about/")
        await session.commit()
    async with route_session_factory() as session, session.begin():
        locale = await session.scalar(__import__("sqlalchemy").select(Locale))
        with pytest.raises(AppException) as raised:
            await create_content_route(session, "page", uuid.uuid4(), locale, "/en/about/")
    assert raised.value.status_code == 409


async def test_owner_locale_has_only_one_canonical_route(
    route_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证服务层与数据库约束只允许一个 owner/locale 规范路由。"""
    owner_id = uuid.uuid4()
    async with route_session_factory() as session, session.begin():
        locale = await session.scalar(__import__("sqlalchemy").select(Locale))
        await create_content_route(session, "page", owner_id, locale, "/en/about/")
        with pytest.raises(AppException) as raised:
            await create_content_route(session, "page", owner_id, locale, "/en/about-alt/")
    assert raised.value.code == "canonical_route_conflict"


async def test_indexable_route_source_requires_published_active_canonical_route(
    route_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 SEO/GEO 索引源只返回已发布且启用语言的结构化规范路由。"""
    async with route_session_factory() as session, session.begin():
        locale = await session.scalar(__import__("sqlalchemy").select(Locale))
        category = ProductCategory(slug="demo-category", status="enabled", sort_order=0)
        session.add(category)
        await session.flush()
        product = Product(
            category_id=category.id,
            slug="demo",
            status="enabled",
            featured=False,
            sort_order=0,
        )
        session.add(product)
        await session.flush()
        route = await create_content_route(session, "product", product.id, locale, "/en/products/demo/")
        session.add_all(
            [
                ContentPublication(
                    owner_type=route.owner_type,
                    owner_id=route.owner_id,
                    locale_id=route.locale_id,
                    status="published",
                ),
                TranslationStatus(
                    owner_type=route.owner_type,
                    owner_id=route.owner_id,
                    locale_id=route.locale_id,
                    source_locale_id=route.locale_id,
                    status="published",
                ),
            ]
        )
        route.active = True
        route.indexable = True
    async with route_session_factory() as session:
        routes = await list_indexable_routes(session)
    assert [item.path for item in routes] == ["/en/products/demo/"]
