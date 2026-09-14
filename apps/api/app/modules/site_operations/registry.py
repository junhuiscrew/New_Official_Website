"""站点运营可选目标和等值初始配置注册表。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# 站内目标由服务端拥有，后台只保存稳定键，不能持久化任意 URL。
SITE_TARGET_PATHS: dict[str, dict[str, str]] = {
    "home": {"zh-CN": "/zh-cn/", "en": "/en/"},
    "products": {"zh-CN": "/zh-cn/products/", "en": "/en/products/"},
    "solutions": {"zh-CN": "/zh-cn/solutions/", "en": "/en/solutions/"},
    "materials": {"zh-CN": "/zh-cn/materials/", "en": "/en/materials/"},
    "applications": {"zh-CN": "/zh-cn/applications/", "en": "/en/applications/"},
    "technologies": {"zh-CN": "/zh-cn/technologies/", "en": "/en/technologies/"},
    "capabilities": {"zh-CN": "/zh-cn/capabilities/", "en": "/en/capabilities/"},
    "case_studies": {"zh-CN": "/zh-cn/case-studies/", "en": "/en/case-studies/"},
    "knowledge": {"zh-CN": "/zh-cn/knowledge/", "en": "/en/knowledge/"},
    "about": {"zh-CN": "/zh-cn/about/", "en": "/en/about/"},
    "contact": {"zh-CN": "/zh-cn/contact/", "en": "/en/contact/"},
    "request_a_quote": {"zh-CN": "/zh-cn/request-a-quote/", "en": "/en/request-a-quote/"},
    "downloads": {"zh-CN": "/zh-cn/downloads/", "en": "/en/downloads/"},
    "privacy": {"zh-CN": "/zh-cn/privacy/", "en": "/en/privacy/"},
    "search": {"zh-CN": "/zh-cn/search/", "en": "/en/search/"},
    "sitemap": {"zh-CN": "/sitemap.xml", "en": "/sitemap.xml"},
}

SITE_TARGET_LABELS: dict[str, dict[str, str]] = {
    "home": {"zh-CN": "首页", "en": "Home"},
    "products": {"zh-CN": "产品", "en": "Products"},
    "solutions": {"zh-CN": "解决方案", "en": "Solutions"},
    "materials": {"zh-CN": "材料", "en": "Materials"},
    "applications": {"zh-CN": "应用", "en": "Applications"},
    "technologies": {"zh-CN": "工艺技术", "en": "Technologies"},
    "capabilities": {"zh-CN": "制造能力", "en": "Capabilities"},
    "case_studies": {"zh-CN": "案例", "en": "Case Studies"},
    "knowledge": {"zh-CN": "知识中心", "en": "Knowledge"},
    "about": {"zh-CN": "关于骏辉", "en": "About"},
    "contact": {"zh-CN": "联系我们", "en": "Contact"},
    "request_a_quote": {"zh-CN": "提交询价", "en": "Request a Quote"},
    "downloads": {"zh-CN": "下载资料", "en": "Downloads"},
    "privacy": {"zh-CN": "隐私政策", "en": "Privacy"},
    "search": {"zh-CN": "站内搜索", "en": "Search"},
    "sitemap": {"zh-CN": "网站地图", "en": "Sitemap"},
}


def default_brand_config() -> dict[str, Any]:
    """
    返回不改变现有视觉的品牌初始配置。

    输入：无。
    输出：dict，包含完整中英文名称；媒体为空时前台使用现有批准 Logo。
    """
    return {
        "translations": {
            "zh-CN": {"display_name": "骏辉全球官网", "short_name": "骏辉"},
            "en": {"display_name": "Junhui Global Website", "short_name": "JUNHUI"},
        }
    }


def default_navigation_config(locale_code: str) -> dict[str, Any]:
    """
    返回与当前导航等值的初始配置。

    输入：locale_code: str，zh-CN 或 en。
    输出：dict，包含顶部菜单及页脚分组；工艺技术不提升为一级菜单。
    """
    labels = {key: values[locale_code] for key, values in SITE_TARGET_LABELS.items()}
    footer_item_labels = {
        **labels,
        "products": "查看全部产品" if locale_code == "zh-CN" else "View All Products",
    }
    header_keys = [
        "products",
        "solutions",
        "materials",
        "applications",
        "capabilities",
        "case_studies",
        "knowledge",
        "about",
    ]
    # 初始页脚严格复刻现有分组；运营人员应用草稿前，不能悄悄扩展公开链接。
    groups = [
        ("products", ["products"]),
        ("solutions", ["solutions"]),
        ("knowledge", ["knowledge"]),
        ("contact", ["contact", "request_a_quote", "downloads"]),
        ("legal", ["privacy", "sitemap"]),
    ]
    config = {
        "header_items": [
            {"id": key.replace("_", "-"), "label": labels[key], "target_key": key, "enabled": True}
            for key in header_keys
        ],
        "footer_groups": [
            {
                "id": group_id,
                "title": labels.get(group_id, "法律" if locale_code == "zh-CN" else "Legal"),
                "enabled": True,
                "items": [
                    {
                        "id": key.replace("_", "-"),
                        "label": footer_item_labels[key],
                        "target_key": key,
                        "enabled": True,
                    }
                    for key in item_keys
                ],
            }
            for group_id, item_keys in groups
        ],
    }
    return deepcopy(config)
