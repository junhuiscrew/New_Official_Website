"""Phase 3.4 Authority Content 生命周期、关系与隐私服务测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    TranslationStatus,
)
from app.modules.localization.models import Locale
from app.modules.users import models as _user_models  # noqa: F401


@pytest.fixture
async def authority_factory(sqlite_database_url: str):
    """
    创建含中英文语言的隔离 Authority Content 数据库。

    输入：sqlite_database_url，测试数据库地址。
    输出：async_sessionmaker，测试结束后释放引擎。
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
                Locale(code="zh-CN", slug="zh-cn", name="Chinese", native_name="中文", is_default=True, is_enabled=True, sort_order=10),
                Locale(code="en", slug="en", name="English", native_name="English", is_default=False, is_enabled=True, sort_order=20),
            ]
        )
    yield factory
    await engine.dispose()


async def test_case_creation_reuses_translation_publication_route_revision(
    authority_factory,
) -> None:
    """创建有翻译的 Case 必须复用统一生命周期并生成 canonical 路由。"""
    from app.modules.authority.schemas import AuthorityTranslationInput, CaseStudyCreate
    from app.modules.authority.services import create_case_study

    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        case = await create_case_study(
            session,
            CaseStudyCreate(
                slug="anonymous-wear-case",
                client_name="Private Client",
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={"title": "匿名磨损案例", "problem": "螺杆磨损"},
                    )
                ],
            ),
        )
        publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == case.id))
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == case.id))
        revision_count = await session.scalar(select(func.count()).select_from(ContentRevision).where(ContentRevision.owner_id == case.id))
        assert publication is not None and publication.status == "draft"
        assert route is not None and route.path == "/zh-cn/case-studies/anonymous-wear-case/"
        assert route.active is False and route.indexable is False
        assert revision_count == 1


async def test_faq_creation_has_translation_status_but_no_public_route(
    authority_factory,
) -> None:
    """FAQ 必须有翻译状态与修订，但默认不创建独立 Publication/Route。"""
    from app.modules.authority.schemas import AuthorityTranslationInput, FAQCreate
    from app.modules.authority.services import create_faq

    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        faq = await create_faq(
            session,
            FAQCreate(
                translations=[AuthorityTranslationInput(locale_id=locale.id, fields={"question": "如何选型？", "answer": "请根据材料与工艺选型。"})]
            ),
        )
        assert await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_id == faq.id)) is not None
        assert await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == faq.id)) is None
        assert await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == faq.id)) is None


async def test_author_expert_requires_verified_real_person(authority_factory) -> None:
    """Author/Expert 独立公开资料必须先核验真实人物。"""
    from app.modules.authority.schemas import AuthorExpertCreate
    from app.modules.authority.services import create_author_expert

    async with authority_factory() as session, session.begin():
        with pytest.raises(AppException) as exc:
            await create_author_expert(
                session,
                AuthorExpertCreate(
                    slug="invented-expert",
                    role_type="expert",
                    public_profile_enabled=True,
                    is_real_person_verified=False,
                ),
            )
        assert exc.value.code == "verified_person_required"


async def test_knowledge_article_route_uses_category_and_real_author(authority_factory) -> None:
    """Knowledge URL 必须包含稳定 category slug，且作者必须为已核验真人。"""
    from app.modules.authority.schemas import (
        AuthorExpertCreate,
        AuthorityTranslationInput,
        KnowledgeArticleCreate,
        KnowledgeCategoryCreate,
    )
    from app.modules.authority.services import (
        create_author_expert,
        create_knowledge_article,
        create_knowledge_category,
    )

    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        category = await create_knowledge_category(session, KnowledgeCategoryCreate(slug="technical-guides"))
        author = await create_author_expert(
            session,
            AuthorExpertCreate(slug="real-engineer", role_type="author_expert", is_real_person_verified=True),
        )
        article = await create_knowledge_article(
            session,
            KnowledgeArticleCreate(
                category_id=category.id,
                author_id=author.id,
                slug="screw-wear-guide",
                translations=[AuthorityTranslationInput(locale_id=locale.id, fields={"title": "Screw wear guide", "body_markdown": "Visible technical guidance."})],
            ),
        )
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == article.id))
        assert route is not None
        assert route.path == "/en/knowledge/technical-guides/screw-wear-guide/"


