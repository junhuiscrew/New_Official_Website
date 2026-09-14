"""受控重定向管理器的额外保护规则。"""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from app.core.exceptions.handlers import AppException
from app.modules.discovery.redirects import RedirectEdge, validate_redirect_rule

_PROTECTED_PREFIXES = (
    "/api",
    "/admin",
    "/_nuxt",
    "/media",
    "/.well-known",
)
_PROTECTED_EXACT = {"/", "/robots.txt", "/sitemap.xml", "/zh-cn/", "/en/"}
_PROTECTED_SEGMENTS = ("/privacy/", "/request-a-quote/", "/contact/")


def validate_managed_redirect(
    *,
    source_host: str,
    source_path: str,
    target_url: str,
    existing_rules: list[RedirectEdge],
    active_paths: set[str],
) -> str:
    """
    校验后台受控重定向草稿，不进行任何网络访问。

    输入：
        source_host: str，允许名单内来源主机。
        source_path: str，来源精确路径。
        target_url: str，正式主域 HTTPS 目标。
        existing_rules: list[RedirectEdge]，需要参与冲突图检查的规则。
        active_paths: set[str]，当前真实有效内容路由。
    输出：
        str，规范化后的安全目标 URL。
    """
    decoded_path = unquote(source_path)
    lowered_path = decoded_path.lower()
    if (
        "?" in source_path
        or "#" in source_path
        or "\\" in decoded_path
        or any(ord(char) < 32 for char in decoded_path)
        or "/../" in f"{decoded_path}/"
        or decoded_path in _PROTECTED_EXACT
        or any(
            lowered_path == prefix or lowered_path.startswith(f"{prefix}/")
            for prefix in _PROTECTED_PREFIXES
        )
        or any(segment in f"{lowered_path.rstrip('/')}/" for segment in _PROTECTED_SEGMENTS)
        or source_path in active_paths
    ):
        raise AppException(409, "protected_redirect_path", "该来源路径属于受保护或现有有效页面")
    parsed = urlparse(target_url)
    if parsed.query:
        raise AppException(409, "redirect_query_forbidden", "受控重定向目标不允许携带查询参数")
    if parsed.port is not None:
        raise AppException(409, "unsafe_redirect_target", "重定向目标不得指定自定义端口")
    return validate_redirect_rule(source_host, source_path, target_url, existing_rules)
