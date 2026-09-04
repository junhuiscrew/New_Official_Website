"""Phase 3.5 Remediation 的存储、RFQ 安全、扫描与 Trust 生命周期回归测试。"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1 import api_v1_router as _api_v1_router  # noqa: F401, E402
from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.catalog.models import Product, ProductCategory, ProductModel
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
        payload = RFQCreate(company_name="ACME", contact_name="Lee", email="lee@example.com", consent_privacy=True, items=[RFQItemInput(product_id=product.id, product_model_id=model.id)])
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
