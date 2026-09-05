"""Phase 3.2 Authentication 与 Cookie 会话行为测试。"""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.auth import _set_auth_cookies
from app.core.config.settings import Settings
from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthSession
from app.modules.content import models as content_models  # noqa: F401
from app.modules.users.models import User


@pytest.fixture
async def auth_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建包含全部认证依赖表的隔离异步数据库。

    输入：
        sqlite_database_url: str，测试专用数据库 URL。

    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，测试数据库 session factory。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "admin@example.com",
    password: str = "StrongPassword!2026",
    is_active: bool = True,
) -> User:
    """
    创建测试用户并使用正式密码哈希函数保存密码。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试数据库工厂。
        email: str，用户邮箱。
        password: str，测试明文密码。
        is_active: bool，账户启用状态。

    输出：User，已持久化用户。
    """
    async with session_factory() as session, session.begin():
        user = User(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            display_name="Phase 3.2 Admin",
            is_active=is_active,
        )
        session.add(user)
    return user


async def _build_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncClient:
    """
    创建覆盖数据库依赖的 ASGI 测试客户端。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试数据库工厂。

    输出：AsyncClient，带 Cookie 容器的 API 客户端。
    """
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.parametrize(
    ("submitted_email", "password", "is_active", "expected_status"),
    [
        ("ADMIN@EXAMPLE.COM", "StrongPassword!2026", True, 200),
        ("admin@example.com", "wrong-password", True, 401),
        ("admin@example.com", "StrongPassword!2026", False, 401),
    ],
)
async def test_login_handles_normalization_password_and_active_state(
    auth_session_factory: async_sessionmaker[AsyncSession],
    submitted_email: str,
    password: str,
    is_active: bool,
    expected_status: int,
) -> None:
    """
    验证登录统一邮箱大小写、不泄露错误原因并拒绝 inactive 用户。

    输入：参数化登录数据与测试数据库工厂。

    输出：None；断言 HTTP 状态和登录审计记录。
    """
    await _create_user(auth_session_factory, is_active=is_active)
    async with await _build_client(auth_session_factory) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": submitted_email, "password": password},
        )

    assert response.status_code == expected_status
    async with auth_session_factory() as session:
        actions = (await session.scalars(select(AuditLog.action))).all()
    assert actions == (["login.success"] if expected_status == 200 else ["login.failed"])


async def test_login_sets_httponly_credentials_and_current_user(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证登录响应设置 HttpOnly Cookie，且 current-user 可读取身份。

    输入：auth_session_factory，测试数据库工厂。

    输出：None；断言 Cookie 属性和 `/auth/me` 响应。
    """
    await _create_user(auth_session_factory)
    async with await _build_client(auth_session_factory) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword!2026"},
        )
        current_user = await client.get("/api/v1/auth/me")

    assert "HttpOnly" in login.headers.get_list("set-cookie")[0]
    assert login.cookies.get("junhui_refresh") is not None
    assert login.cookies.get("junhui_csrf") is not None
    assert current_user.status_code == 200
    assert current_user.json()["data"]["email"] == "admin@example.com"


async def test_refresh_rotates_credential_and_rejects_replay(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 refresh credential 每次使用都会轮换，旧值不可重放。

    输入：auth_session_factory，测试数据库工厂。

    输出：None；断言新旧 Cookie 与撤销状态。
    """
    await _create_user(auth_session_factory)
    async with await _build_client(auth_session_factory) as client:
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword!2026"},
        )
        old_refresh = client.cookies.get("junhui_refresh")
        csrf_token = client.cookies.get("junhui_csrf")
        rotated = await client.post(
            "/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_token or ""}
        )
        new_refresh = client.cookies.get("junhui_refresh")
        rotated_csrf = client.cookies.get("junhui_csrf")
        client.cookies.set("junhui_refresh", old_refresh)
        replay = await client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": client.cookies.get("junhui_csrf") or ""},
        )
        client.cookies.set("junhui_refresh", new_refresh)
        client.cookies.set("junhui_csrf", rotated_csrf)
        descendant_after_replay = await client.post(
            "/api/v1/auth/refresh", headers={"X-CSRF-Token": rotated_csrf or ""}
        )

    assert rotated.status_code == 200
    assert new_refresh != old_refresh
    assert replay.status_code == 401
    assert descendant_after_replay.status_code == 401


async def test_unknown_email_still_runs_dummy_password_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证未知邮箱仍执行 Argon2 路径，降低账号枚举计时差。"""
    verification_calls: list[tuple[str, str | None]] = []

    async def fake_find_user(*_args, **_kwargs):
        return None

    def fake_verify(password: str, password_hash: str | None) -> bool:
        verification_calls.append((password, password_hash))
        return False

    monkeypatch.setattr(auth_service, "find_user_with_permissions", fake_find_user)
    monkeypatch.setattr(auth_service, "verify_password_or_dummy", fake_verify, raising=False)
    result = await auth_service.authenticate_user(object(), "missing@example.com", "Unknown!2026")

    assert result is None
    assert verification_calls == [("Unknown!2026", None)]


def test_mixed_case_production_environment_still_sets_secure_cookies() -> None:
    """验证 APP_ENV 大小写不会绕过生产 Cookie Secure 属性。"""
    settings = Settings(
        app_env="Production",
        database_url="postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
        minio_secret_key="strong-minio-secret-at-least-32-bytes",
        minio_public_endpoint="storage.junhuiscrewbarrel.com",
        minio_public_secure=True,
        jwt_signing_secret="strong-jwt-signing-secret-at-least-32-bytes",
        refresh_token_secret="strong-refresh-token-secret-at-least-32-bytes",
        cors_allowed_origins=["https://junhuiscrewbarrel.com"],
        _env_file=None,
    )
    response = Response()
    _set_auth_cookies(response, User(id=uuid.uuid4()), "refresh-token", settings)

    auth_cookies = [
        value
        for value in response.headers.getlist("set-cookie")
        if value.startswith(("junhui_access=", "junhui_refresh="))
    ]
    assert len(auth_cookies) == 2
    assert all("Secure" in cookie for cookie in auth_cookies)


async def test_refresh_requires_matching_csrf_token(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 Cookie refresh 请求必须携带匹配的双提交 CSRF header。

    输入：auth_session_factory，测试数据库工厂。

    输出：None；断言缺失 CSRF 时返回 403。
    """
    await _create_user(auth_session_factory)
    async with await _build_client(auth_session_factory) as client:
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword!2026"},
        )
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 403


async def test_logout_revokes_refresh_session(
    auth_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证退出会撤销服务端 refresh session 并清理认证 Cookie。

    输入：auth_session_factory，测试数据库工厂。

    输出：None；断言数据库撤销状态和 current-user 变为 401。
    """
    await _create_user(auth_session_factory)
    async with await _build_client(auth_session_factory) as client:
        await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword!2026"},
        )
        csrf_token = client.cookies.get("junhui_csrf")
        logout = await client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token or ""}
        )
        current_user = await client.get("/api/v1/auth/me")

    async with auth_session_factory() as session:
        revoked_count = await session.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_not(None))
        )
        logout_audit = await session.scalar(select(AuditLog).where(AuditLog.action == "logout"))
    assert logout.status_code == 200
    assert current_user.status_code == 401
    assert revoked_count == 1
    assert logout_audit.user_id is not None
    assert logout_audit.target_id is not None
    assert logout_audit.user_agent == "python-httpx/0.28.1"
