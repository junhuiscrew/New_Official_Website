"""Phase 3.4 Remediation 的 GEO、canonical、Expert、关系与 Redirect 回归测试。"""

from __future__ import annotations

import pytest

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException


@pytest.fixture
async def remediation_factory(sqlite_database_url: str):
    """
    创建包含完整 Phase 3.4 元数据的隔离数据库。

    输入：sqlite_database_url，测试专用异步 SQLite URL。
    输出：async_sessionmaker，供行为回归测试创建事务会话。
    """
    from app.modules.audit import models as _audit_models  # noqa: F401
    from app.modules.auth import models as _auth_models  # noqa: F401
    from app.modules.authority import models as _authority_models  # noqa: F401
    from app.modules.catalog import models as _catalog_models  # noqa: F401
    from app.modules.content import models as _content_models  # noqa: F401
    from app.modules.discovery import models as _discovery_models  # noqa: F401
    from app.modules.localization import models as _localization_models  # noqa: F401
    from app.modules.users import models as _user_models  # noqa: F401

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


def test_geo_input_cannot_accept_client_visible_source_text() -> None:
    """
    验证 GEO 写入模型不再暴露客户端可伪造的可见正文参数。

    输入：GeoDocumentUpsert 模型定义。
    输出：None；字段仍存在时失败。
    """
    from app.modules.discovery.schemas import GeoDocumentUpsert

    assert "visible_source_text" not in GeoDocumentUpsert.model_fields


def test_redirect_target_must_be_exact_official_host() -> None:
    """
    验证 www 与旧域只能作为来源，不能作为 Redirect 目标。

    输入：三个候选目标 URL。
    输出：None；非正式非 www 主域目标被接受时失败。
    """
    from app.modules.discovery.redirects import validate_redirect_rule

    for target in (
        "https://www.junhuiscrewbarrel.com/en/new/",
        "https://junhuiscrew.com/en/new/",
        "https://www.junhuiscrew.com/en/new/",
    ):
        with pytest.raises(AppException) as exc:
            validate_redirect_rule("junhuiscrew.com", "/legacy/", target, [])
        assert exc.value.code == "unsafe_redirect_target"

    assert (
        validate_redirect_rule(
            "www.junhuiscrew.com",
            "/legacy/",
            "https://junhuiscrewbarrel.com/en/new/",
            [],
        )
        == "https://junhuiscrewbarrel.com/en/new/"
    )


def test_health_checks_expose_remediation_issue_codes() -> None:
    """
    验证 SEO/GEO 健康检查输出交接文件冻结的稳定问题代码。

    输入：非 self-canonical、断链与缺少证据的最小状态。
    输出：None；任一治理代码缺失时失败。
    """
    from app.modules.discovery.health_checks import geo_health_checks, seo_health_checks

    class Seo:
        seo_title = "Title"
        meta_description = "Description"
        robots_index = True
        canonical_override = "https://junhuiscrewbarrel.com/en/other/"

    seo_codes = {
        item["code"]
        for item in seo_health_checks(
            seo=Seo(),
            canonical_path="/en/current/",
            in_sitemap=False,
            internal_link_count=0,
            has_public_handler=False,
            has_broken_relation_target=True,
        )
    }
    assert {
        "canonical_override_excludes_sitemap",
        "indexable_route_missing_public_handler",
        "missing_internal_links",
        "broken_relation_target",
    }.issubset(seo_codes)

    geo_codes = {
        item["code"]
        for item in geo_health_checks(
            geo=None,
            source_count=0,
            has_first_party_evidence=False,
            claims_match_server_visible_content=False,
            reviewer_verified=False,
        )
    }
    assert {
        "claim_not_in_server_visible_content",
        "reviewer_missing_or_unverified",
        "first_party_evidence_missing",
    }.issubset(geo_codes)


