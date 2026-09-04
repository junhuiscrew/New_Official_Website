"""创建 Phase 3.4 SEO/GEO、来源引用与 Redirect 表。

Revision ID: 20260904_0007
Revises: 20260904_0006
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0007"
down_revision: str | None = "20260904_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """返回统一创建与更新时间字段。"""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="更新时间"),
    )


def upgrade() -> None:
    """创建统一 SEO/GEO、来源引用和重定向规则表。"""
    op.create_table(
        "seo_documents",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("owner_type", sa.String(100), nullable=False, comment="主实体类型"),
        sa.Column("owner_id", sa.Uuid(), nullable=False, comment="主实体ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("seo_title", sa.String(320), nullable=True, comment="SEO标题"),
        sa.Column("meta_description", sa.Text(), nullable=True, comment="Meta描述"),
        sa.Column("canonical_override", sa.String(500), nullable=True, comment="经授权覆盖的规范URL"),
        sa.Column("robots_index", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否允许搜索引擎索引"),
        sa.Column("robots_follow", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否允许搜索引擎跟踪链接"),
        sa.Column("og_title", sa.String(320), nullable=True, comment="Open Graph标题"),
        sa.Column("og_description", sa.Text(), nullable=True, comment="Open Graph描述"),
        sa.Column("og_media_id", sa.Uuid(), nullable=True, comment="Open Graph媒体ID"),
        sa.Column("schema_override_jsonb", sa.JSON(), nullable=True, comment="受控Schema覆盖JSON"),
        *_timestamps(),
        sa.UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_seo_document_owner_locale"),
        comment="统一SEO文档表",
    )
    op.create_table(
        "geo_documents",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("owner_type", sa.String(100), nullable=False, comment="主实体类型"),
        sa.Column("owner_id", sa.Uuid(), nullable=False, comment="主实体ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("direct_answer", sa.Text(), nullable=True, comment="页面可见的直接答案"),
        sa.Column("target_questions_json", sa.JSON(), nullable=False, comment="目标问题JSON数组"),
        sa.Column("key_facts_json", sa.JSON(), nullable=False, comment="页面可见关键事实JSON数组"),
        sa.Column("evidence_json", sa.JSON(), nullable=False, comment="页面可见证据JSON数组"),
        sa.Column("related_questions_json", sa.JSON(), nullable=False, comment="相关问题JSON数组"),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("author_experts.id", ondelete="SET NULL"), nullable=True, comment="真实审核专家ID"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True, comment="最近事实复核时间"),
        *_timestamps(),
        sa.UniqueConstraint("owner_type", "owner_id", "locale_id", name="uq_geo_document_owner_locale"),
        comment="统一GEO文档表",
    )
    op.create_table(
        "source_citations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("geo_document_id", sa.Uuid(), sa.ForeignKey("geo_documents.id", ondelete="CASCADE"), nullable=True, comment="GEO文档ID"),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=True, comment="知识文章ID"),
        sa.Column("title", sa.String(500), nullable=False, comment="来源标题"),
        sa.Column("url", sa.String(1000), nullable=False, comment="来源URL"),
        sa.Column("publisher", sa.String(240), nullable=True, comment="发布机构"),
        sa.Column("publication_date", sa.Date(), nullable=True, comment="来源发布日期"),
        sa.Column("access_date", sa.Date(), nullable=True, comment="来源访问日期"),
        sa.Column("source_type", sa.String(32), nullable=False, comment="来源类型"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="引用排序"),
        *_timestamps(),
        sa.CheckConstraint("source_type IN ('official','standard','technical-paper','manufacturer','internal-first-party','case-evidence','other')", name="source_citation_type_value"),
        sa.CheckConstraint("geo_document_id IS NOT NULL OR article_id IS NOT NULL", name="source_citation_owner_required"),
        comment="来源引用表",
    )
    op.create_table(
        "redirect_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("source_host", sa.String(255), nullable=False, comment="来源主机名"),
        sa.Column("source_path", sa.String(1000), nullable=False, comment="来源精确路径"),
        sa.Column("target_url", sa.String(1500), nullable=False, comment="目标绝对URL"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="301", comment="HTTP状态码：301或308永久，302或307临时"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true(), comment="规则是否启用"),
        sa.Column("hit_count", sa.BigInteger(), nullable=False, server_default="0", comment="规则命中次数"),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True, comment="最近命中时间"),
        sa.Column("notes", sa.Text(), nullable=True, comment="内部备注"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建用户ID"),
        *_timestamps(),
        sa.UniqueConstraint("source_host", "source_path", name="uq_redirect_rule_source"),
        sa.CheckConstraint("status_code IN (301,302,307,308)", name="redirect_rule_status_code_value"),
        comment="重定向规则表",
    )


def downgrade() -> None:
    """按外键依赖逆序删除发现层表。"""
    op.drop_table("redirect_rules")
    op.drop_table("source_citations")
    op.drop_table("geo_documents")
    op.drop_table("seo_documents")
