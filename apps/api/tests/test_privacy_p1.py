"""Privacy P1 版本生命周期、公开交付、权限与 RFQ 绑定行为测试。"""

from __future__ import annotations

import importlib.util
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.exceptions.handlers import AppException
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.content.models import ContentRevision, ContentRoute, SitePage
from app.modules.localization.models import Locale
from app.modules.rfq.models import RFQ, RFQItem
from app.modules.rfq.schemas import RFQCreate
from app.modules.users.models import Permission, Role, RolePermission, User, UserRole
from app.seed import seed_database

TEST_LOGIN_PROOF = "Privacy-Test-Only-2026!"


def _workspace_file_candidates(
    relative_path: str | Path,
    *,
    test_file: Path | None = None,
    project_root: Path | None = None,
) -> tuple[Path, ...]:
    """
    生成测试资源在源码工作树和 API 测试容器中的明确候选路径。

    输入：relative_path，相对仓库根目录的资源路径；test_file，可选测试文件路径；
        project_root，可选容器工作区根目录，默认使用 /workspace。
    输出：tuple[Path, ...]，按源码工作树优先、容器工作区次之排列且不重复的路径。
    """
    resolved_test_file = (test_file or Path(__file__)).resolve(strict=False)
    normalized_relative_path = Path(relative_path)
    candidates: list[Path] = []

    # 本机源码布局为 <repo>/apps/api/tests；通过目录名称识别，避免固定 parents 下标越界。
    for ancestor in resolved_test_file.parents:
        if ancestor.name == "api" and ancestor.parent.name == "apps":
            candidates.append(ancestor.parent.parent / normalized_relative_path)
            break

    # API 测试镜像把仓库级测试资源显式复制到 /workspace。
    candidates.append((project_root or Path("/workspace")) / normalized_relative_path)
    return tuple(dict.fromkeys(candidates))


def _find_workspace_file(relative_path: str | Path, *, required: bool = True) -> Path | None:
    """
    从本机源码工作树或 API 测试容器中查找仓库级测试资源。

    输入：relative_path，相对仓库根目录的资源路径；required，缺失时是否立即断言失败。
    输出：Path | None，首个存在的候选文件；非必需资源不存在时返回 None。
    """
    candidates = _workspace_file_candidates(relative_path)
    resolved_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if required:
        assert resolved_path is not None, (
            f"缺少工作区测试资源 {relative_path}；候选路径："
            + ", ".join(str(candidate) for candidate in candidates)
        )
    return resolved_path


def _privacy_symbols():
    """
    延迟导入待实现的 Privacy P1 模块，使 RED 测试明确失败于功能缺失。

    输入：无。
    输出：tuple，Privacy 模型、Schema 与服务模块。
    """
    from app.modules.privacy import models, schemas, services

    return models, schemas, services


