"""Privacy P1 固定管理接口输入模型。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PrivacyTranslationUpdate(BaseModel):
    """
    表示一次政策语言正文完整替换。

    输入：locale、title 与 body_markdown。
    输出：PrivacyTranslationUpdate，禁止额外字段且不接受内部 ID/哈希。
    """

    model_config = ConfigDict(extra="forbid")

    locale: Literal["zh-CN", "en"]
    title: str = Field(min_length=1, max_length=300)
    body_markdown: str = Field(min_length=1, max_length=200_000)


class PrivacyDraftUpdate(BaseModel):
    """
    表示带乐观版本号的 Privacy 草稿更新。

    输入：expected_revision、可选 effective_at 和一至两种语言完整正文。
    输出：PrivacyDraftUpdate；重复语言、客户端 UUID/哈希或未知字段均被拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    effective_at: datetime | None = None
    translations: list[PrivacyTranslationUpdate] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_unique_locales(self) -> PrivacyDraftUpdate:
        """
        拒绝同一请求重复更新一种语言。

        输入：self，已完成字段校验的更新请求。
        输出：PrivacyDraftUpdate，语言集合唯一时返回自身。
        """
        locales = [item.locale for item in self.translations]
        if len(locales) != len(set(locales)):
            raise ValueError("隐私政策语言不能重复")
        if not locales and "effective_at" not in self.model_fields_set:
            raise ValueError("必须更新生效时间或至少一种语言")
        return self


class PrivacyDraftCreate(BaseModel):
    """
    表示创建服务端编号草稿的固定输入。

    输入：clone_current，是否优先克隆当前公开版本；无任何 owner_type 或 UUID。
    输出：PrivacyDraftCreate。
    """

    model_config = ConfigDict(extra="forbid")

    clone_current: bool = True


class PrivacyReviewAction(BaseModel):
    """
    绑定管理员实际观察到的单语言审核目标。

    输入：版本标签、Revision 与目标语言正文哈希。
    输出：PrivacyReviewAction；内部 UUID 和不完整哈希均被拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    expected_version_label: str = Field(min_length=1, max_length=40)
    expected_revision: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PrivacyPublishAction(BaseModel):
    """
    绑定管理员实际观察到的双语发布目标。

    输入：版本标签、Revision 与 zh-CN/en 两个正文哈希。
    输出：PrivacyPublishAction；语言集合不完整或包含额外语言时拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    expected_version_label: str = Field(min_length=1, max_length=40)
    expected_revision: int = Field(ge=1)
    expected_content_hashes: dict[Literal["zh-CN", "en"], str]

    @model_validator(mode="after")
    def validate_expected_hashes(self) -> PrivacyPublishAction:
        """
        校验发布观察值恰好包含固定双语 SHA-256。

        输入：self，已解析的发布请求。
        输出：PrivacyPublishAction，双语键与哈希格式正确时返回自身。
        """
        if set(self.expected_content_hashes) != {"zh-CN", "en"}:
            raise ValueError("发布必须携带 zh-CN/en 两种语言的正文哈希")
        if any(
            re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in self.expected_content_hashes.values()
        ):
            raise ValueError("正文哈希必须是 64 位小写 SHA-256")
        return self


class PrivacyPageStatusUpdate(BaseModel):
    """
    表示隐私页面启停操作。

    输入：status，只允许 enabled 或 disabled。
    输出：PrivacyPageStatusUpdate。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["enabled", "disabled"]
