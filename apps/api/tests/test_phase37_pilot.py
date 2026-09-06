"""Phase 3.7 首批内容导入、媒体归属和隔离环境回归测试。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

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
from app.phase37_pilot import (
    PilotImportError,
    PilotManifest,
    build_webp_derivative,
    classify_resource,
    redact_evidence,
    validate_source_files,
)
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


def _manifest_payload(source_names: list[str], source_root: Path) -> dict[str, object]:
    """
    构造纯函数测试使用的首批 manifest。

    输入：source_names 文件名列表；source_root 临时源目录。
    输出：dict，可由 PilotManifest 校验的批次数据。
    """
    sources = []
    for order, name in enumerate(source_names, start=1):
        path = source_root / name
        sources.append(
            {
                "external_key": f"junhui:media:nitrided-barrel:{order:02d}",
                "filename": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "order": order,
                "alt_zh_cn": f"注塑机氮化料筒产品图 {order}",
                "alt_en": f"Nitrided barrel for injection molding machines, view {order}",
            }
        )
    return {
        "schema_version": 1,
        "batch_id": "pilot-001",
        "target_environment": "phase37-local-https",
        "draft_import_authorized": True,
        "protected_preview_publish_authorized": False,
        "source_url": "https://www.junhuiscrew.com/product/example.html",
        "category": {
            "external_key": "junhui:product-category:injection-molding-machine-barrels",
            "slug": "injection-molding-machine-barrels",
            "name_zh_cn": "注塑机料筒",
            "name_en": "Injection Molding Machine Barrels",
        },
        "product": {
            "external_key": "junhui:product:nitrided-barrel",
            "slug": "nitrided-barrel",
            "name_zh_cn": "注塑机氮化料筒",
            "name_en": "Nitrided Barrel for Injection Molding Machines",
        },
        "sources": sources,
        "mappings": {},
        "blocked_fields": ["straightness", "chrome_hardness"],
    }


def test_manifest_requires_exact_authorized_scope(tmp_path: Path) -> None:
    """验证 importer 只接受一个产品、四张图、Draft-only 的冻结范围。"""
    for index in range(1, 6):
        (tmp_path / f"source-{index}.jpg").write_bytes(f"source-{index}".encode())
    valid = _manifest_payload(
        [f"source-{index}.jpg" for index in range(1, 5)],
        tmp_path,
    )
    assert PilotManifest.model_validate(valid).product.slug == "nitrided-barrel"

    invalid = _manifest_payload(
        [f"source-{index}.jpg" for index in range(1, 6)],
        tmp_path,
    )
    with pytest.raises(ValueError, match="exactly_four_sources"):
        PilotManifest.model_validate(invalid)


def test_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    """验证源文件被替换后不能继续执行已批准批次。"""
    names = [f"source-{index}.jpg" for index in range(1, 5)]
    for name in names:
        (tmp_path / name).write_bytes(name.encode())
    manifest = PilotManifest.model_validate(_manifest_payload(names, tmp_path))
    (tmp_path / names[0]).write_bytes(b"changed")

    with pytest.raises(PilotImportError, match="source_hash_mismatch"):
        validate_source_files(manifest, tmp_path)


def test_webp_derivative_removes_exif(tmp_path: Path) -> None:
    """验证网站 WebP 派生副本可解码、去 EXIF 且哈希可复算。"""
    from PIL import Image

    source = tmp_path / "source.jpg"
    exif = Image.Exif()
    exif[0x010E] = "internal note"
    Image.new("RGB", (700, 700), (30, 90, 150)).save(source, "JPEG", exif=exif)

    result = build_webp_derivative(source, tmp_path / "derived.webp")
    with Image.open(result.path) as image:
        assert image.format == "WEBP"
        assert image.size == (700, 700)
        assert not image.getexif()
    assert result.sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("items", "mapped_id", "expected"),
    [
        ([], None, "create"),
        ([{"id": "known", "slug": "nitrided-barrel"}], "known", "no-op"),
        ([{"id": "foreign", "slug": "nitrided-barrel"}], None, "conflict"),
        ([], "missing", "conflict"),
    ],
)
def test_resource_classification_is_conservative(
    items: list[dict[str, str]],
    mapped_id: str | None,
    expected: str,
) -> None:
    """验证 importer 不覆盖 manifest 之外的同 slug 实体。"""
    assert classify_resource(items, "nitrided-barrel", mapped_id) == expected


def test_evidence_redaction_removes_credentials_and_internal_ids() -> None:
    """验证普通证据输出不会泄露凭据、Cookie、内部ID或对象键。"""
    payload = {
        "action": "create",
        "password": "secret",
        "cookie": "session",
        "csrf_token": "csrf",
        "storage_key": "public/internal.webp",
        "product_id": "internal-id",
        "nested": {"status": "draft", "media_id": "internal-media-id"},
    }
    redacted = redact_evidence(payload)
    serialized = json.dumps(redacted)

    assert redacted["action"] == "create"
    assert redacted["nested"]["status"] == "draft"
    assert "secret" not in serialized
    assert "internal-id" not in serialized
    assert "public/internal.webp" not in serialized
