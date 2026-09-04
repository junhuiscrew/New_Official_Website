"""Locale API 请求与响应模型。"""

from pydantic import BaseModel, ConfigDict, Field


class LocaleCreate(BaseModel):
    """创建语言配置请求。"""

    code: str = Field(min_length=2, max_length=16)
    slug: str = Field(min_length=2, max_length=16, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=100)
    native_name: str = Field(min_length=1, max_length=100)
    is_enabled: bool = True
    sort_order: int = 0


class LocaleUpdate(BaseModel):
    """更新语言配置请求；未提供字段保持原值。"""

    code: str | None = Field(default=None, min_length=2, max_length=16)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=16,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    name: str | None = Field(default=None, min_length=1, max_length=100)
    native_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_enabled: bool | None = None
    sort_order: int | None = None


class LocaleData(BaseModel):
    """语言配置安全输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    slug: str
    name: str
    native_name: str
    is_default: bool
    is_enabled: bool
    sort_order: int