def test_every_sitemap_owner_type_has_a_public_handler_contract() -> None:
    """
    验证 Sitemap 允许的全部实体类型都被公开 API/SSR 交付层承接。

    输入：索引源和公开交付层的 owner type 常量。
    输出：None；任何可索引类型缺少公开 handler 时失败。
    """
    from app.modules.content.services.indexable import INDEXABLE_OWNER_TYPES
    from app.modules.discovery.public_delivery import PUBLIC_HANDLER_OWNER_TYPES

    assert PUBLIC_HANDLER_OWNER_TYPES == INDEXABLE_OWNER_TYPES


@pytest.mark.asyncio
async def test_server_visible_text_supports_product_knowledge_and_expert(
    remediation_factory,
) -> None:
    """
    验证 Product、Knowledge 与 Expert 的 GEO 事实均来自数据库可见字段。

    输入：三个实体及其英文翻译。
    输出：None；任一实体的真实可见字段未被聚合时失败。
    """
    from app.modules.authority.models import (
        AuthorExpert,
        AuthorExpertTranslation,
        KnowledgeArticle,
        KnowledgeArticleTranslation,
        KnowledgeCategory,
    )
    from app.modules.catalog.models import Product, ProductCategory, ProductTranslation
    from app.modules.discovery.services import build_visible_source_text
    from app.modules.localization.models import Locale

    async with remediation_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        product_category = ProductCategory(slug="screws")
        knowledge_category = KnowledgeCategory(slug="guides")
        expert = AuthorExpert(
            slug="engineer",
            role_type="expert",
            is_real_person_verified=True,
            public_profile_enabled=True,
            years_experience=12,
        )
        session.add_all([locale, product_category, knowledge_category, expert])
        await session.flush()
        product = Product(category_id=product_category.id, slug="screw")
        article = KnowledgeArticle(
            category_id=knowledge_category.id, slug="guide", author_id=expert.id
        )
        session.add_all([product, article])
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Screw",
                    description="Visible product fact",
                ),
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=locale.id,
                    title="Guide",
                    summary="Visible article fact",
                    body_markdown="Body evidence",
                ),
                AuthorExpertTranslation(
                    author_expert_id=expert.id,
                    locale_id=locale.id,
                    name="Engineer",
                    short_bio="Visible expert fact",
                    expertise_json=["wear"],
                ),
            ]
        )
        await session.flush()

        assert "Visible product fact" in await build_visible_source_text(
            session, "product", product.id, locale.id
        )
        assert "Visible article fact" in await build_visible_source_text(
            session, "knowledge_article", article.id, locale.id
        )
        assert "Visible expert fact" in await build_visible_source_text(
            session, "author_expert", expert.id, locale.id
        )


@pytest.mark.asyncio
async def test_geo_uses_server_visible_case_content_and_excludes_private_identity(
    remediation_factory,
) -> None:
    """
    验证 GEO 只使用服务端案例正文，且私密客户名称永不进入事实池。

    输入：含公开翻译与未授权客户名称的案例。
    输出：None；伪造声明通过或私密名称进入事实池时失败。
    """
    from app.modules.authority.models import CaseStudy, CaseStudyTranslation
    from app.modules.discovery.schemas import GeoDocumentUpsert
    from app.modules.discovery.services import build_visible_source_text, upsert_geo_document
    from app.modules.localization.models import Locale

    async with remediation_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        case = CaseStudy(slug="anonymous-case", client_name="Private Client Ltd")
        session.add_all([locale, case])
        await session.flush()
        session.add(
            CaseStudyTranslation(
                case_study_id=case.id,
                locale_id=locale.id,
                title="Anonymous wear case",
                summary="Service life improved by 80 percent.",
                result="Evidence case CS-101.",
            )
        )
        await session.flush()

        visible = await build_visible_source_text(session, "case_study", case.id, locale.id)
        assert "Service life improved by 80 percent" in visible
        assert "Private Client Ltd" not in visible

        with pytest.raises(AppException) as hidden_claim:
            await upsert_geo_document(
                session,
                "case_study",
                case.id,
                locale.id,
                GeoDocumentUpsert(direct_answer="Private Client Ltd achieved 300 percent."),
                None,
            )
        assert hidden_claim.value.code == "case_privacy_violation"

        document = await upsert_geo_document(
            session,
            "case_study",
            case.id,
            locale.id,
            GeoDocumentUpsert(
                direct_answer="Service life improved by 80 percent.",
                evidence_json=["Evidence case CS-101"],
            ),
            None,
        )
        assert document.direct_answer == "Service life improved by 80 percent."


