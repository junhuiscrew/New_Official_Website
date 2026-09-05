"""Phase 3.5 Final Patch v3 Authority 双重权限回归测试。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.audit.models import AuditLog
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.localization.models import Locale
from app.modules.users import models as _user_models  # noqa: F401
from app.seed import ROLE_PERMISSION_MATRIX


@pytest.fixture
async def authority_v3_factory(sqlite_database_url: str):
    """
    创建 Final Patch v3 Authority 权限测试数据库。

    输入：sqlite_database_url，隔离 SQLite 数据库地址。
    输出：async_sessionmaker，预置中英文启用语言。
    """
    from app.modules.authority import models as _authority_models  # noqa: F401
    from app.modules.discovery import models as _discovery_models  # noqa: F401

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add_all(
            [
                Locale(
                    code="zh-CN",
                    slug="zh-cn",
                    name="Chinese",
                    native_name="中文",
                    is_default=True,
                    is_enabled=True,
                    sort_order=10,
                ),
                Locale(
                    code="en",
                    slug="en",
                    name="English",
                    native_name="English",
                    is_default=False,
                    is_enabled=True,
                    sort_order=20,
                ),
            ]
        )
    yield factory
    await engine.dispose()


async def _create_authority_samples(session: Any) -> tuple[Locale, dict[str, Any]]:
    """
    创建 Case、Knowledge 与可公开真实 Expert 测试样本。

    输入：session，当前异步数据库会话。
    输出：(Locale, dict)，英文语言及按 API 资源名索引的实体。
    """
    from app.modules.authority.schemas import (
        AuthorExpertCreate,
        AuthorityTranslationInput,
        CaseStudyCreate,
        KnowledgeArticleCreate,
        KnowledgeCategoryCreate,
    )
    from app.modules.authority.services import (
        create_author_expert,
        create_case_study,
        create_knowledge_article,
        create_knowledge_category,
    )

    locale = await session.scalar(select(Locale).where(Locale.code == "en"))
    expert = await create_author_expert(
        session,
        AuthorExpertCreate(
            slug="v3-real-expert",
            role_type="author_expert",
            is_real_person_verified=True,
            public_profile_enabled=True,
            translations=[
                AuthorityTranslationInput(
                    locale_id=locale.id,
                    fields={"name": "V3 Real Expert", "short_bio": "Verified engineer."},
                )
            ],
        ),
    )
    category = await create_knowledge_category(
        session,
        KnowledgeCategoryCreate(slug="v3-technical-guides"),
    )
    case = await create_case_study(
        session,
        CaseStudyCreate(
            slug="v3-authority-case",
            translations=[
                AuthorityTranslationInput(
                    locale_id=locale.id,
                    fields={"title": "V3 Authority Case"},
                )
            ],
        ),
    )
    article = await create_knowledge_article(
        session,
        KnowledgeArticleCreate(
            category_id=category.id,
            author_id=expert.id,
            slug="v3-authority-guide",
            translations=[
                AuthorityTranslationInput(
                    locale_id=locale.id,
                    fields={
                        "title": "V3 Authority Guide",
                        "body_markdown": "Visible reviewed technical guidance.",
                    },
                )
            ],
        ),
    )
    await session.commit()
    return locale, {"cases": case, "knowledge": article, "experts": expert}


async def test_authority_publication_targets_require_entity_and_global_permissions(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """四种 Publication 目标必须同时通过实体权限与全局内容权限。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        case = entities["cases"]
        actor = SimpleNamespace(id=uuid.uuid4())
        permissions: set[str] = {"case.review", "translation.review"}
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), permissions),
        )
        await authority_api.review_authority_translation(
            "cases", case.id, locale.id, session, actor, None
        )

        # 实体审核权限不能替代统一 content.review。
        with pytest.raises(AppException) as missing_global_review:
            await authority_api.transition_authority_publication(
                "cases",
                case.id,
                locale.id,
                PublicationStatus.REVIEW,
                session,
                actor,
                None,
            )
        assert missing_global_review.value.status_code == 403

        permissions.add("content.review")
        reviewed = await authority_api.transition_authority_publication(
            "cases",
            case.id,
            locale.id,
            PublicationStatus.REVIEW,
            session,
            actor,
            None,
        )
        assert reviewed.data == {"status": "review"}

        permissions.clear()
        permissions.update({"case.publish", "content.publish"})
        scheduled = await authority_api.transition_authority_publication(
            "cases",
            case.id,
            locale.id,
            PublicationStatus.SCHEDULED,
            session,
            actor,
            None,
        )
        assert scheduled.data == {"status": "scheduled"}
        published = await authority_api.transition_authority_publication(
            "cases",
            case.id,
            locale.id,
            PublicationStatus.PUBLISHED,
            session,
            actor,
            None,
        )
        assert published.data == {"status": "published"}

        permissions.clear()
        permissions.update({"case.archive", "content.archive"})
        archived = await authority_api.transition_authority_publication(
            "cases",
            case.id,
            locale.id,
            PublicationStatus.ARCHIVED,
            session,
            actor,
            None,
        )
        assert archived.data == {"status": "archived"}

        permissions.clear()
        permissions.update({"case.update", "content.update"})
        drafted = await authority_api.transition_authority_publication(
            "cases",
            case.id,
            locale.id,
            PublicationStatus.DRAFT,
            session,
            actor,
            None,
        )
        assert drafted.data == {"status": "draft"}


