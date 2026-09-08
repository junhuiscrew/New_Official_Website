"""Phase 3.5 Remediation 的存储、RFQ 安全、扫描与 Trust 生命周期回归测试。"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import Request
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1 import api_v1_router as _api_v1_router  # noqa: F401, E402
from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.catalog.models import Product, ProductCategory, ProductModel, ProductTranslation
from app.modules.company import models as _company_models  # noqa: F401
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    TranslationStatus,
)
from app.modules.discovery import models as _discovery_models  # noqa: F401
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset
from app.modules.rfq import models as _rfq_models  # noqa: F401
from app.modules.rfq.models import RFQ, RFQItem
from app.modules.rfq.schemas import RFQCreate, RFQItemInput
from app.modules.users import models as _user_models  # noqa: F401


@pytest.fixture
async def remediation_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建含中英文语言的隔离 Remediation 数据库。

    输入：sqlite_database_url，pytest 临时数据库 URL。
    输出：async_sessionmaker，测试结束后释放引擎。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add_all(
            [
                Locale(code="zh-CN", slug="zh-cn", name="Chinese", native_name="中文", is_default=True, is_enabled=True, sort_order=10),
                Locale(code="en", slug="en", name="English", native_name="English", is_default=False, is_enabled=True, sort_order=20),
            ]
        )
    yield factory
    await engine.dispose()


def _request(*, peer: str, origin: str | None = None, forwarded_for: str | None = None) -> Request:
    """创建只包含安全上下文字段的 Starlette Request。"""
    headers = []
    if origin:
        headers.append((b"origin", origin.encode()))
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers, "client": (peer, 12345), "scheme": "http", "server": ("testserver", 80)})


def test_cad_headers_require_real_format_markers() -> None:
    """CAD 即使使用 octet-stream，也必须通过各格式文件头识别。"""
    from app.modules.media.services import validate_upload_bytes

    fixtures = {
        "part.step": b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;",
        "part.dwg": b"AC1032\x00binary-dwg",
        "part.dxf": b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF",
        "part.igs": b"Junhui IGES model                                                  S      1",
    }
    for name, content in fixtures.items():
        assert validate_upload_bytes(name, "application/octet-stream", content, private=True)["media_type"] == "cad"
        with pytest.raises(AppException) as raised:
            validate_upload_bytes(name, "application/octet-stream", b"not-a-cad-file", private=True)
        assert raised.value.code == "file_signature_invalid"


def test_origin_validation_uses_exact_scheme_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Origin 必须精确匹配，恶意前后缀域名和 userinfo 均被拒绝。"""
    from app.modules.rfq.services import validate_public_origin

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MINIO_SECRET_KEY", "phase35-production-minio-secret-at-least-32-bytes")
    monkeypatch.setenv("MINIO_PUBLIC_ENDPOINT", "storage.junhuiscrewbarrel.com")
    monkeypatch.setenv("MINIO_PUBLIC_SECURE", "true")
    monkeypatch.setenv("JWT_SIGNING_SECRET", "phase35-production-jwt-secret-at-least-32-bytes")
    monkeypatch.setenv("REFRESH_TOKEN_SECRET", "phase35-production-refresh-secret-at-least-32-bytes")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://junhuiscrewbarrel.com"]')
    from app.core.config import get_settings

    get_settings.cache_clear()
    validate_public_origin(_request(peer="127.0.0.1", origin="https://junhuiscrewbarrel.com"))
    for origin in (
        "https://eviljunhuiscrewbarrel.com",
        "https://junhuiscrewbarrel.com.evil.com",
        "http://junhuiscrewbarrel.com",
        "https://junhuiscrewbarrel.com@evil.com",
        "https://junhuiscrewbarrel.com:444",
    ):
        with pytest.raises(AppException) as raised:
            validate_public_origin(_request(peer="127.0.0.1", origin=origin))
        assert raised.value.code == "origin_not_allowed"


def test_client_ip_only_trusts_forwarded_chain_from_configured_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """非受信 peer 不能伪造 X-Forwarded-For，受信代理使用最左侧合法客户端 IP。"""
    from app.core.config import get_settings
    from app.core.request_context import get_client_ip

    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["10.0.0.0/8"]')
    get_settings.cache_clear()
    assert get_client_ip(_request(peer="203.0.113.10", forwarded_for="198.51.100.8")) == "203.0.113.10"
    assert get_client_ip(_request(peer="10.1.2.3", forwarded_for="198.51.100.8, 10.2.3.4")) == "198.51.100.8"


class _FakeMinioClient:
    """为 Storage Adapter 单元测试提供 MinIO SDK 兼容内存客户端。"""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, bucket: str, key: str, stream: io.BytesIO, length: int, content_type: str):
        self.objects[(bucket, key)] = stream.read(length)

    def stat_object(self, bucket: str, key: str):
        if (bucket, key) not in self.objects:
            raise RuntimeError("missing")
        return object()

    def get_object(self, bucket: str, key: str):
        content = self.objects[(bucket, key)]

        class Response(io.BytesIO):
            def close(self) -> None:
                super().close()

            def release_conn(self) -> None:
                return None

        return Response(content)

    def remove_object(self, bucket: str, key: str):
        self.objects.pop((bucket, key), None)

    def presigned_get_object(self, bucket: str, key: str, expires: timedelta):
        return f"http://localhost:9000/{bucket}/{key}?X-Amz-Expires={int(expires.total_seconds())}"


async def test_storage_adapter_put_get_exists_delete_and_presign() -> None:
    """正式 Adapter 必须调用对象存储，而不是只写数据库元数据。"""
    from app.modules.media.storage import MinioStorageAdapter

    fake = _FakeMinioClient()
    adapter = MinioStorageAdapter(client=fake, public_client=fake)
    await adapter.put_object("public-media", "public/a.pdf", b"%PDF-test", "application/pdf")
    assert await adapter.object_exists("public-media", "public/a.pdf") is True
    assert await adapter.get_object("public-media", "public/a.pdf") == b"%PDF-test"
    url = await adapter.presigned_get("private-rfq", "rfq/a.step", ttl_seconds=600)
    assert "X-Amz-Expires=600" in url and "minio:9000" not in url
    await adapter.delete_object("public-media", "public/a.pdf")
    assert await adapter.object_exists("public-media", "public/a.pdf") is False


