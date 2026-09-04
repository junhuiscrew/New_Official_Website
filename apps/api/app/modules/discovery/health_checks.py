"""可解释的 SEO 与 GEO 内容健康提示。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

OFFICIAL_ORIGIN = "https://junhuiscrewbarrel.com"


def seo_health_checks(
    *,
    seo: Any | None,
    canonical_path: str | None,
    in_sitemap: bool,
    internal_link_count: int,
    has_public_handler: bool = True,
    has_broken_relation_target: bool = False,
) -> list[dict[str, str]]:
    """
    返回 SEO 配置问题提示，不伪装为搜索排名评分。

    输入：SEO 文档、canonical、Sitemap 状态与内部链接数。
    输出：list[dict[str, str]]，稳定问题代码和中文说明。
    """
    issues: list[dict[str, str]] = []
    if seo is None or not seo.seo_title:
        issues.append({"code": "missing_seo_title", "message": "缺少 SEO 标题"})
    if seo is None or not seo.meta_description:
        issues.append({"code": "missing_meta_description", "message": "缺少 Meta 描述"})
    if not canonical_path:
        issues.append({"code": "missing_canonical", "message": "缺少 canonical 路由"})
    if seo is not None and not seo.robots_index and in_sitemap:
        issues.append({"code": "noindex_in_sitemap", "message": "noindex 页面不应进入 Sitemap"})
    if (
        seo is not None
        and seo.canonical_override
        and canonical_path
        and seo.canonical_override != OFFICIAL_ORIGIN + canonical_path
    ):
        issues.append(
            {
                "code": "canonical_override_excludes_sitemap",
                "message": "canonical override 指向其他 URL，当前页面已从 Sitemap 与 hreflang 排除",
            }
        )
    if not has_public_handler:
        issues.append(
            {
                "code": "indexable_route_missing_public_handler",
                "message": "可索引路由缺少公开处理器",
            }
        )
    if internal_link_count == 0:
        issues.append({"code": "missing_internal_links", "message": "页面缺少内部链接入口"})
    if has_broken_relation_target:
        issues.append(
            {"code": "broken_relation_target", "message": "结构化关系包含不可公开的目标"}
        )
    return issues


def geo_health_checks(
    *,
    geo: Any | None,
    source_count: int,
    has_first_party_evidence: bool,
    claims_match_server_visible_content: bool = True,
    reviewer_verified: bool = True,
) -> list[dict[str, str]]:
    """
    返回 GEO 可引用性治理提示，不输出不可解释排名分数。

    输入：GEO 文档、来源数量与第一方证据状态。
    输出：list[dict[str, str]]，稳定问题代码和中文说明。
    """
    issues: list[dict[str, str]] = []
    checks = (
        ("missing_direct_answer", geo is None or not geo.direct_answer, "缺少直接答案"),
        ("missing_key_facts", geo is None or not geo.key_facts_json, "缺少关键事实"),
        ("missing_evidence", geo is None or not geo.evidence_json, "缺少证据"),
        (
            "reviewer_missing_or_unverified",
            geo is None or geo.reviewer_id is None or not reviewer_verified,
            "缺少已核验的真实审核专家",
        ),
        ("missing_source", source_count == 0, "缺少可核验来源"),
        ("first_party_evidence_missing", not has_first_party_evidence, "缺少第一方案例或测试证据"),
        (
            "claim_not_in_server_visible_content",
            not claims_match_server_visible_content,
            "GEO 声明无法在服务端可见事实中找到",
        ),
    )
    for code, failed, message in checks:
        if failed:
            issues.append({"code": code, "message": message})
    if geo is None or geo.last_reviewed_at is None:
        issues.append({"code": "missing_last_reviewed", "message": "缺少事实复核日期"})
    elif geo.last_reviewed_at < datetime.now(UTC) - timedelta(days=365):
        issues.append({"code": "stale_review", "message": "事实复核已超过一年"})
    return issues