async def test_editor_update_permissions_cannot_review_or_publish_authority(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor 只有实体/content update 时不能审核或发布 Authority。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        case = entities["cases"]
        editor = SimpleNamespace(id=uuid.uuid4())
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), {"case.update", "content.update"}),
        )

        with pytest.raises(AppException) as review_error:
            await authority_api.transition_authority_publication(
                "cases",
                case.id,
                locale.id,
                PublicationStatus.REVIEW,
                session,
                editor,
                None,
            )
        assert review_error.value.status_code == 403
        with pytest.raises(AppException) as publish_error:
            await authority_api.transition_authority_publication(
                "cases",
                case.id,
                locale.id,
                PublicationStatus.PUBLISHED,
                session,
                editor,
                None,
            )
        assert publish_error.value.status_code == 403


async def test_reviewer_can_review_expert_translation_and_publication(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer 无 expert.update 也能审核 Expert Translation 与 Publication。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        expert = entities["experts"]
        reviewer = SimpleNamespace(id=uuid.uuid4())
        reviewer_permissions = set(ROLE_PERMISSION_MATRIX["reviewer"])
        assert "expert.review" in reviewer_permissions
        assert "expert.update" not in reviewer_permissions
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), reviewer_permissions),
        )

        translation = await authority_api.review_authority_translation(
            "experts", expert.id, locale.id, session, reviewer, None
        )
        assert translation.data == {"status": "human_reviewed"}
        reviewed = await authority_api.transition_authority_publication(
            "experts",
            expert.id,
            locale.id,
            PublicationStatus.REVIEW,
            session,
            reviewer,
            None,
        )
        assert reviewed.data == {"status": "review"}
        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "author_expert",
                TranslationStatus.owner_id == expert.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        assert status_row.reviewed_by == reviewer.id


async def test_expert_translation_review_accepts_machine_state_and_writes_audit(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expert machine translation 可审核且写审计，published 与无权限请求会被拒绝。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        expert = entities["experts"]
        reviewer = SimpleNamespace(id=uuid.uuid4())
        permissions: set[str] = {"expert.review", "translation.review"}
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), permissions),
        )
        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "author_expert",
                TranslationStatus.owner_id == expert.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        status_row.status = "machine_translated"
        await session.commit()

        reviewed = await authority_api.review_authority_translation(
            "experts", expert.id, locale.id, session, reviewer, None
        )
        assert reviewed.data == {"status": "human_reviewed"}
        assert status_row.reviewed_by == reviewer.id
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "translation.review",
                AuditLog.target_type == "author_expert",
                AuditLog.target_id == str(expert.id),
            )
        )
        assert audit is not None and audit.user_id == reviewer.id

        status_row.status = "published"
        await session.commit()
        with pytest.raises(AppException) as published_error:
            await authority_api.review_authority_translation(
                "experts", expert.id, locale.id, session, reviewer, None
            )
        assert published_error.value.status_code == 409

        status_row.status = "draft"
        await session.commit()
        permissions.clear()
        permissions.add("expert.read")
        with pytest.raises(AppException) as permission_error:
            await authority_api.review_authority_translation(
                "experts", expert.id, locale.id, session, reviewer, None
            )
        assert permission_error.value.status_code == 403


async def test_case_knowledge_and_expert_complete_review_publish_regression(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case、Knowledge、Expert 必须分别完成 Translation Review 与内容发布闭环。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        reviewer = SimpleNamespace(id=uuid.uuid4())
        reviewer_permissions = set(ROLE_PERMISSION_MATRIX["reviewer"])
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), reviewer_permissions),
        )

        for resource, entity in entities.items():
            reviewed_translation = await authority_api.review_authority_translation(
                resource, entity.id, locale.id, session, reviewer, None
            )
            assert reviewed_translation.data == {"status": "human_reviewed"}
            reviewed_publication = await authority_api.transition_authority_publication(
                resource,
                entity.id,
                locale.id,
                PublicationStatus.REVIEW,
                session,
                reviewer,
                None,
            )
            assert reviewed_publication.data == {"status": "review"}
            published = await authority_api.transition_authority_publication(
                resource,
                entity.id,
                locale.id,
                PublicationStatus.PUBLISHED,
                session,
                reviewer,
                None,
            )
            assert published.data == {"status": "published"}
            route = await session.scalar(
                select(ContentRoute).where(
                    ContentRoute.owner_id == entity.id,
                    ContentRoute.locale_id == locale.id,
                    ContentRoute.is_canonical.is_(True),
                )
            )
            assert route.active is True and route.indexable is True


async def test_translation_only_actor_cannot_publish_content_publication(
    authority_v3_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Translator 只有 Translation 权限时不能发布 ContentPublication。"""
    from app.api.v1 import authority as authority_api

    async with authority_v3_factory() as session:
        locale, entities = await _create_authority_samples(session)
        case = entities["cases"]
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "case_study",
                ContentPublication.owner_id == case.id,
                ContentPublication.locale_id == locale.id,
            )
        )
        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "case_study",
                TranslationStatus.owner_id == case.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        publication.status = "review"
        status_row.status = "human_reviewed"
        await session.commit()
        translator = SimpleNamespace(id=uuid.uuid4())
        translator_permissions = set(ROLE_PERMISSION_MATRIX["translator"])
        monkeypatch.setattr(
            authority_api,
            "collect_authorization",
            lambda _user: (set(), translator_permissions),
        )

        with pytest.raises(AppException) as publish_error:
            await authority_api.transition_authority_publication(
                "cases",
                case.id,
                locale.id,
                PublicationStatus.PUBLISHED,
                session,
                translator,
                None,
            )
        assert publish_error.value.status_code == 403


def test_reviewer_seed_adds_expert_review_without_update() -> None:
    """Reviewer Seed 必须包含 expert.review，且不得获得 expert.update/create。"""
    reviewer = ROLE_PERMISSION_MATRIX["reviewer"]
    assert {"expert.read", "expert.review", "expert.publish"}.issubset(reviewer)
    assert not {"expert.create", "expert.update"}.intersection(reviewer)
