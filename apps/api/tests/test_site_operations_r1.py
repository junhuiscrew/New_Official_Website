"""站点运营设置 R1 的服务端白名单、双语与受控重定向测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.security.passwords import hash_password
from app.main import create_app as _create_app
from app.modules.users.models import User
from app.seed import seed_database

# 上方应用入口导入用于注册完整路由模型集合，供隔离数据库 create_all 使用。
assert _create_app


@pytest.fixture
async def site_operations_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建站点运营服务使用的隔离数据库。

    输入：sqlite_database_url: str，pytest 临时数据库地址。
    输出：AsyncIterator，已初始化中英文与权限基础数据的会话工厂。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    yield factory
    await engine.dispose()


async def _actor(factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    """输入隔离会话工厂；输出测试专用操作用户ID。"""
    async with factory() as session, session.begin():
        user = User(
            email=f"site-operations-{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("Site-Operations-R1-Test-Only!"),
            display_name="站点运营测试用户",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        return user.id


def test_brand_draft_requires_both_locales_and_safe_media_ids() -> None:
    """验证品牌草稿必须完整保留中英文，且媒体引用只能使用 UUID。"""
    from app.modules.site_operations.schemas import BrandDraftUpdate

    valid_media_id = uuid.uuid4()
    payload = BrandDraftUpdate.model_validate(
        {
            "expected_revision": 3,
            "translations": {
                "zh-CN": {"display_name": "骏辉", "short_name": "骏辉"},
                "en": {"display_name": "Junhui", "short_name": "JUNHUI"},
            },
            "header_logo_media_id": str(valid_media_id),
            "mobile_logo_media_id": None,
            "favicon_media_id": None,
        }
    )
    assert payload.translations["en"].display_name == "Junhui"

    with pytest.raises(ValidationError):
        BrandDraftUpdate.model_validate(
            {
                "expected_revision": 3,
                "translations": {"zh-CN": {"display_name": "骏辉", "short_name": "骏辉"}},
            }
        )


def test_navigation_uses_server_owned_target_keys_and_rejects_duplicates() -> None:
    """验证导航不接收任意 URL、HTML 或重复稳定标识。"""
    from app.modules.site_operations.schemas import NavigationDraftUpdate

    payload = NavigationDraftUpdate.model_validate(
        {
            "expected_revision": 0,
            "header_items": [
                {"id": "products", "label": "产品", "target_key": "products", "enabled": True}
            ],
            "footer_groups": [],
        }
    )
    assert payload.header_items[0].target_key == "products"

    with pytest.raises(ValidationError):
        NavigationDraftUpdate.model_validate(
            {
                "expected_revision": 0,
                "header_items": [
                    {
                        "id": "bad",
                        "label": "外链",
                        "target_key": "javascript:alert(1)",
                        "enabled": True,
                    }
                ],
                "footer_groups": [],
            }
        )

    with pytest.raises(ValidationError):
        NavigationDraftUpdate.model_validate(
            {
                "expected_revision": 0,
                "header_items": [
                    {"id": "same", "label": "产品", "target_key": "products", "enabled": True},
                    {"id": "same", "label": "方案", "target_key": "solutions", "enabled": True},
                ],
                "footer_groups": [],
            }
        )


def test_default_navigation_preserves_existing_header_and_footer_shape() -> None:
    """验证幂等初始化只导入现有导航，不自行增加一级或页脚栏目。"""
    from app.modules.site_operations.registry import default_navigation_config

    config = default_navigation_config("zh-CN")
    assert [item["target_key"] for item in config["header_items"]] == [
        "products",
        "solutions",
        "materials",
        "applications",
        "capabilities",
        "case_studies",
        "knowledge",
        "about",
    ]
    assert [
        [item["target_key"] for item in group["items"]] for group in config["footer_groups"]
    ] == [
        ["products"],
        ["solutions"],
        ["knowledge"],
        ["contact", "request_a_quote", "downloads"],
        ["privacy", "sitemap"],
    ]


@pytest.mark.parametrize(
    ("source_path", "target_url", "expected_code"),
    [
        ("/", "https://junhuiscrewbarrel.com/en/", "protected_redirect_path"),
        ("/api/private/", "https://junhuiscrewbarrel.com/en/", "protected_redirect_path"),
        ("/legacy/", "https://junhuiscrewbarrel.com/en/?token=secret", "redirect_query_forbidden"),
    ],
)
def test_managed_redirect_rejects_protected_paths_and_query_leakage(
    source_path: str,
    target_url: str,
    expected_code: str,
) -> None:
    """验证受控管理器拒绝保护路径和可能泄露查询参数的目标。"""
    from app.core.exceptions.handlers import AppException
    from app.modules.site_operations.redirects import validate_managed_redirect

    with pytest.raises(AppException) as exc:
        validate_managed_redirect(
            source_host="junhuiscrew.com",
            source_path=source_path,
            target_url=target_url,
            existing_rules=[],
            active_paths=set(),
        )
    assert exc.value.code == expected_code


def test_managed_redirect_accepts_exact_safe_rule_without_network_access() -> None:
    """验证检查逻辑只做本地规范化，不访问外网并返回正式域目标。"""
    from app.modules.site_operations.redirects import validate_managed_redirect

    target = validate_managed_redirect(
        source_host="junhuiscrew.com",
        source_path="/legacy-product/",
        target_url="https://junhuiscrewbarrel.com/en/products/",
        existing_rules=[],
        active_paths=set(),
    )
    assert target == "https://junhuiscrewbarrel.com/en/products/"


async def test_brand_and_navigation_real_save_apply_restore_chain(
    site_operations_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证同库品牌及导航均完成保存、fresh read、应用和恢复，英文不被中文覆盖。"""
    from app.modules.site_operations.schemas import BrandDraftUpdate, NavigationDraftUpdate
    from app.modules.site_operations.services import (
        apply_brand,
        apply_navigation,
        get_brand_detail,
        get_navigation_detail,
        initialize_site_operations,
        restore_brand_draft,
        restore_navigation_draft,
        save_brand_draft,
        save_navigation_draft,
    )

    actor_id = await _actor(site_operations_factory)
    async with site_operations_factory() as session:
        initialized = await initialize_site_operations(session, actor_id=actor_id)
        await session.commit()
        assert initialized["brand"]["draft_revision"] == 0

    async with site_operations_factory() as session:
        saved_brand = await save_brand_draft(
            session,
            payload=BrandDraftUpdate.model_validate(
                {
                    "expected_revision": 0,
                    "translations": {
                        "zh-CN": {"display_name": "测试品牌", "short_name": "测试"},
                        "en": {"display_name": "Test Brand", "short_name": "TEST"},
                    },
                    "header_logo_media_id": None,
                    "mobile_logo_media_id": None,
                    "favicon_media_id": None,
                }
            ),
            actor_id=actor_id,
        )
        await session.commit()
        assert saved_brand["draft_revision"] == 1
    async with site_operations_factory() as session:
        reopened = await get_brand_detail(session)
        assert reopened["draft"]["translations"]["en"]["display_name"] == "Test Brand"
        applied = await apply_brand(session, expected_revision=1, actor_id=actor_id)
        assert applied["applied_revision"] == 1
        restored = await restore_brand_draft(session, expected_revision=1, actor_id=actor_id)
        await session.commit()
        assert restored["draft_revision"] == 2

    async with site_operations_factory() as session:
        zh = await get_navigation_detail(session, "zh-CN")
        en_before = await get_navigation_detail(session, "en")
        zh_config = {**zh["draft"], "expected_revision": zh["draft_revision"]}
        zh_config["header_items"][0]["label"] = "测试产品"
        saved = await save_navigation_draft(
            session,
            locale_code="zh-CN",
            payload=NavigationDraftUpdate.model_validate(zh_config),
            actor_id=actor_id,
        )
        await session.commit()
        assert saved["draft"]["header_items"][0]["label"] == "测试产品"
    async with site_operations_factory() as session:
        en_after = await get_navigation_detail(session, "en")
        assert en_after["draft"] == en_before["draft"]
        applied = await apply_navigation(
            session, locale_code="zh-CN", expected_revision=1, actor_id=actor_id
        )
        restored = await restore_navigation_draft(
            session, locale_code="zh-CN", expected_revision=1, actor_id=actor_id
        )
        await session.commit()
        assert applied["applied_revision"] == 1
        assert restored["draft_revision"] == 2


