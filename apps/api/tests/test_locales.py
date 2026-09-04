"""Locale 管理 API 与单默认语言数据库约束测试。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.main import create_app
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.content.models import ContentRoute
from app.modules.localization.models import Locale
from app.modules.users.bootstrap import create_super_admin
from app.seed import seed_database


@pytest.fixture
async def locale_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建已迁移语义、已 Seed、带 super_admin 的 Locale 测试数据库。"""
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


@asynccontextmanager
async def _authenticated_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """创建使用测试数据库且已登录 super_admin 的客户端。"""
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


async def test_locale_crud_sort_and_set_default_transaction(
    locale_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 list/create/update/sort/set-default 与默认语言禁用保护。"""
    async with _authenticated_client(locale_session_factory) as client:
        listed = await client.get("/api/v1/locales")
        created = await client.post(
            "/api/v1/locales",
            json={
                "code": "vi",
                "slug": "vi",
                "name": "Vietnamese",
                "native_name": "Tiếng Việt",
                "is_enabled": True,
                "sort_order": 30,
            },
        )
        locale_id = created.json()["data"]["id"]
        updated = await client.patch(
            f"/api/v1/locales/{locale_id}",
            json={"native_name": "Tiếng Việt Nam", "sort_order": 25},
        )
        changed_default = await client.post(f"/api/v1/locales/{locale_id}/set-default")
        disable_default = await client.patch(
            f"/api/v1/locales/{locale_id}", json={"is_enabled": False}
        )

    assert listed.status_code == 200
    assert [item["code"] for item in listed.json()["data"]] == ["zh-CN", "en"]
    assert created.status_code == 201
    assert updated.json()["data"]["sort_order"] == 25
    assert changed_default.json()["data"]["is_default"] is True
    assert disable_default.status_code == 409

    async with locale_session_factory() as session:
        locales = {item.code: item for item in (await session.scalars(select(Locale))).all()}
    assert locales["zh-CN"].is_default is False
    assert locales["vi"].is_default is True


@pytest.mark.parametrize(
    "payload",
    [
        {
            "code": "zh-CN",
            "slug": "zh-new",
            "name": "Duplicate Code",
            "native_name": "重复代码",
        },
        {
            "code": "zh-Hans",
            "slug": "zh-cn",
            "name": "Duplicate Slug",
            "native_name": "重复路径",
        },
    ],
)
async def test_locale_rejects_duplicate_code_or_slug(
    locale_session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, str],
) -> None:
    """验证 Locale code 和 slug 均保持唯一。"""
    async with _authenticated_client(locale_session_factory) as client:
        response = await client.post("/api/v1/locales", json=payload)
    assert response.status_code == 409


async def test_database_rejects_a_second_default_locale(
    locale_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证绕过 API 直接写入第二个默认语言仍被数据库拒绝。"""
    async with locale_session_factory() as session:
        english = await session.scalar(select(Locale).where(Locale.code == "en"))
        english.is_default = True
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_locale_mutation_requires_csrf(
    locale_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证已登录用户的 Cookie 写请求仍必须提供 CSRF header。"""
    async with _authenticated_client(locale_session_factory) as client:
        del client.headers["X-CSRF-Token"]
        response = await client.post(
            "/api/v1/locales",
            json={
                "code": "vi",
                "slug": "vi",
                "name": "Vietnamese",
                "native_name": "Tiếng Việt",
            },
        )
    assert response.status_code == 403


async def test_seed_locale_identifiers_are_frozen(
    locale_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 zh-CN/en 的 code 与 URL slug 不能在后台被改写。"""
    async with locale_session_factory() as session:
        english = await session.scalar(select(Locale).where(Locale.code == "en"))
        english_id = english.id
    async with _authenticated_client(locale_session_factory) as client:
        response = await client.patch(f"/api/v1/locales/{english_id}", json={"slug": "english"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "frozen_locale_identifier"


async def test_locale_with_public_route_cannot_be_disabled(
    locale_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证仍有公开路由的非默认语言不能停用。"""
    async with locale_session_factory() as session, session.begin():
        vietnamese = Locale(
            code="vi",
            slug="vi",
            name="Vietnamese",
            native_name="Tiếng Việt",
            is_default=False,
            is_enabled=True,
        )
        session.add(vietnamese)
        await session.flush()
        session.add(
            ContentRoute(
                owner_type="page",
                owner_id=__import__("uuid").uuid4(),
                locale_id=vietnamese.id,
                path="/vi/about/",
                is_canonical=True,
                active=True,
                indexable=True,
            )
        )
        vietnamese_id = vietnamese.id
    async with _authenticated_client(locale_session_factory) as client:
        response = await client.patch(
            f"/api/v1/locales/{vietnamese_id}", json={"is_enabled": False}
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "locale_has_public_content"
