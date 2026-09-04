"""SQLAlchemy Declarative Base 与通用字段 mixin。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 统一命名规则保证 Alembic 约束名称稳定、可预测。
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    全部 ORM 模型共享的声明式基类。

    输入：SQLAlchemy 映射声明。

    输出：DeclarativeBase，为 Alembic 提供统一 metadata。
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UuidPrimaryKeyMixin:
    """为核心实体提供 UUID 主键。"""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="主键ID",
    )


class TimestampMixin:
    """为核心实体提供统一的创建和更新时间字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )
