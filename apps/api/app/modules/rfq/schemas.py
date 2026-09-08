"""RFQ 公共表单、后台状态和文件元数据校验模型。"""

from __future__ import annotations

import uuid
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RFQItemInput(BaseModel):
    """单个询盘项目输入。"""

    item_type: Literal["product", "screw", "barrel", "component", "custom", "other"] = "custom"
    product_id: uuid.UUID | None = None
    product_model_id: uuid.UUID | None = None
    product_name_text: str | None = Field(default=None, max_length=240)
    quantity: str | None = Field(default=None, max_length=80)
    material_text: str | None = Field(default=None, max_length=240)
    screw_diameter: str | None = Field(default=None, max_length=80)
    length: str | None = Field(default=None, max_length=80)
    machine_brand: str | None = Field(default=None, max_length=160)
    machine_model: str | None = Field(default=None, max_length=160)
    requirements: str | None = Field(default=None, max_length=5000)
    sort_order: int = 0


class RFQCreate(BaseModel):
    """匿名询盘创建输入；不接收内部状态或文件路径。"""

    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=240)
    contact_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    website: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=10000)
    # 数据库字段继续允许历史 null；新的公开提交必须明确绑定 Privacy 支持语言。
    preferred_language: Literal["zh-CN", "en"]
    source_type: (
        Literal[
            "product",
            "material",
            "technology",
            "application",
            "solution",
            "case_study",
            "knowledge_article",
            "manufacturing_capability",
            "author_expert",
            "exhibition",
        ]
        | None
    ) = None
    source_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=180,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    items: list[RFQItemInput] = Field(default_factory=list, max_length=20)
    consent_privacy: bool
    consent_marketing: bool = False
    privacy_context_token: str | None = Field(default=None, min_length=1, max_length=4096)
    honeypot: str = Field(default="", max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """统一邮箱大小写，避免重复询盘身份。"""
        return str(value).strip().lower()

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value and urlparse(value).scheme not in {"http", "https"}:
            raise ValueError("website 必须使用 HTTP 或 HTTPS")
        return value

    @model_validator(mode="after")
    def validate_content(self) -> RFQCreate:
        if bool(self.source_type) != bool(self.source_slug):
            raise ValueError("询盘来源类型与 slug 必须同时提供")
        if not self.consent_privacy:
            raise ValueError("必须同意隐私政策")
        if not self.message and not self.items:
            raise ValueError("留言与询盘项目至少填写一项")
        return self


class RFQUpdate(BaseModel):
    """后台询盘状态和优先级更新。"""

    status: (
        Literal[
            "new",
            "qualified",
            "in_progress",
            "waiting_customer",
            "quoted",
            "won",
            "lost",
            "spam",
            "closed",
        ]
        | None
    ) = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None


class RFQAssign(BaseModel):
    """销售分配输入。"""

    assigned_to: uuid.UUID | None = None
