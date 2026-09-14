"""首页呈现配置的严格输入 Schema。"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.presentation.registry import (
    HOMEPAGE_MODULE_KEYS,
    HOMEPAGE_PRODUCT_REFERENCE_MODULES,
    HOMEPAGE_VARIANTS,
)

HomepageModuleKey = Literal[
    "hero",
    "core_product_families",
    "materials",
    "special_applications",
    "technologies",
    "manufacturing_capability",
    "why_junhui",
    "factory_equipment",
    "solutions",
    "case_studies",
    "technical_knowledge",
    "certificates_patents",
    "global_markets",
    "rfq_cta",
]
HomepageVariant = Literal[
    "product-focus",
    "product-rail",
    "light",
    "soft",
    "navy",
    "split",
    "rail",
]

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLIDE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_INTERNAL_PATH_PATTERN = re.compile(r"^/(?!/)[^\s\\\x00-\x1f]*$")


class HomepageHeroSlideInput(BaseModel):
    """
    Hero 轮播单项的严格输入。

    输入：稳定标识、公开图片ID、当前语言文案、可选站内按钮及启用状态。
    输出：HomepageHeroSlideInput，供首页 JSONB 配置安全持久化。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=_SLIDE_ID_PATTERN.pattern)
    media_id: uuid.UUID
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(min_length=1, max_length=300)
    cta_label: str | None = Field(default=None, min_length=1, max_length=40)
    cta_href: str | None = Field(default=None, min_length=1, max_length=240)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_cta(self) -> HomepageHeroSlideInput:
        """
        校验轮播按钮成对出现且只跳转站内路径。

        输入：当前轮播项实例。
        输出：HomepageHeroSlideInput，验证通过的原实例。
        """
        if bool(self.cta_label) != bool(self.cta_href):
            raise ValueError("homepage_hero_cta_incomplete")
        if self.cta_href and not _INTERNAL_PATH_PATTERN.fullmatch(self.cta_href):
            raise ValueError("homepage_hero_cta_href_invalid")
        return self


class HomepageModuleInput(BaseModel):
    """单个首页模块的白名单配置。"""

    model_config = ConfigDict(extra="forbid")

    key: HomepageModuleKey
    visible: bool
    variant: HomepageVariant
    product_slugs: list[str] = Field(default_factory=list, max_length=3)
    slides: list[HomepageHeroSlideInput] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_module_rules(self) -> HomepageModuleInput:
        """
        校验模块样式和产品引用边界。

        输入：当前模块实例。
        输出：HomepageModuleInput，验证通过的原实例。
        """
        if self.variant not in HOMEPAGE_VARIANTS[self.key]:
            raise ValueError("homepage_variant_not_allowed")
        if self.product_slugs and self.key not in HOMEPAGE_PRODUCT_REFERENCE_MODULES:
            raise ValueError("homepage_product_reference_not_allowed")
        if self.slides and self.key != "hero":
            raise ValueError("homepage_hero_slides_not_allowed")
        slide_ids = [slide.id for slide in self.slides]
        if len(set(slide_ids)) != len(slide_ids):
            raise ValueError("homepage_hero_slide_duplicate")
        normalized = [slug.strip() for slug in self.product_slugs]
        if len(set(normalized)) != len(normalized):
            raise ValueError("homepage_product_reference_duplicate")
        if any(not _SLUG_PATTERN.fullmatch(slug) for slug in normalized):
            raise ValueError("homepage_product_reference_invalid")
        self.product_slugs = normalized
        return self


class HomepageDraftUpdate(BaseModel):
    """保存首页草稿时使用的完整十四模块输入。"""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    modules: list[HomepageModuleInput] = Field(min_length=14, max_length=14)

    @model_validator(mode="after")
    def validate_complete_registry(self) -> HomepageDraftUpdate:
        """
        确保十四个固定模块恰好各出现一次。

        输入：当前更新实例。
        输出：HomepageDraftUpdate，顺序保留的完整配置。
        """
        keys = tuple(module.key for module in self.modules)
        if len(set(keys)) != len(keys) or set(keys) != set(HOMEPAGE_MODULE_KEYS):
            raise ValueError("homepage_module_registry_incomplete")
        return self


class HomepageExpectedRevision(BaseModel):
    """应用或恢复操作的乐观锁输入。"""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