@pytest.mark.asyncio
async def test_non_self_canonical_is_excluded_from_sitemap_and_hreflang(
    remediation_factory,
) -> None:
    """
    验证 canonical override 指向其他 URL 时不会进入 Sitemap 或 hreflang。

    输入：已发布、可索引但设置非 self canonical 的案例路由。
    输出：None；路由或 alternate 仍被返回时失败。
    """
    from app.modules.authority.models import CaseStudy, CaseStudyTranslation
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
    from app.modules.content.services.indexable import list_indexable_routes
    from app.modules.discovery.models import SeoDocument
    from app.modules.discovery.public_delivery import _published_alternates
    from app.modules.localization.models import Locale

    async with remediation_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        case = CaseStudy(slug="canonical-case", status="enabled")
        session.add_all([locale, case])
        await session.flush()
        path = "/en/case-studies/canonical-case/"
        session.add_all(
            [
                CaseStudyTranslation(
                    case_study_id=case.id, locale_id=locale.id, title="Canonical case"
                ),
                TranslationStatus(
                    owner_type="case_study",
                    owner_id=case.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="case_study",
                    owner_id=case.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="case_study",
                    owner_id=case.id,
                    locale_id=locale.id,
                    path=path,
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
                SeoDocument(
                    owner_type="case_study",
                    owner_id=case.id,
                    locale_id=locale.id,
                    robots_index=True,
                    canonical_override="https://junhuiscrewbarrel.com/en/case-studies/consolidated/",
                ),
            ]
        )
        await session.flush()

        assert await list_indexable_routes(session) == []
        assert await _published_alternates(session, "case_study", case.id) == {}


@pytest.mark.asyncio
async def test_public_expert_has_person_schema_and_published_article_links(
    remediation_factory,
) -> None:
    """
    验证已核验 Expert 公开 DTO 包含 Person Schema 和真实文章链接。

    输入：严格发布的人物、知识分类和作者文章。
    输出：None；Expert 不可访问或文章关系仍为 UUID 时失败。
    """
    from app.modules.authority.models import (
        AuthorExpert,
        AuthorExpertTranslation,
        KnowledgeArticle,
        KnowledgeArticleTranslation,
        KnowledgeCategory,
    )
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
    from app.modules.discovery.public_delivery import get_public_expert
    from app.modules.localization.models import Locale

    async with remediation_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        expert = AuthorExpert(
            slug="real-expert",
            role_type="author_expert",
            status="enabled",
            is_real_person_verified=True,
            public_profile_enabled=True,
            years_experience=18,
            public_email="engineer@example.net",
        )
        category = KnowledgeCategory(slug="guides", status="enabled")
        session.add_all([locale, expert, category])
        await session.flush()
        article = KnowledgeArticle(
            category_id=category.id, slug="wear-guide", status="enabled", author_id=expert.id
        )
        session.add(article)
        await session.flush()
        session.add_all(
            [
                AuthorExpertTranslation(
                    author_expert_id=expert.id,
                    locale_id=locale.id,
                    name="Real Expert",
                    job_title="Chief Engineer",
                    short_bio="Screw barrel specialist.",
                    expertise_json=["wear analysis"],
                ),
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=locale.id,
                    title="Wear guide",
                    summary="Published guide",
                    body_markdown="Visible guide.",
                ),
            ]
        )
        for owner_type, owner_id, path in (
            ("author_expert", expert.id, "/en/experts/real-expert/"),
            ("knowledge_article", article.id, "/en/knowledge/guides/wear-guide/"),
        ):
            session.add_all(
                [
                    TranslationStatus(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        status="published",
                    ),
                    ContentPublication(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        status="published",
                    ),
                    ContentRoute(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        path=path,
                        is_canonical=True,
                        active=True,
                        indexable=True,
                    ),
                ]
            )
        await session.flush()

        payload = await get_public_expert(session, "en", "real-expert")
        assert payload["schema"][0]["@type"] == "Person"
        assert payload["is_real_person_verified"] is True
        assert payload["public_email"] == "engineer@example.net"
        assert payload["profile_media"] is None
        assert payload["authored_knowledge"] == [
            {
                "type": "knowledge_article",
                "slug": "wear-guide",
                "name": "Wear guide",
                "url": "/en/knowledge/guides/wear-guide/",
                "summary": "Published guide",
            }
        ]


