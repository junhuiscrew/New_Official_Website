"""Phase 3.4 隐私、Redirect、GEO、Sitemap 与 Schema 回归测试。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException


def test_case_public_serializer_uses_explicit_privacy_allowlist() -> None:
    """
    验证未授权客户名称、地址和 Logo 不会进入任何公开 DTO。

    输入：包含内部客户数据的案例对象。
    输出：None；出现私密字段或值时失败。
    """
    from app.modules.authority.public import serialize_public_case

    class Case:
        id = "case-id"
        slug = "anonymous-recycling-case"
        country_code = "DE"
        industry = "Recycling"
        machine_brand = "Internal Brand"
        machine_model = "Internal Model"
        screw_diameter = "90mm"
        filler_percentage = "30%"
        featured = False
        primary_media_id = None
        client_name = "Secret Customer GmbH"
        client_address = "Secret Street 1"
        client_logo_media_id = "secret-logo"
        client_name_public = False
        client_address_public = False
        client_logo_public = False

    result = serialize_public_case(Case(), {"title": "匿名客户案例", "problem": "磨损"})
    serialized = repr(result)
    assert "Secret Customer" not in serialized
    assert "Secret Street" not in serialized
    assert "secret-logo" not in serialized
    assert "client_name_public" not in result
    assert result["translation"]["title"] == "匿名客户案例"


def test_case_public_serializer_includes_only_explicitly_approved_identity() -> None:
    """
    验证单项公开许可只放行对应客户字段。

    输入：仅名称获得许可的案例对象。
    输出：None；越权公开其他客户字段时失败。
    """
    from app.modules.authority.public import serialize_public_case

    class Case:
        id = "case-id"
        slug = "approved-name"
        country_code = None
        industry = None
        machine_brand = None
        machine_model = None
        screw_diameter = None
        filler_percentage = None
        featured = False
        primary_media_id = None
        client_name = "Approved Customer"
        client_address = "Private Address"
        client_logo_media_id = "private-logo"
        client_name_public = True
        client_address_public = False
        client_logo_public = False

    result = serialize_public_case(Case(), {"title": "Case"})
    assert result["client_name"] == "Approved Customer"
    assert "client_address" not in result
    assert "client_logo_media_id" not in result


@pytest.mark.parametrize(
    ("source_host", "source_path", "target_url", "error_code"),
    [
        ("junhuiscrewbarrel.com", "/old/", "https://junhuiscrewbarrel.com/old/", "self_redirect"),
        ("junhuiscrewbarrel.com", "/old/", "http://junhuiscrewbarrel.com/new/", "unsafe_redirect_target"),
        ("junhuiscrewbarrel.com", "relative", "https://junhuiscrewbarrel.com/new/", "invalid_redirect_path"),
        ("junhuiscrewbarrel.com", "/old/", "javascript:alert(1)", "unsafe_redirect_target"),
    ],
)
def test_redirect_validation_rejects_unsafe_rules(
    source_host: str,
    source_path: str,
    target_url: str,
    error_code: str,
) -> None:
    """
    验证 Redirect Manager 拒绝自跳转和不安全目标。

    输入：来源 host/path、目标 URL 与期望错误码。
    输出：None；未拒绝错误规则时失败。
    """
    from app.modules.discovery.redirects import validate_redirect_rule

    with pytest.raises(AppException) as exc:
        validate_redirect_rule(source_host, source_path, target_url, [])
    assert exc.value.code == error_code


def test_redirect_validation_rejects_duplicate_chain_and_loop() -> None:
    """
    验证 Redirect Manager 拒绝重复来源、链式跳转和循环。

    输入：现有规则图。
    输出：None；危险图被接受时失败。
    """
    from app.modules.discovery.redirects import RedirectEdge, validate_redirect_rule

    rules = [
        RedirectEdge("junhuiscrewbarrel.com", "/legacy/", "https://junhuiscrewbarrel.com/final/"),
        RedirectEdge("junhuiscrewbarrel.com", "/next/", "https://junhuiscrewbarrel.com/legacy/"),
    ]
    with pytest.raises(AppException) as duplicate:
        validate_redirect_rule(
            "junhuiscrewbarrel.com",
            "/legacy/",
            "https://junhuiscrewbarrel.com/new/",
            rules,
        )
    assert duplicate.value.code == "duplicate_redirect"
    with pytest.raises(AppException) as chain:
        validate_redirect_rule(
            "junhuiscrewbarrel.com",
            "/old/",
            "https://junhuiscrewbarrel.com/legacy/",
            rules,
        )
    assert chain.value.code == "redirect_chain"
    with pytest.raises(AppException) as loop:
        validate_redirect_rule(
            "junhuiscrewbarrel.com",
            "/final/",
            "https://junhuiscrewbarrel.com/next/",
            rules,
        )
    assert loop.value.code == "redirect_loop"


def test_old_domain_redirect_to_official_domain_is_supported() -> None:
    """
    验证未来旧域名向正式主域名迁移的直接规则有效。

    输入：junhuiscrew.com 旧路径与正式域名目标。
    输出：None；合法规则被拒绝时失败。
    """
    from app.modules.discovery.redirects import validate_redirect_rule

    validate_redirect_rule(
        "junhuiscrew.com",
        "/products/old-screw/",
        "https://junhuiscrewbarrel.com/en/products/extrusion-screw/",
        [],
    )


@pytest.mark.asyncio
async def test_redirect_resolution_is_exact_and_counts_hits(sqlite_database_url: str) -> None:
    """启用规则必须精确匹配 host/path，并在命中后更新统计。"""
    from app.modules.audit import models as _audit_models  # noqa: F401
    from app.modules.auth import models as _auth_models  # noqa: F401
    from app.modules.authority import models as _authority_models  # noqa: F401
    from app.modules.catalog import models as _catalog_models  # noqa: F401
    from app.modules.discovery.models import RedirectRule
    from app.modules.discovery.services import resolve_redirect
    from app.modules.localization import models as _localization_models  # noqa: F401
    from app.modules.users import models as _user_models  # noqa: F401

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        rule = RedirectRule(
            source_host="junhuiscrew.com",
            source_path="/old/",
            target_url="https://junhuiscrewbarrel.com/en/new/",
            status_code=301,
        )
        session.add(rule)
        await session.flush()
        assert await resolve_redirect(session, "JUNHUISCREW.COM.", "/missing/") is None
        matched = await resolve_redirect(session, "JUNHUISCREW.COM.", "/old/")
        assert matched is not None
        assert matched.hit_count == 1 and matched.last_hit_at is not None
    await engine.dispose()


def test_geo_document_rejects_hidden_ai_only_claims() -> None:
    """
    验证 GEO 关键事实与证据必须能在用户可见内容中逐项找到。

    输入：GEO 字段与页面可见事实文本。
    输出：None；隐藏事实被接受时失败。
    """
    from app.modules.discovery.geo import validate_geo_visibility

    with pytest.raises(AppException) as exc:
        validate_geo_visibility(
            direct_answer="该方案可减少磨损。",
            key_facts=["寿命提升 300%"],
            evidence=["实验室编号 X-999"],
            visible_text="该方案可减少磨损。现场测试显示寿命提升 80%。",
        )
    assert exc.value.code == "geo_claim_not_visible"


def test_geo_document_accepts_visible_claims() -> None:
    """
    验证正文可见的直接答案、关键事实和证据可以保存。

    输入：完全可见且一致的 GEO 字段。
    输出：None；合法内容被拒绝时失败。
    """
    from app.modules.discovery.geo import validate_geo_visibility

    visible = "该方案可减少磨损。现场测试显示寿命提升 80%。证据为案例 CS-101。"
    validate_geo_visibility(
        direct_answer="该方案可减少磨损。",
        key_facts=["寿命提升 80%"],
        evidence=["案例 CS-101"],
        visible_text=visible,
    )


def test_schema_generator_never_invents_commercial_or_reputation_data() -> None:
    """
    验证 Product Schema 不会生成虚构价格、Offer、Review 或 Rating。

    输入：没有商业与评价事实的产品公共 DTO。
    输出：None；Schema 出现禁用字段时失败。
    """
    from app.modules.discovery.schema_generator import build_product_schema

    schema = build_product_schema(
        {
            "name": "Extrusion Screw",
            "description": "Industrial screw barrel component.",
            "url": "https://junhuiscrewbarrel.com/en/products/extrusion-screw/",
        }
    )
    rendered = repr(schema).lower()
    for forbidden in ("offers", "price", "review", "rating"):
        assert forbidden not in rendered


def test_schema_override_rejects_fake_offer_review_and_rating() -> None:
    """统一 Schema override 必须拒绝伪造商业和评价字段。"""
    from app.modules.discovery.services import validate_schema_override

    for payload in (
        {"offers": {"price": "1"}},
        {"review": {"author": "Fake"}},
        {"aggregateRating": {"ratingValue": 5}},
    ):
        with pytest.raises(AppException) as exc:
            validate_schema_override(payload)
        assert exc.value.code == "unsafe_schema_override"


def test_article_and_person_schema_require_verified_real_people() -> None:
    """
    验证 Article/Person Schema 只接受已核验的真实作者专家。

    输入：未核验人物。
    输出：None；虚构人物进入 Schema 时失败。
    """
    from app.modules.discovery.schema_generator import build_article_schema, build_person_schema

    person = {"name": "AI Expert", "is_real_person_verified": False}
    with pytest.raises(AppException, match="真实人物"):
        build_person_schema(person)
    with pytest.raises(AppException, match="真实作者"):
        build_article_schema(
            {"headline": "Guide", "url": "https://junhuiscrewbarrel.com/en/knowledge/guide/"},
            person,
        )


def test_website_video_and_faq_schema_use_only_supplied_public_facts() -> None:
    """WebSite、VideoObject 与受控 FAQPage 只能使用明确提供的公开事实。"""
    from app.modules.discovery.schema_generator import (
        build_faq_schema,
        build_video_schema,
        build_website_schema,
    )

    website = build_website_schema()
    video = build_video_schema(
        {
            "name": "Screw barrel inspection",
            "thumbnail_url": "https://junhuiscrewbarrel.com/media/inspection.jpg",
            "upload_date": "2026-09-04",
            "content_url": "https://junhuiscrewbarrel.com/media/inspection.mp4",
        }
    )
    faq_items = [{"question": "What is inspected?", "answer": "Visible wear surfaces."}]
    assert website["@type"] == "WebSite"
    assert video["@type"] == "VideoObject"
    assert build_faq_schema(faq_items, enabled=False) is None
    assert build_faq_schema(faq_items, enabled=True)["@type"] == "FAQPage"


def test_sitemap_uses_real_lastmod_and_absolute_canonical_urls() -> None:
    """
    验证 Sitemap 仅渲染绝对正式 URL 与真实更新时间。

    输入：可索引路由项。
    输出：None；lastmod 被替换为当前时间或 URL 非正式域名时失败。
    """
    from app.modules.discovery.sitemap import SitemapEntry, render_sitemap

    changed_at = datetime(2025, 6, 1, 8, 30, tzinfo=UTC)
    xml = render_sitemap([SitemapEntry("/en/knowledge/technical-guides/screw-wear/", changed_at)])
    assert "https://junhuiscrewbarrel.com/en/knowledge/technical-guides/screw-wear/" in xml
    assert "2025-06-01T08:30:00+00:00" in xml


@pytest.mark.asyncio
async def test_indexable_authority_route_respects_seo_robots_index(
    sqlite_database_url: str,
) -> None:
    """
    验证 Authority Route 除七项公开门槛外还必须尊重 SEO robots_index。

    输入：sqlite_database_url，隔离数据库。
    输出：None；robots_index=false 时仍进入索引源则失败。
    """
    from app.modules.audit import models as _audit_models  # noqa: F401
    from app.modules.auth import models as _auth_models  # noqa: F401
    from app.modules.authority.models import CaseStudy, CaseStudyTranslation
    from app.modules.catalog import models as _catalog_models  # noqa: F401
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
    from app.modules.content.services.indexable import list_indexable_routes
    from app.modules.discovery.models import SeoDocument
    from app.modules.localization.models import Locale
    from app.modules.users import models as _user_models  # noqa: F401

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        locale = Locale(code="en", slug="en", name="English", native_name="English", is_default=True, is_enabled=True)
        case = CaseStudy(slug="published-case", status="enabled")
        session.add_all([locale, case])
        await session.flush()
        session.add_all(
            [
                CaseStudyTranslation(case_study_id=case.id, locale_id=locale.id, title="Published case"),
                TranslationStatus(owner_type="case_study", owner_id=case.id, locale_id=locale.id, status="published"),
                ContentPublication(owner_type="case_study", owner_id=case.id, locale_id=locale.id, status="published"),
                ContentRoute(owner_type="case_study", owner_id=case.id, locale_id=locale.id, path="/en/case-studies/published-case/", is_canonical=True, active=True, indexable=True),
                SeoDocument(owner_type="case_study", owner_id=case.id, locale_id=locale.id, robots_index=False),
            ]
        )
        await session.flush()
        assert await list_indexable_routes(session) == []
        seo = await session.scalar(select(SeoDocument).where(SeoDocument.owner_id == case.id))
        seo.robots_index = True
        await session.flush()
        assert [route.path for route in await list_indexable_routes(session)] == [
            "/en/case-studies/published-case/"
        ]
    await engine.dispose()
