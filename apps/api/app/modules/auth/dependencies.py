"""FastAPI 当前用户与服务端 RBAC 依赖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Cookie, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.security import decode_access_token
from app.core.security.csrf import verify_csrf_token
from app.modules.users.models import User
from app.modules.users.service import collect_authorization, find_user_with_permissions


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias="junhui_access"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    从 HttpOnly access Cookie 校验并加载启用用户。

    输入：
        access_token: str | None，浏览器自动发送的访问 Cookie。
        session: AsyncSession，请求作用域数据库 session。

    输出：User，已预加载角色权限的当前用户。
    """
    settings = get_settings()
    user_id = decode_access_token(access_token or "", settings.jwt_signing_secret)
    if user_id is None:
        raise AppException(401, "authentication_required", "需要登录")
    user = await find_user_with_permissions(session, user_id=user_id)
    if user is None or not user.is_active:
        raise AppException(401, "authentication_required", "需要登录")
    return user


def require_permission(permission_code: str) -> Callable[..., User]:
    """
    创建要求单个原子权限的 FastAPI 依赖。

    输入：
        permission_code: str，resource.action 格式权限代码。

    输出：Callable[..., User]，通过时返回当前用户，缺少权限时返回 403。
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        _roles, permissions = collect_authorization(user)
        if permission_code not in permissions:
            raise AppException(403, "permission_denied", "没有执行此操作的权限")
        return user

    return dependency


def require_any_permission(*permission_codes: str) -> Callable[..., User]:
    """
    创建要求任一权限的 FastAPI 依赖。

    输入：
        permission_codes: str，允许通过的权限代码集合。

    输出：Callable[..., User]，拥有任一权限时返回当前用户。
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        _roles, permissions = collect_authorization(user)
        if not set(permission_codes).intersection(permissions):
            raise AppException(403, "permission_denied", "没有执行此操作的权限")
        return user

    return dependency


def require_role(role_name: str) -> Callable[..., User]:
    """
    创建仅用于少量系统级场景的角色依赖。

    输入：
        role_name: str，系统角色名称。

    输出：Callable[..., User]，具备指定角色时返回当前用户。
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        roles, _permissions = collect_authorization(user)
        if role_name not in roles:
            raise AppException(403, "role_required", "需要指定系统角色")
        return user

    return dependency


async def require_csrf(
    csrf_cookie: str | None = Cookie(default=None, alias="junhui_csrf"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """
    强制 Cookie 认证写请求提供匹配的双提交 CSRF token。

    输入：
        csrf_cookie: str | None，浏览器 CSRF Cookie。
        csrf_header: str | None，前端显式提交的 X-CSRF-Token。

    输出：None；缺失或不匹配时抛出 403。
    """
    if not verify_csrf_token(csrf_cookie, csrf_header):
        raise AppException(403, "csrf_failed", "CSRF 校验失败")