async def test_refresh_public_image_metadata_decodes_object_and_preserves_asset(
    remediation_factory,
) -> None:
    """尺寸刷新只补真实宽高，并保持对象哈希、路径、ID及其他媒体字段不变。"""
    from app.api.v1.media import refresh_image_metadata
    from app.modules.audit.models import AuditLog
    from app.modules.media.storage import MinioStorageAdapter

    output = io.BytesIO()
    Image.new("RGB", (91, 57), (30, 100, 170)).save(output, "WEBP")
    content = output.getvalue()
    digest = __import__("hashlib").sha256(content).hexdigest()
    fake = _FakeMinioClient()
    fake.objects[("public-media", "public/existing/product.webp")] = content
    storage = MinioStorageAdapter(client=fake, public_client=fake)
    actor_id = uuid.uuid4()

    async with remediation_factory() as session:
        asset = MediaAsset(
            visibility="public",
            media_type="image",
            storage_bucket="public-media",
            storage_key="public/existing/product.webp",
            original_filename="product.webp",
            sanitized_filename="product.webp",
            mime_type="image/webp",
            file_extension=".webp",
            file_size_bytes=len(content),
            sha256=digest,
            width=None,
            height=None,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status="ready",
        )
        session.add(asset)
        await session.commit()
        original = {
            "id": asset.id,
            "sha256": asset.sha256,
            "storage_bucket": asset.storage_bucket,
            "storage_key": asset.storage_key,
            "original_filename": asset.original_filename,
        }

        response = await refresh_image_metadata(
            asset.id,
            session=session,
            user=SimpleNamespace(id=actor_id),
            _csrf=None,
            storage=storage,
        )
        await session.refresh(asset)
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "media.metadata_refresh",
                AuditLog.target_id == str(asset.id),
            )
        )

        assert response.data["changed"] is True
        assert (asset.width, asset.height) == (91, 57)
        assert {
            "id": asset.id,
            "sha256": asset.sha256,
            "storage_bucket": asset.storage_bucket,
            "storage_key": asset.storage_key,
            "original_filename": asset.original_filename,
        } == original
        assert audit is not None

        second = await refresh_image_metadata(
            asset.id,
            session=session,
            user=SimpleNamespace(id=actor_id),
            _csrf=None,
            storage=storage,
        )
        audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.action == "media.metadata_refresh",
                        AuditLog.target_id == str(asset.id),
                    )
                )
            ).all()
        )
        assert second.data["changed"] is False
        assert len(audits) == 1


@pytest.mark.minio
async def test_real_minio_round_trip() -> None:
    """显式启用时对真实 MinIO 执行 put/get/stat/presign/delete 闭环。"""
    if os.getenv("TEST_MINIO_REAL") != "1":
        pytest.skip("set TEST_MINIO_REAL=1 to run MinIO integration")
    from app.core.config import get_settings
    from app.modules.media.storage import MinioStorageAdapter

    settings = get_settings()
    adapter = MinioStorageAdapter()
    key = f"integration/{uuid.uuid4()}.pdf"
    await adapter.put_object(settings.minio_private_bucket, key, b"%PDF-real-minio", "application/pdf")
    try:
        assert await adapter.object_exists(settings.minio_private_bucket, key)
        assert await adapter.get_object(settings.minio_private_bucket, key) == b"%PDF-real-minio"
        url = await adapter.presigned_get(settings.minio_private_bucket, key)
        assert isinstance(url, str) and "X-Amz-" in url and "minio:9000" not in url
    finally:
        await adapter.delete_object(settings.minio_private_bucket, key)


