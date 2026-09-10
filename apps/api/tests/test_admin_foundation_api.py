"""Admin Users 与 Roles/Permissions 基础 API 测试。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users.bootstrap import create_super_admin
from app.modules.users.models import Permission, Role, RolePermission, User, UserRole
from app.seed import PERMISSION_CODES, seed_database


@pytest.fixture
async def admin_api_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建含系统 Seed 和 super_admin 的 Admin API 测试数据库。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    await create_super_admin(
        factory,
        email="owner@example.com",
        password="StrongPassword!2026",
        display_name="Owner",
    )
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _admin_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """创建已登录 super_admin 的 Admin API 客户端。"""
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "StrongPassword!2026"},
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


async def test_admin_can_create_update_disable_and_list_users(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Users 基础管理及相应审计动作。"""
    async with _admin_client(admin_api_session_factory) as client:
        created = await client.post(
            "/api/v1/users",
            json={
                "email": "EDITOR@EXAMPLE.COM",
                "password": "EditorPassword!2026",
                "display_name": "Editor",
                "role_names": ["editor"],
            },
        )
        user_id = created.json()["data"]["id"]
        updated = await client.patch(
            f"/api/v1/users/{user_id}", json={"display_name": "Senior Editor"}
        )
        disabled = await client.post(f"/api/v1/users/{user_id}/disable")
        listed = await client.get("/api/v1/users")

    assert created.status_code == 201
    assert created.json()["data"]["email"] == "editor@example.com"
    assert updated.json()["data"]["display_name"] == "Senior Editor"
    assert disabled.json()["data"]["is_active"] is False
    assert len(listed.json()["data"]) == 2
    async with admin_api_session_factory() as session:
        actions = set((await session.scalars(select(AuditLog.action))).all())
    assert {"user.create", "user.update", "user.disable", "role.assign"}.issubset(actions)


async def test_admin_can_view_eight_roles_and_permissions(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Roles/Permissions 查看 API 返回完整系统矩阵。"""
    async with _admin_client(admin_api_session_factory) as client:
        response = await client.get("/api/v1/rbac/roles")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 8
    super_admin = next(item for item in response.json()["data"] if item["name"] == "super_admin")
    assert len(super_admin["permissions"]) == len(PERMISSION_CODES)


async def test_user_email_duplicate_is_case_insensitive(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 API 层同样拒绝仅大小写不同的重复邮箱。"""
    async with _admin_client(admin_api_session_factory) as client:
        response = await client.post(
            "/api/v1/users",
            json={
                "email": "OWNER@EXAMPLE.COM",
                "password": "DifferentPassword!2026",
                "display_name": "Duplicate",
                "role_names": [],
            },
        )
    assert response.status_code == 409


async def test_user_creation_requires_role_manage_permission(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证仅有 user.create 的用户不能借创建用户接口分配角色。"""
    async with admin_api_session_factory() as session, session.begin():
        creator_role = Role(
            name="limited_creator",
            display_name="受限创建者",
            description="仅用于验证权限边界",
            is_system=False,
        )
        creator = User(
            email="creator@example.com",
            password_hash=hash_password("CreatorPassword!2026"),
            display_name="Creator",
            is_active=True,
        )
        session.add_all([creator_role, creator])
        await session.flush()
        create_permission = await session.scalar(
            select(Permission).where(Permission.code == "user.create")
        )
        assert create_permission is not None
        session.add_all(
            [
                RolePermission(role_id=creator_role.id, permission_id=create_permission.id),
                UserRole(user_id=creator.id, role_id=creator_role.id),
            ]
        )

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with admin_api_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "creator@example.com", "password": "CreatorPassword!2026"},
        )
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        response = await client.post(
            "/api/v1/users",
            json={
                "email": "escalated@example.com",
                "password": "EscalatedPassword!2026",
                "display_name": "Escalated",
                "role_names": ["super_admin"],
            },
        )

    assert login.status_code == 200
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


async def test_role_assignment_respects_actor_permission_ceiling(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证具备角色管理权的受限用户仍不能分配高于自身的角色。"""
    async with admin_api_session_factory() as session, session.begin():
        manager_role = Role(
            name="limited_role_manager",
            display_name="受限角色管理员",
            description="仅用于验证权限上限",
            is_system=False,
        )
        manager = User(
            email="manager@example.com",
            password_hash=hash_password("ManagerPassword!2026"),
            display_name="Manager",
            is_active=True,
        )
        session.add_all([manager_role, manager])
        await session.flush()
        permissions = list(
            (
                await session.scalars(
                    select(Permission).where(Permission.code.in_(["user.create", "role.manage"]))
                )
            ).all()
        )
        session.add_all(
            [RolePermission(role_id=manager_role.id, permission_id=item.id) for item in permissions]
            + [UserRole(user_id=manager.id, role_id=manager_role.id)]
        )
        manager_role_id = manager_role.id

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with admin_api_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "manager@example.com", "password": "ManagerPassword!2026"},
        )
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        response = await client.post(
            "/api/v1/users",
            json={
                "email": "too-powerful@example.com",
                "password": "TooPowerfulPassword!2026",
                "display_name": "Too Powerful",
                "role_names": ["super_admin"],
            },
        )
        role_update = await client.put(
            f"/api/v1/rbac/roles/{manager_role_id}/permissions",
            json={"permission_codes": ["user.create", "role.manage", "settings.update"]},
        )

    assert login.status_code == 200
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_permission_ceiling"
    assert role_update.status_code == 403
    assert role_update.json()["error"]["code"] == "permission_grant_ceiling"


