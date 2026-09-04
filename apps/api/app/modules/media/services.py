"""媒体上传校验、文件名清洗与私有下载签名服务。"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from urllib.parse import quote

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.localization.models import Locale
from app.modules.media.models import DownloadResource, DownloadResourceTranslation, MediaAsset


async def list_public_downloads(session, locale_slug: str) -> list[dict[str, object]]:
    """
    查询指定语言的公开下载资源，并过滤到可公开访问的媒体资产。

    输入：
        session: AsyncSession，数据库会话。
        locale_slug: str，已启用语言 slug。
    输出：list[dict]，不包含 storage bucket/key 的公开下载 DTO。
    """
    from sqlalchemy import select

    locale = await session.scalar(select(Locale).where(Locale.slug == locale_slug, Locale.is_enabled.is_(True)))
    if locale is None:
        return []
    rows = (await session.execute(
        select(DownloadResource, DownloadResourceTranslation, MediaAsset)
        .join(DownloadResourceTranslation, DownloadResourceTranslation.download_resource_id == DownloadResource.id)
        .join(MediaAsset, MediaAsset.id == DownloadResource.media_asset_id)
        .where(
            DownloadResource.status == "enabled",
            DownloadResourceTranslation.locale_id == locale.id,
            MediaAsset.visibility == "public",
            MediaAsset.storage_bucket == "public-media",
            MediaAsset.upload_status == "ready",
        )
        .order_by(DownloadResource.sort_order, DownloadResource.created_at.desc())
    )).all()
    return [
        {
            "slug": resource.slug,
            "resource_type": resource.resource_type,
            "title": translation.title,
            "summary": translation.summary,
            "version_label": resource.version_label,
            "published_date": resource.published_date,
            "url": f"/api/v1/public/media/{asset.id}",
            "mime_type": asset.mime_type,
            "file_size_bytes": asset.file_size_bytes,
        }
        for resource, translation, asset in rows
    ]

PUBLIC_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf", ".mp4", ".webm"})
RFQ_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf", ".dwg", ".dxf", ".step", ".stp", ".iges", ".igs"})
MIME_BY_EXTENSION = {
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"}, ".webp": {"image/webp"},
    ".pdf": {"application/pdf"}, ".mp4": {"video/mp4"}, ".webm": {"video/webm"},
    ".dwg": {"application/acad", "image/vnd.dwg", "application/octet-stream"},
    ".dxf": {"application/dxf", "image/vnd.dxf", "application/octet-stream"},
    ".step": {"application/step", "model/step", "application/octet-stream"},
    ".stp": {"application/step", "model/step", "application/octet-stream"},
    ".iges": {"model/iges", "application/iges", "application/octet-stream"},
    ".igs": {"model/iges", "application/iges", "application/octet-stream"},
}


def sanitize_filename(filename: str) -> str:
    """清除路径遍历、控制字符与危险双扩展名，返回稳定文件名。"""
    name = PurePath(filename or "file").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-") or "file"
    return name[:180]


def validate_upload_bytes(filename: str, mime_type: str, content: bytes, *, private: bool = False, max_size: int | None = None) -> dict[str, object]:
    """
    联合校验扩展名、MIME、文件头、大小与 SHA256。

    输入：文件名、客户端MIME、二进制内容及 public/private 模式。
    输出：包含清洗文件名、扩展名、媒体类型、SHA256 的安全元数据。
    """
    settings = get_settings()
    extension = PurePath(filename).suffix.lower()
    allowlist = RFQ_EXTENSIONS if private else PUBLIC_EXTENSIONS
    if extension not in allowlist:
        raise AppException(422, "file_extension_not_allowed", "文件扩展名不在允许列表")
    size_limit = max_size or (settings.rfq_max_file_bytes if private else settings.public_media_max_file_bytes)
    if len(content) > size_limit:
        raise AppException(413, "file_too_large", "文件超过大小限制")
    normalized_mime = (mime_type or "application/octet-stream").lower().split(";", 1)[0]
    if normalized_mime not in MIME_BY_EXTENSION[extension]:
        raise AppException(422, "file_mime_not_allowed", "文件 MIME 与扩展名不匹配")
    # 图片/PDF/视频采用可靠签名；CAD 使用安全二进制策略并要求非空内容。
    signatures = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",), ".pdf": (b"%PDF-",), ".mp4": (b"ftyp",)}
    if extension in signatures and not any(content.startswith(sig) or (extension == ".mp4" and sig in content[:32]) for sig in signatures[extension]):
        raise AppException(422, "file_signature_invalid", "文件头签名校验失败")
    if extension in {".webp"} and not (content.startswith(b"RIFF") and b"WEBP" in content[:16]):
        raise AppException(422, "file_signature_invalid", "WEBP 文件头签名校验失败")
    if not content:
        raise AppException(422, "file_empty", "文件不能为空")
    return {
        "original_filename": filename,
        "sanitized_filename": sanitize_filename(filename),
        "file_extension": extension,
        "mime_type": normalized_mime,
        "media_type": "cad" if extension in RFQ_EXTENSIONS - PUBLIC_EXTENSIONS else "image" if extension in {".jpg", ".jpeg", ".png", ".webp"} else "video" if extension in {".mp4", ".webm"} else "document",
        "file_size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def create_private_download_url(storage_key: str, *, ttl_seconds: int = 600) -> tuple[str, datetime]:
    """生成短期 HMAC 私有下载 URL；不泄露对象存储凭据。"""
    if not storage_key or storage_key.startswith("/") or ".." in storage_key:
        raise AppException(409, "unsafe_storage_key", "私有文件路径不安全")
    settings = get_settings()
    ttl = min(max(ttl_seconds, 60), 900)
    expires = datetime.now(UTC) + timedelta(seconds=ttl)
    payload = f"{settings.minio_private_bucket}:{storage_key}:{int(expires.timestamp())}".encode()
    signature = hmac.new(settings.refresh_token_secret.encode(), payload, hashlib.sha256).hexdigest()
    endpoint = settings.minio_endpoint if settings.minio_secure is False else f"https://{settings.minio_endpoint}"
    if not settings.minio_secure:
        endpoint = f"http://{endpoint}"
    return f"{endpoint}/{quote(settings.minio_private_bucket)}/{quote(storage_key)}?expires={int(expires.timestamp())}&signature={signature}", expires
