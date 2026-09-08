"""Privacy P1 稳定页面指针与不可变政策版本模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin


class PrivacyNoticeVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    保存一份可审核并可被 RFQ 永久引用的隐私政策版本。

    输入：稳定页面、服务端版本号/标签、生效时间、克隆来源与创建用户。
    输出：PrivacyNoticeVersion ORM 实体；公开接口仅暴露 version_label，不暴露 UUID。
    """

    __tablename__ = "privacy_notice_versions"
    __table_args__ = (
        UniqueConstraint(
            "site_page_id",
            "version_no",
            name="uq_privacy_notice_version_number",
        ),
        CheckConstraint("version_no > 0", name="privacy_notice_version_number_positive"),
        CheckConstraint("row_version > 0", name="privacy_notice_row_version_positive"),
        {"comment": "隐私政策不可变版本表"},
    )

    site_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("site_pages.id", ondelete="RESTRICT"),
        nullable=False,
        comment="稳定隐私页面ID",
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="服务端版本序号")
    version_label: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, comment="服务端生成的公开版本标签"
    )
    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="政策生效时间"
    )
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="草稿乐观并发版本号",
    )
    cloned_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"),
        nullable=True,
        comment="克隆来源隐私版本ID",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建用户ID",
    )


class PrivacyNoticeVersionTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    保存隐私政策某个不可变版本的一种语言正文及服务端哈希。

    输入：政策版本、语言、标题、Markdown 正文、哈希算法及内容哈希。
    输出：PrivacyNoticeVersionTranslation ORM 实体；正文不保存可信 HTML。
    """

    __tablename__ = "privacy_notice_version_translations"
    __table_args__ = (
        UniqueConstraint(
            "privacy_notice_version_id",
            "locale_id",
            name="uq_privacy_notice_version_translation_locale",
        ),
        CheckConstraint(
            "((title IS NULL AND body_markdown IS NULL AND content_hash IS NULL) OR "
            "(title IS NOT NULL AND body_markdown IS NOT NULL AND content_hash IS NOT NULL))",
            name="privacy_translation_content_complete",
        ),
        {"comment": "隐私政策版本多语言正文表"},
    )

    privacy_notice_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"),
        nullable=False,
        comment="隐私政策版本ID",
    )
    locale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locales.id", ondelete="RESTRICT"),
        nullable=False,
        comment="政策语言ID",
    )
    title: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="规范化政策标题"
    )
    body_markdown: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="规范化且不含活动内容的Markdown正文"
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="规范化标题与正文的SHA-256十六进制哈希"
    )
    hash_algorithm: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="sha256-nfc-json-v1",
        server_default="sha256-nfc-json-v1",
        comment="内容哈希算法及规范化版本",
    )


class PrivacyPageState(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    保存稳定 Privacy 页面当前公开版本与后台草稿指针。

    输入：site_page_id、唯一公开指针 current_version_id 与工作草稿指针 draft_version_id。
    输出：PrivacyPageState ORM 实体；current_version_id 是唯一公开状态来源。
    """

    __tablename__ = "privacy_page_states"
    __table_args__ = (
        UniqueConstraint("site_page_id", name="uq_privacy_page_state_site_page"),
        CheckConstraint(
            "current_version_id IS NULL OR draft_version_id IS NULL OR "
            "current_version_id <> draft_version_id",
            name="privacy_page_distinct_pointers",
        ),
        {"comment": "隐私页面当前版本状态表"},
    )

    site_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("site_pages.id", ondelete="RESTRICT"),
        nullable=False,
        comment="稳定隐私页面ID",
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"),
        nullable=True,
        comment="当前唯一公开隐私版本ID",
    )
    draft_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("privacy_notice_versions.id", ondelete="RESTRICT"),
        nullable=True,
        comment="当前后台工作草稿版本ID",
    )
