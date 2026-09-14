"""站点运营设置 R1 的独立真实 PostgreSQL、媒体与重定向生命周期验证。"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator
from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient
from minio import Minio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.main import create_app as _create_app
from app.modules.discovery.services import resolve_redirect
from app.modules.media.models import MediaAsset
from app.modules.site_operations.schemas import (
    BrandDraftUpdate,
    ManagedRedirectInput,
    NavigationDraftUpdate,
)
from app.modules.site_operations.services import (
    apply_brand,
    apply_navigation,
    check_managed_redirect,
    confirm_managed_redirect,
    create_managed_redirect,
    disable_managed_redirect,
    get_brand_detail,
    get_navigation_detail,
    initialize_site_operations,
    restore_brand_draft,
    restore_navigation_draft,
    save_brand_draft,
    save_navigation_draft,
)
from app.modules.users.models import User
from app.seed import seed_database

assert _create_app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要独立站点运营 PostgreSQL 测试库"),
]


def _validated_test_database_url() -> str:
    """
    验证测试数据库明确隔离且绝不指向常驻 Demo 或 phase37。

    输入：TEST_DATABASE_URL 与 SITE_OPERATIONS_R1_TEST_ONLY 环境变量。
    输出：str，校验后的异步 PostgreSQL 连接串。
    """
    assert os.getenv("APP_ENV") == "test"
    assert os.getenv("SITE_OPERATIONS_R1_TEST_ONLY") == "1"
    assert TEST_DATABASE_URL
    target = make_url(TEST_DATABASE_URL)
    assert "test" in (target.host or "").lower()
    assert "test" in (target.database or "").lower()
    forbidden = ("junhui-demo-r2", "junhui-phase37-pilot")
    assert not any(value in TEST_DATABASE_URL.lower() for value in forbidden)
    return TEST_DATABASE_URL


def _install_test_media_object(storage_key: str) -> None:
    """
    在独立 MinIO 写入一个 TEST ONLY 图片对象。

    输入：storage_key: str，测试对象键。
    输出：None；对象写入专用 public-media bucket。
    """
    endpoint = os.environ["TEST_MINIO_ENDPOINT"]
    client = Minio(
        endpoint,
        access_key=os.environ["TEST_MINIO_ACCESS_KEY"],
        secret_key=os.environ["TEST_MINIO_SECRET_KEY"],
        secure=False,
    )
    if not client.bucket_exists("public-media"):
        client.make_bucket("public-media")
    # 1x1 透明 PNG，仅用于证明品牌媒体引用和对象存储隔离链。
    payload = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63606060f80f0001040100f50b7d0a0000000049454e44ae426082"
    )
    client.put_object("public-media", storage_key, io.BytesIO(payload), len(payload), "image/png")


async def test_site_operations_postgresql_media_and_redirect_full_chain() -> None:
    """验证真实 PostgreSQL 下三条操作链、真实媒体对象及停用后的 resolver 失效。"""
    database_url = _validated_test_database_url()
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)

    storage_key = f"site-operations-r1/{uuid.uuid4().hex}.png"
    _install_test_media_object(storage_key)
    async with factory() as session, session.begin():
        actor = User(
            email=f"site-operations-r1-{uuid.uuid4().hex}@example.test",
            password_hash="test-only-not-used",
            display_name="Site Operations R1 TEST ONLY",
            is_active=True,
        )
        session.add(actor)
        await session.flush()
        actor_id = actor.id
        media = MediaAsset(
            visibility="public",
            media_type="image",
            storage_bucket="public-media",
            storage_key=storage_key,
            original_filename="site-operations-r1-test-only.png",
            sanitized_filename="site-operations-r1-test-only.png",
            mime_type="image/png",
            file_extension=".png",
            file_size_bytes=67,
            sha256="0" * 64,
            width=1,
            height=1,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status="ready",
            uploaded_by=actor_id,
        )
        session.add(media)
        await session.flush()
        media_id = media.id

    async with factory() as session:
        await initialize_site_operations(session, actor_id=actor_id)
        await session.commit()
    async with factory() as session:
        brand = await save_brand_draft(
            session,
            payload=BrandDraftUpdate.model_validate(
                {
                    "expected_revision": 0,
                    "translations": {
                        "zh-CN": {"display_name": "TEST ONLY 骏辉", "short_name": "TEST"},
                        "en": {"display_name": "Junhui TEST ONLY", "short_name": "TEST"},
                    },
                    "header_logo_media_id": str(media_id),
                    "mobile_logo_media_id": str(media_id),
                    "favicon_media_id": str(media_id),
                }
            ),
            actor_id=actor_id,
        )
        await session.commit()
        assert brand["draft"]["media"]["header_logo"]["filename"].endswith(".png")
    async with factory() as session:
        reopened = await get_brand_detail(session)
        assert reopened["draft"]["translations"]["en"]["display_name"] == "Junhui TEST ONLY"
        await apply_brand(session, expected_revision=1, actor_id=actor_id)
        restored_brand = await restore_brand_draft(session, expected_revision=1, actor_id=actor_id)
        await session.commit()
        assert restored_brand["draft_revision"] == 2

    async with factory() as session:
        zh = await get_navigation_detail(session, "zh-CN")
        en_before = await get_navigation_detail(session, "en")
        original_header_count = len(zh["draft"]["header_items"])
        config = {**deepcopy(zh["draft"]), "expected_revision": zh["draft_revision"]}
        config["header_items"][0]["label"] = "TEST ONLY 产品入口"
        config["header_items"].append(
            {
                "id": "test-only-contact",
                "label": "TEST ONLY 联系",
                "target_key": "contact",
                "enabled": True,
            }
        )
        config["header_items"][1]["enabled"] = False
        config["header_items"][0], config["header_items"][1] = (
            config["header_items"][1],
            config["header_items"][0],
        )
        saved_nav = await save_navigation_draft(
            session,
            locale_code="zh-CN",
            payload=NavigationDraftUpdate.model_validate(config),
            actor_id=actor_id,
        )
        await session.commit()
        assert len(saved_nav["draft"]["header_items"]) == original_header_count + 1
    async with factory() as session:
        en_after = await get_navigation_detail(session, "en")
        assert en_after["draft"] == en_before["draft"]
        await apply_navigation(session, locale_code="zh-CN", expected_revision=1, actor_id=actor_id)
        restored_nav = await restore_navigation_draft(
            session, locale_code="zh-CN", expected_revision=1, actor_id=actor_id
        )
        await session.commit()
        assert restored_nav["draft_revision"] == 2

    async with factory() as session:
        redirect = await create_managed_redirect(
            session,
            payload=ManagedRedirectInput.model_validate(
                {
                    "source_host": "junhuiscrew.com",
                    "source_path": "/site-operations-r1-test-only/",
                    "target_path": "/en/products/",
                    "status_code": 308,
                    "notes": "TEST ONLY",
                }
            ),
            actor_id=actor_id,
        )
        await session.commit()
        rule_id = uuid.UUID(redirect["id"])
    async with factory() as session:
        await check_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        confirmed = await confirm_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        await session.commit()
        assert confirmed["enabled"] is True and confirmed["status_code"] == 308
    async with factory() as session:
        resolved = await resolve_redirect(
            session, "junhuiscrew.com", "/site-operations-r1-test-only/"
        )
        await session.commit()
        assert resolved is not None and resolved.status_code == 308
    app = _create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """输入无；输出绑定独立 PostgreSQL 的请求级数据库会话。"""
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://site-operations-api-test",
        follow_redirects=False,
    ) as client:
        response = await client.get(
            "/api/v1/public/redirects/resolve",
            params={"host": "junhuiscrew.com", "path": "/site-operations-r1-test-only/"},
        )
    assert response.status_code == 308
    assert response.headers["location"] == "https://junhuiscrewbarrel.com/en/products/"
    async with factory() as session:
        await disable_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        await session.commit()
    async with factory() as session:
        assert (
            await resolve_redirect(session, "junhuiscrew.com", "/site-operations-r1-test-only/")
            is None
        )

    await engine.dispose()