@pytest.mark.redis
async def test_real_redis_rate_limit_rejects_after_exact_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式启用时验证 Redis 双窗口使用同一可信客户端 IP。"""
    if os.getenv("TEST_REDIS_REAL") != "1":
        pytest.skip("set TEST_REDIS_REAL=1 to run Redis integration")
    from redis.asyncio import Redis

    from app.core.config import get_settings
    from app.modules.rfq.services import enforce_public_rate_limit

    unique_ip = f"198.51.100.{uuid.uuid4().int % 200 + 1}"
    monkeypatch.setenv("RFQ_RATE_LIMIT_PER_HOUR", "1")
    monkeypatch.setenv("RFQ_RATE_LIMIT_PER_DAY", "1")
    get_settings.cache_clear()
    client = Redis.from_url(get_settings().redis_url)
    try:
        keys = await client.keys(f"rfq:public:{unique_ip}:*")
        if keys:
            await client.delete(*keys)
        await enforce_public_rate_limit(unique_ip)
        with pytest.raises(AppException) as raised:
            await enforce_public_rate_limit(unique_ip)
        assert raised.value.code == "rfq_rate_limited"
    finally:
        await client.aclose()


def test_submission_token_uses_public_reference_not_database_uuid() -> None:
    """匿名上传令牌可验证归属，但载荷不能泄露 RFQ 数据库 UUID。"""
    import jwt

    from app.core.config import get_settings
    from app.modules.rfq.services import create_submission_token, verify_submission_token

    rfq = RFQ(id=uuid.uuid4(), public_reference="RFQ-20260904-ABC123", company_name="ACME", contact_name="Lee", email="lee@example.com", consent_privacy=True)
    token = create_submission_token(rfq)
    payload = jwt.decode(token, get_settings().jwt_signing_secret, algorithms=["HS256"])
    assert payload["sub"] == rfq.public_reference
    assert str(rfq.id) not in token and "ref" not in payload
    assert verify_submission_token(token, rfq.public_reference)


async def test_public_product_slug_is_resolved_to_server_authoritative_rfq_source(
    remediation_factory,
) -> None:
    """公开 CTA 只提交 slug；服务端必须核验发布门禁并写入真实 Product ID 与 canonical。"""
    from app.modules.rfq.services import validate_source

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.slug == "en"))
        category = ProductCategory(slug="parts", status="enabled")
        session.add(category)
        await session.flush()
        product = Product(category_id=category.id, slug="precision-screw", status="enabled")
        session.add(product)
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Precision Screw",
                ),
                TranslationStatus(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=locale.id,
                    path="/en/products/parts/precision-screw/",
                    is_canonical=True,
                    indexable=True,
                    active=True,
                ),
            ]
        )
        await session.flush()
        payload = RFQCreate(
            company_name="ACME",
            contact_name="Lee",
            email="lee@example.com",
            message="Need a quote",
            consent_privacy=True,
            preferred_language="en",
            source_type="product",
            source_slug="precision-screw",
        )

        source_page_url, source_owner_type, source_owner_id = await validate_source(
            session, payload
        )

        assert source_owner_id == product.id
        assert source_owner_type == "product"
        assert source_page_url == (
            "https://junhuiscrewbarrel.com/en/products/parts/precision-screw/"
        )


async def test_unpublished_product_slug_is_rejected_as_rfq_source(remediation_factory) -> None:
    """未发布 Product 即使 slug 真实存在，也不能伪装为公开询盘来源。"""
    from app.modules.rfq.services import validate_source

    async with remediation_factory() as session, session.begin():
        category = ProductCategory(slug="parts", status="enabled")
        session.add(category)
        await session.flush()
        session.add(Product(category_id=category.id, slug="draft-screw", status="enabled"))
        await session.flush()
        payload = RFQCreate(
            company_name="ACME",
            contact_name="Lee",
            email="lee@example.com",
            message="Need a quote",
            consent_privacy=True,
            preferred_language="en",
            source_type="product",
            source_slug="draft-screw",
        )

        with pytest.raises(AppException) as rejected:
            await validate_source(session, payload)

        assert rejected.value.code == "invalid_rfq_source"


def test_public_rfq_schema_rejects_client_supplied_internal_source_fields() -> None:
    """匿名 RFQ schema 必须拒绝 owner UUID 与页面 URL，不能静默忽略后再污染归因。"""
    forbidden_fields = {
        "source_owner_id": str(uuid.uuid4()),
        "source_owner_type": "product",
        "source_page_url": "https://evil.example/private",
    }
    for field_name, value in forbidden_fields.items():
        with pytest.raises(ValueError):
            RFQCreate(
                company_name="ACME",
                contact_name="Lee",
                email="lee@example.com",
                message="Need a quote",
                consent_privacy=True,
                preferred_language="en",
                **{field_name: value},
            )


async def test_rfq_model_and_attachment_item_must_belong_to_parent(remediation_factory) -> None:
    """ProductModel 与 RFQItem 均必须属于当前父实体，拒绝跨对象 UUID 注入。"""
    from app.modules.rfq.services import add_private_file, create_rfq

    async with remediation_factory() as session, session.begin():
        category = ProductCategory(slug="parts", status="enabled")
        session.add(category)
        await session.flush()
        product = Product(category_id=category.id, slug="screw", status="enabled")
        other_product = Product(category_id=category.id, slug="barrel", status="enabled")
        session.add_all([product, other_product])
        await session.flush()
        model = ProductModel(product_id=other_product.id, model_code="B-01", status="enabled")
        session.add(model)
        await session.flush()
        payload = RFQCreate(company_name="ACME", contact_name="Lee", email="lee@example.com", consent_privacy=True, preferred_language="en", items=[RFQItemInput(product_id=product.id, product_model_id=model.id)])
        with pytest.raises(AppException) as mismatch:
            await create_rfq(session, payload, ip="198.51.100.8", user_agent="test")
        assert mismatch.value.code == "product_model_mismatch"

        first = RFQ(public_reference="RFQ-20260904-ONE001", company_name="One", contact_name="Lee", email="one@example.com", consent_privacy=True)
        second = RFQ(public_reference="RFQ-20260904-TWO002", company_name="Two", contact_name="Li", email="two@example.com", consent_privacy=True)
        session.add_all([first, second])
        await session.flush()
        foreign_item = RFQItem(rfq_id=second.id, item_type="custom")
        session.add(foreign_item)
        await session.flush()
        with pytest.raises(AppException) as item_mismatch:
            await add_private_file(session, first, "spec.pdf", "application/pdf", b"%PDF-valid", "pdf", foreign_item.id, None, storage=_FakeMinioClient())
        assert item_mismatch.value.code == "rfq_item_mismatch"


async def test_malware_scan_results_follow_fail_closed_state_machine(remediation_factory) -> None:
    """扫描 clean 才 ready，infected/failed 必须 quarantined。"""
    from app.modules.media.scanner import apply_scan_result

    async with remediation_factory() as session, session.begin():
        asset = MediaAsset(visibility="private", media_type="cad", storage_bucket="private-rfq", storage_key="rfq/a.step", original_filename="a.step", sanitized_filename="a.step", mime_type="application/step", file_extension=".step", file_size_bytes=20, sha256="a" * 64, checksum_verified=True, malware_scan_status="pending", upload_status="pending")
        session.add(asset)
        await session.flush()
        await apply_scan_result(session, asset.id, "clean")
        assert asset.malware_scan_status == "clean" and asset.upload_status == "ready"
        asset.malware_scan_status, asset.upload_status = "pending", "pending"
        await apply_scan_result(session, asset.id, "infected")
        assert asset.malware_scan_status == "infected" and asset.upload_status == "quarantined"
        asset.malware_scan_status, asset.upload_status = "pending", "pending"
        await apply_scan_result(session, asset.id, "failed")
        assert asset.malware_scan_status == "failed" and asset.upload_status == "quarantined"


async def test_published_trust_edit_invalidates_and_slug_rules(remediation_factory) -> None:
    """已发布 Trust 正文编辑撤回公开状态；published slug 冻结，draft slug 同步 Route。"""
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import create_trust_entity, update_trust_entity

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        entity = await create_trust_entity(session, "capabilities", TrustEntityInput(slug="machining", fields={"capability_type": "machining"}, translations=[TrustTranslation(locale_id=locale.id, fields={"name": "Machining", "description": "Original"})]), None)
        publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == entity.id))
        status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_id == entity.id))
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == entity.id))
        publication.status = "published"
        status.status = "published"
        route.active = True
        route.indexable = True
        with pytest.raises(AppException) as raised:
            await update_trust_entity(session, "capabilities", entity.id, TrustEntityInput(slug="new-machining"), None)
        assert raised.value.code == "published_slug_frozen"
        await update_trust_entity(session, "capabilities", entity.id, TrustEntityInput(slug="machining", translations=[TrustTranslation(locale_id=locale.id, fields={"name": "Machining", "description": "Changed"})]), None)
        assert status.status == "draft" and publication.status == "review"
        assert route.active is False and route.indexable is False
        revision = await session.scalar(select(ContentRevision).where(ContentRevision.owner_id == entity.id).order_by(ContentRevision.revision_no.desc()))
        assert revision is not None and revision.snapshot_jsonb["translation"]["description"] == "Changed"
        publication.status = "draft"
        await update_trust_entity(session, "capabilities", entity.id, TrustEntityInput(slug="precision-machining"), None)
        assert route.path == "/en/capabilities/precision-machining/"


async def test_disabled_trust_archives_and_reenable_does_not_publish(remediation_factory) -> None:
    """disabled/retired Trust 退出索引，重新 enabled 不自动发布。"""
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import create_trust_entity, update_trust_entity

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        entity = await create_trust_entity(session, "exhibitions", TrustEntityInput(slug="show-2026", fields={"event_name": "Show"}, translations=[TrustTranslation(locale_id=locale.id, fields={"title": "Show"})]), None)
        publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == entity.id))
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == entity.id))
        publication.status = "published"
        route.active = True
        route.indexable = True
        await update_trust_entity(session, "exhibitions", entity.id, TrustEntityInput(slug="show-2026", status="disabled"), None)
        assert publication.status == "archived" and route.active is False and route.indexable is False
        await update_trust_entity(session, "exhibitions", entity.id, TrustEntityInput(slug="show-2026", status="enabled"), None)
        assert publication.status == "archived" and route.active is False


async def test_capability_geo_source_and_public_index_use_server_visible_published_data(remediation_factory) -> None:
    """能力 GEO 来源由真实正文构造，Trust 索引只返回满足统一发布门槛的条目。"""
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import create_trust_entity, list_public_trust
    from app.modules.discovery.services import build_visible_source_text

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        entity = await create_trust_entity(session, "capabilities", TrustEntityInput(slug="nitriding", fields={"capability_type": "surface-treatment"}, translations=[TrustTranslation(locale_id=locale.id, fields={"name": "Nitriding", "summary": "Wear resistance", "description": "Controlled surface hardening", "key_facts_json": ["Documented process window"]})]), None)
        visible = await build_visible_source_text(session, "manufacturing_capability", entity.id, locale.id)
        assert all(value in visible for value in ["Nitriding", "Wear resistance", "Documented process window"])
        assert await list_public_trust(session, "capabilities", "en") == []
        publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == entity.id, ContentPublication.locale_id == locale.id))
        status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_id == entity.id, TranslationStatus.locale_id == locale.id))
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == entity.id, ContentRoute.locale_id == locale.id))
        publication.status = "published"
        status.status = "published"
        route.active = True
        route.indexable = True
        listed = await list_public_trust(session, "capabilities", "en")
        assert listed == [{"type": "manufacturing_capability", "slug": "nitriding", "title": "Nitriding", "summary": "Wear resistance", "url": "/en/capabilities/nitriding/"}]
        entity.status = "disabled"
        await session.flush()
        assert await list_public_trust(session, "capabilities", "en") == []


async def test_company_profile_requires_full_publication_lifecycle(remediation_factory) -> None:
    """Company Profile 必须完成统一生命周期后才公开，修改后立即撤回。"""
    from app.modules.audit.models import AuditLog
    from app.modules.company.schemas import CompanyProfileInput, TrustTranslation
    from app.modules.company.services import get_public_company_profile, upsert_company_profile
    from app.modules.content.enums import PublicationStatus
    from app.modules.content.services.publication import transition_publication
    from app.modules.discovery.models import GeoDocument, SeoDocument
    from app.modules.discovery.services import build_visible_source_text

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        payload = CompanyProfileInput(
            founded_year=1985,
            translations=[
                TrustTranslation(
                    locale_id=locale.id,
                    fields={
                        "company_name": "浙江精汇",
                        "short_intro": "真实公司简介",
                        "full_intro": "面向全球客户的真实制造能力介绍",
                        "advantages_json": ["可核验制造能力"],
                    },
                )
            ],
        )
        profile = await upsert_company_profile(session, payload, None)
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "company_profile",
                ContentPublication.owner_id == profile.id,
                ContentPublication.locale_id == locale.id,
            )
        )
        status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "company_profile",
                TranslationStatus.owner_id == profile.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "company_profile",
                ContentRoute.owner_id == profile.id,
                ContentRoute.locale_id == locale.id,
            )
        )
        assert publication is not None and status is not None and route is not None
        assert route.path == "/zh-cn/about/" and route.active is False
        with pytest.raises(AppException) as draft_error:
            await get_public_company_profile(session, "zh-cn")
        assert draft_error.value.code == "public_content_not_found"

        status.status = "human_reviewed"
        await transition_publication(
            session,
            publication=publication,
            translation=status,
            route=route,
            target_status=PublicationStatus.REVIEW,
            actor_permissions={"content.review"},
            actor_id=None,
        )
        await transition_publication(
            session,
            publication=publication,
            translation=status,
            route=route,
            target_status=PublicationStatus.PUBLISHED,
            actor_permissions={"content.publish"},
            actor_id=None,
        )
        session.add_all(
            [
                SeoDocument(
                    owner_type="company_profile",
                    owner_id=profile.id,
                    locale_id=locale.id,
                    seo_title="关于精汇",
                    robots_index=True,
                ),
                GeoDocument(
                    owner_type="company_profile",
                    owner_id=profile.id,
                    locale_id=locale.id,
                    direct_answer="真实公司简介",
                ),
            ]
        )
        await session.flush()

        public = await get_public_company_profile(session, "zh-cn")
        assert public["seo"]["canonical"] == "https://junhuiscrewbarrel.com/zh-cn/about/"
        assert public["seo"]["hreflang"] == [
            {"hreflang": "zh-CN", "url": "https://junhuiscrewbarrel.com/zh-cn/about/"},
            {"hreflang": "x-default", "url": "https://junhuiscrewbarrel.com/zh-cn/about/"},
        ]
        assert public["geo"]["direct_answer"] == "真实公司简介"
        visible = await build_visible_source_text(session, "company_profile", profile.id, locale.id)
        assert "真实公司简介" in visible and "可核验制造能力" in visible
        from app.modules.content.services.indexable import list_indexable_routes

        assert route in await list_indexable_routes(session)

        changed = payload.model_copy(deep=True)
        changed.translations[0].fields["short_intro"] = "已修改、待重新审核的简介"
        await upsert_company_profile(session, changed, None)
        assert status.status == "draft" and publication.status == "review"
        assert route.active is False and route.indexable is False
        assert await session.scalar(
            select(ContentRevision.id).where(
                ContentRevision.owner_type == "company_profile",
                ContentRevision.owner_id == profile.id,
            )
        ) is not None
        assert await session.scalar(
            select(AuditLog.id).where(
                AuditLog.target_type == "company_profile",
                AuditLog.target_id == str(profile.id),
            )
        ) is not None


async def test_trust_review_publish_archive_api_reuses_publication_transaction(
    remediation_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trust API 必须形成 review→published→archived 的真实统一状态闭环。"""
    from app.api.v1 import trust as trust_api
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import create_trust_entity

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        entity = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug="api-publication",
                fields={"capability_type": "machining"},
                translations=[
                    TrustTranslation(locale_id=locale.id, fields={"name": "API publication"})
                ],
            ),
            None,
        )
        await session.commit()
        actor = SimpleNamespace(id=uuid.uuid4())
        permissions = {
            "translation.review",
            "translation.publish",
            "content.review",
            "content.publish",
            "content.archive",
        }
        monkeypatch.setattr(trust_api, "collect_authorization", lambda _user: (set(), permissions))

        reviewed = await trust_api.review_trust_translation(
            "capabilities", entity.id, locale.id, session, actor, None
        )
        assert reviewed.data == {"status": "human_reviewed", "publication": "review"}
        published = await trust_api.transition_trust_publication(
            "capabilities",
            entity.id,
            locale.id,
            trust_api.PublicationStatus.PUBLISHED,
            session,
            actor,
            None,
        )
        assert published.data == {"status": "published"}
        archived = await trust_api.transition_trust_publication(
            "capabilities",
            entity.id,
            locale.id,
            trust_api.PublicationStatus.ARCHIVED,
            session,
            actor,
            None,
        )
        assert archived.data == {"status": "archived"}
        publication = await session.scalar(
            select(ContentPublication).where(ContentPublication.owner_id == entity.id)
        )
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == entity.id))
        assert publication.status == "archived"
        assert route.active is False and route.indexable is False


