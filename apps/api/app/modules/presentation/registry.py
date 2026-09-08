"""首页十四模块固定注册表与安全默认配置。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

HOMEPAGE_MODULE_KEYS: tuple[str, ...] = (
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
)

HOMEPAGE_PRODUCT_REFERENCE_MODULES = frozenset(
    {"hero", "core_product_families"}
)

HOMEPAGE_VARIANTS: dict[str, tuple[str, ...]] = {
    "hero": ("product-focus", "navy"),
    "core_product_families": ("product-rail", "light", "soft"),
    "materials": ("light", "soft", "rail"),
    "special_applications": ("light", "soft", "split"),
    "technologies": ("navy", "light", "soft"),
    "manufacturing_capability": ("split", "light", "soft"),
    "why_junhui": ("soft", "light", "navy"),
    "factory_equipment": ("split", "light", "soft"),
    "solutions": ("light", "soft", "rail"),
    "case_studies": ("soft", "light", "rail"),
    "technical_knowledge": ("light", "soft", "rail"),
    "certificates_patents": ("light", "soft", "navy"),
    "global_markets": ("soft", "light", "navy"),
    "rfq_cta": ("navy", "light", "soft"),
}

HOMEPAGE_MANAGEMENT_URLS: dict[str, str] = {
    "hero": "/trust/company",
    "core_product_families": "/catalog/products",
    "materials": "/catalog/materials",
    "special_applications": "/catalog/applications",
    "technologies": "/catalog/technologies",
    "manufacturing_capability": "/trust/capabilities",
    "why_junhui": "/trust/company",
    "factory_equipment": "/trust/equipment",
    "solutions": "/catalog/solutions",
    "case_studies": "/cases",
    "technical_knowledge": "/knowledge",
    "certificates_patents": "/trust",
    "global_markets": "/trust/company",
    "rfq_cta": "/privacy",
}

_DEFAULT_VARIANTS = {
    key: variants[0] for key, variants in HOMEPAGE_VARIANTS.items()
}


def default_homepage_config() -> dict[str, Any]:
    """
    创建不含业务正文和内部标识的十四模块默认配置。

    输入：无。
    输出：dict，调用方可安全修改的独立深拷贝。
    """
    return {
        "schema_version": 1,
        "modules": [
            {
                "key": key,
                "visible": True,
                "variant": _DEFAULT_VARIANTS[key],
                "product_slugs": [],
            }
            for key in HOMEPAGE_MODULE_KEYS
        ],
    }


def clone_homepage_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    深拷贝已验证配置，避免 JSON 字段草稿与应用版共享可变引用。

    输入：
        config: dict，已验证首页配置。
    输出：
        dict，独立配置副本。
    """
    return deepcopy(config)

