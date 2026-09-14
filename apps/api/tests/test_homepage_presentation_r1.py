"""官网呈现 R1：首页布局配置、权限、修订和作者预览回归测试。"""

from __future__ import annotations

import uuid
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
from app.modules.media.models import MediaAsset
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


async def _media_asset(
    factory: async_sessionmaker[AsyncSession],
    *,
    visibility: str = "public",
    upload_status: str = "ready",
    media_type: str = "image",
) -> MediaAsset:
    """
    创建首页轮播输入校验使用的隔离媒体记录。

    输入：
        factory: async_sessionmaker[AsyncSession]，隔离测试会话工厂。
        visibility: str，媒体公开级别。
        upload_status: str，媒体处理状态。
        media_type: str，媒体类型。

    输出：
        MediaAsset，已经提交并可在后续请求中读取的媒体记录。
    """
    asset_token = uuid.uuid4().hex
    bucket = "public-media" if visibility == "public" else "private-rfq"
    extension = ".webp" if media_type == "image" else ".webm"
    mime_type = "image/webp" if media_type == "image" else "video/webm"
    async with factory() as session:
        asset = MediaAsset(
            visibility=visibility,
            media_type=media_type,
            storage_bucket=bucket,
            storage_key=f"homepage-tests/{asset_token}{extension}",
            original_filename=f"homepage-{asset_token}{extension}",
            sanitized_filename=f"homepage-{asset_token}{extension}",
            mime_type=mime_type,
            file_extension=extension,
            file_size_bytes=128,
            sha256=(asset_token * 2)[:64],
            width=1600 if media_type == "image" else None,
            height=900 if media_type == "image" else None,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status=upload_status,
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        return asset


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


async def test_homepage_hero_slides_validate_order_links_and_public_media(
    homepage_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Hero 轮播顺序、链接成对规则及公开图片门禁均由服务端控制。"""
    detail = await _initialize(homepage_api_factory)
    zh = next(item for item in detail["languages"] if item["locale"]["code"] == "zh-CN")
    first_image = await _media_asset(homepage_api_factory)
    second_image = await _media_asset(homepage_api_factory)
    private_image = await _media_asset(homepage_api_factory, visibility="private")
    modules = list(zh["layout"]["draft"]["modules"])
    valid_slides = [
        {
            "id": "precision-manufacturing",
            "media_id": str(first_image.id),
            "title": "螺杆与机筒精密制造",
            "subtitle": "Demo 内容：展示材料、工艺与制造能力的协同路径。",
            "cta_label": "探索产品",
            "cta_href": "/zh-cn/products/",
            "enabled": True,
        },
        {
            "id": "surface-engineering",
            "media_id": str(second_image.id),
            "title": "表面工程与工艺技术",
            "subtitle": "Demo 内容：从实际工艺术语进入技术内容。",
            "cta_label": None,
            "cta_href": None,
            "enabled": False,
        },
    ]
    modules[0] = {**modules[0], "slides": valid_slides}

    async with _role_client(homepage_api_factory, "editor") as client:
        saved = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 0, "modules": modules},
        )
        reopened = await client.get("/api/v1/presentation/homepage/zh-CN")

        assert saved.status_code == 200, saved.text
        duplicate_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        duplicate_modules[0] = {
            **duplicate_modules[0],
            "slides": [valid_slides[0], {**valid_slides[1], "id": valid_slides[0]["id"]}],
        }
        duplicate_ids = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": duplicate_modules},
        )

        unsafe_link_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        unsafe_link_modules[0] = {
            **unsafe_link_modules[0],
            "slides": [{**valid_slides[0], "cta_href": "javascript:alert(1)"}],
        }
        unsafe_link = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": unsafe_link_modules},
        )

        unpaired_cta_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        unpaired_cta_modules[0] = {
            **unpaired_cta_modules[0],
            "slides": [{**valid_slides[0], "cta_href": None}],
        }
        unpaired_cta = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": unpaired_cta_modules},
        )

        private_media_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        private_media_modules[0] = {
            **private_media_modules[0],
            "slides": [{**valid_slides[0], "media_id": str(private_image.id)}],
        }
        private_media = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": private_media_modules},
        )

        too_many_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        too_many_modules[0] = {
            **too_many_modules[0],
            "slides": [
                {**valid_slides[0], "id": f"slide-{index}"}
                for index in range(6)
            ],
        }
        too_many = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": too_many_modules},
        )

        non_hero_modules = list(saved.json()["data"]["layout"]["draft"]["modules"])
        non_hero_modules[1] = {**non_hero_modules[1], "slides": [valid_slides[0]]}
        non_hero = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 1, "modules": non_hero_modules},
        )

    saved_slides = saved.json()["data"]["layout"]["draft"]["modules"][0]["slides"]
    assert [slide["id"] for slide in saved_slides] == [
        "precision-manufacturing",
        "surface-engineering",
    ]
    assert reopened.json()["data"]["layout"]["draft"]["modules"][0]["slides"] == saved_slides
    assert duplicate_ids.status_code == 422
    assert unsafe_link.status_code == 422
    assert unpaired_cta.status_code == 422
    assert too_many.status_code == 422
    assert non_hero.status_code == 422
    assert private_media.status_code == 409
    assert private_media.json()["error"]["code"] == "homepage_hero_media_unavailable"


async def test_public_homepage_exposes_only_enabled_currently_public_hero_slides(
    homepage_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证公开首页只输出启用且仍通过公开媒体门禁的安全轮播 DTO。"""
    detail = await _initialize(homepage_api_factory)
    zh = next(item for item in detail["languages"] if item["locale"]["code"] == "zh-CN")
    first_image = await _media_asset(homepage_api_factory)
    disabled_image = await _media_asset(homepage_api_factory)
    withdrawn_image = await _media_asset(homepage_api_factory)
    modules = list(zh["layout"]["draft"]["modules"])
    modules[0] = {
        **modules[0],
        "slides": [
            {
                "id": "precision-manufacturing",
                "media_id": str(first_image.id),
                "title": "螺杆与机筒精密制造",
                "subtitle": "Demo 内容：展示材料、工艺与制造能力的协同路径。",
                "cta_label": "探索产品",
                "cta_href": "/zh-cn/products/",
                "enabled": True,
            },
            {
                "id": "disabled-demo-slide",
                "media_id": str(disabled_image.id),
                "title": "停用的演示轮播",
                "subtitle": "这条内容不能出现在公开 DTO。",
                "cta_label": None,
                "cta_href": None,
                "enabled": False,
            },
            {
                "id": "manufacturing-capability",
                "media_id": str(withdrawn_image.id),
                "title": "制造能力与质量控制",
                "subtitle": "Demo 内容：展示现有制造能力页面入口。",
                "cta_label": "查看制造能力",
                "cta_href": "/zh-cn/capabilities/",
                "enabled": True,
            },
        ],
    }

    async with _role_client(homepage_api_factory, "content_admin") as client:
        saved = await client.patch(
            "/api/v1/presentation/homepage/zh-CN/draft",
            json={"expected_revision": 0, "modules": modules},
        )
        assert saved.status_code == 200, saved.text
        applied = await client.post(
            "/api/v1/presentation/homepage/zh-CN/apply",
            json={"expected_revision": 1},
        )
        assert applied.status_code == 200, applied.text

    async with _client(homepage_api_factory) as client:
        first_response = await client.get("/api/v1/public/home/zh-cn")

    assert first_response.status_code == 200, first_response.text
    hero = first_response.json()["data"]["presentation"]["modules"][0]
    assert [slide["title"] for slide in hero["slides"]] == [
        "螺杆与机筒精密制造",
        "制造能力与质量控制",
    ]
    assert hero["slides"][0]["media"]["loading"] == "eager"
    assert hero["slides"][1]["media"]["loading"] == "lazy"
    assert "media_id" not in hero["slides"][0]
    assert "id" not in hero["slides"][0]
    assert "enabled" not in hero["slides"][0]
    assert "storage_bucket" not in repr(hero["slides"])

    # 模拟已应用图片随后撤回公开资格；fresh GET 必须即时过滤，不能泄漏陈旧配置。
    async with homepage_api_factory() as session, session.begin():
        asset = await session.get(MediaAsset, withdrawn_image.id)
        assert asset is not None
        asset.visibility = "private"
        asset.storage_bucket = "private-rfq"

    async with _client(homepage_api_factory) as client:
        fresh_response = await client.get("/api/v1/public/home/zh-cn")

    fresh_hero = fresh_response.json()["data"]["presentation"]["modules"][0]
    assert [slide["title"] for slide in fresh_hero["slides"]] == ["螺杆与机筒精密制造"]


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