async def test_trust_hreflang_uses_strict_self_canonical_alternates(remediation_factory) -> None:
    """Trust hreflang 必须保留 self-canonical，并排除 noindex 或非 self-canonical 语言。"""
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import (
        create_trust_entity,
        get_public_trust,
        list_public_trust,
    )
    from app.modules.discovery.models import SeoDocument

    async with remediation_factory() as session, session.begin():
        locales = {
            locale.code: locale
            for locale in (
                await session.scalars(select(Locale).order_by(Locale.sort_order))
            ).all()
        }
        entity = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug="strict-hreflang",
                fields={"capability_type": "machining"},
                translations=[
                    TrustTranslation(locale_id=locales["zh-CN"].id, fields={"name": "精密加工"}),
                    TrustTranslation(locale_id=locales["en"].id, fields={"name": "Precision machining"}),
                ],
            ),
            None,
        )
        for locale in locales.values():
            publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == entity.id, ContentPublication.locale_id == locale.id))
            status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_id == entity.id, TranslationStatus.locale_id == locale.id))
            route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == entity.id, ContentRoute.locale_id == locale.id))
            publication.status = "published"
            status.status = "published"
            route.active = True
            route.indexable = True
        session.add_all(
            [
                SeoDocument(
                    owner_type="manufacturing_capability",
                    owner_id=entity.id,
                    locale_id=locales["zh-CN"].id,
                    canonical_override="https://junhuiscrewbarrel.com/zh-cn/capabilities/strict-hreflang/",
                    robots_index=True,
                ),
                SeoDocument(
                    owner_type="manufacturing_capability",
                    owner_id=entity.id,
                    locale_id=locales["en"].id,
                    robots_index=False,
                ),
            ]
        )
        await session.flush()
        public = await get_public_trust(session, "manufacturing_capability", "zh-cn", "strict-hreflang")
        assert public["seo"]["hreflang"] == [
            {
                "hreflang": "zh-CN",
                "url": "https://junhuiscrewbarrel.com/zh-cn/capabilities/strict-hreflang/",
            },
            {
                "hreflang": "x-default",
                "url": "https://junhuiscrewbarrel.com/zh-cn/capabilities/strict-hreflang/",
            },
        ]
        assert [
            item["slug"]
            for item in await list_public_trust(session, "capabilities", "zh-cn")
        ] == ["strict-hreflang"]
        assert await list_public_trust(session, "capabilities", "en") == []
        with pytest.raises(AppException) as noindex_error:
            await get_public_trust(
                session,
                "manufacturing_capability",
                "en",
                "strict-hreflang",
            )
        assert noindex_error.value.status_code == 404
        en_seo = await session.scalar(
            select(SeoDocument).where(
                SeoDocument.owner_id == entity.id,
                SeoDocument.locale_id == locales["en"].id,
            )
        )
        en_seo.robots_index = True
        en_seo.canonical_override = "https://junhuiscrewbarrel.com/en/capabilities/another/"
        await session.flush()
        assert await list_public_trust(session, "capabilities", "en") == []
        with pytest.raises(AppException) as noncanonical_error:
            await get_public_trust(
                session,
                "manufacturing_capability",
                "en",
                "strict-hreflang",
            )
        assert noncanonical_error.value.status_code == 404


