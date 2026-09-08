"""首页呈现配置的严格输入 Schema。"""

from __future__ import annotations

import re
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


class HomepageModuleInput(BaseModel):
    """单个首页模块的白名单配置。"""

    model_config = ConfigDict(extra="forbid")

    key: HomepageModuleKey
    visible: bool
    variant: HomepageVariant
    product_slugs: list[str] = Field(default_factory=list, max_length=3)

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
