"""Media Library 管理 API：公开资产上传与私有资产隔离。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation
from app.modules.media.services import validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["media"])
public_router = APIRouter(prefix="/public/media", tags=["public-media"])


def _public_dto(asset: MediaAsset) -> dict[str, object]:
    """生成不泄露 storage credential 的媒体 DTO。"""
    return {
        "id": str(asset.id), "type": asset.media_type,
        "url": f"/api/v1/public/media/{asset.id}" if asset.visibility == "public" else None,
        "mime_type": asset.mime_type, "file_extension": asset.file_extension,
        "file_size_bytes": asset.file_size_bytes, "width": asset.width,
        "height": asset.height, "duration_seconds": asset.duration_seconds,
        "visibility": asset.visibility, "upload_status": asset.upload_status,
    }


@router.get("", response_model=ApiResponse[list[dict[str, object]]])
async def list_media(session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("media.read"))) -> ApiResponse[list[dict[str, object]]]:
    """只列出公开媒体资产；私有 RFQ 文件通过 RFQ 权限访问。"""
    assets = list((await session.scalars(select(MediaAsset).where(MediaAsset.visibility == "public").order_by(MediaAsset.created_at.desc()))).all())
    return success_response([_public_dto(asset) for asset in assets])


@router.post("/assets", response_model=ApiResponse[dict[str, object]], status_code=201)
async def upload_public_media(file: UploadFile = File(...), visibility: str = Form("public"), session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("media.upload")), _csrf: None = Depends(require_csrf), storage: MinioStorageAdapter = Depends(get_storage_adapter)) -> ApiResponse[dict[str, object]]:
    """上传并校验公开媒体；private 资产必须由 RFQ 专用流程创建。"""
    if visibility != "public":
        from app.core.exceptions.handlers import AppException
        raise AppException(403, "private_media_requires_rfq", "私有文件只能通过 RFQ 附件流程上传")
    content = await file.read()
    metadata = validate_upload_bytes(file.filename or "file", file.content_type or "", content)
    from app.core.config import get_settings

    settings = get_settings()
    storage_key = f"public/{uuid.uuid4()}/{metadata['sanitized_filename']}"
    await storage.put_object(settings.minio_public_bucket, storage_key, content, str(metadata["mime_type"]))
    asset = MediaAsset(visibility="public", storage_bucket=settings.minio_public_bucket, storage_key=storage_key, checksum_verified=True, malware_scan_status="not_required", upload_status="ready", uploaded_by=user.id, **metadata)
    session.add(asset)
    try:
        await session.flush()
        write_audit_log(session, action="media.upload", target_type="media_asset", target_id=str(asset.id), user_id=user.id, metadata={"sha256": asset.sha256})
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete_object(settings.minio_public_bucket, storage_key)
        raise
    return success_response(_public_dto(asset))


@router.patch("/{asset_id}/translations/{locale_id}", response_model=ApiResponse[dict[str, object]])
async def update_media_translation(asset_id: uuid.UUID, locale_id: uuid.UUID, alt_text: str | None = Form(None), title: str | None = Form(None), caption: str | None = Form(None), session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("media.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """更新公开媒体的多语言元数据，图片 Alt 文本由编辑人员显式维护。"""
    asset = await session.get(MediaAsset, asset_id)
    locale = await session.get(Locale, locale_id)
    if asset is None or asset.visibility != "public" or locale is None:
        from app.core.exceptions.handlers import AppException
        raise AppException(404, "media_translation_target_not_found", "媒体或语言不存在")
    translation = await session.scalar(select(MediaAssetTranslation).where(MediaAssetTranslation.media_asset_id == asset.id, MediaAssetTranslation.locale_id == locale.id))
    if translation is None:
        translation = MediaAssetTranslation(media_asset_id=asset.id, locale_id=locale.id)
        session.add(translation)
    translation.alt_text = alt_text
    translation.title = title
    translation.caption = caption
    write_audit_log(session, action="media.translation_update", target_type="media_asset", target_id=str(asset.id), user_id=user.id, metadata={"locale_id": str(locale.id)})
    await session.commit()
    return success_response({"media_asset_id": str(asset.id), "locale_id": str(locale.id), "alt_text": alt_text, "title": title, "caption": caption})


@public_router.get("/{asset_id}", include_in_schema=False)
async def deliver_public_media(asset_id: uuid.UUID, session: AsyncSession = Depends(get_session), storage: MinioStorageAdapter = Depends(get_storage_adapter)) -> Response:
    """安全代理 public-media 对象，浏览器永远看不到 Docker 内部 MinIO 地址。"""
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public" or asset.storage_bucket != "public-media" or asset.upload_status != "ready":
        raise AppException(404, "media_not_found", "公开媒体不存在")
    if not await storage.object_exists(asset.storage_bucket, asset.storage_key):
        raise AppException(404, "media_object_missing", "公开媒体对象不存在")
    return Response(
        await storage.get_object(asset.storage_bucket, asset.storage_key),
        media_type=asset.mime_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
