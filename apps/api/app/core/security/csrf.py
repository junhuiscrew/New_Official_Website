"""Cookie 认证写请求的双提交 CSRF 工具。"""

import hmac
import secrets


def create_csrf_token() -> str:
    """
    创建可由前端读取并回传的高熵 CSRF token。

    输入：无。

    输出：str，URL-safe CSRF token。
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    """
    使用常量时间比较验证 Cookie 与 Header 中的 CSRF token。

    输入：
        cookie_token: str | None，非 HttpOnly CSRF Cookie。
        header_token: str | None，X-CSRF-Token Header。

    输出：bool，两者存在且一致时为 true。
    """
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)
