"""创建 Phase 3.3 Structured Core Catalog 表。

Revision ID: 20260904_0004
Revises: 20260904_0003
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0004"
down_revision: str | None = "20260904_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIFECYCLE = "status IN ('enabled','disabled','retired')"


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """返回所有核心表复用的创建/更新时间字段。"""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="更新时间"),
    )


def _master_table(
    name: str,
    label: str,
    *columns: sa.Column,
    status_name: str = "status",
    include_featured: bool = True,
) -> None:
    """创建带 UUID、生命周期状态和排序字段的主实体表。"""
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        *columns,
        sa.Column(status_name, sa.String(16), nullable=False, server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"),
        *(
            [
                sa.Column(
                    "featured",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                    comment="是否推荐",
                )
            ]
            if include_featured
            else []
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name=f"{name}_status_value"),
        comment=label,
    )


def _translation_table(name: str, label: str, owner_column: str, owner_table: str, *fields: sa.Column) -> None:
    """创建核心实体的多语言翻译表。"""
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column(owner_column, sa.Uuid(), sa.ForeignKey(f"{owner_table}.id", ondelete="CASCADE"), nullable=False, comment="主实体ID"),
        sa.Column("locale_id", sa.Uuid(), sa.ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID"),
        *fields,
        *_timestamps(),
        sa.UniqueConstraint(owner_column, "locale_id", name=f"uq_{name}_owner_locale"),
        comment=label,
    )


def _relation_table(name: str, left: str, left_table: str, right: str, right_table: str) -> None:
    """创建显式双向关系表和稳定排序字段。"""
    op.create_table(
        name,
        sa.Column(left, sa.Uuid(), sa.ForeignKey(f"{left_table}.id", ondelete="CASCADE"), primary_key=True, comment="左侧实体ID"),
        sa.Column(right, sa.Uuid(), sa.ForeignKey(f"{right_table}.id", ondelete="CASCADE"), primary_key=True, comment="右侧实体ID"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="关系排序"),
        sa.Column("recommendation_level", sa.String(32), nullable=True, comment="推荐级别"),
        sa.Column("notes", sa.Text(), nullable=True, comment="关系备注"),
        comment=f"{name} 显式关系表",
    )


def upgrade() -> None:
    """创建 Structured Core 主实体、翻译、规格与显式关系表。"""
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=True, comment="父分类ID"),
        sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定分类Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="分类排序"),
        sa.Column("cover_media_id", sa.Uuid(), nullable=True, comment="封面媒体ID"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="product_category_status_value"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="product_category_no_self_parent"),
        comment="产品分类表",
    )
    _master_table("materials", "材料主实体表", sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定材料Slug"), sa.Column("abbreviation", sa.String(40), nullable=True, comment="材料缩写"))
    _master_table("technologies", "工艺技术主实体表", sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定技术Slug"))
    _master_table("applications", "应用场景主实体表", sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定应用Slug"))
    _master_table("solutions", "解决方案主实体表", sa.Column("slug", sa.String(160), nullable=False, unique=True, comment="稳定方案Slug"))
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=False, comment="所属分类ID"),
        sa.Column("code", sa.String(100), nullable=True, comment="内部产品编码"),
        sa.Column("slug", sa.String(180), nullable=False, unique=True, comment="稳定产品Slug"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否推荐产品"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="产品排序"),
        sa.Column("primary_media_id", sa.Uuid(), nullable=True, comment="主媒体ID"),
        *_timestamps(),
        sa.CheckConstraint(_LIFECYCLE, name="product_status_value"),
        comment="产品主实体表",
    )
    op.create_table(
        "product_models",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, comment="产品ID"),
        sa.Column("model_code", sa.String(100), nullable=False, comment="型号编码"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="型号排序"),
        *_timestamps(),
        sa.UniqueConstraint("product_id", "model_code", name="uq_product_models_product_code"),
        sa.CheckConstraint(_LIFECYCLE, name="product_model_status_value"),
        comment="产品型号表",
    )
    _master_table(
        "specification_groups",
        "规格分组表",
        sa.Column("code", sa.String(100), nullable=False, unique=True, comment="规格分组编码"),
        include_featured=False,
    )
    op.create_table(
        "specification_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("group_id", sa.Uuid(), sa.ForeignKey("specification_groups.id", ondelete="CASCADE"), nullable=False, comment="规格分组ID"),
        sa.Column("code", sa.String(100), nullable=False, comment="规格定义编码"),
        sa.Column("value_type", sa.String(16), nullable=False, comment="值类型"),
        sa.Column("default_unit", sa.String(32), nullable=True, comment="默认单位"),
        sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否可筛选"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="定义排序"),
        sa.Column("status", sa.String(16), nullable=False, server_default="enabled", comment="业务状态"),
        *_timestamps(),
        sa.UniqueConstraint("group_id", "code", name="uq_specification_definitions_group_code"),
        sa.CheckConstraint("value_type IN ('text','number','range','boolean','enum')", name="specification_definition_type_value"),
        sa.CheckConstraint(_LIFECYCLE, name="specification_definition_status_value"),
        comment="规格定义表",
    )
    op.create_table(
        "product_spec_values",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, comment="主键ID"),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=True, comment="产品ID，与型号ID二选一"),
        sa.Column("product_model_id", sa.Uuid(), sa.ForeignKey("product_models.id", ondelete="CASCADE"), nullable=True, comment="产品型号ID，与产品ID二选一"),
        sa.Column("definition_id", sa.Uuid(), sa.ForeignKey("specification_definitions.id", ondelete="RESTRICT"), nullable=False, comment="规格定义ID"),
        sa.Column("value_text", sa.Text(), nullable=True, comment="文本值"),
        sa.Column("value_number", sa.Numeric(18, 6), nullable=True, comment="数值"),
        sa.Column("value_min", sa.Numeric(18, 6), nullable=True, comment="范围下限"),
        sa.Column("value_max", sa.Numeric(18, 6), nullable=True, comment="范围上限"),
        sa.Column("value_boolean", sa.Boolean(), nullable=True, comment="布尔值"),
        sa.Column("enum_value", sa.String(100), nullable=True, comment="枚举值"),
        sa.Column("unit_override", sa.String(32), nullable=True, comment="覆盖单位"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="规格排序"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否公开展示"),
        *_timestamps(),
        sa.CheckConstraint("(product_id IS NOT NULL) <> (product_model_id IS NOT NULL)", name="product_spec_owner_xor"),
        sa.CheckConstraint("(CASE WHEN value_text IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN value_number IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN value_min IS NOT NULL OR value_max IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN value_boolean IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN enum_value IS NOT NULL THEN 1 ELSE 0 END) = 1", name="product_spec_exactly_one_value"),
        sa.CheckConstraint("value_min IS NULL OR value_max IS NULL OR value_min <= value_max", name="product_spec_valid_range"),
        sa.UniqueConstraint("product_id", "definition_id", name="uq_product_spec_product_definition"),
        sa.UniqueConstraint("product_model_id", "definition_id", name="uq_product_spec_model_definition"),
        comment="产品结构化规格值表",
    )

    _translation_table("product_category_translations", "产品分类翻译表", "category_id", "product_categories", sa.Column("name", sa.String(200), nullable=False, comment="分类名称"), sa.Column("short_description", sa.Text(), nullable=True, comment="分类简述"), sa.Column("description", sa.Text(), nullable=True, comment="分类描述"))
    _translation_table("product_translations", "产品翻译表", "product_id", "products", sa.Column("name", sa.String(240), nullable=False, comment="产品名称"), sa.Column("short_description", sa.Text(), nullable=True, comment="产品简述"), sa.Column("description", sa.Text(), nullable=True, comment="产品描述"), sa.Column("highlights_jsonb", sa.JSON(), nullable=True, comment="产品亮点结构化JSON"))
    _translation_table("product_model_translations", "产品型号翻译表", "product_model_id", "product_models", sa.Column("name", sa.String(240), nullable=False, comment="型号名称"), sa.Column("description", sa.Text(), nullable=True, comment="型号描述"))
    _translation_table("specification_group_translations", "规格分组翻译表", "group_id", "specification_groups", sa.Column("name", sa.String(200), nullable=False, comment="分组名称"))
    _translation_table("specification_definition_translations", "规格定义翻译表", "definition_id", "specification_definitions", sa.Column("name", sa.String(200), nullable=False, comment="规格名称"), sa.Column("help_text", sa.Text(), nullable=True, comment="帮助说明"))
    _translation_table("material_translations", "材料翻译表", "material_id", "materials", sa.Column("name", sa.String(200), nullable=False, comment="材料名称"), sa.Column("definition", sa.Text(), nullable=True, comment="材料定义"), sa.Column("processing_characteristics", sa.Text(), nullable=True, comment="加工特性"), sa.Column("screw_impact", sa.Text(), nullable=True, comment="对螺杆影响"), sa.Column("recommendations", sa.Text(), nullable=True, comment="推荐说明"), sa.Column("limitations", sa.Text(), nullable=True, comment="限制条件"))
    _translation_table("technology_translations", "技术翻译表", "technology_id", "technologies", sa.Column("name", sa.String(200), nullable=False, comment="技术名称"), sa.Column("definition", sa.Text(), nullable=True, comment="技术定义"), sa.Column("process_description", sa.Text(), nullable=True, comment="工艺描述"), sa.Column("benefits", sa.Text(), nullable=True, comment="优势"), sa.Column("limitations", sa.Text(), nullable=True, comment="限制条件"))
    _translation_table("application_translations", "应用翻译表", "application_id", "applications", sa.Column("name", sa.String(200), nullable=False, comment="应用名称"), sa.Column("description", sa.Text(), nullable=True, comment="应用描述"), sa.Column("technical_requirements", sa.Text(), nullable=True, comment="技术要求"), sa.Column("common_problems", sa.Text(), nullable=True, comment="常见问题"))
    _translation_table("solution_translations", "解决方案翻译表", "solution_id", "solutions", sa.Column("name", sa.String(200), nullable=False, comment="方案名称"), sa.Column("definition", sa.Text(), nullable=True, comment="方案定义"), sa.Column("symptoms", sa.Text(), nullable=True, comment="症状"), sa.Column("causes", sa.Text(), nullable=True, comment="原因"), sa.Column("diagnosis", sa.Text(), nullable=True, comment="诊断"), sa.Column("solution", sa.Text(), nullable=True, comment="解决方案"), sa.Column("limitations", sa.Text(), nullable=True, comment="限制条件"))

    _relation_table("product_materials", "product_id", "products", "material_id", "materials")
    _relation_table("product_technologies", "product_id", "products", "technology_id", "technologies")
    _relation_table("product_applications", "product_id", "products", "application_id", "applications")
    _relation_table("product_solutions", "product_id", "products", "solution_id", "solutions")
    _relation_table("material_technologies", "material_id", "materials", "technology_id", "technologies")
    _relation_table("material_solutions", "material_id", "materials", "solution_id", "solutions")
    _relation_table("application_solutions", "application_id", "applications", "solution_id", "solutions")


def downgrade() -> None:
    """按外键依赖反向删除 Phase 3.3 表。"""
    for table in (
        "application_solutions",
        "material_solutions",
        "material_technologies",
        "product_solutions",
        "product_applications",
        "product_technologies",
        "product_materials",
        "solution_translations",
        "application_translations",
        "technology_translations",
        "material_translations",
        "specification_definition_translations",
        "specification_group_translations",
        "product_model_translations",
        "product_translations",
        "product_category_translations",
        "product_spec_values",
        "specification_definitions",
        "specification_groups",
        "product_models",
        "products",
        "solutions",
        "applications",
        "technologies",
        "materials",
        "product_categories",
    ):
        op.drop_table(table)