async def test_authority_lists_include_bilingual_readable_title_projection(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Authority 列表直接返回中英文可读标题，后台无需用 slug 或 UUID 猜测。"""
    from app.modules.authority.models import (
        FAQ,
        CaseStudy,
        CaseStudyTranslation,
        FAQTranslation,
    )
    from app.modules.localization.models import Locale

    async with admin_api_session_factory() as session, session.begin():
        zh_locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        en_locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert zh_locale is not None and en_locale is not None
        case = CaseStudy(slug="readable-case", status="enabled")
        faq = FAQ(status="enabled")
        session.add_all([case, faq])
        await session.flush()
        session.add_all(
            [
                CaseStudyTranslation(
                    case_study_id=case.id,
                    locale_id=zh_locale.id,
                    title="中文案例标题",
                ),
                CaseStudyTranslation(
                    case_study_id=case.id,
                    locale_id=en_locale.id,
                    title="English case title",
                ),
                FAQTranslation(
                    faq_id=faq.id,
                    locale_id=zh_locale.id,
                    question="中文常见问题？",
                    answer="中文答案。",
                ),
                FAQTranslation(
                    faq_id=faq.id,
                    locale_id=en_locale.id,
                    question="English FAQ?",
                    answer="English answer.",
                ),
            ]
        )

    async with _admin_client(admin_api_session_factory) as client:
        cases = await client.get("/api/v1/authority/cases")
        faqs = await client.get("/api/v1/authority/faqs")

    assert cases.status_code == 200
    assert faqs.status_code == 200
    case_item = next(item for item in cases.json()["data"]["items"] if item["slug"] == "readable-case")
    faq_item = faqs.json()["data"]["items"][0]
    assert "display_title" in faq_item, faqs.json()["data"]
    assert faq_item["display_title"] == "中文常见问题？"
    assert case_item["display_title"] == "中文案例标题"
    assert case_item["display_title_en"] == "English case title"
    assert faq_item["display_title_en"] == "English FAQ?"
    assert case_item["translation_count"] == 2


async def test_catalog_lists_include_chinese_first_readable_name_projection(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 Catalog 列表提供中文优先名称，关系选择器无需显示 slug 或 UUID。"""
    from app.api.v1.catalog import _list_entities
    from app.core.pagination import PaginationParams
    from app.modules.catalog.models import Application, ApplicationTranslation
    from app.modules.localization.models import Locale

    async with admin_api_session_factory() as session, session.begin():
        zh_locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        en_locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert zh_locale is not None and en_locale is not None
        application = Application(slug="readable-application", status="enabled")
        session.add(application)
        await session.flush()
        session.add_all(
            [
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=zh_locale.id,
                    name="中文应用名称",
                ),
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=en_locale.id,
                    name="English application name",
                ),
            ]
        )

    async with admin_api_session_factory() as session:
        direct_result = await _list_entities(session, Application, PaginationParams())
    direct_item = next(
        item for item in direct_result["items"] if item["slug"] == "readable-application"
    )
    assert direct_item["display_name"] == "中文应用名称"

    async with _admin_client(admin_api_session_factory) as client:
        response = await client.get("/api/v1/catalog/applications")

    assert response.status_code == 200
    item = next(
        item
        for item in response.json()["data"]["items"]
        if item["slug"] == "readable-application"
    )
    assert "display_name" in item, response.json()["data"]
    assert item["display_name"] == "中文应用名称"
    assert item["display_name_en"] == "English application name"
    assert item["translation_count"] == 2


async def test_rfq_list_supports_server_side_search_status_and_pagination(
    admin_api_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证询盘列表的搜索、状态过滤和分页由服务端执行并返回真实总数。"""
    from app.modules.rfq.models import RFQ

    async with admin_api_session_factory() as session, session.begin():
        session.add_all(
            [
                RFQ(
                    public_reference="CN-UX-001",
                    status="new",
                    company_name="华东演示制造",
                    contact_name="张工",
                    email="zhang@example.com",
                    consent_privacy=True,
                ),
                RFQ(
                    public_reference="CN-UX-002",
                    status="in_progress",
                    company_name="华南演示制造",
                    contact_name="李工",
                    email="li@example.com",
                    consent_privacy=True,
                ),
                RFQ(
                    public_reference="CN-UX-003",
                    status="new",
                    company_name="海外演示制造",
                    contact_name="Lee",
                    email="lee@example.com",
                    consent_privacy=True,
                ),
            ]
        )

    async with _admin_client(admin_api_session_factory) as client:
        response = await client.get(
            "/api/v1/rfqs",
            params={"q": "演示制造", "status": "new", "page": 1, "page_size": 1},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["page"] == 1, payload
    assert payload["page_size"] == 1, payload
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["status"] == "new"
