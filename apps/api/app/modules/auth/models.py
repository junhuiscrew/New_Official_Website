"""可轮换、可撤销的刷新会话模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin


class AuthSession(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    保存刷新凭据摘要及其撤销、轮换状态。

    输入：user_id、token_hash、过期时间和请求上下文。

    输出：AuthSession ORM 实体；数据库中不保存明文 refresh credential。
    """

    __tablename__ = "auth_sessions"
    __table_args__ = {"comment": "认证刷新会话表"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="刷新凭据HMAC摘要"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, comment="刷新会话过期时间"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="撤销时间"
    )
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="轮换来源会话ID",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近使用时间"
    )
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True, comment="客户端IP地址")
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True, comment="客户端User-Agent")
