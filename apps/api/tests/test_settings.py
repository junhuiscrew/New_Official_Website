"""Phase 3.2 配置与生产安全失败快测试。"""

import pytest
from pydantic import ValidationError

from app.core.config.settings import Settings


@pytest.mark.parametrize("ttl_minutes", [0, 61])
def test_privacy_context_ttl_must_remain_short(ttl_minutes: int) -> None:
    """
    验证 Privacy context 配置只能位于 1 到 60 分钟的短时范围。

    输入：ttl_minutes，边界外的分钟数。
    输出：None；错误配置未被 Settings 拒绝时失败。
    """
    with pytest.raises(ValidationError):
        Settings(privacy_context_token_ttl_minutes=ttl_minutes, _env_file=None)


def test_production_rejects_default_secrets() -> None:
    """
    验证生产环境不能使用仓库内的开发示例 Secret。

    输入：无。

    输出：None；Settings 必须抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://junhui:junhui-local-dev@localhost:5432/junhui",
            minio_secret_key="change-me-minio-local-only",
            jwt_signing_secret="change-me-jwt-local-only",
            refresh_token_secret="change-me-refresh-local-only",
            cors_allowed_origins=["http://localhost:3000"],
            _env_file=None,
        )


def test_every_non_development_environment_rejects_default_secrets() -> None:
    """
    验证 test 等所有非 development 环境同样不能继承开发默认 Secret。

    输入：无。

    输出：None；Settings 必须抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://junhui:junhui-local-dev@localhost:5432/junhui",
            minio_secret_key="change-me-minio-local-only",
            jwt_signing_secret="change-me-jwt-local-only",
            refresh_token_secret="change-me-refresh-local-only",
            cors_allowed_origins=["http://testserver"],
            _env_file=None,
        )


def test_production_requires_explicit_non_local_cors_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 production 不能静默继承开发 CORS allowlist。"""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    secure_values = {
        "app_env": "production",
        "database_url": "postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
        "minio_secret_key": "strong-minio-secret-at-least-32-bytes",
        "jwt_signing_secret": "strong-jwt-signing-secret-at-least-32-bytes",
        "refresh_token_secret": "strong-refresh-token-secret-at-least-32-bytes",
        "_env_file": None,
    }
    with pytest.raises(ValidationError):
        Settings(**secure_values)
    with pytest.raises(ValidationError):
        Settings(**secure_values, cors_allowed_origins=["http://localhost:3000"])


def test_production_requires_database_username_and_password() -> None:
    """验证长但缺少密码的 DATABASE_URL 仍被拒绝。"""
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://prod_user@database.internal:5432/junhui",
            minio_secret_key="strong-minio-secret-at-least-32-bytes",
            jwt_signing_secret="strong-jwt-signing-secret-at-least-32-bytes",
            refresh_token_secret="strong-refresh-token-secret-at-least-32-bytes",
            cors_allowed_origins=["https://junhuiscrewbarrel.com"],
            _env_file=None,
        )


def test_production_accepts_explicit_secrets_and_origins() -> None:
    """
    验证生产环境在全部敏感配置显式提供后可以启动。

    输入：无。

    输出：None；断言配置被正确解析。
    """
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
        minio_access_key="prod-minio-access",
        minio_secret_key="strong-minio-secret-at-least-32-bytes",
        minio_public_endpoint="storage.junhuiscrewbarrel.com",
        minio_public_secure=True,
        jwt_signing_secret="strong-jwt-signing-secret-at-least-32-bytes",
        refresh_token_secret="strong-refresh-token-secret-at-least-32-bytes",
        cors_allowed_origins=["https://junhuiscrewbarrel.com"],
        _env_file=None,
    )

    assert settings.app_env == "production"
    assert settings.cors_allowed_origins == ["https://junhuiscrewbarrel.com"]


def test_production_rejects_internal_minio_public_endpoint() -> None:
    """验证生产预签名 URL 不能暴露 localhost 或 Docker 内部 minio 主机名。"""
    for endpoint in ("localhost:9000", "minio:9000"):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
                minio_public_endpoint=endpoint,
                minio_public_secure=True,
                minio_secret_key="strong-minio-secret-at-least-32-bytes",
                jwt_signing_secret="strong-jwt-signing-secret-at-least-32-bytes",
                refresh_token_secret="strong-refresh-token-secret-at-least-32-bytes",
                cors_allowed_origins=["https://junhuiscrewbarrel.com"],
                _env_file=None,
            )


def test_cors_rejects_wildcard_when_credentials_are_enabled() -> None:
    """
    验证 Cookie 认证场景不允许通配 Origin。

    输入：无。

    输出：None；Settings 必须抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        Settings(cors_allowed_origins=["*"], _env_file=None)


@pytest.mark.parametrize("environment", ["prod", "stage", "qa", "unknown"])
def test_unknown_environment_alias_is_rejected(environment: str) -> None:
    """验证环境名拼写或别名不能绕过 staging/production 安全策略。"""
    with pytest.raises(ValidationError):
        Settings(app_env=environment, _env_file=None)


@pytest.mark.parametrize(
    "origin",
    [
        "https://admin.localhost",
        "https://sub.localhost.",
        "https://127.0.0.2",
        "https://[::1]",
        "https://[::ffff:127.0.0.1]",
        "https://169.254.1.2",
    ],
)
def test_production_rejects_all_loopback_cors_hosts(origin: str) -> None:
    """验证 localhost 子域、尾点形式与 loopback IP 均不能作为生产 Origin。"""
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://prod_user:strong-db-secret@db:5432/junhui",
            minio_secret_key="strong-minio-secret-at-least-32-bytes",
            jwt_signing_secret="strong-jwt-signing-secret-at-least-32-bytes",
            refresh_token_secret="strong-refresh-token-secret-at-least-32-bytes",
            cors_allowed_origins=[origin],
            _env_file=None,
        )
