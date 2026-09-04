"""Authority Content 管理 API 的请求校验模型。"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HTML_PATTERN = re.compile(r"<\s*/?\s*[a-z][^>]*>", re.IGNORECASE)


def _validate_slug(value: str) -> str:
    """
    规范并验证稳定 kebab-case slug。

    输入：value，原始 slug。
    输出：str，小写稳定 slug。
    """
    normalized = value.strip().lower()
    if not _SLUG_PATTERN.fullmatch(normalized):
        raise ValueError("slug 必须是小写 kebab-case")
    return normalized


class AuthorityTranslationInput(BaseModel):
    """任一 Authority 实体的单语言结构化字段输入。"""

    locale_id: uuid.UUID
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def reject_unsanitized_html(cls, fields: dict[str, Any]) -> dict[str, Any]:
        """
        禁止正文直接提交任意 HTML，知识正文统一保存 Markdown。

        输入：fields，单语言字段字典。
        输出：dict，校验后的原字典。
        """
        body = fields.get("body_markdown")
        if isinstance(body, str) and _HTML_PATTERN.search(body):
            raise ValueError("body_markdown 不允许未清洗的任意 HTML")
        return fields


class CaseStudyCreate(BaseModel):
    """客户案例创建输入。"""

    slug: str
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    industry: str | None = None
    machine_brand: str | None = None
    machine_model: str | None = None
    screw_diameter: str | None = None
    processed_material_text: str | None = None
    filler_percentage: str | None = None
    client_name: str | None = None
    client_address: str | None = None
    client_logo_media_id: uuid.UUID | None = None
    client_name_public: bool = False
    client_logo_public: bool = False
    client_address_public: bool = False
    featured: bool = False
    sort_order: int = 0
    primary_media_id: uuid.UUID | None = None
    translations: list[AuthorityTranslationInput] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)


class CaseStudyUpdate(BaseModel):
    """客户案例局部更新输入。"""

    slug: str | None = None
    status: Literal["enabled", "disabled", "retired"] | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    industry: str | None = None
    machine_brand: str | None = None
    machine_model: str | None = None
    screw_diameter: str | None = None
    processed_material_text: str | None = None
    filler_percentage: str | None = None
    client_name: str | None = None
    client_address: str | None = None
    client_logo_media_id: uuid.UUID | None = None
    client_name_public: bool | None = None
    client_logo_public: bool | None = None
    client_address_public: bool | None = None
    featured: bool | None = None
    sort_order: int | None = None
    primary_media_id: uuid.UUID | None = None
    translations: list[AuthorityTranslationInput] | None = None

    _slug = field_validator("slug")(_validate_slug)


class KnowledgeCategoryCreate(BaseModel):
    """Knowledge Center 分类创建输入。"""

    slug: str
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    sort_order: int = 0
    translations: list[AuthorityTranslationInput] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)


class KnowledgeCategoryUpdate(BaseModel):
    """Knowledge Center 分类更新输入。"""

    slug: str | None = None
    status: Literal["enabled", "disabled", "retired"] | None = None
    sort_order: int | None = None
    translations: list[AuthorityTranslationInput] | None = None

    _slug = field_validator("slug")(_validate_slug)


class AuthorExpertCreate(BaseModel):
    """真实作者专家创建输入。"""

    slug: str
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    role_type: Literal["author", "expert", "author_expert"]
    is_real_person_verified: bool = False
    public_profile_enabled: bool = False
    profile_media_id: uuid.UUID | None = None
    public_email: str | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    linkedin_url: str | None = None
    sort_order: int = 0
    translations: list[AuthorityTranslationInput] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)


class AuthorExpertUpdate(BaseModel):
    """真实作者专家局部更新输入。"""

    slug: str | None = None
    status: Literal["enabled", "disabled", "retired"] | None = None
    role_type: Literal["author", "expert", "author_expert"] | None = None
    is_real_person_verified: bool | None = None
    public_profile_enabled: bool | None = None
    profile_media_id: uuid.UUID | None = None
    public_email: str | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    linkedin_url: str | None = None
    sort_order: int | None = None
    translations: list[AuthorityTranslationInput] | None = None

    _slug = field_validator("slug")(_validate_slug)


class KnowledgeArticleCreate(BaseModel):
    """Knowledge Article 创建输入。"""

    category_id: uuid.UUID
    slug: str
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    author_id: uuid.UUID
    reviewer_id: uuid.UUID | None = None
    featured: bool = False
    sort_order: int = 0
    last_reviewed_at: datetime | None = None
    primary_media_id: uuid.UUID | None = None
    translations: list[AuthorityTranslationInput] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)


class KnowledgeArticleUpdate(BaseModel):
    """Knowledge Article 局部更新输入。"""

    category_id: uuid.UUID | None = None
    slug: str | None = None
    status: Literal["enabled", "disabled", "retired"] | None = None
    author_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    featured: bool | None = None
    sort_order: int | None = None
    last_reviewed_at: datetime | None = None
    primary_media_id: uuid.UUID | None = None
    translations: list[AuthorityTranslationInput] | None = None

    _slug = field_validator("slug")(_validate_slug)


class FAQCreate(BaseModel):
    """FAQ 创建输入。"""

    status: Literal["enabled", "disabled", "retired"] = "enabled"
    sort_order: int = 0
    translations: list[AuthorityTranslationInput] = Field(default_factory=list)


class FAQUpdate(BaseModel):
    """FAQ 局部更新输入。"""

    status: Literal["enabled", "disabled", "retired"] | None = None
    sort_order: int | None = None
    translations: list[AuthorityTranslationInput] | None = None


class AuthorityRelationUpdate(BaseModel):
    """Authority 实体显式关系整体替换输入。"""

    product_ids: list[uuid.UUID] = Field(default_factory=list)
    material_ids: list[uuid.UUID] = Field(default_factory=list)
    technology_ids: list[uuid.UUID] = Field(default_factory=list)
    application_ids: list[uuid.UUID] = Field(default_factory=list)
    solution_ids: list[uuid.UUID] = Field(default_factory=list)
    case_ids: list[uuid.UUID] = Field(default_factory=list)
    faq_ids: list[uuid.UUID] = Field(default_factory=list)
    article_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_ids(self) -> AuthorityRelationUpdate:
        """拒绝同一关系列表内重复 UUID，保证提交语义明确。"""
        for field_name in self.model_fields:
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} 不能包含重复ID")
        return self