@pytest.fixture
async def privacy_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建包含 Privacy 专用权限与测试用户的隔离数据库。

    输入：
        sqlite_database_url: str，pytest 临时 SQLite 地址。
    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，隔离会话工厂。
    """
    _models, _schemas, services = _privacy_symbols()
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    async with factory() as session, session.begin():
        for role_name in (
            "content_admin",
            "editor",
            "translator",
            "reviewer",
            "seo_manager",
            "sales",
        ):
            role = await session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            user = User(
                email=f"privacy-{role_name}@example.com",
                password_hash=hash_password(TEST_LOGIN_PROOF),
                display_name=f"privacy-{role_name}",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """
    创建使用隔离数据库的匿名 ASGI 客户端。

    输入：session_factory，测试会话工厂。
    输出：AsyncIterator[AsyncClient]，请求结束后自动关闭的客户端。
    """
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """输入无；输出隔离数据库请求会话。"""
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@asynccontextmanager
async def _role_client(
    session_factory: async_sessionmaker[AsyncSession],
    role_name: str,
    *,
    with_csrf: bool = True,
) -> AsyncIterator[AsyncClient]:
    """
    创建指定角色且可选择 CSRF Header 的认证客户端。

    输入：session_factory、role_name 与 with_csrf。
    输出：AsyncIterator[AsyncClient]，已登录测试客户端。
    """
    async with _client(session_factory) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"privacy-{role_name}@example.com",
                "password": TEST_LOGIN_PROOF,
            },
        )
        assert login.status_code == 200
        if with_csrf:
            client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


async def _initialize_and_create_draft(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
) -> tuple[object, object]:
    """
    初始化 Privacy 技术身份并创建空白草稿。

    输入：session 与可选 actor_id。
    输出：tuple，稳定页面与新草稿版本 ORM 对象。
    """
    _models, _schemas, services = _privacy_symbols()
    page = await services.initialize_privacy_page(session, actor_id=actor_id)
    version = await services.create_privacy_draft(session, actor_id=actor_id)
    return page, version


async def _complete_draft(
    session: AsyncSession,
    *,
    effective_at: datetime,
    actor_id: uuid.UUID | None = None,
) -> object:
    """
    为当前草稿保存完整双语内容与生效时间。

    输入：session、effective_at 和可选 actor_id。
    输出：object，更新后的 Privacy 版本。
    """
    _models, schemas, services = _privacy_symbols()
    state = await services.get_privacy_admin_state(session)
    version = await services.update_privacy_draft(
        session,
        schemas.PrivacyDraftUpdate(
            expected_revision=state["draft"]["revision"],
            effective_at=effective_at,
            translations=[
                schemas.PrivacyTranslationUpdate(
                    locale="zh-CN",
                    title="隐私政策",
                    body_markdown="# 隐私\r\n\r\n我们仅处理询盘所需信息。  \r\n",
                ),
                schemas.PrivacyTranslationUpdate(
                    locale="en",
                    title="Privacy Notice",
                    body_markdown="# Privacy\n\nWe process only RFQ data.\n",
                ),
            ],
        ),
        actor_id=actor_id,
    )
    return version


async def _review_and_publish(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
) -> object:
    """
    人工审核当前双语草稿并执行原子发布。

    输入：session 与真实审核用户 actor_id。
    输出：object，发布后当前版本。
    """
    _models, _schemas, services = _privacy_symbols()
    await _review_current(session, services, locale="zh-CN", actor_id=actor_id)
    await _review_current(session, services, locale="en", actor_id=actor_id)
    return await _publish_current(session, services, actor_id=actor_id)


async def _review_current(session, services, *, locale: str, actor_id):
    """
    以 fresh 管理状态构造服务层审核观察值。

    输入：session、services、locale 与真实 actor_id。
    输出：当前 PrivacyNoticeVersion；测试服务边界仍使用完整观察值。
    """
    state = await services.get_privacy_admin_state(session)
    draft = state["draft"]
    assert draft is not None
    return await services.review_privacy_translation(
        session,
        locale=locale,
        actor_id=actor_id,
        expected_version_label=draft["version_label"],
        expected_revision=draft["revision"],
        expected_content_hash=draft["translations"][locale]["content_hash"],
    )


async def _publish_current(session, services, *, actor_id, now: datetime | None = None):
    """
    以 fresh 管理状态构造服务层双语发布观察值。

    输入：session、services、actor_id 与可选可信时钟。
    输出：当前 PrivacyNoticeVersion；测试发布仍经过观察值并发门禁。
    """
    state = await services.get_privacy_admin_state(session)
    draft = state["draft"]
    assert draft is not None
    return await services.publish_privacy_draft(
        session,
        actor_id=actor_id,
        expected_version_label=draft["version_label"],
        expected_revision=draft["revision"],
        expected_content_hashes={
            locale: draft["translations"][locale]["content_hash"]
            for locale in ("zh-CN", "en")
        },
        now=now,
    )


def test_privacy_p1_backend_contract_is_registered() -> None:
    """
    验证 Privacy 模块、固定 API 与数据表均已注册。

    输入：无。
    输出：None；功能尚未实现时失败。
    """
    assert importlib.util.find_spec("app.modules.privacy.models") is not None
    app = create_app()
    paths = app.openapi()["paths"]
    assert {
        "/api/v1/privacy/initialize",
        "/api/v1/privacy/draft",
        "/api/v1/privacy/draft/preview",
        "/api/v1/privacy/draft/publish",
        "/api/v1/privacy/history",
        "/api/v1/public/privacy/{locale_slug}",
        "/api/v1/public/privacy/{locale_slug}/context/{version_label}",
    }.issubset(paths)
    assert {
        "privacy_notice_versions",
        "privacy_notice_version_translations",
        "privacy_page_states",
    }.issubset(Base.metadata.tables)


def test_workspace_file_candidates_cover_source_and_container_layout(tmp_path: Path) -> None:
    """
    验证测试资源候选路径同时覆盖源码工作树与 API 测试容器布局。

    输入：tmp_path，pytest 提供的临时目录。
    输出：None；若候选路径依赖固定 parents 下标或遗漏 /workspace 时失败。
    """
    source_test_file = tmp_path / "repo" / "apps" / "api" / "tests" / "test_privacy_p1.py"
    source_candidates = _workspace_file_candidates(
        "docker-compose.yml",
        test_file=source_test_file,
        project_root=tmp_path / "container-workspace",
    )
    assert tmp_path / "repo" / "docker-compose.yml" in source_candidates

    container_candidates = _workspace_file_candidates(
        "docker-compose.yml",
        test_file=Path("/app/tests/test_privacy_p1.py"),
        project_root=Path("/workspace"),
    )
    assert Path("/workspace/docker-compose.yml") in container_candidates


def test_privacy_models_have_comments_constraints_and_no_seeded_policy() -> None:
    """
    验证新增表字段中文注释、SitePage allowlist 与迁移不植入政策正文。

    输入：无。
    输出：None；结构约束或无内容迁移契约不符时失败。
    """
    models, _schemas, _services = _privacy_symbols()
    for table_name in (
        "privacy_notice_versions",
        "privacy_notice_version_translations",
        "privacy_page_states",
    ):
        table = Base.metadata.tables[table_name]
        assert table.comment
        assert all(column.comment for column in table.columns)
    site_page_constraint = next(
        constraint
        for constraint in SitePage.__table__.constraints
        if constraint.name == "ck_site_pages_site_page_system_key_value"
    )
    assert "'products','privacy'" in str(site_page_constraint.sqltext).replace(" ", "")
    assert models.PrivacyNoticeVersion.__table__.c.version_label.unique is True

    migration_path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / (
        "20260908_0012_privacy_p1.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")
    assert 'down_revision = "20260907_0011"' in migration_text
    assert "INSERT INTO privacy_notice_versions" not in migration_text
    assert "privacy_notice_immutable" in migration_text

    compose_path = _find_workspace_file("docker-compose.yml")
    assert compose_path is not None
    api_test_profile = compose_path.read_text(encoding="utf-8").split("  api-test:", 1)[1]
    assert "APP_ENV: test" in api_test_profile
    assert "PRIVACY_P1_TEST_ONLY: '1'" in api_test_profile
    assert "alembic upgrade head && python -m app.cli seed" in api_test_profile

    adr_path = _find_workspace_file(
        Path("docs") / "architecture" / "privacy-p1-version-binding.md",
        required=False,
    )
    if adr_path is not None:
        adr_text = adr_path.read_text(encoding="utf-8")
        assert "同一 token 重复请求可能产生多条完整 RFQ" in adr_text
        assert "当前没有通用幂等键" in adr_text
        assert "不会产生半条 RFQ" in adr_text
    else:
        # 测试镜像未复制该 ADR；仅在已确认 compose 来自 /workspace 时允许跳过文件内容断言。
        assert compose_path == Path("/workspace/docker-compose.yml")


def test_privacy_migration_executes_each_postgresql_ddl_separately(monkeypatch) -> None:
    """
    验证 asyncpg 执行的每次 op.execute 只包含一个函数或一个触发器 DDL。

    输入：monkeypatch，替换 Alembic op.execute 以捕获 SQL。
    输出：None；六个函数与七个触发器未拆成十三条独立命令时失败。
    """
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / (
        "20260908_0012_privacy_p1.py"
    )
    spec = importlib.util.spec_from_file_location("privacy_p1_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    executed: list[str] = []
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration._install_postgresql_guards()

    normalized = [statement.strip().upper() for statement in executed]
    assert len(normalized) == 13
    assert sum(item.startswith("CREATE OR REPLACE FUNCTION") for item in normalized) == 6
    assert sum(item.startswith("CREATE TRIGGER") for item in normalized) == 7
    assert all(not ("CREATE OR REPLACE FUNCTION" in item and "CREATE TRIGGER" in item) for item in normalized)
    assert all(item.count("CREATE TRIGGER") <= 1 for item in normalized)


def test_privacy_lifecycle_hardening_is_appended_after_p1_schema_migration() -> None:
    """
    验证生命周期数据库加固通过新迁移追加，不把 0013 的状态 trigger 塞入 0012 upgrade。

    输入：仓库中的 Alembic 迁移文件。
    输出：None；缺少 0013 或未绑定 0012 时失败。
    """
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / (
        "20260908_0013_privacy_p1_hardening.py"
    )
    assert migration_path.is_file()
    migration_text = migration_path.read_text(encoding="utf-8")
    assert 'revision = "20260908_0013"' in migration_text
    assert 'down_revision = "20260908_0012"' in migration_text
    assert "privacy_translation_reviewer_required" in migration_text
    assert "privacy_translation_status_transition_invalid" in migration_text


def test_privacy_migration_downgrade_cleans_fixed_page_dependencies() -> None:
    """
    验证回退 Privacy P1 前会删除固定页面及其多态依赖，避免恢复旧约束失败。

    输入：仓库中的 0012 迁移源码。
    输出：None；缺少任一清理边界时失败。
    """
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / (
        "20260908_0012_privacy_p1.py"
    )
    assert migration_path.is_file()
    migration_text = migration_path.read_text(encoding="utf-8")
    for expected_sql in (
        "DELETE FROM content_revisions WHERE owner_type = 'privacy_notice_version'",
        "DELETE FROM audit_logs WHERE action LIKE 'privacy.%'",
        "DELETE FROM site_page_translations",
        "DELETE FROM site_pages WHERE system_key = 'privacy'",
    ):
        assert expected_sql in migration_text


def test_new_rfq_requires_supported_privacy_locale() -> None:
    """
    验证新的公开 RFQ 必须显式提交 Privacy 支持的语言。

    输入：缺失、空白或非支持语言的 RFQ 输入。
    输出：None；任一输入能构造成公开创建模型时失败。
    """
    base = {
        "company_name": "ACME",
        "contact_name": "Lee",
        "email": "lee@example.com",
        "message": "Need a quote",
        "consent_privacy": True,
    }
    with pytest.raises(ValueError):
        RFQCreate(**base)
    for invalid_locale in ("", "zh", "en-US"):
        with pytest.raises(ValueError):
            RFQCreate(**base, preferred_language=invalid_locale)


@pytest.mark.parametrize(
    "unsafe_markdown",
    [
        "<script>alert('xss')</script>",
        '<img src="x" onerror="alert(1)">',
        "[danger](javascript:alert(1))",
        "[danger](JaVaScRiPt&#58;alert(1))",
        "[danger](data:text/html;base64,PHNjcmlwdD4=)",
        "[danger](vbscript:msgbox(1))",
        "![remote policy image](https://images.example.test/tracker.png)",
        "![reference policy image][logo]\n\n[logo]: /assets/logo.png",
        "[unsupported file](ftp://files.example.test/policy.pdf)",
        "[protocol-relative](//evil.example.test/policy)",
        "[complex target](https://example.test/policy_(archived))",
        "[mail header](mailto:privacy@example.test?subject=Injected)",
    ],
)
def test_privacy_markdown_is_normalized_hashed_and_rejects_active_content(
    unsafe_markdown: str,
) -> None:
    """
    验证政策只保存规范化 Markdown，并拒绝 HTML 与可执行链接协议。

    输入：unsafe_markdown，可能触发脚本执行的 Markdown/HTML。
    输出：None；未规范化、哈希不稳定或危险内容被接受时失败。
    """
    _models, _schemas, services = _privacy_symbols()
    first_title, first_body = services.normalize_privacy_content(
        "  Privacy Notice  ",
        "# Privacy\r\n\r\nLine with spaces  \r\n",
    )
    second_title, second_body = services.normalize_privacy_content(
        "Privacy Notice",
        "# Privacy\n\nLine with spaces\n",
    )
    assert (first_title, first_body) == (second_title, second_body)
    assert services.compute_privacy_content_hash(first_title, first_body) == (
        services.compute_privacy_content_hash(second_title, second_body)
    )
    with pytest.raises(AppException) as rejected:
        services.normalize_privacy_content("Privacy Notice", unsafe_markdown)
    assert rejected.value.code == "privacy_markdown_unsafe"


def test_privacy_markdown_allows_only_simple_safe_links() -> None:
    """
    验证普通链接仅允许 HTTP、HTTPS、mailto 与同站相对路径。

    输入：固定安全 Markdown 链接样例。
    输出：None；安全链接被误拒或正文规范化发生漂移时失败。
    """
    _models, _schemas, services = _privacy_symbols()
    markdown = "\n".join(
        (
            "[HTTP](http://example.test/privacy)",
            "[HTTPS](https://example.test/privacy)",
            "[Mail](mailto:privacy@example.test)",
            "[Local](/en/privacy/)",
            "[Anchor](#contact)",
        )
    )
    _title, normalized = services.normalize_privacy_content("Privacy", markdown)
    assert normalized == markdown


async def test_site_page_allowlist_accepts_privacy_but_products_api_stays_products_only(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证数据库允许 privacy，而 Products 专用入口仍拒绝 privacy。

    输入：privacy_factory，隔离数据库。
    输出：None；数据库或既有 API allowlist 被错误放宽时失败。
    """
    async with privacy_factory() as session, session.begin():
        session.add(SitePage(system_key="privacy", status="enabled"))
    async with privacy_factory() as session:
        assert await session.scalar(select(func.count()).select_from(SitePage)) == 1
        session.add(SitePage(system_key="about", status="enabled"))
        with pytest.raises(IntegrityError):
            await session.commit()

    async with _role_client(privacy_factory, "content_admin") as client:
        response = await client.post("/api/v1/discovery/site-pages/privacy/initialize")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "site_page_not_found"


