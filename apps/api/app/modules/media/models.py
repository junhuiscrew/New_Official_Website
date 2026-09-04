"""公共媒体与下载资源模型，明确 public-media/private-rfq 边界。"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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

_JSON = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class MediaAsset(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """统一媒体资产；visibility 决定存储桶与访问边界。"""

    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint("visibility IN ('public','private')", name="media_asset_visibility_value"),
        CheckConstraint("media_type IN ('image','video','document','cad','other')", name="media_asset_media_type_value"),
        CheckConstraint("malware_scan_status IN ('pending','clean','infected','failed','not_required')", name="media_asset_scan_value"),
        CheckConstraint("upload_status IN ('pending','ready','rejected','quarantined')", name="media_asset_upload_status_value"),
        CheckConstraint("(visibility = 'public' AND storage_bucket = 'public-media') OR (visibility = 'private' AND storage_bucket = 'private-rfq')", name="media_asset_bucket_visibility_match"),
        UniqueConstraint("storage_bucket", "storage_key", name="uq_media_asset_storage_key"),
        {"comment": "统一媒体资产表"},
    )

    visibility: Mapped[str] = mapped_column(String(16), nullable=False, comment="可见性：public公开，private私有")
    media_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="媒体类型")
    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False, comment="对象存储桶")
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, comment="对象存储键")
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始文件名")
    sanitized_filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="清洗后文件名")
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False, comment="检测后的MIME类型")
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False, comment="文件扩展名")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件大小字节")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA256校验值")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="图片宽度")
    height: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="图片高度")
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True, comment="视频时长秒")
    checksum_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, comment="是否校验SHA256")
    malware_scan_status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False, comment="恶意软件扫描状态")
    upload_status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False, comment="上传状态")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="上传用户ID")


class MediaAssetTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """媒体公开多语言元数据。"""

    __tablename__ = "media_asset_translations"
    __table_args__ = (UniqueConstraint("media_asset_id", "locale_id", name="uq_media_asset_translation_locale"), {"comment": "媒体翻译表"})

    media_asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, comment="媒体ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="图片Alt文本")
    title: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="媒体标题")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True, comment="媒体说明")


class DownloadResource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """公开下载落地资源，不直接暴露私有桶。"""

    __tablename__ = "download_resources"
    __table_args__ = (CheckConstraint("status IN ('enabled','disabled','retired')", name="download_resource_status_value"), {"comment": "公开下载资源表"})

    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, comment="稳定下载Slug")
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="资源类型")
    status: Mapped[str] = mapped_column(String(16), default="enabled", server_default="enabled", nullable=False, comment="状态")
    media_asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False, comment="公开媒体ID")
    version_label: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="版本标签")
    published_date: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="发布日期")
    requires_form: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False, comment="是否需要表单")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False, comment="排序")


class DownloadResourceTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """下载资源翻译。"""

    __tablename__ = "download_resource_translations"
    __table_args__ = (UniqueConstraint("download_resource_id", "locale_id", name="uq_download_resource_translation_locale"), {"comment": "下载资源翻译表"})

    download_resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("download_resources.id", ondelete="CASCADE"), nullable=False, comment="下载资源ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    title: Mapped[str] = mapped_column(String(320), nullable=False, comment="下载标题")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="下载摘要")

