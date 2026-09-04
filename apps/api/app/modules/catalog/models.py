"""Structured Core Catalog ORM 模型与显式关系表。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")
_LIFECYCLE_CHECK = "status IN ('enabled','disabled','retired')"
_SPEC_VALUE_CHECK = (
    "(CASE WHEN value_text IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN value_number IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN value_min IS NOT NULL OR value_max IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN value_boolean IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN enum_value IS NOT NULL THEN 1 ELSE 0 END) = 1"
)


class ProductCategory(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """产品分类树节点，使用 parent_id 形成可检测循环的层级。"""

    __tablename__ = "product_categories"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="product_category_status_value"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="product_category_no_self_parent"),
        {"comment": "产品分类表"},
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="父分类ID",
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, comment="稳定分类Slug")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="分类排序")
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="封面媒体ID")


class Product(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """产品主实体，公开状态由 Publication 与 Route 决定。"""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="product_status_value"),
        {"comment": "产品主实体表"},
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=False, comment="所属分类ID"
    )
    code: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="内部产品编码")
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, comment="稳定产品Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐产品")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="产品排序")
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="主媒体ID")


class ProductModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """产品型号，型号编码在单个产品范围内唯一。"""

    __tablename__ = "product_models"
    __table_args__ = (
        UniqueConstraint("product_id", "model_code", name="uq_product_models_product_code"),
        CheckConstraint(_LIFECYCLE_CHECK, name="product_model_status_value"),
        {"comment": "产品型号表"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, comment="产品ID")
    model_code: Mapped[str] = mapped_column(String(100), nullable=False, comment="型号编码")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="型号排序")


class SpecificationGroup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """规格分组，定义产品参数的展示和过滤边界。"""

    __tablename__ = "specification_groups"
    __table_args__ = (CheckConstraint(_LIFECYCLE_CHECK, name="specification_group_status_value"), {"comment": "规格分组表"})

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, comment="规格分组编码")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="分组排序")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")


class SpecificationDefinition(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """规格定义，限制规格值的类型和单位。"""

    __tablename__ = "specification_definitions"
    __table_args__ = (
        UniqueConstraint("group_id", "code", name="uq_specification_definitions_group_code"),
        CheckConstraint("value_type IN ('text','number','range','boolean','enum')", name="specification_definition_type_value"),
        CheckConstraint(_LIFECYCLE_CHECK, name="specification_definition_status_value"),
        {"comment": "规格定义表"},
    )

    group_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("specification_groups.id", ondelete="CASCADE"), nullable=False, comment="规格分组ID")
    code: Mapped[str] = mapped_column(String(100), nullable=False, comment="规格定义编码")
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="值类型：text、number、range、boolean、enum")
    default_unit: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="默认单位")
    is_filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否可筛选")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="定义排序")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")


class ProductSpecValue(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """产品或型号的动态规格值，数据库保证恰好一个所有者和值列。"""

    __tablename__ = "product_spec_values"
    __table_args__ = (
        CheckConstraint("(product_id IS NOT NULL) <> (product_model_id IS NOT NULL)", name="product_spec_owner_xor"),
        CheckConstraint(_SPEC_VALUE_CHECK, name="product_spec_exactly_one_value"),
        CheckConstraint("value_min IS NULL OR value_max IS NULL OR value_min <= value_max", name="product_spec_valid_range"),
        UniqueConstraint("product_id", "definition_id", name="uq_product_spec_product_definition"),
        UniqueConstraint("product_model_id", "definition_id", name="uq_product_spec_model_definition"),
        {"comment": "产品结构化规格值表"},
    )

    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=True, comment="产品ID，与型号ID二选一")
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_models.id", ondelete="CASCADE"), nullable=True, comment="产品型号ID，与产品ID二选一")
    definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("specification_definitions.id", ondelete="RESTRICT"), nullable=False, comment="规格定义ID")
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="文本值")
    value_number: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True, comment="数值")
    value_min: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True, comment="范围下限")
    value_max: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True, comment="范围上限")
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="布尔值")
    enum_value: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="枚举值")
    unit_override: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="覆盖单位")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="规格排序")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", comment="是否公开展示")


class Material(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """材料主实体。"""

    __tablename__ = "materials"
    __table_args__ = (CheckConstraint(_LIFECYCLE_CHECK, name="material_status_value"), {"comment": "材料主实体表"})

    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, comment="稳定材料Slug")
    abbreviation: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="材料缩写")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐材料")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="材料排序")


class Technology(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """表面、热处理及制造工艺主实体。"""

    __tablename__ = "technologies"
    __table_args__ = (CheckConstraint(_LIFECYCLE_CHECK, name="technology_status_value"), {"comment": "工艺技术主实体表"})

    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, comment="稳定技术Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐技术")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="技术排序")


class Application(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """行业或工艺应用场景主实体。"""

    __tablename__ = "applications"
    __table_args__ = (CheckConstraint(_LIFECYCLE_CHECK, name="application_status_value"), {"comment": "应用场景主实体表"})

    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, comment="稳定应用Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐应用")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="应用排序")


class Solution(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """问题诊断与解决方案主实体。"""

    __tablename__ = "solutions"
    __table_args__ = (CheckConstraint(_LIFECYCLE_CHECK, name="solution_status_value"), {"comment": "解决方案主实体表"})

    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, comment="稳定方案Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐方案")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="方案排序")


class _TranslationBase(UuidPrimaryKeyMixin, TimestampMixin):
    """核心实体翻译表共享的语言字段。"""

    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")


class ProductCategoryTranslation(_TranslationBase, Base):
    """产品分类翻译。"""

    __tablename__ = "product_category_translations"
    __table_args__ = (UniqueConstraint("category_id", "locale_id", name="uq_category_translation_locale"), {"comment": "产品分类翻译表"})
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=False, comment="分类ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="分类名称")
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="分类简述")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="分类描述")


class ProductTranslation(_TranslationBase, Base):
    """产品翻译。"""

    __tablename__ = "product_translations"
    __table_args__ = (UniqueConstraint("product_id", "locale_id", name="uq_product_translation_locale"), {"comment": "产品翻译表"})
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, comment="产品ID")
    name: Mapped[str] = mapped_column(String(240), nullable=False, comment="产品名称")
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="产品简述")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="产品描述")
    highlights_jsonb: Mapped[list[Any] | None] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=True, comment="产品亮点结构化JSON")


class ProductModelTranslation(_TranslationBase, Base):
    """产品型号翻译。"""

    __tablename__ = "product_model_translations"
    __table_args__ = (UniqueConstraint("product_model_id", "locale_id", name="uq_product_model_translation_locale"), {"comment": "产品型号翻译表"})
    product_model_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False, comment="产品型号ID")
    name: Mapped[str] = mapped_column(String(240), nullable=False, comment="型号名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="型号描述")


class SpecificationGroupTranslation(_TranslationBase, Base):
    """规格分组翻译。"""

    __tablename__ = "specification_group_translations"
    __table_args__ = (UniqueConstraint("group_id", "locale_id", name="uq_spec_group_translation_locale"), {"comment": "规格分组翻译表"})
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("specification_groups.id", ondelete="CASCADE"), nullable=False, comment="分组ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="分组名称")


class SpecificationDefinitionTranslation(_TranslationBase, Base):
    """规格定义翻译。"""

    __tablename__ = "specification_definition_translations"
    __table_args__ = (UniqueConstraint("definition_id", "locale_id", name="uq_spec_definition_translation_locale"), {"comment": "规格定义翻译表"})
    definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("specification_definitions.id", ondelete="CASCADE"), nullable=False, comment="定义ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="规格名称")
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="帮助说明")


class MaterialTranslation(_TranslationBase, Base):
    """材料翻译。"""

    __tablename__ = "material_translations"
    __table_args__ = (UniqueConstraint("material_id", "locale_id", name="uq_material_translation_locale"), {"comment": "材料翻译表"})
    material_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, comment="材料ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="材料名称")
    definition: Mapped[str | None] = mapped_column(Text, nullable=True, comment="材料定义")
    processing_characteristics: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加工特性")
    screw_impact: Mapped[str | None] = mapped_column(Text, nullable=True, comment="对螺杆影响")
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True, comment="推荐说明")
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True, comment="限制条件")


class TechnologyTranslation(_TranslationBase, Base):
    """技术翻译。"""

    __tablename__ = "technology_translations"
    __table_args__ = (UniqueConstraint("technology_id", "locale_id", name="uq_technology_translation_locale"), {"comment": "技术翻译表"})
    technology_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("technologies.id", ondelete="CASCADE"), nullable=False, comment="技术ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="技术名称")
    definition: Mapped[str | None] = mapped_column(Text, nullable=True, comment="技术定义")
    process_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="工艺描述")
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True, comment="优势")
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True, comment="限制条件")


class ApplicationTranslation(_TranslationBase, Base):
    """应用翻译。"""

    __tablename__ = "application_translations"
    __table_args__ = (UniqueConstraint("application_id", "locale_id", name="uq_application_translation_locale"), {"comment": "应用翻译表"})
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, comment="应用ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="应用名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="应用描述")
    technical_requirements: Mapped[str | None] = mapped_column(Text, nullable=True, comment="技术要求")
    common_problems: Mapped[str | None] = mapped_column(Text, nullable=True, comment="常见问题")


class SolutionTranslation(_TranslationBase, Base):
    """解决方案翻译。"""

    __tablename__ = "solution_translations"
    __table_args__ = (UniqueConstraint("solution_id", "locale_id", name="uq_solution_translation_locale"), {"comment": "解决方案翻译表"})
    solution_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("solutions.id", ondelete="CASCADE"), nullable=False, comment="方案ID")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="方案名称")
    definition: Mapped[str | None] = mapped_column(Text, nullable=True, comment="方案定义")
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True, comment="症状")
    causes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原因")
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="诊断")
    solution: Mapped[str | None] = mapped_column(Text, nullable=True, comment="解决方案")
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True, comment="限制条件")


def _relation_model(name: str, table: str, left: str, right: str) -> type[Base]:
    """构造带统一排序和备注字段的显式关系模型。"""
    table_names = {
        "product": "products",
        "material": "materials",
        "technology": "technologies",
        "application": "applications",
        "solution": "solutions",
    }
    return type(
        name,
        (Base,),
        {
            "__tablename__": table,
            "__table_args__": {"comment": f"{table} 显式关系表"},
            left: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{table_names[left.removesuffix('_id')]}.id", ondelete="CASCADE"), primary_key=True, comment=f"{left}关联ID"),
            right: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{table_names[right.removesuffix('_id')]}.id", ondelete="CASCADE"), primary_key=True, comment=f"{right}关联ID"),
            "sort_order": mapped_column(Integer, nullable=False, default=0, server_default="0", comment="关系排序"),
            "recommendation_level": mapped_column(String(32), nullable=True, comment="推荐级别"),
            "notes": mapped_column(Text, nullable=True, comment="关系备注"),
        },
    )


# 显式类名保留给 API、审计和未来关系查询，避免通用 entity_links。
ProductMaterial = _relation_model("ProductMaterial", "product_materials", "product_id", "material_id")
ProductTechnology = _relation_model("ProductTechnology", "product_technologies", "product_id", "technology_id")
ProductApplication = _relation_model("ProductApplication", "product_applications", "product_id", "application_id")
ProductSolution = _relation_model("ProductSolution", "product_solutions", "product_id", "solution_id")
MaterialTechnology = _relation_model("MaterialTechnology", "material_technologies", "material_id", "technology_id")
MaterialSolution = _relation_model("MaterialSolution", "material_solutions", "material_id", "solution_id")
ApplicationSolution = _relation_model("ApplicationSolution", "application_solutions", "application_id", "solution_id")

CORE_ENTITY_MODELS = (ProductCategory, Product, ProductModel, SpecificationGroup, SpecificationDefinition, ProductSpecValue, Material, Technology, Application, Solution)
CORE_TRANSLATION_MODELS = (ProductCategoryTranslation, ProductTranslation, ProductModelTranslation, SpecificationGroupTranslation, SpecificationDefinitionTranslation, MaterialTranslation, TechnologyTranslation, ApplicationTranslation, SolutionTranslation)
CORE_RELATION_MODELS = (ProductMaterial, ProductTechnology, ProductApplication, ProductSolution, MaterialTechnology, MaterialSolution, ApplicationSolution)