async def test_public_downloads_filter_missing_objects_and_report_broken_media(remediation_factory) -> None:
    """数据库为 ready 但对象缺失的下载不得公开，并应进入 broken-media 报告。"""
    from app.modules.media.models import DownloadResource, DownloadResourceTranslation
    from app.modules.media.services import list_broken_public_downloads, list_public_downloads

    class MissingStorage:
        async def object_exists(self, bucket: str, key: str) -> bool:
            return key == "downloads/present.pdf"

    async with remediation_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assets = [
            MediaAsset(
                visibility="public",
                media_type="document",
                storage_bucket="public-media",
                storage_key=key,
                original_filename=key.rsplit("/", 1)[-1],
                sanitized_filename=key.rsplit("/", 1)[-1],
                mime_type="application/pdf",
                file_extension=".pdf",
                file_size_bytes=12,
                sha256=marker * 64,
                checksum_verified=True,
                malware_scan_status="not_required",
                upload_status="ready",
            )
            for key, marker in (("downloads/present.pdf", "a"), ("downloads/missing.pdf", "b"))
        ]
        session.add_all(assets)
        await session.flush()
        for index, asset in enumerate(assets):
            resource = DownloadResource(
                slug=f"download-{index}",
                resource_type="document",
                status="enabled",
                media_asset_id=asset.id,
            )
            session.add(resource)
            await session.flush()
            session.add(
                DownloadResourceTranslation(
                    download_resource_id=resource.id,
                    locale_id=locale.id,
                    title=f"Download {index}",
                )
            )
        await session.flush()

        public = await list_public_downloads(session, "en", storage=MissingStorage())
        broken = await list_broken_public_downloads(session, storage=MissingStorage())
        assert [item["slug"] for item in public] == ["download-0"]
        assert broken == [
            {
                "asset_id": str(assets[1].id),
                "download_slug": "download-1",
                "storage_bucket": "public-media",
                "storage_key": "downloads/missing.pdf",
                "reason": "object_missing",
            }
        ]


async def test_public_trust_page_metadata_is_backend_owned(remediation_factory) -> None:
    """Trust 聚合页 SEO、canonical、hreflang 与 Schema 必须由后端统一生成。"""
    from app.modules.company.services import get_public_page_metadata

    async with remediation_factory() as session:
        metadata = await get_public_page_metadata(session, "capabilities", "en")

    assert metadata["seo"]["canonical"] == "https://junhuiscrewbarrel.com/en/capabilities/"
    assert metadata["seo"]["robots"] == "index, follow"
    assert metadata["seo"]["hreflang"]["zh-CN"].endswith("/zh-cn/capabilities/")
    assert metadata["breadcrumb"][-1]["url"] == metadata["seo"]["canonical"]
    assert [item["@type"] for item in metadata["schema"]] == ["WebPage", "BreadcrumbList"]


