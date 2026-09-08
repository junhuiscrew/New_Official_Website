"""官网呈现 R1：首页布局配置、权限、修订和作者预览回归测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.content.models import ContentRevision, SitePage
from app.modules.presentation.models import HomepageLayout
from app.modules.presentation.registry import HOMEPAGE_MODULE_KEYS
from app.modules.users.models import Role, User, UserRole
from app.seed import seed_database

TEST_LOGIN_PROOF = "Homepage-R1-Test-Only-2026!"


@pytest.fixture
async def homepage_api_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建首页配置 API 的隔离数据库。

    输入：
        sqlite_database_url: str，pytest 临时 SQLite 地址。

    输出：
        AsyncIterator，会话工厂；测试结束后释放引擎。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    async with factory() as session, session.begin():
        for role_name in ("content_admin", "editor", "reviewer"):
            role = await session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            user = User(
                email=f"homepage-{role_name}@example.com",
                password_hash=hash_password(TEST_LOGIN_PROOF),
                display_name=f"homepage-{role_name}",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """输入隔离会话工厂；输出绑定测试应用的匿名客户端。"""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """输入无；输出请求级隔离数据库会话。"""
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@asynccontextmanager
async def _role_client(
    factory: async_sessionmaker[AsyncSession],
    role_name: str,
    *,
    csrf: bool = True,
) -> AsyncIterator[AsyncClient]:
    """输入会话工厂、角色和CSRF开关；输出已登录测试客户端。"""
    async with _client(factory) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"homepage-{role_name}@example.com",
                "password": TEST_LOGIN_PROOF,
            },
        )
        assert response.status_code == 200
        if csrf:
            client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


async def _initialize(
    factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """输入隔离会话工厂；输出首页初始化后的真实双语详情。"""
    async with _role_client(factory, "content_admin") as client:
        response = await client.post("/api/v1/presentation/homepage/initialize")
    assert response.status_code == 200
    return response.json()["data"]


async def test_homepage_initialization_requires_auth_permission_and_csrf(
    homepage_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证初始化权限边界、双语真实页面身份及十四模块默认配置。"""
    path = "/api/v1/presentation/homepage/initialize"
    async with _client(homepage_api_factory) as client:
        anonymous = await client.post(path)
    async with _role_client(homepage_api_factory, "reviewer") as client:
        wrong_permission = await client.post(path)
    async with _role_client(homepage_api_factory, "content_admin", csrf=False) as client:
        missing_csrf = await client.post(path)
    async with _role_client(homepage_api_factory, "content_admin") as client:
        first = await client.post(path)
        second = await client.post(path)

    assert anonymous.status_code == 401
    assert wrong_permission.status_code == 403
    assert missing_csrf.status_code == 403
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    detail = first.json()["data"]
    assert detail["page"]["system_key"] == "home"
    assert {item["locale"]["code"] for item in detail["languages"]} == {"zh-CN", "en"}
    for language in detail["languages"]:
        modules = language["layout"]["draft"]["modules"]
        assert tuple(item["key"] for item in modules) == HOMEPAGE_MODULE_KEYS
        assert all(item["visible"] is True for item in modules)
        assert language["layout"]["draft_revision"] == 0
        assert language["layout"]["applied_revision"] == 0

    async with homepage_api_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(SitePage).where(SitePage.system_key == "home")
            )
            == 1
        )
        assert await session.scalar(select(func.count()).select_from(HomepageLayout)) == 2


async def test_homepage_draft_save_apply_restore_and_revision_conflict(
    homepage_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证排序、显隐、产品slug引用、应用、恢复和并发冲突均由服务端控制。"""
    detail = await _initialize(homepage_api_factory)
    zh = next(item for item in detail["languages"] if item["locale"]["code"] == "zh-CN")
    modules = list(zh["layout"]["draft"]["modules"])
    modules[1], modules[2] = modules[2], modules[1]
    modules[0] = {
        **modules[0],
        "variant": "product-focus",
        "product_slugs": [],
    }
    modules[4] = {**modules[4], "visible": False}
    payload = {"expected_revision": 0, "modules": modules}

    async with _role_client(homepage_api_factory, "editor") as client:
        saved = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json=payload,
        )
        editor_apply = await client.post(
            "/api/v1/presentation/homepage/zh-CN/apply",
            json={"expected_revision": 1},
        )
        conflict = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json=payload,
        )
        unavailable_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        unavailable_modules[0] = {
            **unavailable_modules[0],
            "product_slugs": ["not-published-product"],
        }
        unavailable = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": unavailable_modules},
        )

    assert saved.status_code == 200
    assert saved.json()["data"]["layout"]["draft_revision"] == 1
    assert editor_apply.status_code == 403
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "homepage_revision_conflict"
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "homepage_product_reference_unavailable"

    async with _role_client(homepage_api_factory, "content_admin") as client:
        applied = await client.post(
            "/api/v1/presentation/homepage/zh-CN/apply",
            json={"expected_revision": 1},
        )
        modules_after_apply = list(applied.json()["data"]["layout"]["draft"]["modules"])
        modules_after_apply[0] = {**modules_after_apply[0], "visible": False}
        edited_again = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": modules_after_apply},
        )
        restored = await client.post(
            "/api/v1/presentation/homepage/zh-CN/restore",
            json={"expected_revision": 2},
        )
        reopened = await client.get("/api/v1/presentation/homepage/zh-CN")

    assert applied.status_code == 200
    assert applied.json()["data"]["layout"]["applied_revision"] == 1
    assert edited_again.status_code == 200
    assert restored.status_code == 200
    assert reopened.status_code == 200
    assert (
        reopened.json()["data"]["layout"]["draft"]
        == reopened.json()["data"]["layout"]["applied"]
    )

    async with homepage_api_factory() as session:
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.target_type == "homepage_layout")
                )
            ).all()
        )
        revision_count = await session.scalar(
            select(func.count())
            .select_from(ContentRevision)
            .where(ContentRevision.owner_type == "homepage_layout")
        )
    assert {
        "homepage.initialize",
        "homepage.draft.save",
        "homepage.layout.apply",
        "homepage.draft.restore",
    }.issubset(actions)
    assert revision_count == 4


async def test_author_preview_is_authenticated_no_store_and_lists_all_modules(
    homepage_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证作者预览不由查询参数解锁，并返回十四模块的可解释状态。"""
    await _initialize(homepage_api_factory)
    path = "/api/v1/presentation/homepage/zh-CN/preview"
    async with _client(homepage_api_factory) as client:
        anonymous = await client.get(path)
        query_bypass = await client.get(f"{path}?preview=1")
    async with _role_client(homepage_api_factory, "editor") as client:
        allowed = await client.get(path)
        overview = await client.get("/api/v1/presentation/site-overview/zh-CN")

    assert anonymous.status_code == 401
    assert query_bypass.status_code == 401
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "private, no-store"
    preview = allowed.json()["data"]
    assert preview["preview"] is True
    assert tuple(item["key"] for item in preview["presentation"]["modules"]) == (
        HOMEPAGE_MODULE_KEYS
    )
    assert all(
        "management_url" in item and "content_status" in item
        for item in preview["presentation"]["modules"]
    )

    assert overview.status_code == 200
    rows = overview.json()["data"]["items"]
    technologies = next(item for item in rows if item["key"] == "technologies")
    contact = next(item for item in rows if item["key"] == "contact")
    assert technologies["frontend_url"] == "/zh-cn/technologies/"
    assert technologies["admin_url"] == "/catalog/technologies"
    assert contact["implementation"] == "contact_entry_only"
