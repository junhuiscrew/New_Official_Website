"""Catalog API 的结构化请求与响应校验模型。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slug(value: str) -> str:
    """验证并规范稳定技术 slug。"""
    value = value.strip().lower()
    if not _SLUG.fullmatch(value):
        raise ValueError("slug 必须是小写 kebab-case")
    return value


class TranslationInput(BaseModel):
    """一个语言版本的结构化文本输入。"""

    locale_id: uuid.UUID
    name: str = Field(min_length=1, max_length=240)
    fields: dict[str, Any] = Field(default_factory=dict)


class CategoryCreate(BaseModel):
    """分类创建输入。"""

    parent_id: uuid.UUID | None = None
    slug: str
    status: str = "enabled"
    sort_order: int = 0
    translations: list[TranslationInput] = Field(default_factory=list)

    _validate_slug = field_validator("slug")(_slug)


class CategoryUpdate(BaseModel):
    """分类更新输入。"""

    parent_id: uuid.UUID | None = None
    slug: str | None = None
    status: str | None = None
    sort_order: int | None = None
    translations: list[TranslationInput] | None = None

    _validate_slug = field_validator("slug")(_slug)


class ProductCreate(BaseModel):
    """产品创建输入。"""

    category_id: uuid.UUID
    code: str | None = None
    slug: str
    status: str = "enabled"
    featured: bool = False
    sort_order: int = 0
    primary_media_id: uuid.UUID | None = None
    translations: list[TranslationInput] = Field(default_factory=list)

    _validate_slug = field_validator("slug")(_slug)


class ProductUpdate(BaseModel):
    """产品更新输入。"""

    category_id: uuid.UUID | None = None
    code: str | None = None
    slug: str | None = None
    status: str | None = None
    featured: bool | None = None
    sort_order: int | None = None
    primary_media_id: uuid.UUID | None = None
    translations: list[TranslationInput] | None = None

    _validate_slug = field_validator("slug")(_slug)


class ProductModelCreate(BaseModel):
    """产品型号创建输入。"""

    model_code: str = Field(min_length=1, max_length=100)
    status: str = "enabled"
    sort_order: int = 0
    translations: list[TranslationInput] = Field(default_factory=list)


class ProductModelUpdate(BaseModel):
    """产品型号更新输入。"""

    model_code: str | None = None
    status: str | None = None
    sort_order: int | None = None
    translations: list[TranslationInput] | None = None


class EntityCreate(BaseModel):
    """材料、技术、应用和方案的通用创建输入。"""

    slug: str
    status: str = "enabled"
    featured: bool = False
    sort_order: int = 0
    translations: list[TranslationInput] = Field(default_factory=list)

    _validate_slug = field_validator("slug")(_slug)


class EntityUpdate(BaseModel):
    """材料、技术、应用和方案的通用更新输入。"""

    slug: str | None = None
    status: str | None = None
    featured: bool | None = None
    sort_order: int | None = None
    translations: list[TranslationInput] | None = None

    _validate_slug = field_validator("slug")(_slug)


class SpecificationGroupCreate(BaseModel):
    """规格分组创建输入。"""

    code: str = Field(min_length=1, max_length=100)
    status: str = "enabled"
    sort_order: int = 0
    translations: list[TranslationInput] = Field(default_factory=list)


class SpecificationDefinitionCreate(BaseModel):
    """规格定义创建输入。"""

    group_id: uuid.UUID
    code: str = Field(min_length=1, max_length=100)
    value_type: str
    default_unit: str | None = None
    is_filterable: bool = False
    sort_order: int = 0
    status: str = "enabled"
    translations: list[TranslationInput] = Field(default_factory=list)

    @field_validator("value_type")
    @classmethod
    def validate_value_type(cls, value: str) -> str:
        """限制规格类型为交接文件冻结的五种类型。"""
        if value not in {"text", "number", "range", "boolean", "enum"}:
            raise ValueError("不支持的规格值类型")
        return value


class SpecificationValueCreate(BaseModel):
    """产品或型号规格值输入。"""

    product_id: uuid.UUID | None = None
    product_model_id: uuid.UUID | None = None
    definition_id: uuid.UUID
    value_text: str | None = None
    value_number: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_boolean: bool | None = None
    enum_value: str | None = None
    unit_override: str | None = None
    sort_order: int = 0
    is_public: bool = True

    @model_validator(mode="after")
    def validate_owner_and_value(self) -> SpecificationValueCreate:
        """请求层先保证 owner XOR 和范围边界，数据库/服务层再次兜底。"""
        if (self.product_id is None) == (self.product_model_id is None):
            raise ValueError("product_id 与 product_model_id 必须恰好一个有值")
        values = [self.value_text, self.value_number, self.value_boolean, self.enum_value]
        if self.value_min is not None or self.value_max is not None:
            values.append("range")
        if sum(value is not None for value in values) != 1:
            raise ValueError("规格值必须恰好提供一种值")
        if self.value_min is not None and self.value_max is not None and self.value_min > self.value_max:
            raise ValueError("范围下限不能大于上限")
        return self


class SpecificationValueUpdate(BaseModel):
    """已有产品规格值的局部更新输入。"""

    value_text: str | None = None
    value_number: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_boolean: bool | None = None
    enum_value: str | None = None
    unit_override: str | None = None
    sort_order: int | None = None
    is_public: bool | None = None


class RelationUpdate(BaseModel):
    """产品显式关系的整体替换输入。"""

    material_ids: list[uuid.UUID] = Field(default_factory=list)
    technology_ids: list[uuid.UUID] = Field(default_factory=list)
    application_ids: list[uuid.UUID] = Field(default_factory=list)
    solution_ids: list[uuid.UUID] = Field(default_factory=list)


class CatalogData(BaseModel):
    """Catalog API 的宽松结构化输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str | None = None
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
