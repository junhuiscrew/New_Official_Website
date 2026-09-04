"""审计事件写入服务。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


def write_audit_log(
    session: AsyncSession,
    *,
    action: str,
    target_type: str,
    user_id: uuid.UUID | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """
    在调用方当前事务中追加审计日志。

    输入：
        session: AsyncSession，当前业务事务。
        action: str，稳定的审计动作代码。
        target_type: str，目标实体类型。
        user_id: uuid.UUID | None，操作用户ID。
        target_id: str | None，目标实体ID。
        ip: str | None，客户端IP。
        user_agent: str | None，客户端User-Agent。
        metadata: dict[str, Any] | None，非敏感结构化上下文。

    输出：AuditLog，已加入 session 但由调用方统一提交的日志实体。
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip=ip,
        user_agent=user_agent,
        metadata_json=metadata or {},
    )
    session.add(audit_log)
    return audit_log
