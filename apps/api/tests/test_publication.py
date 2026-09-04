"""Publication/Translation/Route 单事务状态机测试。"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit.models import AuditLog
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.localization.models import Locale
from app.modules.users import models as user_models  # noqa: F401


@pytest.fixture
async def publication_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建发布状态机隔离数据库并写入英文 Locale。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add(
            Locale(
                code="en",
                slug="en",
                name="English",
                native_name="English",
                is_default=True,
                is_enabled=True,
            )
        )
    yield factory
    await engine.dispose()


async def _publication_records(
    session: AsyncSession,
) -> tuple[ContentPublication, TranslationStatus, ContentRoute]:
    """创建同一 owner/locale 的发布、翻译和非公开路由记录。"""
    locale = await session.scalar(select(Locale).where(Locale.code == "en"))
    owner_id = uuid.uuid4()
    publication = ContentPublication(
        owner_type="page", owner_id=owner_id, locale_id=locale.id, status="draft"
    )
    translation = TranslationStatus(
        owner_type="page",
        owner_id=owner_id,
        locale_id=locale.id,
        source_locale_id=locale.id,
        status="human_reviewed",
    )
    route = ContentRoute(
        owner_type="page",
        owner_id=owner_id,
        locale_id=locale.id,
        path="/en/about-junhui/",
        is_canonical=True,
        active=False,
        indexable=False,
    )
    session.add_all([publication, translation, route])
    await session.flush()
    return publication, translation, route


async def test_publish_updates_content_translation_route_and_audit_together(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 review→published 在同一事务同步公开四类状态。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.REVIEW,
            actor_permissions={"content.update"},
            actor_id=None,
            ip="203.0.113.24",
            user_agent="phase32-publication-test",
        )
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.PUBLISHED,
            actor_permissions={"content.publish"},
            actor_id=None,
            ip="203.0.113.24",
            user_agent="phase32-publication-test",
        )

    async with publication_session_factory() as session:
        stored_publication = await session.get(ContentPublication, publication.id)
        stored_translation = await session.get(TranslationStatus, translation.id)
        stored_route = await session.get(ContentRoute, route.id)
        actions = (
            await session.scalars(select(AuditLog.action).order_by(AuditLog.created_at))
        ).all()
        audit_contexts = (
            await session.execute(
                select(AuditLog.ip, AuditLog.user_agent).order_by(AuditLog.created_at)
            )
        ).all()

    assert stored_publication.status == "published"
    assert stored_translation.status == "published"
    assert stored_route.active is True
    assert stored_route.indexable is True
    assert actions == ["publication.status_change", "route.change"] * 2
    assert audit_contexts == [("203.0.113.24", "phase32-publication-test")] * 4


async def test_translator_cannot_bypass_reviewer_to_publish(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证只有翻译权限的用户不能执行最终发布。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        publication.status = "review"
        with pytest.raises(AppException) as raised:
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions={"translation.update", "translation.review"},
                actor_id=None,
            )
    assert raised.value.status_code == 403


async def test_archive_removes_route_from_public_and_indexable_state(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 archived 内容不会继续暴露公开或可索引路由。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        publication.status = "published"
        translation.status = "published"
        route.active = True
        route.indexable = True
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.ARCHIVED,
            actor_permissions={"content.archive"},
            actor_id=None,
        )
    assert publication.status == "archived"
    assert route.active is False
    assert route.indexable is False


async def test_publication_rejects_mismatched_owner_without_mutation(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证不同 owner 的发布记录不能被拼接成一次发布事务。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        publication.status = "review"
        route.owner_id = uuid.uuid4()
        with pytest.raises(AppException) as raised:
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions={"content.publish"},
                actor_id=None,
            )
        assert publication.status == "review"
        assert translation.status == "human_reviewed"
        assert route.active is False
        assert route.indexable is False
    assert raised.value.code == "publication_owner_mismatch"


async def test_disabled_locale_cannot_be_published(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证已禁用 Locale 不能进入 published 状态。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        publication.status = "review"
        locale = await session.get(Locale, publication.locale_id)
        assert locale is not None
        locale.is_enabled = False
        with pytest.raises(AppException) as raised:
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions={"content.publish"},
                actor_id=None,
            )
        assert publication.status == "review"
        assert route.active is False
    assert raised.value.code == "locale_disabled"


async def test_noncanonical_route_cannot_be_published(
    publication_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 redirect/历史等非 canonical route 不能被标记为公开可索引。"""
    async with publication_session_factory() as session, session.begin():
        publication, translation, route = await _publication_records(session)
        publication.status = "review"
        route.is_canonical = False
        with pytest.raises(AppException) as raised:
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions={"content.publish"},
                actor_id=None,
            )
        assert route.active is False and route.indexable is False
    assert raised.value.code == "canonical_route_required"
