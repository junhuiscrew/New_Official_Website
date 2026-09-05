"""媒体上传校验、文件名清洗与私有下载签名服务。"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePath

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.localization.models import Locale
from app.modules.media.models import DownloadResource, DownloadResourceTranslation, MediaAsset
from app.modules.media.storage import MinioStorageAdapter


async def _public_download_rows(session, locale_slug: str | None = None):
    """
    查询具备公开数据库状态的下载资源。

    输入：session 数据库会话；locale_slug 可选语言 slug。
    输出：数据库行列表；对象存储存在性由调用方继续核验。
    """
    from sqlalchemy import select

    statement = (
        select(DownloadResource, DownloadResourceTranslation, MediaAsset)
        .join(
            DownloadResourceTranslation,
            DownloadResourceTranslation.download_resource_id == DownloadResource.id,
        )
        .join(MediaAsset, MediaAsset.id == DownloadResource.media_asset_id)
        .join(Locale, Locale.id == DownloadResourceTranslation.locale_id)
        .where(
            DownloadResource.status == "enabled",
            Locale.is_enabled.is_(True),
            MediaAsset.visibility == "public",
            MediaAsset.storage_bucket == "public-media",
            MediaAsset.upload_status == "ready",
        )
        .order_by(DownloadResource.sort_order, DownloadResource.created_at.desc())
    )
    if locale_slug is not None:
        statement = statement.where(Locale.slug == locale_slug)
    return (await session.execute(statement)).all()


async def list_public_downloads(
    session,
    locale_slug: str,
    *,
    storage: MinioStorageAdapter,
) -> list[dict[str, object]]:
    """
    查询指定语言的公开下载资源，并过滤到可公开访问的媒体资产。

    输入：
        session: AsyncSession，数据库会话。
        locale_slug: str，已启用语言 slug。
    输出：list[dict]，不包含 storage bucket/key 的公开下载 DTO。
    """
    rows = await _public_download_rows(session, locale_slug)
    result: list[dict[str, object]] = []
    for resource, translation, asset in rows:
        # DB ready 只是元数据状态；真实对象缺失时必须 fail-closed，不向访客发坏链。
        if not await storage.object_exists(asset.storage_bucket, asset.storage_key):
            continue
        result.append(
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
        )
    return result


async def list_broken_public_downloads(
    session,
    *,
    storage: MinioStorageAdapter,
) -> list[dict[str, str]]:
    """
    汇总元数据可公开但对象已经缺失的下载资源。

    输入：session 数据库会话；storage 对象存储适配器。
    输出：list[dict]，供 Admin/health 提示修复，不包含任何私有桶资源。
    """
    broken: list[dict[str, str]] = []
    seen_resources: set[tuple[object, object]] = set()
    for resource, _translation, asset in await _public_download_rows(session):
        resource_asset_key = (resource.id, asset.id)
        if resource_asset_key in seen_resources:
            continue
        # 同一下载资源可能拥有多语言翻译；只去重翻译行，不合并不同下载资源。
        seen_resources.add(resource_asset_key)
        if await storage.object_exists(asset.storage_bucket, asset.storage_key):
            continue
        broken.append(
            {
                "asset_id": str(asset.id),
                "download_slug": resource.slug,
                "storage_bucket": asset.storage_bucket,
                "storage_key": asset.storage_key,
                "reason": "object_missing",
            }
        )
    return broken

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
    # 图片/PDF/视频/CAD 均校验真实格式标记，不能因 MIME 为 octet-stream 而跳过。
    signatures = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",), ".pdf": (b"%PDF-",), ".mp4": (b"ftyp",)}
    if extension in signatures and not any(content.startswith(sig) or (extension == ".mp4" and sig in content[:32]) for sig in signatures[extension]):
        raise AppException(422, "file_signature_invalid", "文件头签名校验失败")
    if extension in {".webp"} and not (content.startswith(b"RIFF") and b"WEBP" in content[:16]):
        raise AppException(422, "file_signature_invalid", "WEBP 文件头签名校验失败")
    cad_signatures = {
        ".dwg": lambda value: value.startswith(b"AC10"),
        ".dxf": lambda value: b"SECTION" in value[:256].upper() and b"EOF" in value[-64:].upper(),
        ".step": lambda value: value.lstrip().startswith(b"ISO-10303-21;"),
        ".stp": lambda value: value.lstrip().startswith(b"ISO-10303-21;"),
        ".iges": lambda value: len(value) >= 64 and b"S" in value[60:80].upper(),
        ".igs": lambda value: len(value) >= 64 and b"S" in value[60:80].upper(),
    }
    if extension in cad_signatures and not cad_signatures[extension](content):
        raise AppException(422, "file_signature_invalid", "CAD 文件头签名校验失败")
    if not content:
        raise AppException(422, "file_empty", "文件不能为空")
    return {
        "original_filename": filename,
        "sanitized_filename": sanitize_filename(filename),
        "file_extension": extension,
        "mime_type": normalized_mime,
        "media_type": "cad" if extension in {".dwg", ".dxf", ".step", ".stp", ".iges", ".igs"} else "image" if extension in {".jpg", ".jpeg", ".png", ".webp"} else "video" if extension in {".mp4", ".webm"} else "document",
        "file_size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