async def test_central_seed_adds_privacy_permissions_idempotently_without_privilege_spread(
    sqlite_database_url: str,
) -> None:
    """
    验证中央 seed 在空 schema 中幂等创建 Privacy 权限及最小角色映射。

    输入：sqlite_database_url，pytest 隔离数据库地址。
    输出：None；需要旁路同步或 sales/seo 获得 Privacy 权限时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    await seed_database(factory)

    expected = {
        "super_admin": {
            "privacy.read",
            "privacy.edit",
            "privacy.review",
            "privacy.publish",
            "privacy.history",
        },
        "content_admin": {
            "privacy.read",
            "privacy.edit",
            "privacy.review",
            "privacy.publish",
            "privacy.history",
        },
        "editor": {"privacy.read", "privacy.edit"},
        "translator": {"privacy.read", "privacy.edit"},
        "reviewer": {
            "privacy.read",
            "privacy.review",
            "privacy.publish",
            "privacy.history",
        },
        "sales": set(),
        "seo_manager": set(),
    }
    async with factory() as session:
        for role_name, expected_codes in expected.items():
            actual_codes = set(
                (
                    await session.scalars(
                        select(Permission.code)
                        .join(RolePermission, RolePermission.permission_id == Permission.id)
                        .join(Role, Role.id == RolePermission.role_id)
                        .where(
                            Role.name == role_name,
                            Permission.code.like("privacy.%"),
                        )
                    )
                ).all()
            )
            assert actual_codes == expected_codes
    await engine.dispose()


async def test_draft_save_reopen_conflict_immutability_and_clone(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证草稿保存重开、乐观冲突、审核后不可改与克隆新草稿。

    输入：privacy_factory，隔离数据库。
    输出：None；任一版本编辑边界不符时失败。
    """
    _models, schemas, services = _privacy_symbols()
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        await _initialize_and_create_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=datetime.now(UTC) - timedelta(minutes=1),
            actor_id=reviewer.id,
        )
        saved = await services.get_privacy_admin_state(session)
        stale_revision = saved["draft"]["revision"] - 1

    async with privacy_factory() as session:
        reopened = await services.get_privacy_admin_state(session)
        assert reopened["draft"] == saved["draft"]
        with pytest.raises(AppException) as conflict:
            await services.update_privacy_draft(
                session,
                schemas.PrivacyDraftUpdate(
                    expected_revision=stale_revision,
                    translations=[
                        schemas.PrivacyTranslationUpdate(
                            locale="en", title="Changed", body_markdown="Changed"
                        )
                    ],
                ),
                actor_id=None,
            )
        assert conflict.value.code == "privacy_draft_conflict"

    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        await _review_current(session, services, locale="en", actor_id=reviewer.id)
        with pytest.raises(AppException) as immutable:
            await services.update_privacy_draft(
                session,
                schemas.PrivacyDraftUpdate(
                    expected_revision=saved["draft"]["revision"],
                    translations=[
                        schemas.PrivacyTranslationUpdate(
                            locale="en", title="Forbidden", body_markdown="Forbidden"
                        )
                    ],
                ),
                actor_id=reviewer.id,
            )
        assert immutable.value.code == "privacy_version_immutable"
        cloned = await services.create_privacy_draft(session, actor_id=reviewer.id)
        state = await services.get_privacy_admin_state(session)

    assert state["draft"]["version_label"] == cloned.version_label
    assert state["draft"]["version_label"] != saved["draft"]["version_label"]
    assert state["draft"]["translations"]["en"]["title"] == "Privacy Notice"
    assert state["draft"]["translations"]["en"]["translation_status"] == "draft"


