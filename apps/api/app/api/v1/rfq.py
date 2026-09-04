"""RFQ 公共提交与销售后台 API。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.rfq.models import RFQ, RFQFile, RFQItem
from app.modules.rfq.schemas import RFQAssign, RFQCreate, RFQUpdate
from app.modules.rfq.services import (
    add_private_file,
    create_rfq,
    enforce_public_rate_limit,
    private_download_url,
    validate_status_transition,
)
from app.modules.users.models import User

router = APIRouter(prefix="/rfqs", tags=["rfq"])
public_router = APIRouter(prefix="/public/rfqs", tags=["public-rfq"])


def _dto(rfq: RFQ) -> dict[str, object]:
    """生成后台询盘 DTO；公开接口不复用此结构。"""
    return {column.name: getattr(rfq, column.name) for column in rfq.__table__.columns}


@public_router.post("", response_model=ApiResponse[dict[str, str]], status_code=201)
async def submit_public_rfq(payload: RFQCreate, request: Request, session: AsyncSession = Depends(get_session)) -> ApiResponse[dict[str, str]]:
    """匿名提交 RFQ；校验同源 Origin/Referer、honeypot 和内容后只返回 reference。"""
    if payload.honeypot:
        raise AppException(422, "spam_detected", "提交未通过反垃圾校验")
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if origin and "junhuiscrewbarrel.com" not in origin and "localhost" not in origin and "testserver" not in origin:
        raise AppException(403, "origin_not_allowed", "提交来源不受信任")
    await enforce_public_rate_limit(request.client.host if request.client else None)
    rfq = await create_rfq(session, payload, ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))
    await session.commit()
    return success_response({"reference": rfq.public_reference, "status": "received"})


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
    return success_response({"rfq": _dto(rfq), "items": [_dto(item) for item in items], "files": [{"id": str(item.id), "file_category": item.file_category, "original_filename": item.original_filename, "sha256": item.sha256} for item in files]})


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
async def upload_rfq_file(rfq_id: uuid.UUID, file: UploadFile = File(...), file_category: str = Form("other"), item_id: uuid.UUID | None = Form(None), session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """上传 RFQ 私有附件；附件不会进入 public-media。"""
    rfq = await session.get(RFQ, rfq_id)
    if rfq is None:
        raise AppException(404, "rfq_not_found", "询盘不存在")
    record = await add_private_file(session, rfq, file.filename or "file", file.content_type or "", await file.read(), file_category, item_id, user.id)
    await session.commit()
    return success_response({"id": str(record.id), "file_category": record.file_category, "original_filename": record.original_filename, "sha256": record.sha256})


@router.post("/{rfq_id}/files/{file_id}/download-url", response_model=ApiResponse[dict[str, object]])
async def get_private_download_url(rfq_id: uuid.UUID, file_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("rfq.download_private_file")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, object]]:
    """为有 RFQ 私有文件权限的销售签发短期下载 URL。"""
    url, expires = await private_download_url(session, rfq_id, file_id)
    write_audit_log(session, action="rfq.private_file_download", target_type="rfq", target_id=str(rfq_id), user_id=user.id, metadata={"file_id": str(file_id), "expires_at": expires.isoformat()})
    await session.commit()
    return success_response({"url": url, "expires_at": expires.isoformat()})
