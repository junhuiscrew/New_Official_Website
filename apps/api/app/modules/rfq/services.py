"""RFQ 创建、来源校验、状态流转、附件扫描与私有签名服务。"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.catalog.models import Product, ProductModel
from app.modules.media.models import MediaAsset
from app.modules.media.services import create_private_download_url, validate_upload_bytes
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
    rfq = RFQ(public_reference=generate_public_reference(), company_name=payload.company_name.strip(), contact_name=payload.contact_name.strip(), email=str(payload.email).lower(), phone=payload.phone, whatsapp=payload.whatsapp, country_code=payload.country_code, website=payload.website, message=payload.message, preferred_language=payload.preferred_language, source_page_url=payload.source_page_url, source_owner_type=payload.source_owner_type, source_owner_id=payload.source_owner_id, submitted_ip=ip, user_agent=user_agent, consent_privacy=payload.consent_privacy, consent_marketing=payload.consent_marketing)
    session.add(rfq)
    await session.flush()
    for item in payload.items:
        if item.product_id and (await session.get(Product, item.product_id)) is None:
            raise AppException(422, "invalid_product", "询盘项目产品不存在")
        if item.product_model_id and (await session.get(ProductModel, item.product_model_id)) is None:
            raise AppException(422, "invalid_product_model", "询盘项目型号不存在")
        session.add(RFQItem(rfq_id=rfq.id, **item.model_dump()))
    write_audit_log(session, action="rfq.submit", target_type="rfq", target_id=str(rfq.id), metadata={"item_count": len(payload.items)})
    return rfq


async def add_private_file(session: AsyncSession, rfq: RFQ, file_name: str, mime_type: str, content: bytes, category: str, item_id: uuid.UUID | None, actor_id: uuid.UUID | None) -> RFQFile:
    """校验并保存 RFQ 私有附件，生产未配置扫描器时进入 quarantine。"""
    settings = get_settings()
    current_files = list((await session.scalars(select(MediaAsset).join(RFQFile, RFQFile.media_asset_id == MediaAsset.id).where(RFQFile.rfq_id == rfq.id))).all())
    if len(current_files) >= settings.rfq_max_files:
        raise AppException(413, "rfq_file_count_exceeded", "询盘附件数量超过限制")
    current_total = sum(int(item.file_size_bytes) for item in current_files)
    if current_total + len(content) > settings.rfq_max_total_file_bytes:
        raise AppException(413, "rfq_total_files_too_large", "询盘附件总大小超过限制")
    metadata = validate_upload_bytes(file_name, mime_type, content, private=True)
    scan_status = "pending" if settings.malware_scanner_enabled else "clean" if settings.app_env in {"development", "test"} else "quarantined"
    upload_status = "ready" if scan_status == "clean" else "quarantined"
    asset = MediaAsset(visibility="private", storage_bucket="private-rfq", storage_key=f"rfq/{rfq.id}/{uuid.uuid4()}/{metadata['sanitized_filename']}", checksum_verified=True, malware_scan_status=scan_status, upload_status=upload_status, uploaded_by=actor_id, **metadata)
    session.add(asset)
    await session.flush()
    record = RFQFile(rfq_id=rfq.id, rfq_item_id=item_id, media_asset_id=asset.id, file_category=category, original_filename=file_name, sha256=metadata["sha256"], uploaded_at=datetime.now(UTC).isoformat())
    session.add(record)
    write_audit_log(session, action="rfq.file_uploaded", target_type="rfq", target_id=str(rfq.id), user_id=actor_id, metadata={"file_id": str(record.id), "sha256": metadata["sha256"]})
    return record


async def private_download_url(session: AsyncSession, rfq_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, datetime]:
    """仅为 clean + ready 且属于该 RFQ 的私有附件生成短期 URL。"""
    row = await session.scalar(select(RFQFile).where(RFQFile.id == file_id, RFQFile.rfq_id == rfq_id))
    if row is None:
        raise AppException(404, "rfq_file_not_found", "询盘附件不存在")
    asset = await session.get(MediaAsset, row.media_asset_id)
    if asset is None or asset.visibility != "private" or asset.storage_bucket != "private-rfq":
        raise AppException(403, "private_file_denied", "附件存储边界不合法")
    if asset.malware_scan_status != "clean" or asset.upload_status != "ready":
        raise AppException(409, "private_file_not_ready", "附件尚未通过安全扫描")
    return create_private_download_url(asset.storage_key)


def validate_status_transition(current: str, target: str) -> None:
    """校验 RFQ 冻结状态机，拒绝任意字符串跳转。"""
    if target not in _TRANSITIONS.get(current, set()):
        raise AppException(409, "invalid_rfq_transition", "不允许的询盘状态转换")