async def test_admin_readback_reports_actual_privacy_route_indexable_state(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证后台回读不会用固定 false 掩盖 Privacy Route 的数据库漂移。

    输入：privacy_factory，隔离数据库。
    输出：None；真实 indexable=true 未出现在后台 DTO 时失败。
    """
    _models, _schemas, services = _privacy_symbols()
    async with privacy_factory() as session, session.begin():
        page = await services.initialize_privacy_page(session, actor_id=None)
        await services.create_privacy_draft(session, actor_id=None)
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "site_page",
                ContentRoute.owner_id == page.id,
                ContentRoute.path == "/en/privacy/",
            )
        )
        assert route is not None
        route.indexable = True
        await session.flush()
        state = await services.get_privacy_admin_state(session)

    assert state["draft"]["translations"]["en"]["route_indexable"] is True


async def test_clone_uses_reviewed_draft_content_but_never_inherits_effective_at(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证克隆仅继承正文/hash，并优先继承待重修 reviewed draft 而非旧 current。

    输入：privacy_factory，隔离数据库。
    输出：None；新版本继承旧生效时间或丢回旧 current 正文时失败。
    """
    _models, schemas, services = _privacy_symbols()
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(
            select(User).where(User.email == "privacy-reviewer@example.com")
        )
        assert reviewer is not None
        await _initialize_and_create_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=datetime.now(UTC) - timedelta(minutes=1),
            actor_id=reviewer.id,
        )
        await _review_and_publish(session, actor_id=reviewer.id)

        version_b = await services.create_privacy_draft(session, actor_id=reviewer.id)
        state_b = await services.get_privacy_admin_state(session)
        assert state_b["draft"]["effective_at"] is None
        await services.update_privacy_draft(
            session,
            schemas.PrivacyDraftUpdate(
                expected_revision=state_b["draft"]["revision"],
                effective_at=datetime.now(UTC) + timedelta(days=2),
                translations=[
                    schemas.PrivacyTranslationUpdate(
                        locale="zh-CN", title="待重修政策 B", body_markdown="正文 B"
                    ),
                    schemas.PrivacyTranslationUpdate(
                        locale="en", title="Reviewed Draft B", body_markdown="Body B"
                    ),
                ],
            ),
            actor_id=reviewer.id,
        )
        await _review_current(session, services, locale="zh-CN", actor_id=reviewer.id)
        await _review_current(session, services, locale="en", actor_id=reviewer.id)

        version_c = await services.create_privacy_draft(session, actor_id=reviewer.id)
        state_c = await services.get_privacy_admin_state(session)

    assert version_c.cloned_from_id == version_b.id
    assert state_c["draft"]["effective_at"] is None
    assert state_c["draft"]["translations"]["zh-CN"]["title"] == "待重修政策 B"
    assert state_c["draft"]["translations"]["en"]["title"] == "Reviewed Draft B"


