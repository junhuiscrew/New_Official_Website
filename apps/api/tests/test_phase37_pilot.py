"""Phase 3.7 首批内容导入、媒体归属和隔离环境回归测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.main import create_app
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.media.models import MediaAsset
from app.modules.users import models as user_models  # noqa: F401
from app.modules.users.bootstrap import create_super_admin
from app.seed import seed_database


@pytest.fixture
async def phase37_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建首批导入 API 测试所需的隔离数据库。

    输入：sqlite_database_url，pytest 提供的临时数据库地址。
    输出：async_sessionmaker，已包含系统 Seed 和测试管理员。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    await create_super_admin(
        factory,
        email="phase37-owner@example.com",
        password="StrongPassword!2026",
        display_name="Phase 37 Owner",
    )
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _phase37_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """
    创建带认证 Cookie 与 CSRF Header 的 API 客户端。

    输入：session_factory，隔离数据库会话工厂。
    输出：AsyncClient，可调用受保护 Catalog API。
    """
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """向 FastAPI 注入同一隔离数据库会话。"""
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "phase37-owner@example.com",
                "password": "StrongPassword!2026",
            },
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


async def _media_asset(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    visibility: str = "public",
    upload_status: str = "ready",
) -> MediaAsset:
    """
    创建指定可见性和上传状态的媒体测试记录。

    输入：session_factory、visibility 和 upload_status。
    输出：MediaAsset，已提交并可被 Product API 引用。
    """
    bucket = "public-media" if visibility == "public" else "private-rfq"
    async with session_factory() as session:
        asset = MediaAsset(
            visibility=visibility,
            media_type="image",
            storage_bucket=bucket,
            storage_key=f"phase37/{visibility}-{upload_status}.webp",
            original_filename="pilot.webp",
            sanitized_filename="pilot.webp",
            mime_type="image/webp",
            file_extension=".webp",
            file_size_bytes=128,
            sha256="1" * 64,
            width=700,
            height=700,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status=upload_status,
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        return asset


async def _category(client: AsyncClient) -> str:
    """
    创建 Product 测试所需分类。

    输入：client，已认证 API 客户端。
    输出：str，新分类 UUID 字符串。
    """
    response = await client.post(
        "/api/v1/catalog/categories",
        json={"slug": "phase37-barrels", "translations": []},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


async def test_product_primary_media_round_trips_in_detail(
    phase37_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Product 创建和详情 DTO 保留可用公开主媒体。"""
    public_asset = await _media_asset(phase37_session_factory)
    async with _phase37_client(phase37_session_factory) as client:
        category_id = await _category(client)
        response = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category_id,
                "slug": "pilot-nitrided-barrel",
                "primary_media_id": str(public_asset.id),
                "translations": [],
            },
        )
        assert response.status_code == 201
        detail = await client.get(
            f"/api/v1/catalog/products/{response.json()['data']['id']}"
        )

    assert detail.status_code == 200
    assert detail.json()["data"]["primary_media_id"] == str(public_asset.id)


@pytest.mark.parametrize(
    ("visibility", "upload_status"),
    [("private", "ready"), ("public", "pending")],
)
async def test_product_primary_media_requires_ready_public_asset(
    phase37_session_factory: async_sessionmaker[AsyncSession],
    visibility: str,
    upload_status: str,
) -> None:
    """验证私有或未完成媒体不能被设置为 Product 主图。"""
    asset = await _media_asset(
        phase37_session_factory,
        visibility=visibility,
        upload_status=upload_status,
    )
    async with _phase37_client(phase37_session_factory) as client:
        category_id = await _category(client)
        response = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category_id,
                "slug": f"invalid-{visibility}-{upload_status}",
                "primary_media_id": str(asset.id),
                "translations": [],
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "product_primary_media_invalid"
