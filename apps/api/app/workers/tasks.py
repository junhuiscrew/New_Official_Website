"""Celery 后台任务：扫描私有 RFQ 文件并执行失败关闭状态机。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.modules.audit.service import write_audit_log
from app.modules.media.models import MediaAsset
from app.modules.media.scanner import ClamAVScanner, apply_scan_result
from app.modules.media.storage import MinioStorageAdapter
from app.modules.rfq.models import RFQ
from app.workers.celery_app import celery_app


async def scan_private_asset(asset_id: uuid.UUID) -> str:
    """
    从 private-rfq 读取对象、调用扫描器并持久化扫描结论。

    输入：asset_id，待扫描媒体 ID。
    输出：str，clean、infected、failed 或 missing。
    """
    async with async_session_factory() as session, session.begin():
        asset = await session.get(MediaAsset, asset_id)
        if asset is None:
            return "missing"
        if asset.visibility != "private" or asset.storage_bucket != "private-rfq":
            await apply_scan_result(session, asset.id, "failed")
            return "failed"
        try:
            content = await MinioStorageAdapter().get_object(asset.storage_bucket, asset.storage_key)
            result = await ClamAVScanner().scan_bytes(content)
        except Exception:
            # 扫描器、对象存储或网络异常一律失败关闭，不让文件进入 ready。
            result = "failed"
        await apply_scan_result(session, asset.id, result)
        write_audit_log(
            session,
            action="rfq.file_scan_result",
            target_type="media_asset",
            target_id=str(asset.id),
            metadata={"result": result},
        )
        return result


@celery_app.task(name="media.scan_private_asset")
def scan_private_asset_task(asset_id: str) -> str:
    """输入媒体 UUID 字符串；输出扫描结果，供 Celery worker 执行异步扫描。"""
    return asyncio.run(scan_private_asset(uuid.UUID(asset_id)))


def enqueue_private_asset_scan(asset_id: uuid.UUID) -> None:
    """输入媒体 ID；输出 None，将已提交对象加入 Celery 扫描队列。"""
    scan_private_asset_task.delay(str(asset_id))


async def count_expired_rfq_candidates() -> int:
    """
    按配置保留期统计可清理 RFQ，暂不自动删除生产客户数据。

    输入：无，从 RFQ_RETENTION_DAYS 读取保留期。
    输出：int，超过保留期且已经 closed 的候选数量。
    """
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().rfq_retention_days)
    async with async_session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(RFQ).where(RFQ.status == "closed", RFQ.created_at < cutoff)) or 0)


@celery_app.task(name="rfq.count_retention_candidates")
def count_expired_rfq_candidates_task() -> int:
    """输入无；输出过期候选数量，供未来审批式清理流程和监控使用。"""
    return asyncio.run(count_expired_rfq_candidates())
