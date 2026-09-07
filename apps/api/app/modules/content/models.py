"""多语言发布、路由注册与内容修订基础模型。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.modules.content.enums import PublicationStatus, TranslationState

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class TranslationStatus(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存某个主实体在指定语言下的翻译生命周期状态。"""

    __tablename__ = "translation_statuses"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_translation_owner_locale"),
        CheckConstraint(
            "status IN ('missing','draft','machine_translated','human_reviewed','published')",
            name="translation_status_value",
        ),
        {"comment": "内容翻译状态表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, comment="主实体ID"
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="目标语言ID",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TranslationState.MISSING.value,
        server_default="missing",
        comment="翻译状态：missing缺失，draft草稿，machine_translated机翻，human_reviewed人工审核，published已发布",
    )
    source_locale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=True,
        comment="源语言ID",
    )
    translated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="翻译用户ID",
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核用户ID",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="翻译发布时间"
    )


class ContentPublication(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存可复用的内容发布状态，不绑定具体 Product 等业务表。"""

    __tablename__ = "content_publications"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_publication_owner_locale"),
        CheckConstraint(
            "status IN ('draft','review','scheduled','published','archived')",
            name="publication_status_value",
        ),
        {"comment": "内容发布状态表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, comment="主实体ID"
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="发布语言ID",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default="draft",
        comment="发布状态：draft草稿，review审核，scheduled定时，published已发布，archived已归档",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="计划发布时间"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="实际发布时间"
    )


class ContentRoute(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存跨内容类型复用的规范 URL 注册记录。"""

    __tablename__ = "content_routes"
    __table_args__ = (
        UniqueConstraint("path", name="uq_content_routes_path"),
        Index("ix_content_route_owner_locale", "owner_type", "owner_id", "locale_id"),
        Index(
            "ux_content_routes_one_canonical",
            "owner_type",
            "owner_id",
            "locale_id",
            unique=True,
            postgresql_where=text("is_canonical"),
            sqlite_where=text("is_canonical = 1"),
        ),
        {"comment": "内容路由注册表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, comment="主实体ID"
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="路由语言ID",
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False, comment="站内绝对路径")
    is_canonical: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False, comment="是否规范路由"
    )
    indexable: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False, comment="是否允许索引"
    )
    active: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False, comment="是否对外生效"
    )


class ContentRevision(UuidPrimaryKeyMixin, Base):
    """保存不可变内容快照，供预览、审计与回滚流程使用。"""

    __tablename__ = "content_revisions"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "locale_id", "revision_no", name="uq_content_revision_number"
        ),
        {"comment": "内容修订快照表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, comment="主实体ID"
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="修订语言ID",
    )
    revision_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="同一内容语言下的修订序号"
    )
    snapshot_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE, nullable=False, comment="内容快照JSON"
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="变更用户ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="修订创建时间"
    )


class SitePage(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存由系统识别的固定站点页面身份。"""

    __tablename__ = "site_pages"
    __table_args__ = (
        UniqueConstraint("system_key", name="uq_site_pages_system_key"),
        CheckConstraint("system_key IN ('products')", name="site_page_system_key_value"),
        CheckConstraint(
            "status IN ('enabled','disabled','retired')", name="site_page_status_value"
        ),
        {"comment": "固定站点页面表"},
    )

    system_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="系统稳定页面键：仅允许products"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="enabled",
        server_default="enabled",
        comment="页面状态：enabled启用，disabled禁用，retired退役",
    )


class SitePageTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """保存固定站点页面的真实语言名称。"""

    __tablename__ = "site_page_translations"
    __table_args__ = (
        UniqueConstraint("site_page_id", "locale_id", name="uq_site_page_translation_locale"),
        {"comment": "固定站点页面翻译表"},
    )

    site_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("site_pages.id", ondelete="CASCADE"),
        nullable=False,
        comment="固定页面ID",
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="语言ID",
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, comment="页面显示名称")
