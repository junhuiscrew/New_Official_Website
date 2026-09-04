"""Phase 3.3 Remediation 精确清理迁移契约测试。"""

import uuid
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_phase33_remediation_migration_remains_in_linear_history() -> None:
    """
    验证 Remediation 通过 0005 新迁移实现，不修改既有历史。

    输入：无。
    输出：None；断言 Alembic head 与迁移文件名正确。
    """
    api_root = Path(__file__).resolve().parents[1]
    script = ScriptDirectory(str(api_root / "alembic"))
    revision_ids = {revision.revision for revision in script.walk_revisions()}
    assert "20260904_0005" in revision_ids
    assert (api_root / "alembic/versions/20260904_0005_phase33_remediation.py").is_file()


def test_phase33_remediation_migration_only_disables_internal_public_lifecycle(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证 0005 只清理 ProductModel/Specification 遗留公开记录。

    输入：sqlite_database_url、monkeypatch。
    输出：None；断言 Product 公开状态不受影响。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    command.upgrade(config, "20260904_0004")

    sync_engine = create_engine(sqlite_database_url.replace("sqlite+aiosqlite", "sqlite"))
    metadata = MetaData()
    metadata.reflect(sync_engine)
    locales = metadata.tables["locales"]
    publications = metadata.tables["content_publications"]
    routes = metadata.tables["content_routes"]
    locale_id = uuid.uuid4()
    internal_owner_id = uuid.uuid4()
    product_owner_id = uuid.uuid4()
    with sync_engine.begin() as connection:
        connection.execute(
            locales.insert().values(
                id=locale_id.hex,
                code="migration-test",
                slug="migration-test",
                name="Migration Test",
                native_name="Migration Test",
                is_default=True,
                is_enabled=True,
                sort_order=1,
            )
        )
        connection.execute(
            publications.insert(),
            [
                {
                    "id": uuid.uuid4().hex,
                    "owner_type": "product_model",
                    "owner_id": internal_owner_id.hex,
                    "locale_id": locale_id.hex,
                    "status": "published",
                },
                {
                    "id": uuid.uuid4().hex,
                    "owner_type": "product",
                    "owner_id": product_owner_id.hex,
                    "locale_id": locale_id.hex,
                    "status": "published",
                },
            ],
        )
        connection.execute(
            routes.insert(),
            [
                {
                    "id": uuid.uuid4().hex,
                    "owner_type": "product_model",
                    "owner_id": internal_owner_id.hex,
                    "locale_id": locale_id.hex,
                    "path": "/migration-test/models/internal/",
                    "is_canonical": True,
                    "active": True,
                    "indexable": True,
                },
                {
                    "id": uuid.uuid4().hex,
                    "owner_type": "product",
                    "owner_id": product_owner_id.hex,
                    "locale_id": locale_id.hex,
                    "path": "/migration-test/products/public/",
                    "is_canonical": True,
                    "active": True,
                    "indexable": True,
                },
            ],
        )

    command.upgrade(config, "head")
    with sync_engine.connect() as connection:
        publication_rows = {
            row.owner_type: row.status for row in connection.execute(select(publications))
        }
        route_rows = {
            row.owner_type: (row.active, row.indexable)
            for row in connection.execute(select(routes))
        }
    assert publication_rows == {"product_model": "archived", "product": "published"}
    assert route_rows == {"product_model": (False, False), "product": (True, True)}
