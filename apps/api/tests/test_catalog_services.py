"""Structured Core 服务层行为测试。"""

import pytest
from sqlalchemy import select

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog.models import ProductCategory
from app.modules.catalog.schemas import CategoryCreate, CategoryUpdate
from app.modules.catalog.services import create_category, update_category
from app.modules.localization.models import Locale
from app.modules.users import models as _user_models  # noqa: F401


@pytest.mark.asyncio
async def test_category_service_rejects_circular_parent(sqlite_database_url: str) -> None:
    """分类服务必须拒绝把祖先设置为自己的子孙。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        zh = Locale(code="zh-CN", slug="zh-cn", name="Chinese", native_name="中文", is_default=True)
        session.add(zh)
        await session.flush()
        parent = await create_category(session, CategoryCreate(slug="parent", translations=[]))
        child = await create_category(session, CategoryCreate(slug="child", parent_id=parent.id, translations=[]))
        with pytest.raises(AppException, match="循环"):
            await update_category(session, parent.id, CategoryUpdate(parent_id=child.id))
    await engine.dispose()


@pytest.mark.asyncio
async def test_category_service_creates_publication_route_and_revision(sqlite_database_url: str) -> None:
    """创建带翻译分类时必须同时建立统一内容生命周期记录。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        zh = Locale(code="zh-CN", slug="zh-cn", name="Chinese", native_name="中文", is_default=True)
        session.add(zh)
        await session.flush()
        category = await create_category(session, CategoryCreate(slug="injection-screws", translations=[]))
        assert category.id is not None
        assert await session.scalar(select(ProductCategory.id).where(ProductCategory.id == category.id)) == category.id
    await engine.dispose()
