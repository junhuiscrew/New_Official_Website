"""Phase 3.2 数据库结构与迁移契约测试。"""

from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql

from alembic import command
from alembic.config import Config
from app.modules.audit.models import AuditLog
from app.modules.content.models import ContentRevision
from app.modules.users.models import User


def test_user_email_compiles_to_postgresql_citext() -> None:
    """
    验证 PostgreSQL 下用户邮箱使用大小写不敏感 CITEXT。

    输入：无。

    输出：None；断言 PostgreSQL 类型编译结果。
    """
    compiled_type = User.__table__.c.email.type.compile(dialect=postgresql.dialect())
    assert compiled_type == "CITEXT"


def test_phase32_migration_creates_foundation_tables_and_default_locale_index(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证从空库升级到 head 会创建 Phase 3.2 表和默认语言唯一索引。

    输入：
        sqlite_database_url: str，测试专用异步 SQLite URL。
        monkeypatch: pytest.MonkeyPatch，用于覆盖 Alembic 数据库地址。

    输出：None；断言新表及索引存在。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(api_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_root / "alembic"))

    command.upgrade(alembic_config, "head")

    sync_url = sqlite_database_url.replace("sqlite+aiosqlite", "sqlite")
    inspector = inspect(create_engine(sync_url))
    assert {
        "auth_sessions",
        "translation_statuses",
        "content_publications",
        "content_routes",
        "content_revisions",
        "audit_logs",
    }.issubset(inspector.get_table_names())
    locale_indexes = {index["name"] for index in inspector.get_indexes("locales")}
    assert "ux_locales_single_default" in locale_indexes
    route_indexes = {index["name"] for index in inspector.get_indexes("content_routes")}
    assert "ux_content_routes_one_canonical" in route_indexes


def test_json_documents_compile_to_postgresql_jsonb() -> None:
    """验证修订快照与审计元数据在 PostgreSQL 使用 JSONB。"""
    dialect = postgresql.dialect()
    assert ContentRevision.__table__.c.snapshot_jsonb.type.compile(dialect=dialect) == "JSONB"
    assert AuditLog.__table__.c.metadata_json.type.compile(dialect=dialect) == "JSONB"
