"""Alembic migration 集成测试。"""

from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config


def test_alembic_upgrade_creates_phase31_tables(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证首版 migration 可以从空库升级到 head 并创建基础表。

    输入：
        sqlite_database_url: str，测试专用异步数据库 URL。
        monkeypatch: pytest.MonkeyPatch，用于覆盖迁移数据库配置。

    输出：None；断言失败时由 pytest 报告。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(api_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_root / "alembic"))

    command.upgrade(alembic_config, "head")

    sync_url = sqlite_database_url.replace("sqlite+aiosqlite", "sqlite")
    inspector = inspect(create_engine(sync_url))
    assert {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "locales",
    }.issubset(inspector.get_table_names())
