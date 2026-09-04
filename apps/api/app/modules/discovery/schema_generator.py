"""与公开可见事实一致的统一 Schema.org JSON-LD 生成器。"""

from __future__ import annotations

from typing import Any

from app.core.exceptions.handlers import AppException


def build_organization_schema() -> dict[str, Any]:
    """
    生成正式站点组织 Schema。

    输入：无。
    输出：dict[str, Any]，只包含已冻结的公司站点事实。
    """
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Junhui",
        "url": "https://junhuiscrewbarrel.com/",
    }


def build_website_schema() -> dict[str, Any]:
    """
    生成正式主域的 WebSite Schema。

    输入：无。
    输出：dict[str, Any]，不声明尚未实现的站内搜索动作。
    """
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Junhui Global Website",
        "url": "https://junhuiscrewbarrel.com/",
        "publisher": build_organization_schema(),
    }


def build_video_schema(video: dict[str, Any]) -> dict[str, Any]:
    """
    根据已有公开视频事实生成 VideoObject Schema。

    输入：video，含 name、thumbnail_url、upload_date、content_url 等公开字段。
    输出：dict[str, Any]，VideoObject JSON-LD；关键事实缺失时拒绝生成。
    """
    required = ("name", "thumbnail_url", "upload_date")
    if any(not video.get(field) for field in required):
        raise AppException(409, "video_schema_facts_required", "VideoObject 缺少名称、缩略图或上传日期")
    result = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": video["name"],
        "description": video.get("description"),
        "thumbnailUrl": video["thumbnail_url"],
        "uploadDate": video["upload_date"],
        "contentUrl": video.get("content_url"),
        "embedUrl": video.get("embed_url"),
        "duration": video.get("duration"),
    }
    return {key: value for key, value in result.items() if value is not None}


def build_product_schema(product: dict[str, Any]) -> dict[str, Any]:
    """
    从公开 Product DTO 生成不含虚构商业或评价数据的 Schema。

    输入：product，公开且可见的产品字段。
    输出：dict[str, Any]，Product JSON-LD。
    """
    result = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product["name"],
        "description": product.get("description"),
        "url": product["url"],
        "brand": {"@type": "Brand", "name": "Junhui"},
    }
    if product.get("image"):
        result["image"] = product["image"]
    return {key: value for key, value in result.items() if value is not None}


def build_person_schema(person: dict[str, Any]) -> dict[str, Any]:
    """
    仅为已核验真实人物生成 Person Schema。

    输入：person，公开 Author/Expert DTO。
    输出：dict[str, Any]，Person JSON-LD；未核验时拒绝。
    """
    if not person.get("is_real_person_verified"):
        raise AppException(409, "verified_person_required", "Person Schema 只能使用已核验的真实人物")
    result = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": person["name"],
        "jobTitle": person.get("job_title"),
        "description": person.get("short_bio"),
        "url": person.get("url"),
        "sameAs": [person["linkedin_url"]] if person.get("linkedin_url") else None,
    }
    return {key: value for key, value in result.items() if value is not None}


def build_article_schema(article: dict[str, Any], author: dict[str, Any]) -> dict[str, Any]:
    """
    为知识文章生成带真实作者的 Article Schema。

    输入：article 公开文章字段与 author 公开人物字段。
    输出：dict[str, Any]，Article JSON-LD；虚构作者时拒绝。
    """
    if not author.get("is_real_person_verified"):
        raise AppException(409, "verified_author_required", "Article Schema 必须使用已核验的真实作者")
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["headline"],
        "description": article.get("description"),
        "url": article["url"],
        "author": {"@type": "Person", "name": author["name"]},
        "publisher": build_organization_schema(),
        **({"dateModified": article["date_modified"]} if article.get("date_modified") else {}),
    }


def build_breadcrumb_schema(items: list[dict[str, str]]) -> dict[str, Any]:
    """
    从页面可见面包屑生成一致的 BreadcrumbList。

    输入：items，按页面展示顺序提供的 name/url 项。
    输出：dict[str, Any]，BreadcrumbList JSON-LD。
    """
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["name"], "item": item["url"]}
            for index, item in enumerate(items, start=1)
        ],
    }


def build_webpage_schema(page: dict[str, Any]) -> dict[str, Any]:
    """
    从公开 Case 等页面字段生成基础 WebPage Schema。

    输入：page，包含 name/url/description 的公开字段。
    输出：dict[str, Any]，不含客户内部身份数据的 WebPage JSON-LD。
    """
    result = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": page["name"],
        "url": page["url"],
        "description": page.get("description"),
        "isPartOf": {"@type": "WebSite", "url": "https://junhuiscrewbarrel.com/"},
    }
    return {key: value for key, value in result.items() if value is not None}


def build_faq_schema(items: list[dict[str, str]], *, enabled: bool) -> dict[str, Any] | None:
    """
    在功能开关开启时按可见 FAQ 生成 FAQPage。

    输入：可见问答 items 与 enabled 开关。
    输出：dict 或 None；关闭时不生成且不承诺 Rich Result。
    """
    if not enabled or not items:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in items
        ],
    }
