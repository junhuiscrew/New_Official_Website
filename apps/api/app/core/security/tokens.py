"""短期访问令牌和高熵刷新凭据工具。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


def create_access_token(user_id: uuid.UUID, secret: str, ttl_minutes: int) -> str:
    """
    创建仅用于短期 API 访问的签名 JWT。

    输入：
        user_id: uuid.UUID，认证用户ID。
        secret: str，服务端 JWT 签名 Secret。
        ttl_minutes: int，访问令牌有效分钟数。

    输出：str，HS256 签名访问令牌。
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> uuid.UUID | None:
    """
    校验访问令牌签名、有效期、类型和用户ID。

    输入：
        token: str，客户端 Cookie 中的 JWT。
        secret: str，服务端签名 Secret。

    输出：uuid.UUID | None，有效时返回用户ID，失败返回 None。
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def generate_refresh_token() -> str:
    """
    生成不可预测的 refresh credential。

    输入：无。

    输出：str，至少 256 bit 随机强度的 URL-safe 凭据。
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str, secret: str) -> str:
    """
    使用服务端 Secret 计算 refresh credential 的 HMAC 摘要。

    输入：
        token: str，明文 refresh credential。
        secret: str，服务端 refresh Secret。

    输出：str，数据库可保存的十六进制 SHA-256 HMAC。
    """
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
