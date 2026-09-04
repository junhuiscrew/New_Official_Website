"""创建 Phase 3.4 Authority Content 表。

Revision ID: 20260904_0006
Revises: 20260904_0005
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0006"
down_revision: str | None = "20260904_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIFECYCLE = "status IN ('enabled','disabled','retired')"


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """返回统一创建与更新时间字段。"""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="更新时间"),
    )


def _relation(
    table_name: str,
    left_column: str,
    left_table: str,
    right_column: str,
    right_table: str,
) -> None:
    """创建带稳定排序的显式关系表。"""
    op.create_table(
        table_name,
        sa.Column(left_column, sa.Uuid(), sa.ForeignKey(f"{left_table}.id", ondelete="CASCADE"), primary_key=True, comment="左侧实体ID"),
        sa.Column(right_column, sa.Uuid(), sa.ForeignKey(f"{right_table}.id", ondelete="CASCADE"), primary_key=True, comment="右侧实体ID"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="关系排序"),
        comment=f"{table_name} 显式关系表",
    )


def upgrade() -> None:
    """创建案例、知识、FAQ、真实作者专家与全部显式关系。"""
    op.create_table(
        "case_studies",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("slug", sa.String(180), nullable=False, unique=True, comment="稳定案例Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        sa.Column("country_code", sa.String(2), nullable=True, comment="案例国家二字代码"),
        sa.Column("industry", sa.String(160), nullable=True, comment="客户所属行业"),
        sa.Column("machine_brand", sa.String(160), nullable=True, comment="设备品牌"),
        sa.Column("machine_model", sa.String(160), nullable=True, comment="设备型号"),
        sa.Column("screw_diameter", sa.String(80), nullable=True, comment="螺杆直径描述"),
        sa.Column("processed_material_text", sa.Text(), nullable=True, comment="加工材料内部描述"),
        sa.Column("filler_percentage", sa.String(80), nullable=True, comment="填充比例描述"),
        sa.Column("client_name", sa.String(240), nullable=True, comment="客户真实名称，仅内部使用"),
        sa.Column("client_address", sa.Text(), nullable=True, comment="客户真实地址，仅内部使用"),
        sa.Column("client_logo_media_id", sa.Uuid(), nullable=True, comment="客户Logo媒体ID，仅内部使用"),
        sa.Column("client_name_public", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否获得客户名称公开许可"),
        sa.Column("client_logo_public", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否获得客户Logo公开许可"),
        sa.Column("client_address_public", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否获得客户地址公开许可"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否推荐案例"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="案例排序"),
        sa.Column("primary_media_id", sa.Uuid(), nullable=True, comment="案例主媒体ID"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="case_study_status_value"),
        comment="客户案例主实体表",
    )
    op.create_table(
        "case_study_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("case_study_id", sa.Uuid(), sa.ForeignKey("case_studies.id", ondelete="CASCADE"), nullable=False, comment="客户案例ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("title", sa.String(240), nullable=False, comment="案例标题"),
        sa.Column("summary", sa.Text(), nullable=True, comment="案例摘要"),
        sa.Column("client_description", sa.Text(), nullable=True, comment="经许可的客户公开描述"),
        sa.Column("problem", sa.Text(), nullable=True, comment="客户问题"),
        sa.Column("analysis", sa.Text(), nullable=True, comment="技术分析"),
        sa.Column("solution", sa.Text(), nullable=True, comment="实施方案"),
        sa.Column("result", sa.Text(), nullable=True, comment="实施结果"),
        sa.Column("engineer_comment", sa.Text(), nullable=True, comment="工程师点评"),
        *_timestamps(),
        sa.UniqueConstraint("case_study_id", "locale_id", name="uq_case_study_translation_locale"),
        comment="客户案例翻译表",
    )
    op.create_table(
        "knowledge_categories",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("slug", sa.String(120), nullable=False, unique=True, comment="稳定知识分类Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="分类排序"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="knowledge_category_status_value"),
        comment="知识分类表",
    )
    op.create_table(
        "knowledge_category_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("knowledge_categories.id", ondelete="CASCADE"), nullable=False, comment="知识分类ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("name", sa.String(160), nullable=False, comment="分类名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="分类说明"),
        *_timestamps(),
        sa.UniqueConstraint("category_id", "locale_id", name="uq_knowledge_category_translation_locale"),
        comment="知识分类翻译表",
    )
    op.create_table(
        "author_experts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定作者专家Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        sa.Column("role_type", sa.String(24), nullable=False, comment="人物类型：author作者，expert专家，author_expert兼任"),
        sa.Column("is_real_person_verified", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否已核验为真实人物"),
        sa.Column("public_profile_enabled", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否允许发布独立公开资料页"),
        sa.Column("profile_media_id", sa.Uuid(), nullable=True, comment="公开头像媒体ID"),
        sa.Column("public_email", sa.String(320), nullable=True, comment="经本人许可的公开邮箱"),
        sa.Column("years_experience", sa.Integer(), nullable=True, comment="公开从业年限"),
        sa.Column("linkedin_url", sa.String(500), nullable=True, comment="公开LinkedIn链接"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="人物排序"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="author_expert_status_value"),
        sa.CheckConstraint("role_type IN ('author','expert','author_expert')", name="author_expert_role_type_value"),
        comment="真实作者专家表",
    )
    op.create_table(
        "author_expert_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("author_expert_id", sa.Uuid(), sa.ForeignKey("author_experts.id", ondelete="CASCADE"), nullable=False, comment="作者专家ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("name", sa.String(160), nullable=False, comment="人物姓名"),
        sa.Column("job_title", sa.String(200), nullable=True, comment="公开职位"),
        sa.Column("short_bio", sa.Text(), nullable=True, comment="公开短简介"),
        sa.Column("expertise_json", sa.JSON(), nullable=False, comment="专业领域JSON数组"),
        *_timestamps(),
        sa.UniqueConstraint("author_expert_id", "locale_id", name="uq_author_expert_translation_locale"),
        comment="作者专家翻译表",
    )
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("knowledge_categories.id", ondelete="RESTRICT"), nullable=False, comment="知识分类ID"),
        sa.Column("slug", sa.String(180), nullable=False, unique=True, comment="稳定文章Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("author_experts.id", ondelete="RESTRICT"), nullable=False, comment="真实作者ID"),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("author_experts.id", ondelete="SET NULL"), nullable=True, comment="真实审核专家ID"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否推荐文章"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="文章排序"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True, comment="最近专业复核时间"),
        sa.Column("primary_media_id", sa.Uuid(), nullable=True, comment="文章主媒体ID"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="knowledge_article_status_value"),
        comment="知识文章主实体表",
    )
    op.create_table(
        "knowledge_article_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False, comment="知识文章ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("title", sa.String(260), nullable=False, comment="文章标题"),
        sa.Column("summary", sa.Text(), nullable=True, comment="文章摘要"),
        sa.Column("body_markdown", sa.Text(), nullable=False, comment="安全Markdown正文"),
        *_timestamps(),
        sa.UniqueConstraint("article_id", "locale_id", name="uq_knowledge_article_translation_locale"),
        comment="知识文章翻译表",
    )
    op.create_table(
        "faqs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="常见问题排序"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="faq_status_value"),
        comment="常见问题主实体表",
    )
    op.create_table(
        "faq_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("faq_id", sa.Uuid(), sa.ForeignKey("faqs.id", ondelete="CASCADE"), nullable=False, comment="常见问题ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        sa.Column("question", sa.String(500), nullable=False, comment="公开问题"),
        sa.Column("answer", sa.Text(), nullable=False, comment="公开答案"),
        *_timestamps(),
        sa.UniqueConstraint("faq_id", "locale_id", name="uq_faq_translation_locale"),
        comment="常见问题翻译表",
    )

    for args in (
        ("case_products", "case_study_id", "case_studies", "product_id", "products"),
        ("case_materials", "case_study_id", "case_studies", "material_id", "materials"),
        ("case_technologies", "case_study_id", "case_studies", "technology_id", "technologies"),
        ("case_applications", "case_study_id", "case_studies", "application_id", "applications"),
        ("case_solutions", "case_study_id", "case_studies", "solution_id", "solutions"),
        ("article_products", "article_id", "knowledge_articles", "product_id", "products"),
        ("article_materials", "article_id", "knowledge_articles", "material_id", "materials"),
        ("article_technologies", "article_id", "knowledge_articles", "technology_id", "technologies"),
        ("article_applications", "article_id", "knowledge_articles", "application_id", "applications"),
        ("article_solutions", "article_id", "knowledge_articles", "solution_id", "solutions"),
        ("article_cases", "article_id", "knowledge_articles", "case_study_id", "case_studies"),
        ("article_faqs", "article_id", "knowledge_articles", "faq_id", "faqs"),
        ("faq_products", "faq_id", "faqs", "product_id", "products"),
        ("faq_materials", "faq_id", "faqs", "material_id", "materials"),
        ("faq_solutions", "faq_id", "faqs", "solution_id", "solutions"),
        ("faq_articles", "faq_id", "faqs", "article_id", "knowledge_articles"),
        ("faq_cases", "faq_id", "faqs", "case_study_id", "case_studies"),
    ):
        _relation(*args)


def downgrade() -> None:
    """按外键依赖逆序删除 Authority Content 表。"""
    for table_name in (
        "faq_cases", "faq_articles", "faq_solutions", "faq_materials", "faq_products",
        "article_faqs", "article_cases", "article_solutions", "article_applications",
        "article_technologies", "article_materials", "article_products", "case_solutions",
        "case_applications", "case_technologies", "case_materials", "case_products",
    ):
        op.drop_table(table_name)
    for table_name in (
        "faq_translations", "faqs", "knowledge_article_translations", "knowledge_articles",
        "author_expert_translations", "author_experts", "knowledge_category_translations",
        "knowledge_categories", "case_study_translations", "case_studies",
    ):
        op.drop_table(table_name)
