"""Structured Core 的业务生命周期和动态规格类型。"""

from enum import StrEnum


class CatalogLifecycle(StrEnum):
    """核心实体业务状态，不替代统一 Publication 状态。"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    RETIRED = "retired"


class SpecificationValueType(StrEnum):
    """规格值允许的结构化类型。"""

    TEXT = "text"
    NUMBER = "number"
    RANGE = "range"
    BOOLEAN = "boolean"
    ENUM = "enum"
