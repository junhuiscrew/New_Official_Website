"""登录验证与 refresh session 生命周期服务。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.core.security.passwords import verify_password_or_dummy
from app.modules.auth.models import AuthSession
from app.modules.users.models import User
from app.modules.users.service import find_user_with_permissions


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    """
    校验归一化邮箱、Argon2id 密码和账户启用状态。

    输入：
        session: AsyncSession，数据库 session。
        email: str，登录邮箱。
        password: str，登录明文密码。

    输出：User | None，认证成功返回用户，否则统一返回 None。
    """
    user = await find_user_with_permissions(session, email=email)
    password_valid = verify_password_or_dummy(password, user.password_hash if user else None)
    if user is None or not password_valid or not user.is_active:
        return None
    return user


async def create_refresh_session(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    ip: str | None,
    user_agent: str | None,
    rotated_from: AuthSession | None = None,
) -> tuple[str, AuthSession]:
    """
    创建只保存 HMAC 摘要的 refresh session。

    输入：session、用户、配置、请求上下文和可选轮换来源。

    输出：tuple[str, AuthSession]，仅向 Cookie 返回的明文凭据和数据库实体。
    """
    refresh_token = generate_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token, settings.refresh_token_secret),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        rotated_from_id=rotated_from.id if rotated_from else None,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(auth_session)
    await session.flush()
    return refresh_token, auth_session


async def rotate_refresh_session(
    session: AsyncSession,
    refresh_token: str,
    settings: Settings,
    *,
    ip: str | None,
    user_agent: str | None,
) -> tuple[User, str] | None:
    """
    原子撤销旧 refresh session 并签发新凭据。

    输入：session、明文 refresh token、配置与请求上下文。

    输出：tuple[User, str] | None，有效时返回用户与新凭据，失效返回 None。
    """
    token_hash = hash_refresh_token(refresh_token, settings.refresh_token_secret)
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash).with_for_update()
    )
    now = datetime.now(UTC)
    if auth_session is None:
        return None
    if auth_session.revoked_at is not None:
        # 已撤销凭据再次出现代表可能被盗；撤销同一用户全部后继会话以封闭重放链。
        await session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == auth_session.user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        auth_session.revoked_at = now
        return None
    user = await find_user_with_permissions(session, user_id=auth_session.user_id)
    if user is None or not user.is_active:
        auth_session.revoked_at = now
        return None
    auth_session.revoked_at = now
    auth_session.last_used_at = now
    new_token, _new_session = await create_refresh_session(
        session,
        user,
        settings,
        ip=ip,
        user_agent=user_agent,
        rotated_from=auth_session,
    )
    return user, new_token


async def revoke_refresh_session(
    session: AsyncSession,
    refresh_token: str | None,
    settings: Settings,
) -> AuthSession | None:
    """
    撤销与 Cookie refresh credential 对应的服务端会话。

    输入：session、可选明文凭据和配置。

    输出：AuthSession | None，找到并首次撤销返回会话，否则返回 None。
    """
    if not refresh_token:
        return None
    token_hash = hash_refresh_token(refresh_token, settings.refresh_token_secret)
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash).with_for_update()
    )
    if auth_session is None or auth_session.revoked_at is not None:
        return None
    auth_session.revoked_at = datetime.now(UTC)
    return auth_session
