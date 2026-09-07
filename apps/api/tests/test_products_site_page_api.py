"""固定 Products SitePage 的服务、权限与 SEO API 回归测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.exceptions.handlers import AppException
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.audit.models import AuditLog
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    SitePage,
    SitePageTranslation,
    TranslationStatus,
)
from app.modules.discovery import models as _discovery_models  # noqa: F401
from app.modules.discovery.models import SeoDocument
from app.modules.localization import models as _localization_models  # noqa: F401
from app.modules.localization.models import Locale
from app.modules.users.models import Role, User, UserRole
from app.seed import seed_database

# 仅供隔离测试登录使用；不是环境账号、口令或可复用凭据。
TEST_LOGIN_PROOF = "Test-Only-Auth-2026!"
PRODUCTS_KEY = "products"


@pytest.fixture
async def products_site_page_api_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建带四类后台角色的隔离 SitePage API 数据库。

    输入：
        sqlite_database_url: str，pytest 临时 SQLite 数据库地址。

    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，隔离会话工厂。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    async with factory() as session, session.begin():
        for role_name in ("content_admin", "editor", "reviewer", "seo_manager"):
            role = await session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            user = User(
                email=f"products-{role_name}@example.com",
                password_hash=hash_password(TEST_LOGIN_PROOF),
                display_name=f"products-{role_name}",
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
    创建覆盖数据库依赖的匿名 HTTP 客户端。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试会话工厂。

    输出：
        AsyncIterator[AsyncClient]，未登录客户端。
    """
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """输入无；输出使用隔离数据库的请求级会话。"""
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@asynccontextmanager
async def _role_client(
    session_factory: async_sessionmaker[AsyncSession],
    role_name: str,
    *,
    with_csrf: bool = True,
) -> AsyncIterator[AsyncClient]:
    """
    创建指定角色的认证客户端，并按需携带 CSRF 请求头。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试会话工厂。
        role_name: str，要登录的系统角色名。
        with_csrf: bool，是否附带双提交 CSRF Header。

    输出：
        AsyncIterator[AsyncClient]，已认证客户端。
    """
    async with _client(session_factory) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"products-{role_name}@example.com",
                "password": TEST_LOGIN_PROOF,
            },
        )
        assert login.status_code == 200
        if with_csrf:
            client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


