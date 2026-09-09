"""Demo R2 批次来源追踪与多类型内容媒体关系模型。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.modules.media.models import MediaAsset  # noqa: F401  确保外键目标进入统一 metadata。

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class DemoContentRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    记录一条演示内容在当前独立数据库中的来源、别名和初始指纹。

    输入：由显式 Demo 初始化器写入批次、实体和来源信息。
    输出：可用于幂等导入、冲突检测和后续替换追踪的持久记录。
    """

    __tablename__ = "demo_content_records"
    __table_args__ = (
        UniqueConstraint("batch_id", "alias", name="uq_demo_content_batch_alias"),
        UniqueConstraint(
            "batch_id",
            "entity_type",
            "entity_id",
            name="uq_demo_content_batch_entity",
        ),
        CheckConstraint(
            "content_origin IN ('synthetic_demo','approved_public_copy','generated_demo','licensed_demo')",
            name="demo_content_origin",
        ),
        CheckConstraint(
            "replacement_status IN ('demo_active','replaced','conflict','retired')",
            name="demo_content_replacement_status",
        ),
        CheckConstraint(
            "length(initial_fingerprint) = 64",
            name="demo_content_fingerprint_length",
        ),
        {"comment": "演示内容批次来源与替换状态表"},
    )

    batch_id: Mapped[str] = mapped_column(String(80), nullable=False, comment="演示批次ID")
    alias: Mapped[str] = mapped_column(String(160), nullable=False, comment="包内稳定演示别名")
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="业务实体类型")
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, comment="独立演示库实体ID")
    content_origin: Mapped[str] = mapped_column(String(32), nullable=False, comment="内容来源类型")
    initial_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, comment="首次受控导入内容SHA256")
    replacement_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="demo_active",
        server_default="demo_active",
        comment="替换状态：demo_active演示中，replaced已替换，conflict人工修改冲突，retired停用",
    )
    source_metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(
        _JSON_DOCUMENT_TYPE,
        nullable=False,
        default=dict,
        comment="生成来源、许可、原始样例和替换说明JSON",
    )


class ContentMediaLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """
    为任意 CMS 内容建立有类型且有序的媒体引用。

    输入：内容 owner、媒体资产、用途角色和排序。
    输出：前台图库、视频、封面与后台引用位置的统一关系记录。
    """

    __tablename__ = "content_media_links"
    __table_args__ = (
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "role",
            "sort_order",
            name="uq_content_media_owner_role_order",
        ),
        CheckConstraint(
            "role IN ('primary','gallery','video','video_poster','download','cover','hero')",
            name="content_media_role",
        ),
        {"comment": "跨内容类型媒体引用关系表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="内容主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, comment="内容主实体ID")
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
        comment="媒体资产ID",
    )
    role: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="媒体用途：主图、图库、视频、视频封面、下载、封面或首页Hero",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="同一用途下的媒体排序",
    )