async def test_atomic_publish_rejects_incomplete_unreviewed_and_future_then_succeeds(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证发布必须双语完整、人工审核、哈希有效且已到生效时间。

    输入：privacy_factory，隔离数据库。
    输出：None；门禁可被部分发布绕过或合格版本不能发布时失败。
    """
    _models, schemas, services = _privacy_symbols()
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        await _initialize_and_create_draft(session, actor_id=reviewer.id)
        with pytest.raises(AppException) as missing_actor:
            await _publish_current(session, services, actor_id=None)
        assert missing_actor.value.code == "privacy_publisher_required"
        state = await services.get_privacy_admin_state(session)
        await services.update_privacy_draft(
            session,
            schemas.PrivacyDraftUpdate(
                expected_revision=state["draft"]["revision"],
                effective_at=datetime.now(UTC) - timedelta(minutes=1),
                translations=[
                    schemas.PrivacyTranslationUpdate(
                        locale="zh-CN", title="隐私政策", body_markdown="完整中文正文"
                    )
                ],
            ),
            actor_id=reviewer.id,
        )
        with pytest.raises(AppException) as incomplete:
            await _publish_current(session, services, actor_id=reviewer.id)
        assert incomplete.value.code == "privacy_translation_incomplete"

        state = await services.get_privacy_admin_state(session)
        await services.update_privacy_draft(
            session,
            schemas.PrivacyDraftUpdate(
                expected_revision=state["draft"]["revision"],
                translations=[
                    schemas.PrivacyTranslationUpdate(
                        locale="en", title="Privacy Notice", body_markdown="Complete English body"
                    )
                ],
            ),
            actor_id=reviewer.id,
        )
        with pytest.raises(AppException) as unreviewed:
            await _publish_current(session, services, actor_id=reviewer.id)
        assert unreviewed.value.code == "privacy_translation_not_reviewed"

        state = await services.get_privacy_admin_state(session)
        future_effective_at = datetime.now(UTC) + timedelta(days=1)
        await services.update_privacy_draft(
            session,
            schemas.PrivacyDraftUpdate(
                expected_revision=state["draft"]["revision"],
                effective_at=future_effective_at,
            ),
            actor_id=reviewer.id,
        )
        await _review_current(session, services, locale="zh-CN", actor_id=reviewer.id)
        await _review_current(session, services, locale="en", actor_id=reviewer.id)
        with pytest.raises(AppException) as future:
            await _publish_current(session, services, actor_id=reviewer.id)
        assert future.value.code == "privacy_effective_in_future"

        # 此处模拟可信时钟到达生效点，内容与审核记录保持不变。
        published = await _publish_current(
            session,
            services,
            actor_id=reviewer.id,
            now=future_effective_at + timedelta(seconds=1),
        )
        final_state = await services.get_privacy_admin_state(session)

    assert final_state["current"]["version_label"] == published.version_label
    assert final_state["draft"] is None
    assert all(
        language["publication_status"] == "published"
        for language in final_state["current"]["translations"].values()
    )


async def test_effective_at_only_update_writes_bilingual_revisions_and_safe_audit(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证仅改生效时间仍写双语修订，并只在审计元数据记录 ISO from/to。

    输入：privacy_factory，隔离数据库。
    输出：None；修订缺失、审计不可追溯或泄露正文时失败。
    """
    _models, schemas, services = _privacy_symbols()
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(
            select(User).where(User.email == "privacy-reviewer@example.com")
        )
        assert reviewer is not None
        _page, version = await _initialize_and_create_draft(session, actor_id=reviewer.id)
        initial_effective_at = datetime.now(UTC) + timedelta(days=1)
        await _complete_draft(
            session,
            effective_at=initial_effective_at,
            actor_id=reviewer.id,
        )
        before_revision_count = await session.scalar(
            select(func.count())
            .select_from(ContentRevision)
            .where(
                ContentRevision.owner_type == "privacy_notice_version",
                ContentRevision.owner_id == version.id,
            )
        )
        state = await services.get_privacy_admin_state(session)
        next_effective_at = initial_effective_at + timedelta(days=1)
        await services.update_privacy_draft(
            session,
            schemas.PrivacyDraftUpdate(
                expected_revision=state["draft"]["revision"],
                effective_at=next_effective_at,
            ),
            actor_id=reviewer.id,
        )
        after_revision_count = await session.scalar(
            select(func.count())
            .select_from(ContentRevision)
            .where(
                ContentRevision.owner_type == "privacy_notice_version",
                ContentRevision.owner_id == version.id,
            )
        )
        audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(AuditLog.action == "privacy.draft_update")
                )
            ).all()
        )
        audit = next(
            item
            for item in audits
            if item.metadata_json.get("revision") == state["draft"]["revision"] + 1
        )

    assert after_revision_count == before_revision_count + 2
    assert audit is not None
    assert audit.metadata_json["effective_at_from"] == initial_effective_at.isoformat()
    assert audit.metadata_json["effective_at_to"] == next_effective_at.isoformat()
    assert "body" not in str(audit.metadata_json).lower()