async def _initialize_products(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """
    通过受保护 HTTP 接口初始化固定 Products 页面。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试会话工厂。

    输出：
        dict[str, object]，初始化接口返回的页面详情。
    """
    async with _role_client(session_factory, "content_admin") as client:
        response = await client.post(f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/initialize")
    assert response.status_code == 200
    return response.json()["data"]


async def test_products_initializer_requires_auth_content_update_and_csrf_and_is_idempotent(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证固定页面初始化要求认证、content.update、CSRF，并且重复调用不产生副作用。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；权限、初始状态、双语记录或幂等性不符时失败。
    """
    path = f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/initialize"
    async with _client(products_site_page_api_factory) as client:
        anonymous = await client.post(path)
    async with _role_client(products_site_page_api_factory, "seo_manager") as client:
        wrong_permission = await client.post(path)
    async with _role_client(
        products_site_page_api_factory, "content_admin", with_csrf=False
    ) as client:
        missing_csrf = await client.post(path)
    async with _role_client(products_site_page_api_factory, "content_admin") as client:
        first = await client.post(path)
        second = await client.post(path)

    assert anonymous.status_code == 401
    assert wrong_permission.status_code == 403
    assert missing_csrf.status_code == 403
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert all("seo" not in item for item in first.json()["data"]["languages"])

    detail = first.json()["data"]
    assert detail["page"]["system_key"] == PRODUCTS_KEY
    assert detail["page"]["status"] == "enabled"
    languages = {item["locale"]["code"]: item for item in detail["languages"]}
    assert set(languages) == {"zh-CN", "en"}
    assert languages["zh-CN"]["translation"]["display_name"] == "产品"
    assert languages["en"]["translation"]["display_name"] == "Products"
    assert languages["zh-CN"]["translation_status"]["status"] == "draft"
    assert languages["en"]["publication"]["status"] == "draft"
    assert languages["zh-CN"]["route"]["path"] == "/zh-cn/products/"
    assert languages["en"]["route"]["path"] == "/en/products/"
    assert all(
        item["route"]["active"] is False and item["route"]["indexable"] is False
        for item in languages.values()
    )

    async with products_site_page_api_factory() as session:
        counts = {
            "pages": await session.scalar(select(func.count()).select_from(SitePage)),
            "translations": await session.scalar(
                select(func.count()).select_from(SitePageTranslation)
            ),
            "translation_statuses": await session.scalar(
                select(func.count())
                .select_from(TranslationStatus)
                .where(TranslationStatus.owner_type == "site_page")
            ),
            "publications": await session.scalar(
                select(func.count())
                .select_from(ContentPublication)
                .where(ContentPublication.owner_type == "site_page")
            ),
            "routes": await session.scalar(
                select(func.count())
                .select_from(ContentRoute)
                .where(ContentRoute.owner_type == "site_page")
            ),
            "initialize_audits": await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "site_page.initialize")
            ),
        }
    assert counts == {
        "pages": 1,
        "translations": 2,
        "translation_statuses": 2,
        "publications": 2,
        "routes": 2,
        "initialize_audits": 1,
    }


async def test_products_initializer_rejects_occupied_canonical_path_without_overwrite(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 Products 正式路径被其他内容占用时返回 409 且不创建 SitePage。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；冲突路径被覆盖或页面被部分创建时失败。
    """
    async with products_site_page_api_factory() as session, session.begin():
        zh_locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        assert zh_locale is not None
        session.add(
            ContentRoute(
                owner_type="product",
                owner_id=uuid.uuid4(),
                locale_id=zh_locale.id,
                path="/zh-cn/products/",
                is_canonical=True,
                active=False,
                indexable=False,
            )
        )

    async with _role_client(products_site_page_api_factory, "content_admin") as client:
        response = await client.post(
            f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/initialize"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "site_page_conflict"
    async with products_site_page_api_factory() as session:
        assert await session.scalar(select(func.count()).select_from(SitePage)) == 0
        occupied = await session.scalar(
            select(ContentRoute).where(ContentRoute.path == "/zh-cn/products/")
        )
        assert occupied is not None and occupied.owner_type == "product"


async def test_products_initializer_rejects_incoherent_existing_lifecycle_state(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证已有 draft 页面若 Route 被异常开启，重复初始化返回 409 而不自动修复。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；不一致状态被接受或被静默覆盖时失败。
    """
    detail = await _initialize_products(products_site_page_api_factory)
    page_id = uuid.UUID(detail["page"]["id"])
    async with products_site_page_api_factory() as session, session.begin():
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "site_page",
                ContentRoute.owner_id == page_id,
                ContentRoute.path == "/zh-cn/products/",
            )
        )
        assert route is not None
        route.active = True

    async with _role_client(products_site_page_api_factory, "content_admin") as client:
        response = await client.post(
            f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/initialize"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "site_page_conflict"
    async with products_site_page_api_factory() as session:
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "site_page",
                ContentRoute.owner_id == page_id,
                ContentRoute.path == "/zh-cn/products/",
            )
        )
        assert route is not None and route.active is True


async def test_site_page_seo_update_is_partial_validates_locale_and_skips_noop_history(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证按 key/语言更新 SEO 会保留省略字段、校验归属，并跳过 no-op 历史。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；字段丢失、越权 owner/locale 或重复 Revision/Audit 时失败。
    """
    detail = await _initialize_products(products_site_page_api_factory)
    languages = {item["locale"]["code"]: item for item in detail["languages"]}
    en_locale_id = languages["en"]["locale"]["id"]
    first_payload = {
        "seo_title": "Initial Products Title",
        "meta_description": "Initial products description.",
        "canonical_override": "https://junhuiscrewbarrel.com/en/products/",
        "robots_index": False,
        "robots_follow": False,
        "og_title": "Products OG",
        "og_description": "Products OG description.",
        "og_media_id": str(uuid.uuid4()),
        "schema_override_jsonb": {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Products",
        },
    }
    endpoint = f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/seo/en"
    async with _role_client(products_site_page_api_factory, "seo_manager") as client:
        first = await client.put(endpoint, json=first_payload)
        partial = await client.patch(endpoint, json={"seo_title": "Updated Products Title"})
        noop = await client.patch(endpoint, json={"seo_title": "Updated Products Title"})
        reopened = await client.get(f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}")
        invalid_owner = await client.put(
            f"/api/v1/discovery/seo/site_page/{uuid.uuid4()}/{en_locale_id}",
            json={"seo_title": "Must not be saved"},
        )

    assert first.status_code == 200
    assert partial.status_code == 200
    assert noop.status_code == 200
    assert reopened.status_code == 200
    assert invalid_owner.status_code == 409
    assert invalid_owner.json()["error"]["code"] == "site_page_fixed_key_required"

    saved = next(
        item
        for item in reopened.json()["data"]["languages"]
        if item["locale"]["code"] == "en"
    )["seo"]
    assert saved["seo_title"] == "Updated Products Title"
    for field_name, expected in first_payload.items():
        if field_name != "seo_title":
            assert saved[field_name] == expected

    async with products_site_page_api_factory() as session:
        document = await session.scalar(
            select(SeoDocument).where(
                SeoDocument.owner_type == "site_page",
                SeoDocument.locale_id == uuid.UUID(en_locale_id),
            )
        )
        assert document is not None
        revision_count = await session.scalar(
            select(func.count())
            .select_from(ContentRevision)
            .where(
                ContentRevision.owner_type == "seo_document",
                ContentRevision.owner_id == document.id,
                ContentRevision.locale_id == document.locale_id,
            )
        )
        audit_count = await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "seo.upsert",
                AuditLog.target_type == "site_page",
                AuditLog.target_id == str(document.owner_id),
            )
        )
    assert revision_count == 2
    assert audit_count == 2


async def test_site_page_writes_reject_incoherent_records_before_commit(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 SEO 与生命周期写入会先检查完整页面身份，冲突时不提交部分修改。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；不一致页面被写入 SEO 或推进审核状态时失败。
    """
    await _initialize_products(products_site_page_api_factory)
    async with products_site_page_api_factory() as session, session.begin():
        translation = await session.scalar(
            select(SitePageTranslation).where(SitePageTranslation.display_name == "产品")
        )
        assert translation is not None
        translation.display_name = "人工冲突名称"

    async with _role_client(products_site_page_api_factory, "seo_manager") as client:
        seo_response = await client.patch(
            f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/seo/zh-CN",
            json={"seo_title": "不得写入"},
        )
    async with _role_client(products_site_page_api_factory, "reviewer") as client:
        review_response = await client.post(
            f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/translations/zh-CN/review"
        )

    assert seo_response.status_code == 409
    assert review_response.status_code == 409
    async with products_site_page_api_factory() as session:
        assert await session.scalar(select(func.count()).select_from(SeoDocument)) == 0
        translation_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "site_page",
                TranslationStatus.locale_id
                == select(Locale.id).where(Locale.code == "zh-CN").scalar_subquery(),
            )
        )
        assert translation_status is not None
        assert translation_status.status == "draft"


async def test_generic_seo_put_keeps_existing_full_replace_contract(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 SitePage 局部保存不会改变既有通用 SEO PUT 的完整替换语义。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；通用 PUT 省略字段未恢复模型默认值时失败。
    """
    async with products_site_page_api_factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert locale is not None
        locale_id = locale.id
    owner_id = uuid.uuid4()
    endpoint = f"/api/v1/discovery/seo/legacy_owner/{owner_id}/{locale_id}"
    async with _role_client(products_site_page_api_factory, "seo_manager") as client:
        first = await client.put(
            endpoint,
            json={
                "seo_title": "Initial",
                "canonical_override": "https://junhuiscrewbarrel.com/en/products/",
                "robots_index": False,
                "robots_follow": False,
            },
        )
        replaced = await client.put(
            endpoint,
            json={"seo_title": "Replaced", "legacy_extra_field": "ignored"},
        )

    assert first.status_code == 200
    assert replaced.status_code == 200
    saved = replaced.json()["data"]
    assert saved["seo_title"] == "Replaced"
    assert saved["canonical_override"] is None
    assert saved["robots_index"] is True
    assert saved["robots_follow"] is True


async def test_products_review_and_publish_require_both_global_permissions_and_transition_service(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 SitePage 审核/发布要求 Translation 与 Content 双权限并同步生命周期状态。

    输入：products_site_page_api_factory，隔离 API 会话工厂。
    输出：None；SEO 权限越权或生命周期不同步时失败。
    """
    await _initialize_products(products_site_page_api_factory)
    review_path = (
        f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/translations/zh-CN/review"
    )
    publish_path = (
        f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/publications/zh-CN/publish"
    )

    async with _role_client(products_site_page_api_factory, "seo_manager") as client:
        seo_review = await client.post(review_path)
        seo_publish = await client.post(publish_path)
    async with _role_client(products_site_page_api_factory, "reviewer") as client:
        reviewed = await client.post(review_path)
        published = await client.post(publish_path)

    assert seo_review.status_code == 403
    assert seo_publish.status_code == 403
    assert reviewed.status_code == 200
    assert published.status_code == 200
    assert all("seo" not in item for item in published.json()["data"]["languages"])
    zh = next(
        item
        for item in published.json()["data"]["languages"]
        if item["locale"]["code"] == "zh-CN"
    )
    assert zh["translation_status"]["status"] == "published"
    assert zh["publication"]["status"] == "published"
    assert zh["route"]["active"] is True
    assert zh["route"]["indexable"] is True

    async with products_site_page_api_factory() as session:
        actions = list(
            (
                await session.scalars(
                    select(AuditLog.action)
                    .where(
                        AuditLog.target_type == "site_page",
                        AuditLog.action.in_(
                            {
                                "translation.review",
                                "publication.status_change",
                                "route.change",
                            }
                        ),
                    )
                    .order_by(AuditLog.created_at, AuditLog.id)
                )
            ).all()
        )
    assert actions.count("translation.review") == 1
    assert actions.count("publication.status_change") == 2
    assert actions.count("route.change") == 2


async def test_products_lifecycle_rejects_each_single_half_permission(
    products_site_page_api_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证审核和发布权限组合中任意一项缺失都会在 API 层被拒绝。

    输入：products_site_page_api_factory 与 monkeypatch 隔离权限集合。
    输出：None；任一单独 Translation/Content 权限可越权时失败。
    """
    from app.api.v1 import discovery as discovery_api

    await _initialize_products(products_site_page_api_factory)
    actor = SimpleNamespace(id=uuid.uuid4())
    original_collect_authorization = discovery_api.collect_authorization
    async with products_site_page_api_factory() as session:
        for permissions in ({"translation.review"}, {"content.review"}):
            monkeypatch.setattr(
                discovery_api,
                "collect_authorization",
                lambda _user, current=permissions: ([], current),
            )
            with pytest.raises(AppException) as review_error:
                await discovery_api.review_site_page_translation(
                    PRODUCTS_KEY,
                    "zh-CN",
                    session,
                    actor,
                    None,
                )
            assert review_error.value.status_code == 403

    monkeypatch.setattr(
        discovery_api,
        "collect_authorization",
        original_collect_authorization,
    )
    async with _role_client(products_site_page_api_factory, "reviewer") as client:
        reviewed = await client.post(
            f"/api/v1/discovery/site-pages/{PRODUCTS_KEY}/translations/zh-CN/review"
        )
    assert reviewed.status_code == 200

    async with products_site_page_api_factory() as session:
        for permissions in ({"translation.publish"}, {"content.publish"}):
            monkeypatch.setattr(
                discovery_api,
                "collect_authorization",
                lambda _user, current=permissions: ([], current),
            )
            with pytest.raises(AppException) as publish_error:
                await discovery_api.publish_site_page_publication(
                    PRODUCTS_KEY,
                    "zh-CN",
                    session,
                    actor,
                    None,
                )
            assert publish_error.value.status_code == 403
