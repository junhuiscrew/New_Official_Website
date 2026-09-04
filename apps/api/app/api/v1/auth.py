"""登录、刷新、退出与 Current User API。"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.core.security import create_access_token, create_csrf_token, verify_csrf_token
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import CurrentUserData, LoginRequest, LogoutData
from app.modules.auth.service import (
    authenticate_user,
    create_refresh_session,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/auth", tags=["authentication"])


def _current_user_data(user: User) -> CurrentUserData:
    """
    将 ORM 用户转换为不含密码和 token 的 API 输出。

    输入：
        user: User，已加载授权关系的用户。

    输出：CurrentUserData，安全用户信息。
    """
    roles, permissions = collect_authorization(user)
    return CurrentUserData(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        permissions=permissions,
    )


def _set_auth_cookies(
    response: Response,
    user: User,
    refresh_token: str,
    settings: Settings,
) -> None:
    """
    设置 HttpOnly 访问/刷新 Cookie 与双提交 CSRF Cookie。

    输入：response、用户、明文刷新凭据和运行配置。

    输出：None；在响应对象上追加 Set-Cookie headers。
    """
    secure = settings.auth_cookie_secure or settings.app_env in {"staging", "production"}
    access_token = create_access_token(
        user.id, settings.jwt_signing_secret, settings.access_token_ttl_minutes
    )
    response.set_cookie(
        "junhui_access",
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    response.set_cookie(
        "junhui_refresh",
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/v1/auth",
    )
    response.set_cookie(
        "junhui_csrf",
        create_csrf_token(),
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=False,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """
    清理所有认证 Cookie。

    输入：
        response: Response，当前 FastAPI 响应。

    输出：None；写入三个过期 Cookie。
    """
    response.delete_cookie("junhui_access", path="/")
    response.delete_cookie("junhui_refresh", path="/api/v1/auth")
    response.delete_cookie("junhui_csrf", path="/")


def _require_csrf(cookie_token: str | None, header_token: str | None) -> None:
    """
    强制 refresh/logout 请求通过双提交 CSRF 校验。

    输入：Cookie token 与 Header token。

    输出：None；不匹配时抛出 403 AppException。
    """
    if not verify_csrf_token(cookie_token, header_token):
        raise AppException(403, "csrf_failed", "CSRF 校验失败")


@router.post("/login", response_model=ApiResponse[CurrentUserData])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[CurrentUserData]:
    """
    校验用户密码并创建 refresh session。

    输入：登录数据、请求响应对象和数据库 session。

    输出：ApiResponse[CurrentUserData]，成功时同时设置认证 Cookie。
    """
    settings = get_settings()
    ip, user_agent = get_client_context(request)
    async with session.begin():
        user = await authenticate_user(session, str(payload.email), payload.password)
        if user is None:
            write_audit_log(
                session,
                action="login.failed",
                target_type="user",
                ip=ip,
                user_agent=user_agent,
                metadata={"email": str(payload.email).strip().lower()},
            )
        else:
            refresh_token, _auth_session = await create_refresh_session(
                session, user, settings, ip=ip, user_agent=user_agent
            )
            write_audit_log(
                session,
                action="login.success",
                target_type="user",
                user_id=user.id,
                target_id=str(user.id),
                ip=ip,
                user_agent=user_agent,
            )
    if user is None:
        raise AppException(401, "invalid_credentials", "邮箱或密码错误")
    _set_auth_cookies(response, user, refresh_token, settings)
    return success_response(_current_user_data(user))


@router.post("/refresh", response_model=ApiResponse[CurrentUserData])
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="junhui_refresh"),
    csrf_cookie: str | None = Cookie(default=None, alias="junhui_csrf"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[CurrentUserData]:
    """
    校验 CSRF 并原子轮换 refresh credential。

    输入：请求响应、认证 Cookie/Header 和数据库 session。

    输出：ApiResponse[CurrentUserData]，成功时替换全部认证 Cookie。
    """
    _require_csrf(csrf_cookie, csrf_header)
    if not refresh_token:
        raise AppException(401, "invalid_refresh", "刷新会话无效")
    settings = get_settings()
    ip, user_agent = get_client_context(request)
    async with session.begin():
        rotated = await rotate_refresh_session(
            session, refresh_token, settings, ip=ip, user_agent=user_agent
        )
    if rotated is None:
        _clear_auth_cookies(response)
        raise AppException(401, "invalid_refresh", "刷新会话无效")
    user, new_refresh_token = rotated
    _set_auth_cookies(response, user, new_refresh_token, settings)
    return success_response(_current_user_data(user))


@router.post("/logout", response_model=ApiResponse[LogoutData])
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="junhui_refresh"),
    csrf_cookie: str | None = Cookie(default=None, alias="junhui_csrf"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[LogoutData]:
    """
    撤销服务端 refresh session 并删除认证 Cookie。

    输入：请求响应、认证 Cookie/Header 和数据库 session。

    输出：ApiResponse[LogoutData]，返回撤销结果。
    """
    _require_csrf(csrf_cookie, csrf_header)
    ip, user_agent = get_client_context(request)
    async with session.begin():
        revoked_session = await revoke_refresh_session(session, refresh_token, get_settings())
        write_audit_log(
            session,
            action="logout",
            target_type="auth_session",
            user_id=revoked_session.user_id if revoked_session else None,
            target_id=str(revoked_session.id) if revoked_session else None,
            ip=ip,
            user_agent=user_agent,
            metadata={"revoked": revoked_session is not None},
        )
    _clear_auth_cookies(response)
    return success_response(LogoutData(revoked=revoked_session is not None))


@router.get("/me", response_model=ApiResponse[CurrentUserData])
async def current_user(user: User = Depends(get_current_user)) -> ApiResponse[CurrentUserData]:
    """
    返回当前登录用户、角色和权限代码。

    输入：
        user: User，由 get_current_user 强制认证。

    输出：ApiResponse[CurrentUserData]，安全用户信息。
    """
    return success_response(_current_user_data(user))
