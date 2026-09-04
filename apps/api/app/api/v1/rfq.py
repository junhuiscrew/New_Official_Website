"""RFQ 公共提交与销售后台 API。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.modules.audit.models import AuditLog
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.media.models import MediaAsset
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter
from app.modules.rfq.models import RFQ, RFQFile, RFQItem
from app.modules.rfq.schemas import RFQAssign, RFQCreate, RFQUpdate
from app.modules.rfq.services import (
    add_private_file,
    create_rfq,
    create_submission_token,
    enforce_public_rate_limit,
    private_download_url,
    validate_public_origin,
    validate_status_transition,
    verify_submission_token,
)
from app.modules.users.models import User
from app.workers.tasks import enqueue_private_asset_scan

router = APIRouter(prefix="/rfqs", tags=["rfq"])
public_router = APIRouter(prefix="/public/rfqs", tags=["public-rfq"])


def _dto(record: Any) -> dict[str, object]:
    """输入后台 ORM 记录；输出列 DTO，公开接口绝不复用此结构。"""
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


@public_router.post("", response_model=ApiResponse[dict[str, str]], status_code=201)
async def submit_public_rfq(payload: RFQCreate, request: Request, session: AsyncSession = Depends(get_session)) -> ApiResponse[dict[str, str]]:
    """匿名提交 RFQ；校验来源和反垃圾后返回公开编号及短期附件令牌。"""
    if payload.honeypot:
        raise AppException(422, "spam_detected", "提交未通过反垃圾校验")
    validate_public_origin(request)
    client_ip, user_agent = get_client_context(request)
    await enforce_public_rate_limit(client_ip)
    rfq = await create_rfq(session, payload, ip=client_ip, user_agent=user_agent)
    await session.commit()
    return success_response({"reference": rfq.public_reference, "status": "received", "submission_token": create_submission_token(rfq)})


@public_router.post("/{public_reference}/files", response_model=ApiResponse[dict[str, str]], status_code=201)
async def upload_public_rfq_file(public_reference: str, request: Request, file: UploadFile = File(...), file_category: str = Form("other"), item_id: uuid.UUID | None = Form(None), session: AsyncSession = Depends(get_session), storage: MinioStorageAdapter = Depends(get_storage_adapter)) -> ApiResponse[dict[str, str]]:
    """匿名客户使用短期提交令牌，为刚创建的 RFQ 上传私有附件。"""
    validate_public_origin(request)
    rfq = await session.scalar(select(RFQ).where(RFQ.public_reference == public_reference))
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    token = request.headers.get("x-rfq-submission-token", "")
    if not verify_submission_token(token, rfq.public_reference):
        raise AppException(403, "invalid_submission_token", "附件提交令牌无效或已过期")
    record = await add_private_file(session, rfq, file.filename or "file", file.content_type or "", await file.read(), file_category, item_id, None, storage)
    asset = await session.get(MediaAsset, record.media_asset_id)
    stored_object = (asset.storage_bucket, asset.storage_key) if asset else None
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        if stored_object:
            await storage.delete_object(*stored_object)
        raise
    asset = await session.get(MediaAsset, record.media_asset_id)
    if asset and asset.malware_scan_status == "pending":
        enqueue_private_asset_scan(asset.id)
    return success_response({"status": "received"})


@router.get("", response_model=ApiResponse[dict[str, object]])
async def list_rfqs(session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("rfq.read"))) -> ApiResponse[dict[str, object]]:
    """销售读取询盘列表。"""
    rows = list((await session.scalars(select(RFQ).order_by(RFQ.created_at.desc()))).all())
    return success_response({"items": [_dto(row) for row in rows], "total": len(rows)})


@router.get("/{rfq_id}", response_model=ApiResponse[dict[str, object]])
async def get_rfq(rfq_id: uuid.UUID, session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("rfq.read"))) -> ApiResponse[dict[str, object]]:
    """销售读取询盘详情、项目、附件元数据。"""
    rfq = await session.get(RFQ, rfq_id)
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    items = list((await session.scalars(select(RFQItem).where(RFQItem.rfq_id == rfq.id).order_by(RFQItem.sort_order))).all())
    files = list((await session.scalars(select(RFQFile).where(RFQFile.rfq_id == rfq.id))).all())
    audit_logs = list((await session.scalars(select(AuditLog).where(AuditLog.target_type == "rfq", AuditLog.target_id == str(rfq.id)).order_by(AuditLog.created_at.desc()))).all())
    file_rows = []
    for item in files:
        asset = await session.get(MediaAsset, item.media_asset_id)
        file_rows.append({"id": str(item.id), "item_id": str(item.rfq_item_id) if item.rfq_item_id else None, "file_category": item.file_category, "original_filename": item.original_filename, "sha256": item.sha256, "malware_scan_status": asset.malware_scan_status if asset else "missing", "upload_status": asset.upload_status if asset else "missing"})
    return success_response({"rfq": _dto(rfq), "items": [_dto(item) for item in items], "files": file_rows, "audit_logs": [_dto(item) for item in audit_logs]})


@router.patch("/{rfq_id}", response_model=ApiResponse[dict[str, object]])
async def patch_rfq(rfq_id: uuid.UUID, payload: RFQUpdate, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """按冻结状态机更新询盘状态或优先级。"""
    rfq = await session.get(RFQ, rfq_id)
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    if payload.status:
        validate_status_transition(rfq.status, payload.status)
        old = rfq.status
        rfq.status = payload.status
        write_audit_log(session, action="rfq.status_change", target_type="rfq", target_id=str(rfq.id), user_id=user.id, metadata={"from": old, "to": payload.status})
    if payload.priority:
        rfq.priority = payload.priority
        write_audit_log(session, action="rfq.priority_change", target_type="rfq", target_id=str(rfq.id), user_id=user.id)
    await session.commit()
    return success_response(_dto(rfq))


@router.post("/{rfq_id}/assign", response_model=ApiResponse[dict[str, object]])
async def assign_rfq(rfq_id: uuid.UUID, payload: RFQAssign, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.assign")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """分配询盘给销售，并写审计。"""
    rfq = await session.get(RFQ, rfq_id)
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    rfq.assigned_to = payload.assigned_to
    write_audit_log(session, action="rfq.assign", target_type="rfq", target_id=str(rfq.id), user_id=user.id, metadata={"assigned_to": str(payload.assigned_to) if payload.assigned_to else None})
    await session.commit()
    return success_response(_dto(rfq))


@router.post("/{rfq_id}/files", response_model=ApiResponse[dict[str, object]], status_code=201)
async def upload_rfq_file(rfq_id: uuid.UUID, file: UploadFile = File(...), file_category: str = Form("other"), item_id: uuid.UUID | None = Form(None), session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.update")), _csrf: None = Depends(require_csrf), storage: MinioStorageAdapter = Depends(get_storage_adapter)) -> ApiResponse[dict[str, object]]:
    """上传 RFQ 私有附件；附件不会进入 public-media。"""
    rfq = await session.get(RFQ, rfq_id)
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    record = await add_private_file(session, rfq, file.filename or "file", file.content_type or "", await file.read(), file_category, item_id, user.id, storage)
    asset = await session.get(MediaAsset, record.media_asset_id)
    stored_object = (asset.storage_bucket, asset.storage_key) if asset else None
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        if stored_object:
            await storage.delete_object(*stored_object)
        raise
    asset = await session.get(MediaAsset, record.media_asset_id)
    if asset and asset.malware_scan_status == "pending":
        enqueue_private_asset_scan(asset.id)
    return success_response({"id": str(record.id), "file_category": record.file_category, "original_filename": record.original_filename, "sha256": record.sha256})


@router.post("/{rfq_id}/files/{file_id}/download-url", response_model=ApiResponse[dict[str, object]])
async def get_private_download_url(rfq_id: uuid.UUID, file_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.download_private_file")), _csrf: None = Depends(require_csrf), storage: MinioStorageAdapter = Depends(get_storage_adapter)) -> ApiResponse[dict[str, object]]:
    """为有 RFQ 私有文件权限的销售签发短期下载 URL。"""
    url, expires = await private_download_url(session, rfq_id, file_id, storage)
    write_audit_log(session, action="rfq.private_file_download", target_type="rfq", target_id=str(rfq_id), user_id=user.id, metadata={"file_id": str(file_id), "expires_at": expires.isoformat()})
    await session.commit()
    return success_response({"url": url, "expires_at": expires.isoformat()})