def test_minio_internal_and_public_transport_security_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """内部 MinIO 与浏览器签名端点必须分别控制 TLS，生产外部端点强制 HTTPS。"""
    from pydantic import ValidationError

    from app.core.config import get_settings
    from app.core.config.settings import Settings
    from app.modules.media import storage as storage_module

    created: list[tuple[str, bool]] = []

    class FakeClient:
        def __init__(self, endpoint: str, **kwargs) -> None:
            created.append((endpoint, kwargs["secure"]))

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MINIO_ENDPOINT", "internal.example:9000")
    monkeypatch.setenv("MINIO_PUBLIC_ENDPOINT", "public.example:9000")
    monkeypatch.setenv("MINIO_INTERNAL_SECURE", "true")
    monkeypatch.setenv("MINIO_PUBLIC_SECURE", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(storage_module, "Minio", FakeClient)
    storage_module.MinioStorageAdapter()
    assert created == [("internal.example:9000", True), ("public.example:9000", False)]

    secure_values = {
        "app_env": "production",
        "database_url": "postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
        "minio_secret_key": "strong-minio-secret-at-least-32-bytes",
        "minio_public_endpoint": "storage.junhuiscrewbarrel.com",
        "jwt_signing_secret": "strong-jwt-signing-secret-at-least-32-bytes",
        "refresh_token_secret": "strong-refresh-token-secret-at-least-32-bytes",
        "cors_allowed_origins": ["https://junhuiscrewbarrel.com"],
        "_env_file": None,
    }
    with pytest.raises(ValidationError):
        Settings(**secure_values, minio_public_secure=False)
    assert Settings(**secure_values, minio_public_secure=True).minio_public_secure is True


async def test_production_rejects_http_private_presigned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """SDK 即使异常返回 HTTP，生产私有下载也必须 fail-closed。"""
    from app.core.config import get_settings
    from app.modules.media.storage import MinioStorageAdapter

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui")
    monkeypatch.setenv("MINIO_SECRET_KEY", "strong-minio-secret-at-least-32-bytes")
    monkeypatch.setenv("MINIO_PUBLIC_ENDPOINT", "storage.junhuiscrewbarrel.com")
    monkeypatch.setenv("MINIO_PUBLIC_SECURE", "true")
    monkeypatch.setenv("JWT_SIGNING_SECRET", "strong-jwt-signing-secret-at-least-32-bytes")
    monkeypatch.setenv("REFRESH_TOKEN_SECRET", "strong-refresh-token-secret-at-least-32-bytes")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://junhuiscrewbarrel.com"]')
    get_settings.cache_clear()
    fake = _FakeMinioClient()
    adapter = MinioStorageAdapter(client=fake, public_client=fake)
    with pytest.raises(AppException) as raised:
        await adapter.presigned_get("private-rfq", "rfq/unsafe.pdf")
    assert raised.value.code == "insecure_presigned_url"


async def test_certificate_translation_review_publish_controls_public_aggregate(
    remediation_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证书必须按 draft→human_reviewed→published 流程进入公开聚合页，且不创建独立路由。"""
    from app.api.v1 import trust as trust_api
    from app.core.pagination import PaginationParams
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import (
        create_trust_entity,
        list_public_trust,
        update_trust_entity,
    )

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        certificate = await create_trust_entity(
            session,
            "certificates",
            TrustEntityInput(
                slug="iso-9001",
                fields={"certificate_type": "quality", "issuer": "Accredited body"},
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={"name": "ISO 9001", "summary": "Quality management"},
                    )
                ],
            ),
            None,
        )
        await session.commit()
        actor = SimpleNamespace(id=uuid.uuid4())
        monkeypatch.setattr(
            trust_api,
            "collect_authorization",
            lambda _user: (
                set(),
                {"certificate.read", "translation.review", "translation.publish"},
            ),
        )

        assert await list_public_trust(session, "certificates", "en") == []
        reviewed = await trust_api.review_trust_translation(
            "certificates", certificate.id, locale.id, session, actor, None
        )
        assert reviewed.data == {"status": "human_reviewed"}
        assert await list_public_trust(session, "certificates", "en") == []

        published = await trust_api.publish_trust_translation(
            "certificates", certificate.id, locale.id, session, actor, None
        )
        assert published.data == {"status": "published"}
        assert [item["slug"] for item in await list_public_trust(session, "certificates", "en")] == [
            "iso-9001"
        ]
        admin_list = await trust_api.list_trust(
            "certificates",
            PaginationParams(page=1, page_size=20),
            session,
            actor,
        )
        assert admin_list.data["items"][0]["translation_statuses"][0]["status"] == "published"
        assert admin_list.data["items"][0]["publications"] == []
        assert admin_list.data["items"][0]["routes"] == []
        assert await session.scalar(
            select(ContentPublication.id).where(
                ContentPublication.owner_type == "certificate",
                ContentPublication.owner_id == certificate.id,
            )
        ) is None
        assert await session.scalar(
            select(ContentRoute.id).where(
                ContentRoute.owner_type == "certificate",
                ContentRoute.owner_id == certificate.id,
            )
        ) is None

        await update_trust_entity(
            session,
            "certificates",
            certificate.id,
            TrustEntityInput(slug="iso-9001", status="disabled"),
            actor.id,
        )
        await session.commit()
        assert await list_public_trust(session, "certificates", "en") == []
        await update_trust_entity(
            session,
            "certificates",
            certificate.id,
            TrustEntityInput(slug="iso-9001", status="enabled"),
            actor.id,
        )
        await session.commit()
        assert await list_public_trust(session, "certificates", "en") == []


@pytest.mark.parametrize(
    ("resource", "owner_type", "slug", "title"),
    [
        ("patents", "patent", "patent-a", "Fastener patent"),
        ("honors", "honor", "honor-a", "Manufacturing honor"),
    ],
)
async def test_published_non_route_translation_edit_returns_to_draft_and_disappears(
    remediation_factory,
    monkeypatch: pytest.MonkeyPatch,
    resource: str,
    owner_type: str,
    slug: str,
    title: str,
) -> None:
    """已发布专利或荣誉翻译再次编辑后必须回到 draft，并立即退出公开聚合页。"""
    from app.api.v1 import trust as trust_api
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import (
        create_trust_entity,
        list_public_trust,
        update_trust_entity,
    )

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        entity = await create_trust_entity(
            session,
            resource,
            TrustEntityInput(
                slug=slug,
                translations=[TrustTranslation(locale_id=locale.id, fields={"title": title})],
            ),
            None,
        )
        await session.commit()
        actor = SimpleNamespace(id=uuid.uuid4())
        monkeypatch.setattr(
            trust_api,
            "collect_authorization",
            lambda _user: (set(), {"translation.review", "translation.publish"}),
        )
        await trust_api.review_trust_translation(
            resource, entity.id, locale.id, session, actor, None
        )
        await trust_api.publish_trust_translation(
            resource, entity.id, locale.id, session, actor, None
        )
        assert [item["slug"] for item in await list_public_trust(session, resource, "en")] == [
            slug
        ]

        await update_trust_entity(
            session,
            resource,
            entity.id,
            TrustEntityInput(
                slug=slug,
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={"title": f"{title} revised"},
                    )
                ],
            ),
            actor.id,
        )
        await session.commit()
        status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == owner_type,
                TranslationStatus.owner_id == entity.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        assert status.status == "draft"
        assert status.reviewed_by is None and status.published_at is None
        assert await list_public_trust(session, resource, "en") == []
        assert len(
            list(
                await session.scalars(
                    select(ContentRevision.id).where(
                        ContentRevision.owner_type == owner_type,
                        ContentRevision.owner_id == entity.id,
                    )
                )
            )
        ) >= 2


async def test_capability_only_exposes_equipment_with_published_translation(
    remediation_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """能力公开 DTO 只能嵌入已发布且 enabled 的设备翻译。"""
    from app.api.v1 import trust as trust_api
    from app.modules.authority.models import (
        CaseProduct,
        CaseStudy,
        CaseStudyTranslation,
        CaseTechnology,
    )
    from app.modules.catalog.models import (
        Product,
        ProductCategory,
        ProductTechnology,
        ProductTranslation,
        Technology,
        TechnologyTranslation,
    )
    from app.modules.company.models import CapabilityEquipment, TechnologyEquipment
    from app.modules.company.schemas import TrustEntityInput, TrustTranslation
    from app.modules.company.services import (
        create_trust_entity,
        get_public_trust,
        update_trust_entity,
    )
    from app.modules.discovery.models import SeoDocument

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        capability = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug="turning",
                fields={"capability_type": "machining"},
                translations=[TrustTranslation(locale_id=locale.id, fields={"name": "Turning"})],
            ),
            None,
        )
        equipment = await create_trust_entity(
            session,
            "equipment",
            TrustEntityInput(
                slug="cnc-lathe",
                fields={"equipment_type": "lathe", "manufacturer": "Verified maker"},
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={"name": "CNC lathe", "summary": "Precision turning"},
                    )
                ],
            ),
            None,
        )
        session.add(
            CapabilityEquipment(
                capability_id=capability.id,
                equipment_id=equipment.id,
                sort_order=10,
            )
        )
        capability_publication = await session.scalar(
            select(ContentPublication).where(ContentPublication.owner_id == capability.id)
        )
        capability_status = await session.scalar(
            select(TranslationStatus).where(TranslationStatus.owner_id == capability.id)
        )
        capability_route = await session.scalar(
            select(ContentRoute).where(ContentRoute.owner_id == capability.id)
        )
        capability_publication.status = "published"
        capability_status.status = "published"
        capability_route.active = True
        capability_route.indexable = True
        await session.commit()

        draft_public = await get_public_trust(
            session, "manufacturing_capability", "en", "turning"
        )
        assert draft_public["equipment"] == []

        actor = SimpleNamespace(id=uuid.uuid4())
        monkeypatch.setattr(
            trust_api,
            "collect_authorization",
            lambda _user: (set(), {"translation.review", "translation.publish"}),
        )
        await trust_api.review_trust_translation(
            "equipment", equipment.id, locale.id, session, actor, None
        )
        await trust_api.publish_trust_translation(
            "equipment", equipment.id, locale.id, session, actor, None
        )
        category = ProductCategory(slug="relation-components")
        technology = Technology(slug="published-turning")
        hidden_technology = Technology(slug="hidden-turning")
        session.add_all([category, technology, hidden_technology])
        await session.flush()
        product = Product(slug="related-product", category_id=category.id)
        case_study = CaseStudy(slug="related-case")
        session.add_all([product, case_study])
        await session.flush()
        session.add_all(
            [
                TechnologyTranslation(
                    technology_id=technology.id,
                    locale_id=locale.id,
                    name="Published turning",
                ),
                TechnologyTranslation(
                    technology_id=hidden_technology.id,
                    locale_id=locale.id,
                    name="Hidden turning",
                ),
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Related product",
                ),
                CaseStudyTranslation(
                    case_study_id=case_study.id,
                    locale_id=locale.id,
                    title="Related case",
                ),
                TechnologyEquipment(
                    technology_id=technology.id,
                    equipment_id=equipment.id,
                    sort_order=10,
                ),
                TechnologyEquipment(
                    technology_id=hidden_technology.id,
                    equipment_id=equipment.id,
                    sort_order=20,
                ),
                ProductTechnology(product_id=product.id, technology_id=technology.id),
                CaseTechnology(case_study_id=case_study.id, technology_id=technology.id),
                CaseProduct(case_study_id=case_study.id, product_id=product.id),
            ]
        )
        for owner_type, owner_id, path, robots_index in (
            (
                "technology",
                technology.id,
                "/en/technologies/published-turning/",
                True,
            ),
            (
                "technology",
                hidden_technology.id,
                "/en/technologies/hidden-turning/",
                False,
            ),
            ("product", product.id, "/en/products/relation-components/related-product/", True),
            ("case_study", case_study.id, "/en/case-studies/related-case/", True),
        ):
            session.add_all(
                [
                    TranslationStatus(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        source_locale_id=locale.id,
                        status="published",
                    ),
                    ContentPublication(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        status="published",
                    ),
                    ContentRoute(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        path=path,
                        is_canonical=True,
                        active=True,
                        indexable=True,
                    ),
                    SeoDocument(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        robots_index=robots_index,
                    ),
                ]
            )
        await session.commit()
        published_public = await get_public_trust(
            session, "manufacturing_capability", "en", "turning"
        )
        # Phase 3.6 公开详情所需的展示字段必须由后端统一批准，前端不得重建。
        assert published_public["breadcrumb"] == [
            {"name": "Home", "url": "https://junhuiscrewbarrel.com/en/"},
            {
                "name": "Capabilities",
                "url": "https://junhuiscrewbarrel.com/en/capabilities/",
            },
            {
                "name": "Turning",
                "url": "https://junhuiscrewbarrel.com/en/capabilities/turning/",
            },
        ]
        assert published_public["relations"] == {
            "technologies": [
                {
                    "type": "technology",
                    "slug": "published-turning",
                    "name": "Published turning",
                    "url": "/en/technologies/published-turning/",
                    "summary": "",
                }
            ],
            "products": [
                {
                    "type": "product",
                    "slug": "related-product",
                    "name": "Related product",
                    "url": "/en/products/relation-components/related-product/",
                    "summary": "",
                }
            ],
            "cases": [
                {
                    "type": "case_study",
                    "slug": "related-case",
                    "name": "Related case",
                    "url": "/en/case-studies/related-case/",
                    "summary": "",
                }
            ],
        }
        assert published_public["primary_media"] is None
        assert published_public["equipment"] == [
            {
                "slug": "cnc-lathe",
                "equipment_type": "lathe",
                "manufacturer": "Verified maker",
                "model": None,
                "quantity": None,
                "commissioning_year": None,
                "precision_text": None,
                "capacity_text": None,
                "featured": False,
                "translation": {
                    "name": "CNC lathe",
                    "summary": "Precision turning",
                    "description": None,
                    "public_specs_json": None,
                },
            }
        ]

        await update_trust_entity(
            session,
            "equipment",
            equipment.id,
            TrustEntityInput(
                slug="cnc-lathe",
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={"name": "CNC lathe revised"},
                    )
                ],
            ),
            actor.id,
        )
        await session.commit()
        withdrawn_public = await get_public_trust(
            session, "manufacturing_capability", "en", "turning"
        )
        assert withdrawn_public["equipment"] == []
        assert withdrawn_public["relations"] == {
            "technologies": [],
            "products": [],
            "cases": [],
        }


async def test_reviewer_can_review_trust_and_company_without_update_permissions(
    remediation_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer 仅凭 translation/content review 权限即可审核 Trust 与 Company。"""
    from app.api.v1 import trust as trust_api
    from app.modules.company.schemas import (
        CompanyProfileInput,
        TrustEntityInput,
        TrustTranslation,
    )
    from app.modules.company.services import create_trust_entity, upsert_company_profile

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        capability = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug="reviewer-capability",
                fields={"capability_type": "machining"},
                translations=[
                    TrustTranslation(locale_id=locale.id, fields={"name": "Reviewer capability"})
                ],
            ),
            None,
        )
        profile = await upsert_company_profile(
            session,
            CompanyProfileInput(
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={
                            "company_name": "Junhui",
                            "short_intro": "Verified manufacturer",
                            "full_intro": "Verified manufacturer profile",
                        },
                    )
                ]
            ),
            None,
        )
        await session.commit()
        reviewer = SimpleNamespace(id=uuid.uuid4())
        reviewer_permissions = {
            "translation.review",
            "content.review",
            "translation.publish",
            "content.publish",
        }
        monkeypatch.setattr(
            trust_api,
            "collect_authorization",
            lambda _user: (set(), reviewer_permissions),
        )

        trust_reviewed = await trust_api.review_trust_translation(
            "capabilities", capability.id, locale.id, session, reviewer, None
        )
        company_reviewed = await trust_api.review_company_profile_translation(
            profile.id, locale.id, session, reviewer, None
        )
        assert trust_reviewed.data["status"] == "human_reviewed"
        assert company_reviewed.data["status"] == "human_reviewed"

        published = await trust_api.transition_trust_publication(
            "capabilities",
            capability.id,
            locale.id,
            trust_api.PublicationStatus.PUBLISHED,
            session,
            reviewer,
            None,
        )
        assert published.data == {"status": "published"}
        company_published = await trust_api.transition_company_profile_publication(
            profile.id,
            locale.id,
            trust_api.PublicationStatus.PUBLISHED,
            session,
            reviewer,
            None,
        )
        assert company_published.data == {"status": "published"}


