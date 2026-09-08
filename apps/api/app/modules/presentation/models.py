"""首页模块化布局草稿与应用状态模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class HomepageLayout(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存固定首页每种语言的草稿和已应用模块组合。"""

    __tablename__ = "homepage_layouts"
    __table_args__ = (
        UniqueConstraint(
            "site_page_id",
            "locale_id",
            name="uq_homepage_layout_site_page_locale",
        ),
        CheckConstraint(
            "draft_revision >= 0",
            name="homepage_layout_draft_revision_nonnegative",
        ),
        CheckConstraint(
            "applied_revision >= 0",
            name="homepage_layout_applied_revision_nonnegative",
        ),
        {"comment": "首页模块化布局配置表"},
    )

    site_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("site_pages.id", ondelete="CASCADE"),
        nullable=False,
        comment="固定首页页面ID",
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="首页布局语言ID",
    )
    draft_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE,
        nullable=False,
        comment="后台当前草稿模块配置JSON",
    )
    applied_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE,
        nullable=False,
        comment="普通首页当前应用模块配置JSON",
    )
    draft_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="草稿乐观锁修订号",
    )
    applied_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="已应用布局修订号",
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近保存草稿的用户ID",
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近应用布局的用户ID",
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近应用布局时间",
    )

