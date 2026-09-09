"""Phase 3.4 Alembic 迁移链与表结构测试。"""

from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def _config(api_root: Path, database_url: str) -> Config:
    """
    创建测试专用 Alembic 配置。

    输入：API 根目录与异步数据库 URL。
    输出：Config，可直接执行 migration。
    """
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_phase34_migrations_are_linear_new_heads() -> None:
    """
    验证历史 Phase 3.4 迁移仍存在，且当前新增迁移保持单一线性 head。

    输入：无。
    输出：None；迁移链不正确时失败。
    """
    api_root = Path(__file__).resolve().parents[1]
    script = ScriptDirectory(str(api_root / "alembic"))
    assert script.get_current_head() == "20260909_0015"
    assert (api_root / "alembic/versions/20260904_0006_authority_content.py").is_file()
    assert (api_root / "alembic/versions/20260904_0007_discovery_delivery.py").is_file()
    assert (api_root / "alembic/versions/20260907_0011_site_pages.py").is_file()
    assert (api_root / "alembic/versions/20260908_0012_privacy_p1.py").is_file()
    assert (api_root / "alembic/versions/20260908_0013_privacy_p1_hardening.py").is_file()
    assert (api_root / "alembic/versions/20260908_0014_homepage_presentation_r1.py").is_file()
    assert (api_root / "alembic/versions/20260909_0015_demo_r2_foundation.py").is_file()


def test_empty_database_upgrades_to_phase34_tables(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证空数据库可直接升级到 Phase 3.4 latest。

    输入：测试数据库 URL 与环境变量隔离器。
    输出：None；升级失败或缺表时失败。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    command.upgrade(_config(api_root, sqlite_database_url), "head")
    inspector = inspect(create_engine(sqlite_database_url.replace("sqlite+aiosqlite", "sqlite")))
    assert {
        "case_studies",
        "case_study_translations",
        "knowledge_articles",
        "knowledge_article_translations",
        "faqs",
        "faq_translations",
        "author_experts",
        "seo_documents",
        "geo_documents",
        "source_citations",
        "redirect_rules",
        "homepage_layouts",
    }.issubset(inspector.get_table_names())


def test_existing_0001_database_upgrades_to_phase34(
    sqlite_database_url: str,
    monkeypatch,
) -> None:
    """
    验证 0001 基线数据库可线性升级到 Phase 3.4。

    输入：测试数据库 URL 与环境变量隔离器。
    输出：None；升级失败时失败。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    config = _config(api_root, sqlite_database_url)
    command.upgrade(config, "20260904_0001")
    command.upgrade(config, "head")
    inspector = inspect(create_engine(sqlite_database_url.replace("sqlite+aiosqlite", "sqlite")))
    assert "redirect_rules" in inspector.get_table_names()
