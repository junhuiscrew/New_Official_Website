"""系统固定 SitePage 模型与迁移测试。"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import Uuid, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from alembic.config import Config
from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.content.models import SitePage, SitePageTranslation
from app.modules.localization.models import Locale


async def _create_site_page_model_tables(engine: AsyncEngine) -> None:
    """
    仅创建固定页面模型测试所需的三张表。

    输入：engine，隔离 SQLite 异步引擎。
    输出：None，创建 locales、site_pages 与 site_page_translations。
    """
    tables = [Locale.__table__, SitePage.__table__, SitePageTranslation.__table__]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(sync_connection, tables=tables)
        )


def test_site_page_tables_are_registered_with_chinese_comments() -> None:
    """
    验证固定页面及其翻译表进入 metadata，且所有字段都有中文注释。

    输入：无。
    输出：None；表缺失或字段未提供中文注释时失败。
    """
    assert {"site_pages", "site_page_translations"}.issubset(Base.metadata.tables)
    for table_name in ("site_pages", "site_page_translations"):
        table = Base.metadata.tables[table_name]
        assert table.comment
        assert all(column.comment for column in table.columns)


def test_site_page_identity_and_status_are_database_constrained() -> None:
    """
    验证固定页面使用既有 ORM UUID 主键，并只允许 products 与既有业务状态。

    输入：无。
    输出：None；UUID 默认、唯一约束或状态检查约束缺失时失败。
    """
    page_table = Base.metadata.tables["site_pages"]
    translation_table = Base.metadata.tables["site_page_translations"]

    assert isinstance(page_table.c.id.type, Uuid)
    assert page_table.c.id.primary_key is True
    assert page_table.c.id.default is not None
    assert page_table.c.id.server_default is None
    assert {constraint.name for constraint in page_table.constraints} >= {
        "uq_site_pages_system_key",
        "ck_site_pages_site_page_system_key_value",
        "ck_site_pages_site_page_status_value",
    }
    assert "uq_site_page_translation_locale" in {
        constraint.name for constraint in translation_table.constraints
    }


@pytest.mark.asyncio
async def test_site_page_orm_creation_assigns_real_uuid(
    sqlite_database_url: str,
) -> None:
    """
    验证既有 ORM UUID mixin 在创建 SitePage 时生成真实 UUID。

    输入：sqlite_database_url，pytest 临时 SQLite 数据库。
    输出：None；flush 后主键不是 UUID 时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    try:
        await _create_site_page_model_tables(engine)
        factory = create_session_factory(engine)
        async with factory() as session, session.begin():
            page = SitePage(system_key="products", status="enabled")
            session.add(page)
            await session.flush()
            assert isinstance(page.id, uuid.UUID)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "system_key",
    ["products", "privacy", "home", "contact", "request-a-quote"],
)
async def test_site_page_database_accepts_supported_fixed_page_identities(
    sqlite_database_url: str,
    system_key: str,
) -> None:
    """
    验证数据库只接受代码明确登记的固定页面身份。

    输入：
        sqlite_database_url: str，隔离 SQLite 数据库地址。
        system_key: str，受支持的固定页面键。

    输出：
        None；任一登记页面无法写入时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    try:
        await _create_site_page_model_tables(engine)
        factory = create_session_factory(engine)
        async with factory() as session, session.begin():
            page = SitePage(system_key=system_key, status="enabled")
            session.add(page)
            await session.flush()
            assert isinstance(page.id, uuid.UUID)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_values",
    [
        {"system_key": "about", "status": "enabled"},
        {"system_key": "products", "status": "draft"},
    ],
)
async def test_site_page_database_rejects_unsupported_identity_or_status(
    sqlite_database_url: str,
    invalid_values: dict[str, str],
) -> None:
    """
    验证数据库拒绝未登记 key 和既有业务语义之外的状态。

    输入：sqlite_database_url，隔离 SQLite；invalid_values，非法模型字段。
    输出：None；非法固定页面可写入时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    try:
        await _create_site_page_model_tables(engine)
        factory = create_session_factory(engine)
        async with factory() as session:
            session.add(SitePage(**invalid_values))
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_site_page_and_translation_uniqueness_is_enforced(
    sqlite_database_url: str,
) -> None:
    """
    验证 system_key 唯一，且同一固定页面每种语言只能有一条真实翻译。

    输入：sqlite_database_url，pytest 临时 SQLite 数据库。
    输出：None；任一唯一约束可被绕过时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    try:
        await _create_site_page_model_tables(engine)
        factory = create_session_factory(engine)
        async with factory() as session, session.begin():
            locale = Locale(
                code="zh-CN",
                slug="zh-cn",
                name="Chinese",
                native_name="简体中文",
                is_default=True,
                is_enabled=True,
            )
            page = SitePage(system_key="products", status="enabled")
            session.add_all([locale, page])
            await session.flush()
            session.add(
                SitePageTranslation(
                    site_page_id=page.id,
                    locale_id=locale.id,
                    display_name="产品",
                )
            )
            page_id = page.id
            locale_id = locale.id

        async with factory() as session:
            session.add(SitePage(system_key="products", status="enabled"))
            with pytest.raises(IntegrityError):
                await session.commit()

        async with factory() as session:
            page = await session.get(SitePage, page_id)
            locale = await session.get(Locale, locale_id)
            assert page is not None and locale is not None
            session.add(
                SitePageTranslation(
                    site_page_id=page.id,
                    locale_id=locale.id,
                    display_name="重复产品名称",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


def test_site_page_migration_is_linear_empty_and_reversible(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证 0011 迁移线性建表、不写业务数据，并可降级回 0010 后再次升级。

    输入：sqlite_database_url，隔离 SQLite；monkeypatch，覆盖迁移数据库配置。
    输出：None；迁移链、结构、空表或 downgrade 不符合要求时失败。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(api_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_root / "alembic"))

    command.upgrade(alembic_config, "head")
    sync_url = sqlite_database_url.replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(sync_url)
    inspector = inspect(engine)
    assert {"site_pages", "site_page_translations"}.issubset(inspector.get_table_names())
    page_id = next(item for item in inspector.get_columns("site_pages") if item["name"] == "id")
    assert page_id["default"] is None
    assert {item["name"] for item in inspector.get_unique_constraints("site_pages")} >= {
        "uq_site_pages_system_key"
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM site_pages")) == 0

    command.downgrade(alembic_config, "20260905_0010")
    inspector = inspect(engine)
    inspector.clear_cache()
    assert "site_pages" not in inspector.get_table_names()
    assert "site_page_translations" not in inspector.get_table_names()
    command.upgrade(alembic_config, "head")
    engine.dispose()