async def test_published_authority_translation_edit_withdraws_and_records_revision(
    authority_factory,
) -> None:
    """已发布 Authority 正文修改后必须退出索引并保存新 Revision。"""
    from app.modules.authority.schemas import (
        AuthorityTranslationInput,
        CaseStudyCreate,
        CaseStudyUpdate,
    )
    from app.modules.authority.services import create_case_study, update_case_study

    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        case = await create_case_study(
            session,
            CaseStudyCreate(slug="published-case", translations=[AuthorityTranslationInput(locale_id=locale.id, fields={"title": "原标题"})]),
        )
        publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_id == case.id))
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == case.id))
        status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_id == case.id, TranslationStatus.locale_id == locale.id))
        publication.status = "published"
        status.status = "published"
        route.active = True
        route.indexable = True
        await update_case_study(
            session,
            case.id,
            CaseStudyUpdate(translations=[AuthorityTranslationInput(locale_id=locale.id, fields={"title": "新标题"})]),
        )
        revision_count = await session.scalar(select(func.count()).select_from(ContentRevision).where(ContentRevision.owner_id == case.id))
        assert publication.status == "review"
        assert status.status == "draft"
        assert route.active is False and route.indexable is False
        assert revision_count == 2


async def test_case_private_identity_cannot_enter_seo_or_geo(
    authority_factory,
) -> None:
    """未获公开许可的客户身份不得写入 SEO 或 GEO 文档。"""
    from app.modules.authority.schemas import CaseStudyCreate
    from app.modules.authority.services import create_case_study
    from app.modules.discovery.schemas import GeoDocumentUpsert, SeoDocumentUpsert
    from app.modules.discovery.services import upsert_geo_document, upsert_seo_document

    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        case = await create_case_study(
            session,
            CaseStudyCreate(slug="private-client-case", client_name="绝密客户有限公司"),
        )
        with pytest.raises(AppException) as seo_error:
            await upsert_seo_document(
                session,
                "case_study",
                case.id,
                locale.id,
                SeoDocumentUpsert(seo_title="绝密客户有限公司成功案例"),
                None,
            )
        assert seo_error.value.code == "case_privacy_violation"
        with pytest.raises(AppException) as geo_error:
            await upsert_geo_document(
                session,
                "case_study",
                case.id,
                locale.id,
                GeoDocumentUpsert(
                    direct_answer="绝密客户有限公司采用了本方案。",
                ),
                None,
            )
        assert geo_error.value.code == "case_privacy_violation"


async def test_public_case_dto_and_schema_never_leak_unconsented_identity(
    authority_factory,
) -> None:
    """严格发布后的 Case DTO 与 Schema 也不得泄漏未授权客户身份。"""
    from app.modules.authority.schemas import AuthorityTranslationInput, CaseStudyCreate
    from app.modules.authority.services import create_case_study
    from app.modules.discovery.public_delivery import get_public_case

    secret_name = "Confidential Customer 7842"
    secret_address = "Private Plant Address 19"
    async with authority_factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        case = await create_case_study(
            session,
            CaseStudyCreate(
                slug="anonymous-public-case",
                client_name=secret_name,
                client_address=secret_address,
                client_name_public=False,
                client_address_public=False,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={"title": "Anonymous wear case", "summary": "Published visible facts."},
                    )
                ],
            ),
        )
        publication = await session.scalar(
            select(ContentPublication).where(ContentPublication.owner_id == case.id)
        )
        translation_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_id == case.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_id == case.id,
                ContentRoute.locale_id == locale.id,
            )
        )
        publication.status = "published"
        translation_status.status = "published"
        route.active = True
        route.indexable = True
        await session.flush()

        payload = await get_public_case(session, "en", "anonymous-public-case")
        rendered = repr(payload)
        assert secret_name not in rendered
        assert secret_address not in rendered
        assert "client_name" not in payload and "client_address" not in payload
