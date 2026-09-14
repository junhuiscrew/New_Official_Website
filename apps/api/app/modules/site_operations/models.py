"""站点品牌与导航页脚的草稿、应用版持久化模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class SiteBrandSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存唯一站点品牌的完整双语草稿和已应用版本。"""

    __tablename__ = "site_brand_settings"
    __table_args__ = (
        CheckConstraint("singleton_key = 'primary'", name="site_brand_singleton_key_value"),
        CheckConstraint("draft_revision >= 0", name="site_brand_draft_revision_nonnegative"),
        CheckConstraint("applied_revision >= 0", name="site_brand_applied_revision_nonnegative"),
        {"comment": "站点品牌草稿与应用配置表"},
    )

    singleton_key: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        default="primary",
        server_default="primary",
        comment="唯一品牌设置键，固定为primary",
    )
    draft_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, comment="品牌完整双语草稿JSON"
    )
    applied_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, comment="品牌完整双语应用版JSON"
    )
    draft_header_logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="草稿桌面Logo媒体ID",
    )
    draft_mobile_logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="草稿移动端Logo媒体ID",
    )
    draft_favicon_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="草稿浏览器小图标媒体ID",
    )
    applied_header_logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="应用版桌面Logo媒体ID",
    )
    applied_mobile_logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="应用版移动端Logo媒体ID",
    )
    applied_favicon_media_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        comment="应用版浏览器小图标媒体ID",
    )
    draft_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="品牌草稿乐观锁修订号"
    )
    applied_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="品牌应用版修订号"
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近保存草稿用户ID",
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近应用品牌用户ID",
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近应用品牌时间"
    )


class SiteNavigationSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存每种语言的顶部导航与页脚草稿和已应用版本。"""

    __tablename__ = "site_navigation_settings"
    __table_args__ = (
        CheckConstraint("draft_revision >= 0", name="site_navigation_draft_revision_nonnegative"),
        CheckConstraint(
            "applied_revision >= 0", name="site_navigation_applied_revision_nonnegative"
        ),
        {"comment": "站点导航与页脚草稿及应用配置表"},
    )

    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        comment="导航语言ID",
    )
    draft_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, comment="当前语言导航与页脚草稿JSON"
    )
    applied_config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, comment="当前语言导航与页脚应用版JSON"
    )
    draft_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="导航草稿乐观锁修订号"
    )
    applied_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0", comment="导航应用版修订号"
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近保存草稿用户ID",
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最近应用导航用户ID",
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近应用导航时间"
    )
