"""Media Library 管理 API：公开资产上传与私有资产隔离。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import get_current_user, require_csrf, require_permission
from app.modules.media.models import MediaAsset
from app.modules.media.services import validate_upload_bytes
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
async def upload_public_media(file: UploadFile = File(...), visibility: str = Form("public"), session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """上传并校验公开媒体；private 资产必须由 RFQ 专用流程创建。"""
    if visibility != "public":
        from app.core.exceptions.handlers import AppException
        raise AppException(403, "private_media_requires_rfq", "私有文件只能通过 RFQ 附件流程上传")
    content = await file.read()
    metadata = validate_upload_bytes(file.filename or "file", file.content_type or "", content)
    asset = MediaAsset(visibility="public", storage_bucket="public-media", storage_key=f"public/{uuid.uuid4()}/{metadata['sanitized_filename']}", checksum_verified=True, malware_scan_status="not_required", upload_status="ready", uploaded_by=user.id, **metadata)
    session.add(asset)
    await session.commit()
    return success_response(_public_dto(asset))


@public_router.get("/{asset_id}", include_in_schema=False)
async def deliver_public_media(asset_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    """仅对 public-media 且 ready 资产返回对象存储地址，拒绝私有 RFQ 文件。"""
    from app.core.config import get_settings
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public" or asset.storage_bucket != "public-media" or asset.upload_status != "ready":
        raise AppException(404, "media_not_found", "公开媒体不存在")
    settings = get_settings()
    endpoint = f"http://{settings.minio_endpoint}" if not settings.minio_secure else f"https://{settings.minio_endpoint}"
    return RedirectResponse(f"{endpoint}/{settings.minio_public_bucket}/{asset.storage_key}")
