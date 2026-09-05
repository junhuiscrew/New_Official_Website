"""公开下载资源管理 API：真实 CRUD 并强制 public-media 引用边界。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.company.schemas import DownloadInput
from app.modules.media.models import DownloadResource, DownloadResourceTranslation, MediaAsset
from app.modules.media.services import list_broken_public_downloads
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter
from app.modules.users.models import User

router = APIRouter(prefix="/downloads", tags=["downloads"])


def _serialize(record: Any) -> dict[str, Any]:
    """输入 SQLAlchemy 实体；输出包含列值的 Admin DTO。"""
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


async def _validate_public_asset(session: AsyncSession, asset_id: uuid.UUID) -> MediaAsset:
    """输入数据库会话与媒体 ID；输出可用 public-media 资产，否则抛出 422。"""
    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public" or asset.storage_bucket != "public-media" or asset.upload_status != "ready":
        raise AppException(422, "public_media_required", "下载资源必须引用已就绪的 public-media 资产")
    return asset


async def _save_translations(session: AsyncSession, resource: DownloadResource, payload: DownloadInput) -> None:
    """输入下载资源及多语言载荷；输出 None，按 locale 幂等保存标题和摘要。"""
    for item in payload.translations:
        translation = await session.scalar(select(DownloadResourceTranslation).where(DownloadResourceTranslation.download_resource_id == resource.id, DownloadResourceTranslation.locale_id == item.locale_id))
        fields = item.fields
        title = str(fields.get("title") or "").strip()
        if not title:
            raise AppException(422, "download_title_required", "下载资源翻译标题不能为空")
        if translation is None:
            translation = DownloadResourceTranslation(download_resource_id=resource.id, locale_id=item.locale_id, title=title)
            session.add(translation)
        translation.title = title
        translation.summary = fields.get("summary")


@router.get("", response_model=ApiResponse[dict[str, Any]])
async def list_downloads(session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("download.read"))) -> ApiResponse[dict[str, Any]]:
    """输入认证会话；输出全部下载资源及其翻译。"""
    resources = list((await session.scalars(select(DownloadResource).order_by(DownloadResource.sort_order, DownloadResource.created_at.desc()))).all())
    items = []
    for resource in resources:
        translations = list((await session.scalars(select(DownloadResourceTranslation).where(DownloadResourceTranslation.download_resource_id == resource.id))).all())
        items.append({**_serialize(resource), "translations": [_serialize(item) for item in translations]})
    return success_response({"items": items, "total": len(items)})


@router.get("/broken-media", response_model=ApiResponse[dict[str, Any]])
async def get_broken_download_media(
    session: AsyncSession = Depends(get_session),
    storage: MinioStorageAdapter = Depends(get_storage_adapter),
    _user: User = Depends(require_permission("download.read")),
) -> ApiResponse[dict[str, Any]]:
    """
    返回公开下载引用的缺失对象提示。

    输入：认证会话、对象存储适配器与 download.read 用户。
    输出：ApiResponse，包含 object_missing 项和数量，供 Admin 修复坏链。
    """
    items = await list_broken_public_downloads(session, storage=storage)
    return success_response({"items": items, "total": len(items)})


@router.post("", response_model=ApiResponse[dict[str, Any]], status_code=201)
async def create_download(payload: DownloadInput, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("download.create")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """输入下载载荷；输出新建资源，且媒体边界已通过服务端校验。"""
    await _validate_public_asset(session, payload.media_asset_id)
    values = payload.model_dump(exclude={"translations"})
    resource = DownloadResource(**values)
    session.add(resource)
    await session.flush()
    await _save_translations(session, resource, payload)
    write_audit_log(session, action="download.create", target_type="download_resource", target_id=str(resource.id), user_id=user.id)
    await session.commit()
    return success_response(_serialize(resource))


@router.patch("/{resource_id}", response_model=ApiResponse[dict[str, Any]])
async def update_download(resource_id: uuid.UUID, payload: DownloadInput, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("download.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """输入资源 ID 与完整载荷；输出已更新下载资源。"""
    resource = await session.get(DownloadResource, resource_id)
    if resource is None:
        raise AppException(404, "download_not_found", "下载资源不存在")
    await _validate_public_asset(session, payload.media_asset_id)
    for key, value in payload.model_dump(exclude={"translations"}).items():
        setattr(resource, key, value)
    await _save_translations(session, resource, payload)
    write_audit_log(session, action="download.update", target_type="download_resource", target_id=str(resource.id), user_id=user.id)
    await session.commit()
    return success_response(_serialize(resource))


@router.post("/{resource_id}/archive", response_model=ApiResponse[dict[str, Any]])
async def archive_download(resource_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("download.archive")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """输入资源 ID；输出 retired 资源，使其立即退出公开下载列表。"""
    resource = await session.get(DownloadResource, resource_id)
    if resource is None:
        raise AppException(404, "download_not_found", "下载资源不存在")
    resource.status = "retired"
    write_audit_log(session, action="download.archive", target_type="download_resource", target_id=str(resource.id), user_id=user.id)
    await session.commit()
    return success_response(_serialize(resource))