async def test_redirect_real_draft_check_confirm_resolve_and_disable_chain(
    site_operations_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证同库重定向必须检查后启用，真实 resolver 返回3xx数据，停用后立即失效。"""
    from app.modules.discovery.models import RedirectRule
    from app.modules.discovery.services import resolve_redirect
    from app.modules.site_operations.schemas import ManagedRedirectInput
    from app.modules.site_operations.services import (
        check_managed_redirect,
        confirm_managed_redirect,
        create_managed_redirect,
        disable_managed_redirect,
    )

    actor_id = await _actor(site_operations_factory)
    async with site_operations_factory() as session:
        created = await create_managed_redirect(
            session,
            payload=ManagedRedirectInput.model_validate(
                {
                    "source_host": "junhuiscrew.com",
                    "source_path": "/test-only-legacy/",
                    "target_path": "/en/products/",
                    "status_code": 302,
                    "notes": "TEST ONLY",
                }
            ),
            actor_id=actor_id,
        )
        await session.commit()
        assert created["enabled"] is False
        rule_id = uuid.UUID(created["id"])
    async with site_operations_factory() as session:
        checked = await check_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        confirmed = await confirm_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        await session.commit()
        assert checked["workflow_status"] == "checked"
        assert confirmed["enabled"] is True
    async with site_operations_factory() as session:
        resolved = await resolve_redirect(session, "junhuiscrew.com", "/test-only-legacy/")
        await session.commit()
        assert resolved is not None
        assert resolved.target_url == "https://junhuiscrewbarrel.com/en/products/"
        rule = await session.scalar(select(RedirectRule).where(RedirectRule.id == rule_id))
        assert rule is not None and rule.hit_count == 1
    async with site_operations_factory() as session:
        disabled = await disable_managed_redirect(
            session, rule_id=rule_id, expected_revision=0, actor_id=actor_id
        )
        await session.commit()
        assert disabled["enabled"] is False
    async with site_operations_factory() as session:
        assert await resolve_redirect(session, "junhuiscrew.com", "/test-only-legacy/") is None
