"""不可变内容修订快照存储与回滚读取服务。"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.content.models import ContentRevision


async def store_revision(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    snapshot: dict[str, Any],
    changed_by: uuid.UUID | None,
) -> ContentRevision:
    """
    为同一 owner/locale 分配递增序号并保存深拷贝快照。

    输入：session、owner 标识、locale_id、snapshot 与 changed_by。

    输出：ContentRevision，新创建的不可变修订记录。
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        # PostgreSQL 事务级咨询锁串行化同一内容语言的序号分配，避免并发 max+1 冲突。
        revision_key = f"{owner_type}:{owner_id}:{locale_id}"
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:revision_key, 0))"),
            {"revision_key": revision_key},
        )
    latest_number = await session.scalar(
        select(func.max(ContentRevision.revision_no)).where(
            ContentRevision.owner_type == owner_type,
            ContentRevision.owner_id == owner_id,
            ContentRevision.locale_id == locale_id,
        )
    )
    revision = ContentRevision(
        owner_type=owner_type,
        owner_id=owner_id,
        locale_id=locale_id,
        revision_no=(latest_number or 0) + 1,
        snapshot_jsonb=copy.deepcopy(snapshot),
        changed_by=changed_by,
        created_at=datetime.now(UTC),
    )
    session.add(revision)
    await session.flush()
    return revision


async def get_rollback_snapshot(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    revision_no: int,
) -> dict[str, Any]:
    """
    读取指定历史快照的深拷贝，实际应用和新修订由未来业务服务负责。

    输入：session、owner 标识、locale_id 与 revision_no。

    输出：dict[str, Any]，不会修改已存修订的快照副本。
    """
    revision = await session.scalar(
        select(ContentRevision).where(
            ContentRevision.owner_type == owner_type,
            ContentRevision.owner_id == owner_id,
            ContentRevision.locale_id == locale_id,
            ContentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        raise AppException(404, "revision_not_found", "内容修订不存在")
    return copy.deepcopy(revision.snapshot_jsonb)
