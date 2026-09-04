"""Company Trust 管理输入模型。"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.authority.schemas import _validate_slug


class TrustTranslation(BaseModel):
    """通用 Trust 翻译字段。"""

    locale_id: uuid.UUID
    fields: dict[str, Any] = Field(default_factory=dict)


class CompanyProfileInput(BaseModel):
    """公司档案主字段与翻译。"""

    status: Literal["enabled", "disabled", "retired"] = "enabled"
    founded_year: int | None = Field(default=None, ge=1800, le=2200)
    years_experience: int | None = Field(default=None, ge=0, le=300)
    employee_count_range: str | None = None
    factory_area_sqm: float | None = Field(default=None, ge=0)
    annual_capacity_text: str | None = None
    export_markets_json: list[str] | None = None
    public_phone: str | None = None
    public_email: str | None = None
    public_address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    logo_media_id: uuid.UUID | None = None
    primary_factory_media_id: uuid.UUID | None = None
    translations: list[TrustTranslation] = Field(default_factory=list)


class TrustEntityInput(BaseModel):
    """能力、设备及可信内容实体的通用输入。"""

    slug: str
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    sort_order: int = 0
    fields: dict[str, Any] = Field(default_factory=dict)
    translations: list[TrustTranslation] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)


class DownloadInput(BaseModel):
    """公开下载资源输入。"""

    slug: str
    resource_type: str = "document"
    status: Literal["enabled", "disabled", "retired"] = "enabled"
    media_asset_id: uuid.UUID
    version_label: str | None = None
    published_date: str | None = None
    requires_form: bool = False
    sort_order: int = 0
    translations: list[TrustTranslation] = Field(default_factory=list)

    _slug = field_validator("slug")(_validate_slug)

