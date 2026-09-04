"""统一 SEO、GEO、来源引用与 Redirect ORM 模型。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
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

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class SeoDocument(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """跨实体复用的单语言 SEO 文档。"""

    __tablename__ = "seo_documents"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_seo_document_owner_locale"),
        {"comment": "统一SEO文档表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, comment="主实体ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    seo_title: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="SEO标题")
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Meta描述")
    canonical_override: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="经授权覆盖的规范URL")
    robots_index: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", comment="是否允许搜索引擎索引")
    robots_follow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", comment="是否允许搜索引擎跟踪链接")
    og_title: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="Open Graph标题")
    og_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Open Graph描述")
    og_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="Open Graph媒体ID")
    schema_override_jsonb: Mapped[dict[str, Any] | None] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=True, comment="受控Schema覆盖JSON")


class GeoDocument(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """跨实体复用且必须与可见内容一致的 GEO 文档。"""

    __tablename__ = "geo_documents"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_geo_document_owner_locale"),
        {"comment": "统一GEO文档表"},
    )

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="主实体类型")
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, comment="主实体ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    direct_answer: Mapped[str | None] = mapped_column(Text, nullable=True, comment="页面可见的直接答案")
    target_questions_json: Mapped[list[str]] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=False, default=list, comment="目标问题JSON数组")
    key_facts_json: Mapped[list[str]] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=False, default=list, comment="页面可见关键事实JSON数组")
    evidence_json: Mapped[list[str]] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=False, default=list, comment="页面可见证据JSON数组")
    related_questions_json: Mapped[list[str]] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=False, default=list, comment="相关问题JSON数组")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("author_experts.id", ondelete="SET NULL"), nullable=True, comment="真实审核专家ID")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近事实复核时间")


class SourceCitation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """可核验的 GEO 或 Knowledge 来源引用。"""

    __tablename__ = "source_citations"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('official','standard','technical-paper','manufacturer','internal-first-party','case-evidence','other')",
            name="source_citation_type_value",
        ),
        CheckConstraint("geo_document_id IS NOT NULL OR article_id IS NOT NULL", name="source_citation_owner_required"),
        {"comment": "来源引用表"},
    )

    geo_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("geo_documents.id", ondelete="CASCADE"), nullable=True, comment="GEO文档ID")
    article_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=True, comment="知识文章ID")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="来源标题")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, comment="来源URL")
    publisher: Mapped[str | None] = mapped_column(String(240), nullable=True, comment="发布机构")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="来源发布日期")
    access_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="来源访问日期")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="来源类型")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="引用排序")


class RedirectRule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """精确路径 Redirect Manager 规则。"""

    __tablename__ = "redirect_rules"
    __table_args__ = (
        UniqueConstraint("source_host", "source_path", name="uq_redirect_rule_source"),
        CheckConstraint("status_code IN (301,302,307,308)", name="redirect_rule_status_code_value"),
        {"comment": "重定向规则表"},
    )

    source_host: Mapped[str] = mapped_column(String(255), nullable=False, comment="来源主机名")
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="来源精确路径")
    target_url: Mapped[str] = mapped_column(String(1500), nullable=False, comment="目标绝对URL")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=301, server_default="301", comment="HTTP状态码：301或308永久，302或307临时")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", comment="规则是否启用")
    hit_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0", comment="规则命中次数")
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近命中时间")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内部备注")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建用户ID")