@pytest.mark.asyncio
async def test_product_relations_are_canonical_link_dtos(remediation_factory) -> None:
    """
    验证 Product 关系只返回严格发布 Material 的 canonical Link DTO。

    输入：一个公开产品、一个公开材料和一个未发布材料关系。
    输出：None；DTO 仍为 UUID 或未发布目标泄漏时失败。
    """
    from app.modules.catalog.models import (
        Material,
        MaterialTranslation,
        Product,
        ProductCategory,
        ProductMaterial,
        ProductTranslation,
    )
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
    from app.modules.discovery.public_delivery import get_public_product
    from app.modules.localization.models import Locale

    async with remediation_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        zh_locale = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=False,
            is_enabled=True,
        )
        category = ProductCategory(slug="screws", status="enabled")
        published_material = Material(slug="nitrided-steel", status="enabled")
        draft_material = Material(slug="draft-alloy", status="enabled")
        session.add_all([locale, zh_locale, category, published_material, draft_material])
        await session.flush()
        product = Product(category_id=category.id, slug="extrusion-screw", status="enabled")
        session.add(product)
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Extrusion screw",
                    short_description="Visible product",
                ),
                ProductTranslation(
                    product_id=product.id,
                    locale_id=zh_locale.id,
                    name="挤出螺杆",
                    short_description="公开产品",
                ),
                MaterialTranslation(
                    material_id=published_material.id,
                    locale_id=locale.id,
                    name="Nitrided steel",
                    definition="Wear-resistant material",
                ),
                MaterialTranslation(
                    material_id=draft_material.id, locale_id=locale.id, name="Draft alloy"
                ),
                ProductMaterial(
                    product_id=product.id, material_id=published_material.id, sort_order=1
                ),
                ProductMaterial(product_id=product.id, material_id=draft_material.id, sort_order=2),
            ]
        )
        for owner_type, owner_id, path, status in (
            ("product", product.id, "/en/products/screws/extrusion-screw/", "published"),
            ("material", published_material.id, "/en/materials/nitrided-steel/", "published"),
            ("material", draft_material.id, "/en/materials/draft-alloy/", "draft"),
        ):
            session.add_all(
                [
                    TranslationStatus(
                        owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, status=status
                    ),
                    ContentPublication(
                        owner_type=owner_type, owner_id=owner_id, locale_id=locale.id, status=status
                    ),
                    ContentRoute(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale.id,
                        path=path,
                        is_canonical=True,
                        active=status == "published",
                        indexable=status == "published",
                    ),
                ]
            )
        session.add_all(
            [
                TranslationStatus(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=zh_locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=zh_locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="product",
                    owner_id=product.id,
                    locale_id=zh_locale.id,
                    path="/zh-cn/products/screws/extrusion-screw/",
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
            ]
        )
        await session.flush()

        payload = await get_public_product(session, "en", "screws", "extrusion-screw")
        assert payload["relations"]["materials"] == [
            {
                "type": "material",
                "slug": "nitrided-steel",
                "name": "Nitrided steel",
                "url": "/en/materials/nitrided-steel/",
                "summary": "Wear-resistant material",
            }
        ]
        zh_payload = await get_public_product(
            session, "zh-cn", "screws", "extrusion-screw"
        )
        assert [item["name"] for item in zh_payload["breadcrumb"][:2]] == ["首页", "产品"]
        assert [item["name"] for item in zh_payload["schema"][1]["itemListElement"][:2]] == [
            "首页",
            "产品",
        ]
        assert zh_payload["breadcrumb"][0]["url"] == "https://junhuiscrewbarrel.com/zh-cn/"
