"""Redirect Manager 的规范化与图安全校验。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.core.exceptions.handlers import AppException

OFFICIAL_HOST = "junhuiscrewbarrel.com"
LEGACY_HOST = "junhuiscrew.com"
ALLOWED_TARGET_HOSTS = frozenset(
    {OFFICIAL_HOST, f"www.{OFFICIAL_HOST}", LEGACY_HOST, f"www.{LEGACY_HOST}"}
)


@dataclass(frozen=True)
class RedirectEdge:
    """用于验证重定向图的只读边。"""

    source_host: str
    source_path: str
    target_url: str


def _source_url(host: str, path: str) -> str:
    """
    生成标准 HTTPS 来源 URL。

    输入：host 主机名与 path 精确路径。
    输出：str，规范化绝对来源 URL。
    """
    return f"https://{host.lower().rstrip('.')}{path}"


def normalize_redirect_target(target_url: str) -> str:
    """
    验证并规范化 Redirect 目标为正式主域 HTTPS URL。

    输入：target_url，候选绝对 URL。
    输出：str，规范化目标；不安全时抛出 AppException。
    """
    parsed = urlparse(target_url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() != "https"
        or hostname not in ALLOWED_TARGET_HOSTS
        or parsed.username
        or parsed.password
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        raise AppException(409, "unsafe_redirect_target", "重定向目标必须是正式主域的安全 HTTPS URL")
    netloc = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
    return urlunparse(("https", netloc, parsed.path, "", parsed.query, ""))


def validate_redirect_rule(
    source_host: str,
    source_path: str,
    target_url: str,
    existing_rules: list[RedirectEdge],
) -> str:
    """
    拒绝 self、loop、chain、duplicate 与 unsafe Redirect。

    输入：来源 host/path、目标 URL 和全部已启用现有边。
    输出：str，校验后的规范目标 URL。
    """
    host = source_host.strip().lower().rstrip(".")
    if not host or not source_path.startswith("/") or "//" in source_path:
        raise AppException(409, "invalid_redirect_path", "重定向来源必须是精确绝对路径")
    normalized_target = normalize_redirect_target(target_url)
    source_url = _source_url(host, source_path)
    if normalized_target == source_url:
        raise AppException(409, "self_redirect", "重定向来源与目标不能相同")

    edge_map = {
        _source_url(edge.source_host.strip().lower().rstrip("."), edge.source_path): normalize_redirect_target(edge.target_url)
        for edge in existing_rules
    }
    if source_url in edge_map:
        raise AppException(409, "duplicate_redirect", "同一来源只能存在一条重定向规则")

    # 先完整遍历以识别回到新来源的循环，再把普通多跳识别为 chain。
    cursor = normalized_target
    visited: set[str] = set()
    traversed_existing = False
    while cursor in edge_map:
        if cursor in visited:
            raise AppException(409, "redirect_loop", "现有重定向图已包含循环")
        visited.add(cursor)
        traversed_existing = True
        cursor = edge_map[cursor]
        if cursor == source_url:
            raise AppException(409, "redirect_loop", "新规则会形成重定向循环")
    if traversed_existing:
        raise AppException(409, "redirect_chain", "目标必须直接指向最终 canonical，不能形成链")
    return normalized_target
