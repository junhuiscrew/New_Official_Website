"""公开发现层 DTO：以显式白名单隔离 ORM 与内部存储字段。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PublicMediaDto(BaseModel):
    """
    公开媒体展示 DTO，仅包含浏览器渲染所需字段。

    输入：代理地址、媒体类型、尺寸、本地化文案与加载策略。
    输出：PublicMediaDto，不包含媒体 ID、桶名、对象键或上传者信息。
    """

    model_config = ConfigDict(extra="forbid")

    src: str
    type: Literal["image", "video", "document", "cad", "other"]
    mime_type: str
    width: int | None = None
    height: int | None = None
    alt: str
    caption: str | None = None
    loading: Literal["eager", "lazy"] = "lazy"


class PublicSpecDto(BaseModel):
    """
    公开产品规格 DTO，仅暴露翻译名称、格式化值和展示单位。

    输入：规格名称、展示值、单位、分组名称和值类型。
    输出：PublicSpecDto，不包含规格定义、产品或审计字段。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str
    unit: str | None = None
    group: str
    type: Literal["text", "number", "range", "boolean", "enum"]
