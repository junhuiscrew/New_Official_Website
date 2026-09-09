"""Demo R2 数据隔离、来源追踪与媒体引用契约测试。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Uuid, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.authority import services as authority_services
from app.modules.authority.models import AuthorExpert
from app.modules.authority.schemas import KnowledgeArticleUpdate
from app.modules.authority.services import (
    article_author_is_eligible,
    editorial_identity_is_eligible,
    update_knowledge_article,
)
from app.modules.demo.models import ContentMediaLink, DemoContentRecord
from app.modules.demo.package import (
    DemoPackageError,
    canonical_demo_slug,
    load_demo_package,
    record_fingerprint,
)
from app.modules.demo.presentation import presentation_media_selection_token
from app.modules.demo.setup import _apply_demo_rfq_scenario, _mime_type_for_demo_media
from app.modules.discovery.schema_generator import build_article_schema

_configured_project_root = os.getenv("PROJECT_ROOT")
PROJECT_ROOT = (
    Path(_configured_project_root)
    if _configured_project_root
    else Path(__file__).resolve().parents[3]
)


def test_demo_compose_is_loopback_only_and_uses_isolated_state() -> None:
    """
    验证 Demo 编排只绑定本机端口，并使用独立数据库、缓存、对象存储和会话配置。

    输入：无。
    输出：None；缺少隔离或存在自动 Demo 导入时测试失败。
    """
    compose = (PROJECT_ROOT / "docker-compose.demo-r2.yml").read_text(encoding="utf-8")
    nginx = (PROJECT_ROOT / "infra/nginx/nginx.local-domain-demo-edge.conf").read_text(
        encoding="utf-8"
    )
    edge = (PROJECT_ROOT / "docker-compose.local-domain.demo-edge.yml").read_text(
        encoding="utf-8"
    )
    local_domain = (PROJECT_ROOT / "docker-compose.local-domain.yml").read_text(
        encoding="utf-8"
    )

    assert "name: junhui-demo-r2" in compose
    assert compose.count("ports: !reset []") >= 7
    assert "postgres_demo_r2_data" in compose
    assert "redis_demo_r2_data" in compose
    assert "minio_demo_r2_data" in compose
    assert "DEMO_MODE: 'true'" in compose
    assert "python -m app.cli demo-r2-setup" not in compose
    assert "alembic upgrade head" not in compose
    assert "python -m app.cli seed" not in compose
    assert "demo.junhuiscrewbarrel.com" in nginx
    assert "admin-demo.junhuiscrewbarrel.com" in nginx
    assert "api-demo.junhuiscrewbarrel.com" in nginx
    assert "junhui_demo_r2_edge" in edge
    assert "127.0.0.1:443:443" in local_domain
    assert "auth_basic" not in nginx
    assert 'X-Robots-Tag "noindex, nofollow"' in nginx


def test_demo_settings_require_explicit_nonproduction_mode() -> None:
    """
    验证 Demo 能力必须显式启用且永远不能进入 production。

    输入：无。
    输出：None；生产配置可开启 Demo 时测试失败。
    """
    settings = Settings(
        app_env="test",
        demo_mode=True,
        demo_batch_id="JH-DEMO-R2-V1",
        cors_allowed_origins=["http://testserver"],
    )
    assert settings.demo_mode is True
    assert settings.demo_batch_id == "JH-DEMO-R2-V1"

    with pytest.raises(ValueError, match="Demo mode"):
        Settings(
            app_env="production",
            demo_mode=True,
            demo_batch_id="JH-DEMO-R2-V1",
            database_url="postgresql+asyncpg://demo:strong-demo-database-password@db.example/junhui",
            minio_public_endpoint="media.example.com",
            minio_internal_secure=True,
            minio_public_secure=True,
            minio_secret_key="strong-demo-minio-secret-value",
            jwt_signing_secret="strong-demo-jwt-signing-secret-value",
            refresh_token_secret="strong-demo-refresh-secret-value",
            cors_allowed_origins=["https://demo.example.com"],
        )


def test_demo_tables_have_uuid_keys_constraints_and_chinese_comments() -> None:
    """
    验证 Demo 来源与媒体关联表具有真实 UUID、唯一约束和完整中文字段注释。

    输入：无。
    输出：None；模型契约不完整时测试失败。
    """
    for table_name in ("demo_content_records", "content_media_links"):
        table = Base.metadata.tables[table_name]
        assert table.comment
        assert isinstance(table.c.id.type, Uuid)
        assert table.c.id.primary_key is True
        assert all(column.comment for column in table.columns)

    demo_constraints = {
        constraint.name for constraint in Base.metadata.tables["demo_content_records"].constraints
    }
    media_constraints = {
        constraint.name for constraint in Base.metadata.tables["content_media_links"].constraints
    }
    assert "uq_demo_content_batch_alias" in demo_constraints
    assert "uq_demo_content_batch_entity" in demo_constraints
    assert "ck_demo_content_records_demo_content_origin" in demo_constraints
    assert "ck_demo_content_records_demo_content_replacement_status" in demo_constraints
    assert "uq_content_media_owner_role_order" in media_constraints
    assert "ck_content_media_links_content_media_role" in media_constraints


@pytest.mark.asyncio
async def test_demo_record_and_media_link_persist_real_uuids(
    sqlite_database_url: str,
) -> None:
    """
    验证两类新模型可在隔离数据库持久化并生成真实 UUID。

    输入：sqlite_database_url，pytest 临时 SQLite 数据库。
    输出：None；持久化或 UUID 生成失败时测试失败。
    """
    engine: AsyncEngine = create_database_engine(sqlite_database_url)
    try:
        tables = [DemoContentRecord.__table__, ContentMediaLink.__table__]
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=tables,
                )
            )
        factory = create_session_factory(engine)
        entity_id = uuid.uuid4()
        media_id = uuid.uuid4()
        async with factory() as session, session.begin():
            record = DemoContentRecord(
                batch_id="JH-DEMO-R2-V1",
                alias="DEMO-S01",
                entity_type="product",
                entity_id=entity_id,
                content_origin="synthetic_demo",
                initial_fingerprint="0" * 64,
                replacement_status="demo_active",
                source_metadata_jsonb={"source": "package"},
            )
            link = ContentMediaLink(
                owner_type="product",
                owner_id=entity_id,
                media_asset_id=media_id,
                role="primary",
                sort_order=0,
            )
            session.add_all([record, link])
            await session.flush()
            assert isinstance(record.id, uuid.UUID)
            assert isinstance(link.id, uuid.UUID)
    finally:
        await engine.dispose()


def test_demo_migration_is_linear_and_empty(sqlite_database_url: str, monkeypatch) -> None:
    """
    验证 Demo 迁移追加在当前 head 后且只建表、不写演示业务数据。

    输入：sqlite_database_url，隔离 SQLite；monkeypatch，迁移环境替换器。
    输出：None；迁移链、表结构或空表契约不满足时测试失败。
    """
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))

    command.upgrade(config, "head")
    # SQLAlchemy Inspector 使用同步连接，迁移测试只核对结构和空表。
    from sqlalchemy import create_engine, text

    engine = create_engine(sqlite_database_url.replace("sqlite+aiosqlite", "sqlite"))
    inspector = inspect(engine)
    assert {"demo_content_records", "content_media_links"}.issubset(
        inspector.get_table_names()
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM demo_content_records")) == 0
        assert connection.scalar(text("SELECT count(*) FROM content_media_links")) == 0
    engine.dispose()


def test_demo_package_validates_complete_user_supplied_dataset() -> None:
    """
    验证用户包被当作内容记录解析，且90条记录、72条关系和双语内容完整。

    输入：仓库私有 data/demo-r2/input 内容包副本。
    输出：None；范围、批次或语言内容缺失时测试失败。
    """
    package = load_demo_package(PROJECT_ROOT / "data/demo-r2/input/demo-content-v1.json")

    assert package.demo_batch_id == "JH-DEMO-R2-V1"
    assert package.record_count == 90
    assert len(package.records) == 90
    assert len(package.relations) == 72
    assert len(package.homepage) == 14
    assert all(set(record.locale_content) == {"zh-CN", "en"} for record in package.records)


def test_demo_package_rejects_wrong_batch_and_has_stable_slugs(tmp_path: Path) -> None:
    """
    验证错误批次被拒绝，缺显式slug的记录可获得稳定且合法的Demo slug。

    输入：临时错误包与若干稳定别名。
    输出：None；环境门禁或slug规则失效时测试失败。
    """
    wrong = tmp_path / "wrong.json"
    wrong.write_text(
        '{"demo_batch_id":"NOT-APPROVED","records":[],"relations":[],"homepage":[]}',
        encoding="utf-8",
    )
    with pytest.raises(DemoPackageError, match="demo_batch_id_invalid"):
        load_demo_package(wrong)

    assert canonical_demo_slug("MAT-01", None) == "demo-mat-01"
    assert canonical_demo_slug("DEMO-S01", "demo-nitrided-screw") == "demo-nitrided-screw"
    assert canonical_demo_slug("Proof_CARD 03", None) == "demo-proof-card-03"


def test_demo_record_fingerprint_is_order_independent() -> None:
    """
    验证初始指纹不受JSON键顺序影响，以支持幂等导入和人工修改冲突检测。

    输入：语义相同但键顺序不同的两条记录。
    输出：None；指纹不稳定时测试失败。
    """
    left = {"alias": "DEMO-S01", "locale_content": {"en": {"name": "A"}}, "kind": "product"}
    right = {"kind": "product", "locale_content": {"en": {"name": "A"}}, "alias": "DEMO-S01"}
    assert record_fingerprint(left) == record_fingerprint(right)
    assert len(record_fingerprint(left)) == 64


def test_demo_editorial_organization_never_impersonates_verified_person() -> None:
    """
    验证Demo编辑组织仅在Demo模式可作为文章作者，且Schema明确使用Organization。

    输入：未核验、无人物公开页的组织作者。
    输出：None；生产放行或生成Person Schema时测试失败。
    """
    author = AuthorExpert(
        slug="demo-editorial-team",
        status="enabled",
        role_type="author",
        identity_kind="organization",
        is_real_person_verified=False,
        public_profile_enabled=False,
    )
    assert article_author_is_eligible(author, demo_mode=True) is True
    assert article_author_is_eligible(author, demo_mode=False) is False
    assert editorial_identity_is_eligible(author, demo_mode=True) is True
    assert editorial_identity_is_eligible(author, demo_mode=False) is False

    schema = build_article_schema(
        {"headline": "Demo article", "url": "https://demo.example/article"},
        {
            "name": "Demo editorial team",
            "identity_kind": "organization",
            "is_real_person_verified": False,
            "is_demo_content": True,
        },
    )
    assert schema["author"] == {
        "@type": "Organization",
        "name": "Demo editorial team",
    }


@pytest.mark.asyncio
async def test_demo_article_update_uses_same_editorial_identity_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证Demo文章更新与创建共用同一作者资格，不要求虚构组织冒充真人。

    输入：显式Demo模式、未核验且无人物页的演示编辑组织。
    输出：None；更新应进入通用持久化服务，生产门禁仍由资格函数控制。
    """
    author = AuthorExpert(
        id=uuid.uuid4(),
        slug="demo-editorial-team",
        status="enabled",
        role_type="author",
        identity_kind="organization",
        is_real_person_verified=False,
        public_profile_enabled=False,
    )
    session = AsyncMock()
    session.get.return_value = author
    expected_article = object()
    update_entity = AsyncMock(return_value=expected_article)
    monkeypatch.setattr(
        authority_services,
        "get_settings",
        lambda: SimpleNamespace(demo_mode=True),
    )
    monkeypatch.setattr(authority_services, "_update_entity", update_entity)

    result = await update_knowledge_article(
        session,
        uuid.uuid4(),
        KnowledgeArticleUpdate(author_id=author.id),
        uuid.uuid4(),
    )

    assert result is expected_article
    update_entity.assert_awaited_once()


