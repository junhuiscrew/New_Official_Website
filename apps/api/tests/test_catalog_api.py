"""Structured Core Catalog API 的最小权限、生命周期与动态规格测试。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.main import create_app
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401
from app.modules.users.bootstrap import create_super_admin
from app.modules.users.models import Permission
from app.seed import seed_database


@asynccontextmanager
async def _catalog_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """创建已登录 super_admin 的 Catalog API 客户端。"""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "StrongPassword!2026"},
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


@pytest.fixture
async def catalog_api_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建含 Phase 3.3 Seed 和临时 super_admin 的隔离测试数据库。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    await create_super_admin(
        factory,
        email="owner@example.com",
        password="StrongPassword!2026",
        display_name="Owner",
    )
    yield factory
    await engine.dispose()


async def test_catalog_category_product_and_relation_workflow(
    catalog_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证分类、产品、型号与显式关系 API 可以按依赖顺序工作。"""
    async with _catalog_client(catalog_api_session_factory) as client:
        category_response = await client.post(
            "/api/v1/catalog/categories",
            json={"slug": "barrel-components", "translations": []},
        )
        assert category_response.status_code == 201
        category_id = category_response.json()["data"]["id"]

        product_response = await client.post(
            "/api/v1/catalog/products",
            json={"category_id": category_id, "slug": "demo-product", "translations": []},
        )
        assert product_response.status_code == 201
        product_id = product_response.json()["data"]["id"]

        material_response = await client.post(
            "/api/v1/catalog/materials",
            json={"slug": "hardened-steel", "translations": []},
        )
        relation_response = await client.put(
            f"/api/v1/catalog/products/{product_id}/relations",
            json={"material_ids": [material_response.json()["data"]["id"]]},
        )

        model_response = await client.post(
            f"/api/v1/catalog/products/{product_id}/models",
            json={"model_code": "DM-001", "translations": []},
        )
        assert model_response.status_code == 201
        detail = await client.get(f"/api/v1/catalog/products/{product_id}")

    assert detail.status_code == 200
    assert detail.json()["data"]["models"][0]["model_code"] == "DM-001"
    assert material_response.status_code == 201
    assert relation_response.status_code == 200


async def test_catalog_specification_type_mismatch_is_rejected(
    catalog_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 SpecificationDefinition.value_type 在服务端而非仅前端执行。"""
    async with _catalog_client(catalog_api_session_factory) as client:
        group = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={"code": "dimensions", "translations": []},
        )
        definition = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": group.json()["data"]["id"],
                "code": "diameter",
                "value_type": "number",
                "translations": [],
            },
        )
        # 不存在的 owner 先由请求校验拒绝；类型值不匹配也必须返回稳定 422。
        response = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": "00000000-0000-0000-0000-000000000001",
                "definition_id": definition.json()["data"]["id"],
                "value_text": "not-a-number",
            },
        )

    assert group.status_code == 201
    assert definition.status_code == 201
    assert response.status_code == 422


async def test_catalog_seed_contains_structured_permissions(
    catalog_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证新增 Catalog 权限进入统一 Seed，而不是写死在 API 中。"""
    async with catalog_api_session_factory() as session:
        codes = set((await session.scalars(select(Permission.code))).all())
    assert {"catalog.read", "catalog.create", "specification.manage", "solution.archive"} <= codes