async def test_public_delivery_is_bilingual_current_only_noindex_and_excluded_from_discovery(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证仅当前合格双语政策公开，强制 noindex 且不进入 Sitemap/Search/GEO。

    输入：privacy_factory，隔离数据库。
    输出：None；公开门禁或营销发现隔离失效时失败。
    """
    _models, _schemas, services = _privacy_symbols()
    from app.modules.content.services.indexable import list_sitemap_candidates
    from app.modules.discovery.public_collections import search_public_content
    from app.modules.discovery.services import build_visible_source_text

    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        page, _version = await _initialize_and_create_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=datetime.now(UTC) - timedelta(minutes=1),
            actor_id=reviewer.id,
        )
        await _review_and_publish(session, actor_id=reviewer.id)

    async with _client(privacy_factory) as client:
        response = await client.get("/api/v1/public/privacy/en")
        context_response = await client.get(
            f"/api/v1/public/privacy/en/context/{response.json()['data']['version_label']}"
        )
        stale_context_response = await client.get(
            "/api/v1/public/privacy/en/context/PRIVACY-NOT-CURRENT"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
    assert response.headers["x-robots-tag"] == "noindex, follow"
    assert context_response.status_code == 200
    assert context_response.headers["cache-control"] == "no-store"
    assert context_response.headers["x-robots-tag"] == "noindex, follow"
    assert stale_context_response.status_code == 409
    assert stale_context_response.headers["cache-control"] == "no-store"
    assert stale_context_response.headers["x-robots-tag"] == "noindex, follow"
    payload = response.json()["data"]
    assert payload["title"] == "Privacy Notice"
    assert payload["robots"] == {"index": False, "follow": True}
    assert payload["canonical_path"] == "/en/privacy/"
    assert payload["alternates"] == {
        "zh-CN": "/zh-cn/privacy/",
        "en": "/en/privacy/",
    }
    assert payload["content_format"] == "markdown"
    assert payload["rendering_trust"] == "untrusted"
    assert "body_html" not in payload
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        str(payload),
        re.IGNORECASE,
    )

    async with privacy_factory() as session:
        assert all("/privacy/" not in item.path for item in await list_sitemap_candidates(session))
        search = await search_public_content(session, "en", "Privacy", None, 20)
        assert "privacy" not in search["groups"]
        en_locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert en_locale is not None
        with pytest.raises(AppException) as geo_rejected:
            await build_visible_source_text(
                session,
                "privacy_notice_version",
                _version.id,
                en_locale.id,
            )
        assert geo_rejected.value.code == "unsupported_geo_owner"
    # 发布新版本后再次 GET 必须强制重验证，并立即返回新的 current 标签。
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(
            select(User).where(User.email == "privacy-reviewer@example.com")
        )
        assert reviewer is not None
        await services.create_privacy_draft(session, actor_id=reviewer.id)
        draft = await services.get_privacy_admin_state(session)
        await services.update_privacy_draft(
            session,
            _schemas.PrivacyDraftUpdate(
                expected_revision=draft["draft"]["revision"],
                effective_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
            actor_id=reviewer.id,
        )
        await _review_current(session, services, locale="zh-CN", actor_id=reviewer.id)
        await _review_current(session, services, locale="en", actor_id=reviewer.id)
        version_b = await _publish_current(session, services, actor_id=reviewer.id)
    async with _client(privacy_factory) as client:
        switched = await client.get("/api/v1/public/privacy/en")
    assert switched.status_code == 200
    assert switched.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
    assert switched.json()["data"]["version_label"] == version_b.version_label

    # 禁用必须走授权状态服务/API，不把 SQLite 直接改字段当成生产可达路径。
    async with _role_client(privacy_factory, "content_admin") as client:
        status_response = await client.patch("/api/v1/privacy/status", json={"status": "disabled"})
    assert status_response.status_code == 200
    async with _client(privacy_factory) as client:
        disabled = await client.get("/api/v1/public/privacy/en")
    assert disabled.status_code == 404
    assert disabled.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
    assert disabled.headers["x-robots-tag"] == "noindex, follow"
    assert disabled.json()["error"]["code"] == "privacy_policy_unavailable"


async def test_public_policy_rejects_no_policy_draft_and_future_effective_version(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证生产可达的无政策、仅草稿及未来生效版本均不能公开。

    输入：privacy_factory，隔离数据库。
    输出：None；任一生产可达的非合格状态可公开时失败。
    """
    models, _schemas, services = _privacy_symbols()
    now = datetime.now(UTC)
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(
            select(User).where(User.email == "privacy-reviewer@example.com")
        )
        assert reviewer is not None
        await services.initialize_privacy_page(session, actor_id=reviewer.id)
        with pytest.raises(AppException) as no_policy:
            await services.get_public_privacy_policy(session, "en", now=now)
        assert no_policy.value.code == "privacy_policy_unavailable"

        await services.create_privacy_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=now + timedelta(days=1),
            actor_id=reviewer.id,
        )
        with pytest.raises(AppException) as draft:
            await services.get_public_privacy_policy(session, "en", now=now)
        assert draft.value.code == "privacy_policy_unavailable"

        await _review_current(session, services, locale="zh-CN", actor_id=reviewer.id)
        await _review_current(session, services, locale="en", actor_id=reviewer.id)
        await _publish_current(
            session,
            services,
            actor_id=reviewer.id,
            now=now + timedelta(days=2),
        )
        with pytest.raises(AppException) as future:
            await services.get_public_privacy_policy(session, "en", now=now)
        assert future.value.code == "privacy_policy_unavailable"


