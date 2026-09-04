"""Authority Content 的公开 DTO 白名单序列化。"""

from __future__ import annotations

from typing import Any


def serialize_public_case(case: Any, translation: dict[str, Any]) -> dict[str, Any]:
    """
    使用显式白名单序列化客户案例，按单项许可放行客户身份信息。

    输入：
        case: Any，CaseStudy ORM 实体或具备同名属性的对象。
        translation: dict[str, Any]，已经过发布校验的当前语言正文。

    输出：dict[str, Any]，不含内部客户字段和隐私开关的公开 DTO。
    """
    # 白名单从零构造，禁止先 dump ORM 后删除敏感字段的脆弱做法。
    result: dict[str, Any] = {
        "slug": case.slug,
        "country_code": case.country_code,
        "industry": case.industry,
        "machine_brand": case.machine_brand,
        "machine_model": case.machine_model,
        "screw_diameter": case.screw_diameter,
        "filler_percentage": case.filler_percentage,
        "featured": case.featured,
        "primary_media_id": str(case.primary_media_id) if case.primary_media_id else None,
        "translation": {
            key: translation.get(key)
            for key in (
                "title",
                "summary",
                "client_description",
                "problem",
                "analysis",
                "solution",
                "result",
                "engineer_comment",
            )
        },
    }
    if case.client_name_public and case.client_name:
        result["client_name"] = case.client_name
    if case.client_address_public and case.client_address:
        result["client_address"] = case.client_address
    if case.client_logo_public and case.client_logo_media_id:
        result["client_logo_media_id"] = str(case.client_logo_media_id)
    return result
