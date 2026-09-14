"""站点运营设置的严格白名单输入模型。"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.site_operations.registry import SITE_TARGET_PATHS

TargetKey = Literal[
    "home",
    "products",
    "solutions",
    "materials",
    "applications",
    "technologies",
    "capabilities",
    "case_studies",
    "knowledge",
    "about",
    "contact",
    "request_a_quote",
    "downloads",
    "privacy",
    "search",
    "sitemap",
]

_ITEM_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BrandTranslationInput(BaseModel):
    """单语言品牌展示名称输入。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    short_name: str = Field(min_length=1, max_length=40)


class BrandDraftUpdate(BaseModel):
    """品牌完整双语草稿输入，禁止局部保存清空另一语言。"""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    translations: dict[Literal["zh-CN", "en"], BrandTranslationInput]
    header_logo_media_id: uuid.UUID | None = None
    mobile_logo_media_id: uuid.UUID | None = None
    favicon_media_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_languages(self) -> BrandDraftUpdate:
        """
        校验品牌草稿同时包含中英文。

        输入：当前品牌草稿。
        输出：BrandDraftUpdate，验证通过的原实例。
        """
        if set(self.translations) != {"zh-CN", "en"}:
            raise ValueError("brand_bilingual_content_required")
        return self


class NavigationItemInput(BaseModel):
    """只能指向服务端注册目标的菜单项输入。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=_ITEM_ID_PATTERN.pattern)
    label: str = Field(min_length=1, max_length=80)
    target_key: TargetKey
    enabled: bool = True


class FooterGroupInput(BaseModel):
    """页脚分组输入。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=_ITEM_ID_PATTERN.pattern)
    title: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    items: list[NavigationItemInput] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_unique_items(self) -> FooterGroupInput:
        """输入当前分组；输出无重复项目标识的分组。"""
        item_ids = [item.id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("navigation_item_id_duplicate")
        return self


class NavigationDraftUpdate(BaseModel):
    """顶部导航与页脚的完整单语言草稿。"""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    header_items: list[NavigationItemInput] = Field(default_factory=list, max_length=12)
    footer_groups: list[FooterGroupInput] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> NavigationDraftUpdate:
        """
        校验顶栏和分组稳定标识唯一，目标仍来自服务端注册表。

        输入：当前导航草稿。
        输出：NavigationDraftUpdate，验证通过的原实例。
        """
        header_ids = [item.id for item in self.header_items]
        group_ids = [group.id for group in self.footer_groups]
        if len(header_ids) != len(set(header_ids)) or len(group_ids) != len(set(group_ids)):
            raise ValueError("navigation_id_duplicate")
        if any(item.target_key not in SITE_TARGET_PATHS for item in self.header_items):
            raise ValueError("navigation_target_not_allowed")
        return self


class ExpectedRevision(BaseModel):
    """保存、应用与恢复动作使用的乐观锁输入。"""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)


class ManagedRedirectInput(BaseModel):
    """受控重定向草稿输入。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_host: Literal[
        "junhuiscrewbarrel.com",
        "www.junhuiscrewbarrel.com",
        "junhuiscrew.com",
        "www.junhuiscrew.com",
    ]
    source_path: str = Field(min_length=1, max_length=1000)
    target_path: str = Field(min_length=1, max_length=1000)
    status_code: Literal[301, 302, 307, 308] = 301
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_paths(self) -> ManagedRedirectInput:
        """
        校验来源和目标均为不含查询、片段或遍历的站内绝对路径。

        输入：当前重定向表单。
        输出：ManagedRedirectInput，验证通过的原实例。
        """
        for path in (self.source_path, self.target_path):
            if (
                not path.startswith("/")
                or path.startswith("//")
                or any(char in path for char in ("\\", "?", "#"))
                or any(ord(char) < 32 for char in path)
                or "/../" in f"{path}/"
            ):
                raise ValueError("managed_redirect_path_invalid")
        return self


class ManagedRedirectUpdate(ManagedRedirectInput):
    """带修订号的受控重定向修改输入。"""

    expected_revision: int = Field(ge=0)