async def test_public_policy_defensively_rejects_sqlite_corrupted_published_translation(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证读取层防御性拒绝 SQLite 人工制造的 published 正文损坏。

    输入：privacy_factory，隔离 SQLite 数据库。
    输出：None；该测试不代表生产可达路径，仅验证纵深防御读取门禁。
    """
    models, _schemas, services = _privacy_symbols()
    now = datetime.now(UTC)
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(
            select(User).where(User.email == "privacy-reviewer@example.com")
        )
        assert reviewer is not None
        await _initialize_and_create_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=now - timedelta(minutes=1),
            actor_id=reviewer.id,
        )
        version = await _review_and_publish(session, actor_id=reviewer.id)
        en_locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert en_locale is not None
        translation = await session.scalar(
            select(models.PrivacyNoticeVersionTranslation).where(
                models.PrivacyNoticeVersionTranslation.privacy_notice_version_id == version.id,
                models.PrivacyNoticeVersionTranslation.locale_id == en_locale.id,
            )
        )
        assert translation is not None
        # TEST ONLY：SQLite 无 PostgreSQL 不可变触发器，直接损坏记录以验证读取层 fail-closed。
        translation.title = None
        translation.body_markdown = None
        translation.content_hash = None
        await session.flush()
        with pytest.raises(AppException) as missing:
            await services.get_public_privacy_policy(
                session,
                "zh-CN",
                now=now,
            )
        assert missing.value.code == "privacy_policy_unavailable"


async def test_context_validation_and_rfq_binding_preserve_exact_current_version(
    privacy_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证当前令牌成功，缺失/过期/伪造/错语言/陈旧令牌零写入。

    输入：privacy_factory，隔离数据库。
    输出：None；RFQ 可绕过政策版本绑定或落库元数据不完整时失败。
    """
    _models, _schemas, privacy_services = _privacy_symbols()
    from app.modules.rfq.services import create_rfq

    async def allow_test_http_requests(_ip: str | None) -> None:
        """
        隔离本测试的 Redis 限流计数，使连续负向请求只验证 Privacy HTTP 错误契约。

        输入：_ip，请求解析出的客户端 IP，本测试不使用该值。
        输出：None，允许请求继续进入 Privacy context 校验。
        """

    # 限流阈值由独立 Redis 测试覆盖；此处替换路由已绑定的引用，避免共享客户端 IP 污染。
    monkeypatch.setattr("app.api.v1.rfq.enforce_public_rate_limit", allow_test_http_requests)

    now = datetime.now(UTC)
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        await _initialize_and_create_draft(session, actor_id=reviewer.id)
        await _complete_draft(
            session,
            effective_at=now - timedelta(minutes=1),
            actor_id=reviewer.id,
        )
        version_a = await _review_and_publish(session, actor_id=reviewer.id)
        policy_a = await privacy_services.get_public_privacy_policy(session, "en", now=now)
        token_a = privacy_services.create_privacy_context_token(policy_a, now=now)
        expired = privacy_services.create_privacy_context_token(
            policy_a,
            now=now - timedelta(hours=1),
            ttl=timedelta(minutes=1),
        )

    def rfq_payload(token: str | None, preferred_language: str = "en") -> RFQCreate:
        """输入令牌和语言；输出最小合法 RFQ 输入。"""
        return RFQCreate(
            company_name="ACME",
            contact_name="Lee",
            email="lee@example.com",
            message="Need a quote",
            consent_privacy=True,
            preferred_language=preferred_language,
            privacy_context_token=token,
            items=[
                {
                    "item_type": "custom",
                    "product_name_text": "Test-only screw component",
                    "quantity": "1",
                }
            ],
        )

    decoded_claims = jwt.decode(token_a, options={"verify_signature": False})
    assert set(decoded_claims) == {"aud", "type", "ver", "loc", "hash", "url", "iat", "exp"}
    assert decoded_claims["aud"] == "junhui-rfq-privacy-consent"
    assert decoded_claims["type"] == "privacy_policy_context"
    assert decoded_claims["ver"] == policy_a["version_label"]
    assert decoded_claims["loc"] == "en"
    assert decoded_claims["hash"] == policy_a["content_hash"]
    assert decoded_claims["url"] == policy_a["canonical_url"]
    assert decoded_claims["iat"] == int(now.timestamp())
    assert decoded_claims["exp"] - decoded_claims["iat"] == 600
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        str(decoded_claims),
        re.IGNORECASE,
    )
    wrong_hash_policy = {**policy_a, "content_hash": "0" * 64}
    wrong_url_policy = {
        **policy_a,
        "canonical_url": "https://junhuiscrewbarrel.com/en/not-privacy/",
    }
    from app.core.config import get_settings

    signing_secret = get_settings().jwt_signing_secret
    wrong_audience_token = jwt.encode(
        {**decoded_claims, "aud": "wrong-privacy-audience"},
        signing_secret,
        algorithm="HS256",
    )
    wrong_type_token = jwt.encode(
        {**decoded_claims, "type": "wrong_privacy_context_type"},
        signing_secret,
        algorithm="HS256",
    )
    invalid_cases = (
        (None, "en", "privacy_context_required"),
        (expired, "en", "privacy_context_expired"),
        (token_a[:-1] + ("a" if token_a[-1] != "a" else "b"), "en", "privacy_context_invalid"),
        (token_a, "zh-CN", "privacy_context_locale_mismatch"),
        (wrong_audience_token, "en", "privacy_context_invalid"),
        (wrong_type_token, "en", "privacy_context_invalid"),
        (
            privacy_services.create_privacy_context_token(wrong_hash_policy, now=now),
            "en",
            "privacy_context_stale",
        ),
        (
            privacy_services.create_privacy_context_token(wrong_url_policy, now=now),
            "en",
            "privacy_context_stale",
        ),
    )
    async with _client(privacy_factory) as client:
        for token, locale, expected_code in invalid_cases:
            rejected = await client.post(
                "/api/v1/public/rfqs",
                json=rfq_payload(token, locale).model_dump(mode="json"),
            )
            assert rejected.status_code in {409, 422}
            assert rejected.json()["error"]["code"] == expected_code
            assert "submission_token" not in rejected.text
    async with privacy_factory() as session:
        assert await session.scalar(select(func.count()).select_from(RFQ)) == 0
        assert await session.scalar(select(func.count()).select_from(RFQItem)) == 0

    async with privacy_factory() as session, session.begin():
        created = await create_rfq(
            session,
            rfq_payload(token_a),
            ip="198.51.100.9",
            user_agent="privacy-test",
        )
        created_reference = created.public_reference
    async with privacy_factory() as session:
        stored = await session.scalar(select(RFQ).where(RFQ.public_reference == created_reference))
        assert stored is not None
        assert stored.privacy_notice_version_id == version_a.id
        assert stored.privacy_version_label == version_a.version_label
        assert stored.privacy_policy_locale == "en"
        assert stored.privacy_content_hash == policy_a["content_hash"]
        assert stored.privacy_canonical_url.endswith("/en/privacy/")
        assert stored.privacy_confirmed_at is not None

    # 切换到 B 后，A 令牌必须变陈旧且不能新增任何 RFQ。
    async with privacy_factory() as session, session.begin():
        reviewer = await session.scalar(select(User).where(User.email == "privacy-reviewer@example.com"))
        assert reviewer is not None
        await privacy_services.create_privacy_draft(session, actor_id=reviewer.id)
        draft_b = await privacy_services.get_privacy_admin_state(session)
        await privacy_services.update_privacy_draft(
            session,
            _schemas.PrivacyDraftUpdate(
                expected_revision=draft_b["draft"]["revision"],
                effective_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
            actor_id=reviewer.id,
        )
        await _review_current(
            session, privacy_services, locale="zh-CN", actor_id=reviewer.id
        )
        await _review_current(session, privacy_services, locale="en", actor_id=reviewer.id)
        version_b = await _publish_current(
            session, privacy_services, actor_id=reviewer.id
        )
        assert version_b.version_label != version_a.version_label
    async with privacy_factory() as session:
        before = await session.scalar(select(func.count()).select_from(RFQ))
        before_items = await session.scalar(select(func.count()).select_from(RFQItem))
    async with _client(privacy_factory) as client:
        stale = await client.post(
            "/api/v1/public/rfqs",
            json=rfq_payload(token_a).model_dump(mode="json"),
        )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "privacy_context_stale"
    assert "submission_token" not in stale.text
    async with privacy_factory() as session:
        assert await session.scalar(select(func.count()).select_from(RFQ)) == before
        assert await session.scalar(select(func.count()).select_from(RFQItem)) == before_items


async def test_legacy_rfq_is_nullable_and_partial_policy_metadata_is_rejected(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证历史 consent=true RFQ 保持全空，并拒绝只写部分版本证据。

    输入：privacy_factory，隔离数据库。
    输出：None；兼容性或组合完整性约束失效时失败。
    """
    async with privacy_factory() as session, session.begin():
        legacy = RFQ(
            public_reference="RFQ-LEGACY-PRIVACY",
            company_name="Legacy",
            contact_name="Lee",
            email="legacy@example.com",
            consent_privacy=True,
        )
        session.add(legacy)
    assert legacy.privacy_notice_version_id is None
    assert legacy.privacy_version_label is None
    assert legacy.privacy_confirmed_at is None

    async with privacy_factory() as session:
        session.add(
            RFQ(
                public_reference="RFQ-PARTIAL-PRIVACY",
                company_name="Invalid",
                contact_name="Lee",
                email="invalid@example.com",
                consent_privacy=True,
                privacy_version_label="PRIVACY-000001",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_privacy_admin_permission_csrf_history_and_revision_audit_boundaries(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 Privacy 写操作权限/CSRF、历史隔离及 Revision/Audit 记录。

    输入：privacy_factory，隔离数据库。
    输出：None；sales/seo 越权或变更缺少审计快照时失败。
    """
    path = "/api/v1/privacy/initialize"
    async with _client(privacy_factory) as client:
        anonymous = await client.post(path)
    async with _role_client(privacy_factory, "seo_manager") as client:
        seo = await client.post(path)
    async with _role_client(privacy_factory, "sales") as client:
        sales = await client.post(path)
    async with _role_client(privacy_factory, "content_admin", with_csrf=False) as client:
        no_csrf = await client.post(path)
    async with _role_client(privacy_factory, "content_admin") as client:
        initialized = await client.post(path)
        drafted = await client.post("/api/v1/privacy/drafts", json={})
        draft_revision = drafted.json()["data"]["draft"]["revision"]
        updated = await client.put(
            "/api/v1/privacy/draft",
            json={
                "expected_revision": draft_revision,
                "effective_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "translations": [
                    {
                        "locale": "zh-CN",
                        "title": "隐私政策",
                        "body_markdown": "# 隐私政策\n\n询盘用途。",
                    },
                    {
                        "locale": "en",
                        "title": "Privacy Notice",
                        "body_markdown": "# Privacy\n\nRFQ purposes.",
                    },
                ],
            },
        )
    async with _role_client(privacy_factory, "editor") as client:
        forbidden_history = await client.get("/api/v1/privacy/history")
        editor_status = await client.patch(
            "/api/v1/privacy/status", json={"status": "disabled"}
        )
    async with _role_client(privacy_factory, "translator") as client:
        translator_status = await client.patch(
            "/api/v1/privacy/status", json={"status": "disabled"}
        )
    async with _role_client(privacy_factory, "content_admin", with_csrf=False) as client:
        no_csrf_status = await client.patch(
            "/api/v1/privacy/status", json={"status": "disabled"}
        )

    assert anonymous.status_code == 401
    assert seo.status_code == 403
    assert sales.status_code == 403
    assert no_csrf.status_code == 403
    assert initialized.status_code == 200
    assert drafted.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["draft"]["revision"] == draft_revision + 1
    assert forbidden_history.status_code == 403
    assert editor_status.status_code == 403
    assert translator_status.status_code == 403
    assert no_csrf_status.status_code == 403
    assert "id" not in str(drafted.json()["data"])

    async with privacy_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ContentRevision)) >= 4
        assert await session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action.like("privacy.%"))
        ) >= 2