async def test_editor_update_permissions_cannot_review_or_publish(
    remediation_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor 的实体 update/content update 权限不得隐式授予 Review 或 Publish。"""
    from app.api.v1 import trust as trust_api
    from app.modules.company.schemas import (
        CompanyProfileInput,
        TrustEntityInput,
        TrustTranslation,
    )
    from app.modules.company.services import create_trust_entity, upsert_company_profile

    async with remediation_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        capability = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug="editor-forbidden",
                fields={"capability_type": "machining"},
                translations=[
                    TrustTranslation(locale_id=locale.id, fields={"name": "Editor forbidden"})
                ],
            ),
            None,
        )
        certificate = await create_trust_entity(
            session,
            "certificates",
            TrustEntityInput(
                slug="editor-certificate",
                translations=[
                    TrustTranslation(locale_id=locale.id, fields={"name": "Editor certificate"})
                ],
            ),
            None,
        )
        certificate_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "certificate",
                TranslationStatus.owner_id == certificate.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        certificate_status.status = "human_reviewed"
        profile = await upsert_company_profile(
            session,
            CompanyProfileInput(
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={
                            "company_name": "Editor forbidden company",
                            "short_intro": "Draft company profile",
                            "full_intro": "Draft company profile for permission validation",
                        },
                    )
                ]
            ),
            None,
        )
        profile_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "company_profile",
                TranslationStatus.owner_id == profile.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        profile_publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "company_profile",
                ContentPublication.owner_id == profile.id,
                ContentPublication.locale_id == locale.id,
            )
        )
        profile_status.status = "human_reviewed"
        profile_publication.status = "review"
        await session.commit()
        editor = SimpleNamespace(id=uuid.uuid4())
        editor_permissions = {
            "capability.update",
            "certificate.update",
            "content.update",
        }
        monkeypatch.setattr(
            trust_api,
            "collect_authorization",
            lambda _user: (set(), editor_permissions),
        )

        with pytest.raises(AppException) as review_error:
            await trust_api.review_trust_translation(
                "capabilities", capability.id, locale.id, session, editor, None
            )
        assert review_error.value.status_code == 403
        with pytest.raises(AppException) as publish_error:
            await trust_api.publish_trust_translation(
                "certificates", certificate.id, locale.id, session, editor, None
            )
        assert publish_error.value.status_code == 403
        with pytest.raises(AppException) as company_review_error:
            await trust_api.review_company_profile_translation(
                profile.id, locale.id, session, editor, None
            )
        assert company_review_error.value.status_code == 403
        with pytest.raises(AppException) as company_publish_error:
            await trust_api.transition_company_profile_publication(
                profile.id,
                locale.id,
                trust_api.PublicationStatus.PUBLISHED,
                session,
                editor,
                None,
            )
        assert company_publish_error.value.status_code == 403


def test_reviewer_seed_has_trust_read_but_no_update_permissions() -> None:
    """Reviewer 可读取审核目标，但不会得到 Company/Trust 更新权限。"""
    from app.seed import ROLE_PERMISSION_MATRIX

    reviewer = ROLE_PERMISSION_MATRIX["reviewer"]
    for permission in (
        "company.read",
        "capability.read",
        "equipment.read",
        "certificate.read",
        "patent.read",
        "honor.read",
        "exhibition.read",
    ):
        assert permission in reviewer
    assert not any(
        permission in reviewer
        for permission in (
            "company.update",
            "capability.update",
            "equipment.update",
            "certificate.update",
            "patent.update",
            "honor.update",
            "exhibition.update",
        )
    )
