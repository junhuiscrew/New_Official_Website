"""安全与业务操作审计日志模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UuidPrimaryKeyMixin

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class AuditLog(UuidPrimaryKeyMixin, Base):
    """
    保存不可由普通业务流程覆盖的操作审计事件。

    输入：操作用户、动作、目标、请求上下文和结构化元数据。

    输出：AuditLog ORM 实体。
    """

    __tablename__ = "audit_logs"
    __table_args__ = {"comment": "操作审计日志表"}

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作用户ID，匿名或用户被删除时为空",
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="审计动作")
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="目标实体类型")
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="目标实体ID")
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="客户端IP地址")
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="客户端User-Agent")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, default=dict, comment="审计结构化元数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="审计事件创建时间",
    )
