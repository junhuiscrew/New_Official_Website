"""测试公共夹具：为 API、迁移与 Seed 提供隔离的临时数据库。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    """
    创建测试专用 SQLite 异步数据库 URL。

    输入：
        tmp_path: Path，pytest 为当前测试创建的临时目录。

    输出：
        str，可供 SQLAlchemy 与 Alembic 使用的异步数据库 URL。
    """
    database_path = tmp_path / "junhui-test.db"
    return f"sqlite+aiosqlite:///{database_path.as_posix()}"


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """
    在每个测试前后清理配置缓存，避免环境变量相互污染。

    输入：
        monkeypatch: pytest.MonkeyPatch，用于隔离环境变量。

    输出：
        Iterator[None]，测试生命周期控制器。
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test_user:phase32-test-db-secret@postgres-test:5432/junhui_test",
    )
    monkeypatch.setenv("MINIO_SECRET_KEY", "junhui-minio-development-secret-32-bytes")
    monkeypatch.setenv("JWT_SIGNING_SECRET", "phase32-test-jwt-signing-secret-at-least-32-bytes")
    monkeypatch.setenv("REFRESH_TOKEN_SECRET", "phase32-test-refresh-secret-at-least-32-bytes")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://testserver"]')
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