async def test_privacy_review_and_publish_bind_to_admin_observed_draft(
    privacy_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证审核/发布只能作用于管理员实际看到的版本、Revision 与正文哈希。

    输入：privacy_factory，隔离数据库。
    输出：None；陈旧或伪造观察值能改变生命周期时失败。
    """
    async with _role_client(privacy_factory, "content_admin") as client:
        assert (await client.post("/api/v1/privacy/initialize")).status_code == 200
        assert (
            await client.post("/api/v1/privacy/drafts", json={"clone_current": True})
        ).status_code == 200
        state = (await client.get("/api/v1/privacy")).json()["data"]
        update = await client.put(
            "/api/v1/privacy/draft",
            json={
                "expected_revision": state["draft"]["revision"],
                "effective_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "translations": [
                    {
                        "locale": "zh-CN",
                        "title": "隐私政策",
                        "body_markdown": "仅用于询盘。",
                    },
                    {
                        "locale": "en",
                        "title": "Privacy Notice",
                        "body_markdown": "Used only for RFQs.",
                    },
                ],
            },
        )
        observed = update.json()["data"]["draft"]
        stale_review = await client.post(
            "/api/v1/privacy/draft/review/zh-CN",
            json={
                "expected_version_label": observed["version_label"],
                "expected_revision": observed["revision"] - 1,
                "expected_content_hash": observed["translations"]["zh-CN"]["content_hash"],
            },
        )
        assert stale_review.status_code == 409
        assert stale_review.json()["error"]["code"] == "privacy_draft_observation_conflict"
        unchanged = (await client.get("/api/v1/privacy")).json()["data"]["draft"]
        assert unchanged["translations"]["zh-CN"]["translation_status"] == "draft"

        for locale in ("zh-CN", "en"):
            reviewed = await client.post(
                f"/api/v1/privacy/draft/review/{locale}",
                json={
                    "expected_version_label": observed["version_label"],
                    "expected_revision": observed["revision"],
                    "expected_content_hash": observed["translations"][locale]["content_hash"],
                },
            )
            assert reviewed.status_code == 200

        stale_publish = await client.post(
            "/api/v1/privacy/draft/publish",
            json={
                "expected_version_label": observed["version_label"],
                "expected_revision": observed["revision"],
                "expected_content_hashes": {
                    "zh-CN": observed["translations"]["zh-CN"]["content_hash"],
                    "en": "0" * 64,
                },
            },
        )
        assert stale_publish.status_code == 409
        assert stale_publish.json()["error"]["code"] == "privacy_draft_observation_conflict"
        before_publish = (await client.get("/api/v1/privacy")).json()["data"]
        assert before_publish["current"] is None

        published = await client.post(
            "/api/v1/privacy/draft/publish",
            json={
                "expected_version_label": observed["version_label"],
                "expected_revision": observed["revision"],
                "expected_content_hashes": {
                    locale: observed["translations"][locale]["content_hash"]
                    for locale in ("zh-CN", "en")
                },
            },
        )
        assert published.status_code == 200
        assert published.json()["data"]["current"]["version_label"] == observed["version_label"]