def test_demo_media_mime_resolution_handles_webp_without_os_registry() -> None:
    """
    验证Demo导入不依赖宿主系统是否注册WEBP MIME。

    输入：WEBP和常规媒体文件名。
    输出：None；已允许扩展名不能稳定解析时测试失败。
    """
    assert _mime_type_for_demo_media(Path("approved-product-01.webp")) == "image/webp"
    assert _mime_type_for_demo_media(Path("sample.pdf")) == "application/pdf"


def test_demo_cli_registers_rfq_privacy_foreign_key_target() -> None:
    """
    验证独立CLI导入RFQ前已注册隐私版本外键目标表。

    输入：已导入Demo初始化模块的SQLAlchemy元数据。
    输出：None；CLI路径缺少外键目标模型时测试失败。
    """
    assert "privacy_notice_versions" in Base.metadata.tables
    target_tables = {
        foreign_key.column.table.name
        for foreign_key in Base.metadata.tables["rfqs"].foreign_keys
    }
    assert "privacy_notice_versions" in target_tables


def test_demo_rfq_scenario_reconciles_existing_fixture_status() -> None:
    """
    验证重复执行 Demo 初始化时会把既有虚构询盘恢复为内容包指定场景。

    输入：内存中的既有询盘与内容包记录替身。
    输出：None；状态未更新或重复更新未保持幂等时测试失败。
    """
    entity = SimpleNamespace(status="new")
    record = SimpleNamespace(model_extra={"status_scenario": "follow_up"})

    assert _apply_demo_rfq_scenario(entity, record) is True
    assert entity.status == "waiting_customer"
    assert _apply_demo_rfq_scenario(entity, record) is False


def test_demo_presentation_media_token_is_stable_and_conflict_sensitive() -> None:
    """
    验证演示首页媒体选择使用稳定并发令牌，任一槽位变化都会产生新令牌。

    输入：同一选择的不同键顺序，以及一个发生替换的媒体槽位。
    输出：None；令牌受字典顺序影响或不能识别替换时测试失败。
    """
    original = {
        "hero": "00000000-0000-0000-0000-000000000001",
        "video_1": "00000000-0000-0000-0000-000000000002",
        "poster_1": None,
    }
    reordered = {
        "poster_1": None,
        "video_1": "00000000-0000-0000-0000-000000000002",
        "hero": "00000000-0000-0000-0000-000000000001",
    }
    changed = {**original, "video_1": "00000000-0000-0000-0000-000000000003"}

    assert presentation_media_selection_token(original) == presentation_media_selection_token(
        reordered
    )
    assert presentation_media_selection_token(original) != presentation_media_selection_token(
        changed
    )
    assert len(presentation_media_selection_token(original)) == 64
