"""RFQ 创建、来源校验、状态流转、附件扫描与私有签名服务。"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import jwt
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.catalog.models import Product, ProductModel
from app.modules.media.models import MediaAsset
from app.modules.media.scanner import apply_scan_result
from app.modules.media.services import validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter, private_url_expiry
from app.modules.rfq.models import RFQ, RFQFile, RFQItem
from app.modules.rfq.schemas import RFQCreate

_TRANSITIONS = {
    "new": {"qualified", "spam"}, "qualified": {"in_progress", "spam"},
    "in_progress": {"waiting_customer", "quoted", "spam"},
    "waiting_customer": {"in_progress", "quoted", "spam"},
    "quoted": {"won", "lost"}, "won": {"closed"}, "lost": {"closed"}, "spam": {"closed"}, "closed": set(),
}


async def enforce_public_rate_limit(ip: str | None) -> None:
    """
    使用 Redis 对匿名 RFQ 按 IP 执行小时/日双窗口限流。

    输入：
        ip: str | None，客户端 IP；缺失时跳过计数但不绕过其他校验。
    输出：None；超过任一窗口时抛出 429 业务异常。
    """
    if not ip:
        return
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        hour_key = f"rfq:public:{ip}:hour:{datetime.now(UTC):%Y%m%d%H}"
        day_key = f"rfq:public:{ip}:day:{datetime.now(UTC):%Y%m%d}"
        hour_count = await client.incr(hour_key)
        day_count = await client.incr(day_key)
        if hour_count == 1:
            await client.expire(hour_key, 3600)
        if day_count == 1:
            await client.expire(day_key, 86400)
        if hour_count > settings.rfq_rate_limit_per_hour or day_count > settings.rfq_rate_limit_per_day:
            raise AppException(429, "rfq_rate_limited", "提交频率超过限制，请稍后再试")
    except AppException:
        raise
    except Exception as exc:
        # 本地测试/开发允许 Redis 暂时不可用；生产必须 fail-closed，避免限流失效。
        if settings.app_env == "production":
            raise AppException(503, "rfq_rate_limit_unavailable", "提交服务暂时不可用") from exc
    finally:
        await client.aclose()


def generate_public_reference() -> str:
    """生成不可简单预测且便于人工沟通的询盘编号。"""
    return f"RFQ-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(3).upper()}"


def validate_public_origin(request: Request) -> None:
    """
    精确校验匿名 RFQ 的 Origin/Referer scheme、hostname 与 port。

    输入：request，匿名表单请求。
    输出：None；不匹配当前环境允许 Origin 时抛出 403。
    """
    settings = get_settings()
    raw_origin = request.headers.get("origin") or request.headers.get("referer")
    if not raw_origin:
        if settings.app_env == "production":
            raise AppException(403, "origin_not_allowed", "生产环境提交必须包含 Origin 或 Referer")
        return
    parsed = urlparse(raw_origin)
    actual = (parsed.scheme.lower(), (parsed.hostname or "").lower().rstrip("."), parsed.port)
    allowed: set[tuple[str, str, int | None]] = set()
    for value in settings.cors_allowed_origins:
        candidate = urlparse(value)
        allowed.add((candidate.scheme.lower(), (candidate.hostname or "").lower().rstrip("."), candidate.port))
    if actual not in allowed:
        raise AppException(403, "origin_not_allowed", "提交来源不受信任")


def create_submission_token(rfq: RFQ) -> str:
    """输入 RFQ；输出仅允许该匿名提交者短期上传附件的 JWT。"""
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": rfq.public_reference,
            "type": "rfq_submission",
            "iat": now,
            "exp": now + timedelta(minutes=settings.rfq_submission_token_ttl_minutes),
        },
        settings.jwt_signing_secret,
        algorithm="HS256",
    )


def verify_submission_token(token: str, public_reference: str) -> bool:
    """输入令牌和公开编号；输出 bool，仅签名、类型、期限和归属均正确时为真。"""
    try:
        payload = jwt.decode(token, get_settings().jwt_signing_secret, algorithms=["HS256"])
        return payload.get("type") == "rfq_submission" and payload.get("sub") == public_reference
    except jwt.PyJWTError:
        return False


async def validate_source(session: AsyncSession, payload: RFQCreate) -> None:
    """验证来源 URL、owner 类型和真实实体，防止任意 UUID 注入。"""
    if not payload.source_owner_type and not payload.source_owner_id:
        return
    if payload.source_owner_type != "product" or payload.source_owner_id is None:
        raise AppException(422, "invalid_rfq_source", "询盘来源只能引用公开 Product")
    product = await session.get(Product, payload.source_owner_id)
    if product is None or product.status != "enabled":
        raise AppException(422, "invalid_rfq_source", "询盘来源产品不存在")
    if payload.source_page_url:
        parsed = urlparse(payload.source_page_url)
        if parsed.scheme != "https" or parsed.hostname != "junhuiscrewbarrel.com":
            raise AppException(422, "invalid_rfq_source", "询盘来源 URL 必须是正式主域")


async def create_rfq(session: AsyncSession, payload: RFQCreate, *, ip: str | None, user_agent: str | None) -> RFQ:
    """创建询盘及多项目记录，公开返回只使用 public_reference。"""
    await validate_source(session, payload)
    # 唯一索引是最终防线；先用有限重试避免极低概率的公开编号碰撞。
    public_reference = ""
    for _attempt in range(5):
        candidate = generate_public_reference()
        exists = await session.scalar(select(RFQ.id).where(RFQ.public_reference == candidate))
        if exists is None:
            public_reference = candidate
            break
    if not public_reference:
        raise AppException(503, "rfq_reference_unavailable", "暂时无法生成询盘编号")
    rfq = RFQ(public_reference=public_reference, company_name=payload.company_name.strip(), contact_name=payload.contact_name.strip(), email=str(payload.email).lower(), phone=payload.phone, whatsapp=payload.whatsapp, country_code=payload.country_code, website=payload.website, message=payload.message, preferred_language=payload.preferred_language, source_page_url=payload.source_page_url, source_owner_type=payload.source_owner_type, source_owner_id=payload.source_owner_id, submitted_ip=ip, user_agent=user_agent, consent_privacy=payload.consent_privacy, consent_marketing=payload.consent_marketing)
    session.add(rfq)
    await session.flush()
    for item in payload.items:
        if item.product_id and (await session.get(Product, item.product_id)) is None:
            raise AppException(422, "invalid_product", "询盘项目产品不存在")
        if item.product_model_id:
            product_model = await session.get(ProductModel, item.product_model_id)
            if product_model is None:
                raise AppException(422, "invalid_product_model", "询盘项目型号不存在")
            if item.product_id is None or product_model.product_id != item.product_id:
                raise AppException(422, "product_model_mismatch", "询盘型号不属于当前产品")
        session.add(RFQItem(rfq_id=rfq.id, **item.model_dump()))
    write_audit_log(session, action="rfq.submit", target_type="rfq", target_id=str(rfq.id), metadata={"item_count": len(payload.items)})
    return rfq


async def add_private_file(session: AsyncSession, rfq: RFQ, file_name: str, mime_type: str, content: bytes, category: str, item_id: uuid.UUID | None, actor_id: uuid.UUID | None, storage: MinioStorageAdapter | None = None) -> RFQFile:
    """校验并保存 RFQ 私有附件，生产未配置扫描器时进入 quarantine。"""
    settings = get_settings()
    current_files = list((await session.scalars(select(MediaAsset).join(RFQFile, RFQFile.media_asset_id == MediaAsset.id).where(RFQFile.rfq_id == rfq.id))).all())
    if len(current_files) >= settings.rfq_max_files:
        raise AppException(413, "rfq_file_count_exceeded", "询盘附件数量超过限制")
    current_total = sum(int(item.file_size_bytes) for item in current_files)
    if current_total + len(content) > settings.rfq_max_total_file_bytes:
        raise AppException(413, "rfq_total_files_too_large", "询盘附件总大小超过限制")
    metadata = validate_upload_bytes(file_name, mime_type, content, private=True)
    if item_id is not None:
        item = await session.scalar(select(RFQItem).where(RFQItem.id == item_id, RFQItem.rfq_id == rfq.id))
        if item is None:
            raise AppException(422, "rfq_item_mismatch", "附件项目不属于当前询盘")
    storage = storage or MinioStorageAdapter()
    storage_key = f"rfq/{rfq.id}/{uuid.uuid4()}/{metadata['sanitized_filename']}"
    await storage.put_object(settings.minio_private_bucket, storage_key, content, str(metadata["mime_type"]))
    asset = MediaAsset(visibility="private", storage_bucket=settings.minio_private_bucket, storage_key=storage_key, checksum_verified=True, malware_scan_status="pending", upload_status="pending", uploaded_by=actor_id, **metadata)
    session.add(asset)
    try:
        await session.flush()
    except Exception:
        await storage.delete_object(settings.minio_private_bucket, storage_key)
        raise
    record = RFQFile(rfq_id=rfq.id, rfq_item_id=item_id, media_asset_id=asset.id, file_category=category, original_filename=file_name, sha256=metadata["sha256"], uploaded_at=datetime.now(UTC).isoformat())
    session.add(record)
    write_audit_log(session, action="rfq.file_uploaded", target_type="rfq", target_id=str(rfq.id), user_id=actor_id, metadata={"file_id": str(record.id), "sha256": metadata["sha256"]})
    # 开发/测试未启用外部扫描器时使用可信测试路径；生产永远失败关闭。
    if not settings.malware_scanner_enabled and settings.app_env in {"development", "test"}:
        await apply_scan_result(session, asset.id, "clean")
    elif not settings.malware_scanner_enabled:
        await apply_scan_result(session, asset.id, "failed")
    return record


async def private_download_url(session: AsyncSession, rfq_id: uuid.UUID, file_id: uuid.UUID, storage: MinioStorageAdapter | None = None) -> tuple[str, datetime]:
    """仅为 clean + ready 且属于该 RFQ 的私有附件生成短期 URL。"""
    row = await session.scalar(select(RFQFile).where(RFQFile.id == file_id, RFQFile.rfq_id == rfq_id))
    if row is None:
        raise AppException(404, "rfq_file_not_found", "询盘附件不存在")
    asset = await session.get(MediaAsset, row.media_asset_id)
    if asset is None or asset.visibility != "private" or asset.storage_bucket != "private-rfq":
        raise AppException(403, "private_file_denied", "附件存储边界不合法")
    if asset.malware_scan_status != "clean" or asset.upload_status != "ready":
        raise AppException(409, "private_file_not_ready", "附件尚未通过安全扫描")
    storage = storage or MinioStorageAdapter()
    url = await storage.presigned_get(asset.storage_bucket, asset.storage_key, ttl_seconds=600)
    return url, private_url_expiry(600)


def validate_status_transition(current: str, target: str) -> None:
    """校验 RFQ 冻结状态机，拒绝任意字符串跳转。"""
    if target not in _TRANSITIONS.get(current, set()):
        raise AppException(409, "invalid_rfq_transition", "不允许的询盘状态转换")
