"""产品公开规格查询与安全格式化。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import (
    ProductSpecValue,
    SpecificationDefinition,
    SpecificationDefinitionTranslation,
    SpecificationGroup,
    SpecificationGroupTranslation,
)
from app.modules.discovery.public_schemas import PublicSpecDto
from app.modules.localization.models import Locale

SPEC_VALUE_TYPES = frozenset({"text", "number", "range", "boolean", "enum"})


def _decimal_text(value: object) -> str | None:
    """
    将数据库数值安全转换为非科学计数法字符串。

    输入：
        value: object，Decimal 或可精确转换为 Decimal 的数值。

    输出：
        str | None，去除无意义尾零的十进制文本；非法或非有限值返回 None。
    """
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not decimal_value.is_finite():
        return None
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _stored_value_type(spec_value: Any) -> str | None:
    """
    判断规格记录实际使用的唯一存储列类型。

    输入：
        spec_value: Any，具备五类规格值列的 ORM 实体或等价对象。

    输出：
        str | None，唯一存储类型；存在多列或无值时返回 None。
    """
    present_types: list[str] = []
    if getattr(spec_value, "value_text", None) is not None:
        present_types.append("text")
    if getattr(spec_value, "value_number", None) is not None:
        present_types.append("number")
    if (
        getattr(spec_value, "value_min", None) is not None
        or getattr(spec_value, "value_max", None) is not None
    ):
        present_types.append("range")
    if getattr(spec_value, "value_boolean", None) is not None:
        present_types.append("boolean")
    if getattr(spec_value, "enum_value", None) is not None:
        present_types.append("enum")
    return present_types[0] if len(present_types) == 1 else None


def _format_spec_value(spec_value: Any, value_type: str, locale_code: str) -> str | None:
    """
    按规格定义格式化唯一存储值。

    输入：
        spec_value: Any，规格值 ORM 实体或等价对象。
        value_type: str，text、number、range、boolean 或 enum。
        locale_code: str，当前语言代码，用于本地化布尔标签。

    输出：
        str | None，可直接公开的显示文本；非法组合返回 None。
    """
    if value_type == "text":
        value = getattr(spec_value, "value_text", None)
        return value if isinstance(value, str) else None
    if value_type == "number":
        return _decimal_text(getattr(spec_value, "value_number", None))
    if value_type == "range":
        minimum = _decimal_text(getattr(spec_value, "value_min", None))
        maximum = _decimal_text(getattr(spec_value, "value_max", None))
        if minimum is None or maximum is None:
            return None
        try:
            if Decimal(minimum) > Decimal(maximum):
                return None
        except InvalidOperation:
            return None
        return f"{minimum}–{maximum}"
    if value_type == "boolean":
        value = getattr(spec_value, "value_boolean", None)
        if not isinstance(value, bool):
            return None
        if locale_code.lower().replace("_", "-").startswith("zh"):
            return "是" if value else "否"
        return "Yes" if value else "No"
    if value_type == "enum":
        value = getattr(spec_value, "enum_value", None)
        return value if isinstance(value, str) else None
    return None


def serialize_public_spec(
    spec_value: Any,
    definition: Any,
    definition_translation: Any,
    group_translation: Any,
    locale_code: str,
) -> PublicSpecDto | None:
    """
    将单条规格 ORM 组合转换为公开白名单 DTO。

    输入：
        spec_value: Any，产品规格值。
        definition: Any，规格定义，提供值类型与默认单位。
        definition_translation: Any，当前语言规格名称。
        group_translation: Any，当前语言分组名称。
        locale_code: str，当前语言代码。

    输出：
        PublicSpecDto | None，合法公开规格；类型与存储列不一致时返回 None。
    """
    value_type = getattr(definition, "value_type", None)
    if value_type not in SPEC_VALUE_TYPES or _stored_value_type(spec_value) != value_type:
        return None

    value = _format_spec_value(spec_value, value_type, locale_code)
    name = getattr(definition_translation, "name", None)
    group_name = getattr(group_translation, "name", None)
    if value is None or not isinstance(name, str) or not isinstance(group_name, str):
        return None

    unit_override = getattr(spec_value, "unit_override", None)
    default_unit = getattr(definition, "default_unit", None)
    unit = unit_override if isinstance(unit_override, str) and unit_override else default_unit
    if unit is not None and not isinstance(unit, str):
        return None
    return PublicSpecDto(
        name=name,
        value=value,
        unit=unit,
        group=group_name,
        type=value_type,
    )


async def serialize_public_specifications(
    session: AsyncSession,
    product_id: Any,
    locale: Locale,
) -> list[PublicSpecDto]:
    """
    查询并序列化产品当前语言下的公开规格。

    输入：
        session: AsyncSession，数据库会话。
        product_id: Any，已通过产品发布门禁的产品 ID。
        locale: Locale，已启用的当前语言。

    输出：
        list[PublicSpecDto]，过滤停用定义、缺少翻译及非法存储组合后的规格。
    """
    rows = (
        await session.execute(
            select(
                ProductSpecValue,
                SpecificationDefinition,
                SpecificationDefinitionTranslation,
                SpecificationGroupTranslation,
            )
            .join(
                SpecificationDefinition,
                SpecificationDefinition.id == ProductSpecValue.definition_id,
            )
            .join(
                SpecificationGroup,
                SpecificationGroup.id == SpecificationDefinition.group_id,
            )
            .join(
                SpecificationDefinitionTranslation,
                (SpecificationDefinitionTranslation.definition_id == SpecificationDefinition.id)
                & (SpecificationDefinitionTranslation.locale_id == locale.id),
            )
            .join(
                SpecificationGroupTranslation,
                (SpecificationGroupTranslation.group_id == SpecificationGroup.id)
                & (SpecificationGroupTranslation.locale_id == locale.id),
            )
            .where(
                ProductSpecValue.product_id == product_id,
                ProductSpecValue.is_public.is_(True),
                SpecificationDefinition.status == "enabled",
                SpecificationGroup.status == "enabled",
            )
            .order_by(
                ProductSpecValue.sort_order,
                SpecificationGroup.sort_order,
                SpecificationDefinition.sort_order,
            )
        )
    ).all()

    result: list[PublicSpecDto] = []
    for value, definition, definition_translation, group_translation in rows:
        dto = serialize_public_spec(
            value,
            definition,
            definition_translation,
            group_translation,
            locale.code,
        )
        # 数据库约束之外仍采用失败闭合，避免历史脏数据进入公开响应。
        if dto is not None:
            result.append(dto)
    return result
