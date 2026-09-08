"""Privacy P1 PostgreSQL 迁移、触发器、外键与真实锁竞争测试。"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.database import create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.content.models import ContentRoute, SitePage
from app.modules.privacy.models import (
    PrivacyNoticeVersion,
    PrivacyNoticeVersionTranslation,
    PrivacyPageState,
)
from app.modules.privacy.schemas import PrivacyDraftUpdate, PrivacyTranslationUpdate
from app.modules.privacy.services import (
    create_privacy_context_token,
    create_privacy_draft,
    get_privacy_admin_state,
    get_public_privacy_policy,
    initialize_privacy_page,
    publish_privacy_draft,
    review_privacy_translation,
    update_privacy_draft,
)
from app.modules.rfq.models import RFQ, RFQItem
from app.modules.rfq.schemas import RFQCreate
from app.modules.rfq.services import create_rfq
from app.modules.users.models import Permission, Role, RolePermission, User
from app.seed import seed_database

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要独立 Docker PostgreSQL 测试库"),
]


def _validated_test_database_url() -> str:
    """
    在建立连接前校验 PostgreSQL 目标只能是显式隔离测试库。

    输入：APP_ENV、PRIVACY_P1_TEST_ONLY 与 TEST_DATABASE_URL 环境变量。
    输出：str，已确认 host/database 均带 test 标识且不含主试点名称的连接串。
    """
    assert os.getenv("APP_ENV") == "test", "Privacy P1 PostgreSQL 测试要求 APP_ENV=test"
    assert os.getenv("PRIVACY_P1_TEST_ONLY") == "1", (
        "Privacy P1 PostgreSQL 测试要求 PRIVACY_P1_TEST_ONLY=1"
    )
    assert TEST_DATABASE_URL, "缺少 TEST_DATABASE_URL"
    target = make_url(TEST_DATABASE_URL)
    host = (target.host or "").lower()
    database = (target.database or "").lower()
    assert "test" in host and "test" in database, "PostgreSQL host/database 必须明确命名为 test"
    assert "junhui-phase37-pilot" not in TEST_DATABASE_URL.lower(), "禁止连接主试点数据库"
    return TEST_DATABASE_URL


async def _create_test_reviewer(session, prefix: str) -> User:
    """
    创建具有真实数据库 ID 的 TEST ONLY 审核用户。

    输入：session 与邮箱前缀。
    输出：User，可作为审核/发布操作的真实 actor，不伪造系统用户。
    """
    reviewer = User(
        email=f"{prefix}-{uuid.uuid4().hex}@example.test",
        password_hash="test-only-not-used",
        display_name="Privacy PostgreSQL TEST ONLY reviewer",
        is_active=True,
    )
    session.add(reviewer)
    await session.flush()
    return reviewer


async def _review_current(session, locale: str, actor_id: uuid.UUID) -> PrivacyNoticeVersion:
    """
    以 fresh 管理状态构造 PostgreSQL 审核观察值。

    输入：session、locale 与真实审核用户 ID。
    输出：PrivacyNoticeVersion，完成目标语言审核后的版本。
    """
    state = await get_privacy_admin_state(session)
    draft = state["draft"]
    assert draft is not None
    return await review_privacy_translation(
        session,
        locale=locale,
        actor_id=actor_id,
        expected_version_label=draft["version_label"],
        expected_revision=draft["revision"],
        expected_content_hash=draft["translations"][locale]["content_hash"],
    )


async def _publish_current(session, actor_id: uuid.UUID) -> PrivacyNoticeVersion:
    """
    以 fresh 管理状态构造 PostgreSQL 双语发布观察值。

    输入：session 与真实发布用户 ID。
    输出：PrivacyNoticeVersion，原子切换后的当前版本。
    """
    state = await get_privacy_admin_state(session)
    draft = state["draft"]
    assert draft is not None
    return await publish_privacy_draft(
        session,
        actor_id=actor_id,
        expected_version_label=draft["version_label"],
        expected_revision=draft["revision"],
        expected_content_hashes={
            locale: draft["translations"][locale]["content_hash"]
            for locale in ("zh-CN", "en")
        },
    )


async def _create_ready_draft(session, reviewer_id: uuid.UUID, marker: str) -> PrivacyNoticeVersion:
    """
    创建具有显式生效时间、完整双语正文和真实审核记录的待发布草稿。

    输入：session、reviewer_id 与区分正文的 marker。
    输出：PrivacyNoticeVersion，可由发布竞争测试直接切换的草稿。
    """
    version = await create_privacy_draft(session, actor_id=reviewer_id)
    state = await get_privacy_admin_state(session)
    await update_privacy_draft(
        session,
        PrivacyDraftUpdate(
            expected_revision=state["draft"]["revision"],
            effective_at=datetime.now(UTC) - timedelta(seconds=1),
            translations=[
                PrivacyTranslationUpdate(
                    locale="zh-CN", title=f"隐私政策 {marker}", body_markdown=f"正文 {marker}"
                ),
                PrivacyTranslationUpdate(
                    locale="en", title=f"Privacy {marker}", body_markdown=f"Body {marker}"
                ),
            ],
        ),
        actor_id=reviewer_id,
    )
    await _review_current(session, "zh-CN", reviewer_id)
    await _review_current(session, "en", reviewer_id)
    return version


def _rfq_payload(token: str, email: str) -> RFQCreate:
    """
    构造带合法 item 的 TEST ONLY RFQ。

    输入：当前政策 token 与唯一邮箱。
    输出：RFQCreate，用于验证 RFQ 和 RFQItem 的同事务结果。
    """
    return RFQCreate(
        company_name="Privacy race TEST ONLY",
        contact_name="Lee",
        email=email,
        message="Test-only race submission",
        consent_privacy=True,
        preferred_language="en",
        privacy_context_token=token,
        items=[
            {
                "item_type": "custom",
                "product_name_text": "Test-only screw component",
                "quantity": "1",
            }
        ],
    )


async def test_postgresql_migration_then_central_seed_contract_is_ready() -> None:
    """
    验证 test profile 的空库迁移→当前线性 head 且 Privacy 权限最小。

    输入：经安全门确认的独立 PostgreSQL 测试库。
    输出：None；迁移未到 head、seed 不幂等或角色越权时失败。
    """
    engine = create_database_engine(_validated_test_database_url())
    factory = create_session_factory(engine)
    await seed_database(factory)
    await seed_database(factory)
    expected = {
        "super_admin": 5,
        "content_admin": 5,
        "editor": 2,
        "translator": 2,
        "reviewer": 4,
        "sales": 0,
        "seo_manager": 0,
    }
    async with factory() as session:
        assert await session.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260908_0014"
        )
        assert await session.scalar(text("SELECT to_regclass('privacy_notice_versions')")) == (
            "privacy_notice_versions"
        )
        for role_name, expected_count in expected.items():
            count = await session.scalar(
                select(func.count())
                .select_from(RolePermission)
                .join(Role, Role.id == RolePermission.role_id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(Role.name == role_name, Permission.code.like("privacy.%"))
            )
            assert count == expected_count
    await engine.dispose()


async def test_postgresql_translation_status_requires_legal_review_transition() -> None:
    """
    验证数据库拒绝无审核者的人工审核和 draft 直接发布。

    输入：经安全门确认的独立 PostgreSQL 测试库。
    输出：None；非法状态迁移能够绕过服务层时失败。
    """
    engine = create_database_engine(_validated_test_database_url())
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        reviewer = await _create_test_reviewer(session, "privacy-pg-transition")
        await initialize_privacy_page(session, actor_id=reviewer.id)
        version = await create_privacy_draft(session, actor_id=reviewer.id)
        status_id = await session.scalar(
            text(
                "SELECT id FROM translation_statuses "
                "WHERE owner_type = 'privacy_notice_version' AND owner_id = :version_id "
                "ORDER BY created_at LIMIT 1"
            ),
            {"version_id": version.id},
        )
        assert status_id is not None

        with pytest.raises(DBAPIError) as missing_reviewer:
            async with session.begin_nested():
                await session.execute(
                    text(
                        "UPDATE translation_statuses "
                        "SET status = 'human_reviewed', reviewed_by = NULL WHERE id = :status_id"
                    ),
                    {"status_id": status_id},
                )
        assert "privacy_translation_reviewer_required" in str(missing_reviewer.value)

        with pytest.raises(DBAPIError) as skipped_review:
            async with session.begin_nested():
                await session.execute(
                    text(
                        "UPDATE translation_statuses "
                        "SET status = 'published', reviewed_by = :reviewer_id, "
                        "published_at = CURRENT_TIMESTAMP WHERE id = :status_id"
                    ),
                    {"status_id": status_id, "reviewer_id": reviewer.id},
                )
        assert "privacy_translation_status_transition_invalid" in str(skipped_review.value)
        # 该约束测试不向同一测试库留下可编辑草稿，避免影响后续发布竞争用例。
        await session.rollback()
    await engine.dispose()


async def test_postgresql_privacy_immutability_and_rfq_restrict_are_independent() -> None:
    """
    验证 published 正文不可覆盖，并独立实证 RFQ FK RESTRICT。

    输入：经安全门确认的独立 PostgreSQL 测试库。
    输出：None；触发器失效或 RFQ 引用版本可删除时失败。
    """
    engine = create_database_engine(_validated_test_database_url())
    factory = create_session_factory(engine)
    marker = datetime.now(UTC).isoformat()
    async with factory() as session, session.begin():
        reviewer = await _create_test_reviewer(session, "privacy-pg-immutable")
        page = await initialize_privacy_page(session, actor_id=reviewer.id)
        version = await _create_ready_draft(session, reviewer.id, marker)
        await _publish_current(session, reviewer.id)
        page_id, version_id = page.id, version.id

        latest_number = await session.scalar(
            select(func.max(PrivacyNoticeVersion.version_no)).where(
                PrivacyNoticeVersion.site_page_id == page.id
            )
        )
        referenced_version = PrivacyNoticeVersion(
            site_page_id=page.id,
            version_no=(latest_number or 0) + 1,
            version_label=f"PRIVACY-FK-{uuid.uuid4().hex[:12].upper()}",
            effective_at=None,
            row_version=1,
            created_by=reviewer.id,
        )
        session.add(referenced_version)
        await session.flush()
        referenced_rfq = RFQ(
            public_reference=f"RFQ-FK-{uuid.uuid4().hex[:12].upper()}",
            company_name="FK TEST ONLY",
            contact_name="Lee",
            email=f"rfq-fk-{uuid.uuid4().hex}@example.test",
            consent_privacy=True,
            privacy_notice_version_id=referenced_version.id,
            privacy_version_label=referenced_version.version_label,
            privacy_policy_locale="en",
            privacy_content_hash="f" * 64,
            privacy_canonical_url="https://junhuiscrewbarrel.com/en/privacy/",
            privacy_confirmed_at=datetime.now(UTC),
        )
        session.add(referenced_rfq)
        await session.flush()
        referenced_version_id = referenced_version.id

    async with factory() as session:
        translation = await session.scalar(
            select(PrivacyNoticeVersionTranslation).where(
                PrivacyNoticeVersionTranslation.privacy_notice_version_id == version_id
            )
        )
        assert translation is not None
        translation.title = "不可覆盖"
        with pytest.raises((DBAPIError, IntegrityError)):
            await session.commit()
        await session.rollback()

    async with factory() as session:
        # TEST ONLY：事务内暂时关闭不可变触发器，确保失败来源确为 RFQ RESTRICT FK。
        await session.execute(
            text(
                "ALTER TABLE privacy_notice_versions "
                "DISABLE TRIGGER trg_privacy_notice_version_immutable"
            )
        )
        with pytest.raises(IntegrityError) as restricted:
            await session.execute(
                text("DELETE FROM privacy_notice_versions WHERE id = :version_id"),
                {"version_id": referenced_version_id},
            )
            await session.commit()
        assert "fk_rfqs_privacy_notice_version_id_privacy_notice_versions" in str(
            restricted.value
        )
        await session.rollback()
        assert await session.get(SitePage, page_id) is not None
    await engine.dispose()


async def test_postgresql_rfq_and_publish_real_races_cover_both_winners() -> None:
    """
    验证不手工预锁时 RFQ 先赢记录 A，发布先赢则 A stale 且零新增。

    输入：经安全门确认的独立 PostgreSQL 测试库。
    输出：None；出现版本错配、半条 RFQ/Item 或锁顺序不一致时失败。
    """
    engine = create_database_engine(_validated_test_database_url())
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        reviewer = await _create_test_reviewer(session, "privacy-pg-race")
        reviewer_id = reviewer.id
        await initialize_privacy_page(session, actor_id=reviewer_id)
        state = await session.scalar(select(PrivacyPageState))
        assert state is not None
        if state.current_version_id is None:
            await _create_ready_draft(session, reviewer_id, "race-A")
            await _publish_current(session, reviewer_id)
        policy_a = await get_public_privacy_policy(session, "en")
        token_a = create_privacy_context_token(policy_a)
        await _create_ready_draft(session, reviewer_id, "race-B")

    publish_started = asyncio.Event()

    async def publish_ready_draft() -> str:
        """输入无；输出业务发布自然取得锁后切换的版本标签。"""
        publish_started.set()
        async with factory() as session, session.begin():
            version = await _publish_current(session, reviewer_id)
            return version.version_label

    # A 先赢：create_rfq 自然持有锁，发布必须等待其事务提交。
    async with factory() as rfq_session:
        rfq_transaction = await rfq_session.begin()
        created = await create_rfq(
            rfq_session,
            _rfq_payload(token_a, f"race-a-{uuid.uuid4().hex}@example.com"),
            ip="198.51.100.11",
            user_agent="pg-race-test",
        )
        reference_a = created.public_reference
        publish_task = asyncio.create_task(publish_ready_draft())
        await publish_started.wait()
        await asyncio.sleep(0.1)
        assert not publish_task.done()
        await rfq_transaction.commit()
    version_b_label = await asyncio.wait_for(publish_task, timeout=10)

    async with factory() as session:
        stored = await session.scalar(select(RFQ).where(RFQ.public_reference == reference_a))
        assert stored is not None
        assert stored.privacy_version_label == policy_a["version_label"]
        assert stored.privacy_version_label != version_b_label
        assert await session.scalar(
            select(func.count()).select_from(RFQItem).where(RFQItem.rfq_id == stored.id)
        ) == 1

    # B 先赢：发布业务自然持锁，旧 token A 解锁后必须 stale 且没有半条数据。
    async with factory() as session, session.begin():
        policy_before_switch = await get_public_privacy_policy(session, "en")
        stale_after_switch_token = create_privacy_context_token(policy_before_switch)
        await _create_ready_draft(session, reviewer_id, "race-next-B")
    async with factory() as count_session:
        before_rfqs = await count_session.scalar(select(func.count()).select_from(RFQ))
        before_items = await count_session.scalar(select(func.count()).select_from(RFQItem))

    async def submit_stale_after_publish() -> None:
        """输入无；发布提交后尝试旧 token，输出 None 或抛出 stale。"""
        async with factory() as session, session.begin():
            await create_rfq(
                session,
                _rfq_payload(
                    stale_after_switch_token,
                    f"race-stale-{uuid.uuid4().hex}@example.com",
                ),
                ip="198.51.100.12",
                user_agent="pg-race-test",
            )

    async with factory() as publish_session:
        publish_transaction = await publish_session.begin()
        switched = await _publish_current(publish_session, reviewer_id)
        assert switched.version_label != policy_before_switch["version_label"]
        stale_task = asyncio.create_task(submit_stale_after_publish())
        await asyncio.sleep(0.1)
        assert not stale_task.done()
        await publish_transaction.commit()
    with pytest.raises(AppException) as stale:
        await asyncio.wait_for(stale_task, timeout=10)
    assert stale.value.code == "privacy_context_stale"

    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(RFQ)) == before_rfqs
        assert await session.scalar(select(func.count()).select_from(RFQItem)) == before_items
        privacy_routes = list(
            (
                await session.scalars(
                    select(ContentRoute)
                    .join(SitePage, SitePage.id == ContentRoute.owner_id)
                    .where(SitePage.system_key == "privacy")
                )
            ).all()
        )
        assert all(route.active and not route.indexable for route in privacy_routes)
    await engine.dispose()
