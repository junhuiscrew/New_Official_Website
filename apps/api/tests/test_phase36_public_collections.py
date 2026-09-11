"""Phase 3.6 导航与首页公开聚合接口回归测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.database import (
    Base,
    create_database_engine,
    create_session_factory,
    get_session,
)
from app.core.exceptions.handlers import AppException
from app.main import create_app
from app.modules.authority.models import (
    ArticleApplication,
    ArticleMaterial,
    ArticleSolution,
    ArticleTechnology,
    AuthorExpert,
    AuthorExpertTranslation,
    CaseApplication,
    CaseMaterial,
    CaseSolution,
    CaseStudy,
    CaseStudyTranslation,
    CaseTechnology,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
    KnowledgeCategory,
    KnowledgeCategoryTranslation,
)
from app.modules.catalog.models import (
    Application,
    ApplicationSolution,
    ApplicationTranslation,
    Material,
    MaterialSolution,
    MaterialTechnology,
    MaterialTranslation,
    Product,
    ProductApplication,
    ProductCategory,
    ProductCategoryTranslation,
    ProductMaterial,
    ProductSolution,
    ProductTechnology,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.company.models import (
    CompanyProfile,
    CompanyProfileTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.content.models import (
    ContentPublication,
    ContentRoute,
    SitePage,
    SitePageTranslation,
    TranslationStatus,
)
from app.modules.discovery.models import SeoDocument
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation
from app.modules.rfq.schemas import RFQCreate
from app.modules.rfq.services import validate_source

PRODUCTS_SITE_PAGE_TITLE = "Products Site Page SEO"
PRODUCTS_SITE_PAGE_DESCRIPTION = "SEO description owned by the published products site page."


@pytest.fixture
async def public_collections_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建包含完整公开聚合模型的隔离数据库。

    输入：
        sqlite_database_url: str，pytest 临时 SQLite 数据库地址。

    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，测试数据库会话工厂。
    """
    # 导入各模块模型，确保 Base.metadata 包含所有外键依赖表。
    from app.modules.audit import models as _audit_models  # noqa: F401
    from app.modules.auth import models as _auth_models  # noqa: F401
    from app.modules.authority import models as _authority_models  # noqa: F401
    from app.modules.catalog import models as _catalog_models  # noqa: F401
    from app.modules.company import models as _company_models  # noqa: F401
    from app.modules.content import models as _content_models  # noqa: F401
    from app.modules.discovery import models as _discovery_models  # noqa: F401
    from app.modules.localization import models as _localization_models  # noqa: F401
    from app.modules.media import models as _media_models  # noqa: F401
    from app.modules.users import models as _user_models  # noqa: F401

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _public_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """
    创建使用测试数据库的匿名公开 API 客户端。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，测试会话工厂。

    输出：
        AsyncIterator[AsyncClient]，已覆盖数据库依赖的 HTTP 客户端。
    """
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        """输入：无；输出：测试专用 AsyncSession。"""
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        yield client


def _add_lifecycle(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: object,
    locale_id: object,
    path: str,
    status: str = "published",
    active: bool = True,
    indexable: bool = True,
    robots_index: bool | None = None,
    canonical_override: str | None = None,
) -> None:
    """
    添加指定内容的统一翻译、发布、路由和可选 SEO 生命周期记录。

    输入：
        session: AsyncSession，当前数据库会话。
        owner_type: str，内容所有者类型。
        owner_id: object，内容实体 ID。
        locale_id: object，语言 ID。
        path: str，canonical 站内路径。
        status: str，翻译及发布状态。
        active: bool，路由是否生效。
        indexable: bool，路由是否允许索引。
        robots_index: bool | None，SEO robots_index；None 表示不建 SEO 文档。
        canonical_override: str | None，SEO canonical 覆盖地址。

    输出：
        None，将记录加入当前事务。
    """
    session.add_all(
        [
            TranslationStatus(
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale_id,
                status=status,
            ),
            ContentPublication(
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale_id,
                status=status,
                published_at=datetime.now(UTC) if status == "published" else None,
            ),
            ContentRoute(
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale_id,
                path=path,
                is_canonical=True,
                active=active,
                indexable=indexable,
            ),
        ]
    )
    if robots_index is not None or canonical_override is not None:
        session.add(
            SeoDocument(
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale_id,
                robots_index=True if robots_index is None else robots_index,
                canonical_override=canonical_override,
            )
        )


@pytest.mark.asyncio
async def test_navigation_and_home_only_return_fully_indexable_content(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证聚合接口过滤草稿、停用、非 self-canonical 与 robots noindex 内容。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；任何不可索引内容或客户隐私进入响应时失败。
    """
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="screws", status="enabled", sort_order=1)
        session.add_all([locale, category])
        await session.flush()
        session.add(
            ProductCategoryTranslation(
                category_id=category.id,
                locale_id=locale.id,
                name="Screws",
                short_description="Precision screw categories",
            )
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=locale.id,
            path="/en/products/screws/",
        )

        product_specs = (
            ("published-screw", "enabled", "published", None, None),
            ("draft-screw", "enabled", "draft", None, None),
            ("disabled-screw", "disabled", "published", None, None),
            (
                "non-self-canonical-screw",
                "enabled",
                "published",
                True,
                "https://junhuiscrewbarrel.com/en/products/screws/consolidated/",
            ),
            ("robots-noindex-screw", "enabled", "published", False, None),
        )
        for position, (
            slug,
            business_status,
            publication_status,
            robots_index,
            canonical_override,
        ) in enumerate(product_specs, start=1):
            product = Product(
                category_id=category.id,
                slug=slug,
                status=business_status,
                featured=True,
                sort_order=position,
            )
            session.add(product)
            await session.flush()
            session.add(
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name=slug,
                    short_description=f"{slug} summary",
                )
            )
            _add_lifecycle(
                session,
                owner_type="product",
                owner_id=product.id,
                locale_id=locale.id,
                path=f"/en/products/screws/{slug}/",
                status=publication_status,
                robots_index=robots_index,
                canonical_override=canonical_override,
            )

        # 已发布案例含未经许可的客户名，聚合响应只能返回公开 Link DTO。
        case_study = CaseStudy(
            slug="wear-case",
            status="enabled",
            client_name="private-client-name",
            client_name_public=False,
            featured=True,
        )
        session.add(case_study)
        await session.flush()
        session.add(
            CaseStudyTranslation(
                case_study_id=case_study.id,
                locale_id=locale.id,
                title="Wear case",
                summary="Published technical outcome",
            )
        )
        _add_lifecycle(
            session,
            owner_type="case_study",
            owner_id=case_study.id,
            locale_id=locale.id,
            path="/en/case-studies/wear-case/",
        )

        hero = MediaAsset(
            visibility="public",
            media_type="image",
            storage_bucket="public-media",
            storage_key="phase36/factory.webp",
            original_filename="factory.webp",
            sanitized_filename="factory.webp",
            mime_type="image/webp",
            file_extension=".webp",
            file_size_bytes=1024,
            sha256="a" * 64,
            width=1600,
            height=900,
            checksum_verified=True,
            malware_scan_status="clean",
            upload_status="ready",
        )
        session.add(hero)
        await session.flush()
        session.add(
            MediaAssetTranslation(
                media_asset_id=hero.id,
                locale_id=locale.id,
                alt_text="Junhui factory",
            )
        )
        company = CompanyProfile(
            status="enabled",
            founded_year=1985,
            years_experience=41,
            public_phone="+86 580 0000",
            public_email="sales@example.com",
            public_address="Published factory address",
            primary_factory_media_id=hero.id,
        )
        session.add(company)
        await session.flush()
        session.add(
            CompanyProfileTranslation(
                company_profile_id=company.id,
                locale_id=locale.id,
                company_name="Junhui Test Manufacturing",
                short_intro="Published company introduction",
                full_intro="Published company profile",
            )
        )
        _add_lifecycle(
            session,
            owner_type="company_profile",
            owner_id=company.id,
            locale_id=locale.id,
            path="/en/about/",
            robots_index=True,
        )

    async with _public_client(public_collections_factory) as client:
        navigation_response = await client.get("/api/v1/public/navigation/en")
        home_response = await client.get("/api/v1/public/home/en")

    from app.modules.content.services.indexable import list_sitemap_candidates

    async with public_collections_factory() as session:
        sitemap_candidates = await list_sitemap_candidates(session)

    assert navigation_response.status_code == 200
    assert home_response.status_code == 200
    navigation = navigation_response.json()["data"]
    home = home_response.json()["data"]

    assert navigation["locale"] == "en"
    assert navigation["primary"] == ["products", "case_studies", "about"]
    assert [item["slug"] for item in navigation["products"]["featured"]] == ["published-screw"]
    assert [item["slug"] for item in home["featured_products"]] == ["published-screw"]
    assert [item["slug"] for item in home["cases"]] == ["wear-case"]
    assert navigation["company"] == {
        "name": "Junhui Test Manufacturing",
        "phone": "+86 580 0000",
        "email": "sales@example.com",
        "address": "Published factory address",
    }
    assert home["company"]["company_name"] == "Junhui Test Manufacturing"
    assert home["hero_media"]["alt"] == "Junhui factory"
    assert home["hero_media"]["loading"] == "eager"
    assert home["trust_summary"]["founded_year"] == 1985
    assert home["seo"] == {
        "title": "Junhui Screw",
        "description": "Published company introduction",
        "canonical": "https://junhuiscrewbarrel.com/en/",
        "robots": "index, follow",
        "hreflang": {"en": "https://junhuiscrewbarrel.com/en/"},
    }
    assert home["schema"][0]["url"] == home["seo"]["canonical"]
    assert home["featured_products"][0]["media"] is None
    assert home["featured_products"][0]["category"]["slug"] == "screws"
    assert home["featured_products"][0]["specifications"] == []
    sitemap_paths = [candidate.path for candidate in sitemap_candidates]
    assert "/en/" in sitemap_paths
    assert "/en/products/" in sitemap_paths
    assert "/en/products/screws/" in sitemap_paths
    assert "/en/products/screws/published-screw/" in sitemap_paths

    serialized_payloads = f"{navigation!r}{home!r}"
    for forbidden in (
        "draft-screw",
        "disabled-screw",
        "non-self-canonical-screw",
        "robots-noindex-screw",
        "private-client-name",
    ):
        assert forbidden not in serialized_payloads


@pytest.mark.asyncio
async def test_empty_collections_return_empty_arrays_without_fabricated_facts(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证只有启用语言时，各内容族返回空数组或 null 且不伪造事实。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；响应出现虚构产品、数量、证书或公司事实时失败。
    """
    async with public_collections_factory() as session, session.begin():
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

    async with _public_client(public_collections_factory) as client:
        navigation_response = await client.get("/api/v1/public/navigation/en")
        home_response = await client.get("/api/v1/public/home/en")

    assert navigation_response.status_code == 200
    assert home_response.status_code == 200
    navigation = navigation_response.json()["data"]
    home = home_response.json()["data"]

    assert navigation["products"] == {"categories": [], "featured": []}
    assert navigation["primary"] == []
    assert navigation["solutions"] == {"featured": [], "problems": []}
    assert navigation["materials"] == []
    assert navigation["applications"] == []
    assert navigation["company"] is None
    assert home["company"] is None
    assert home["featured_products"] == []
    assert home["seo"]["canonical"] == "https://junhuiscrewbarrel.com/en/"
    assert home["seo"]["robots"] == "noindex, follow"
    assert home["seo"]["description"]
    assert home["seo"]["hreflang"] == {}
    assert home["schema"] == []
    assert home["certificates"] == []
    assert home["patents"] == []
    # 首页呈现 R1 会暴露固定模块键；这里仅检查值中没有虚构的认证或规模事实。
    serialized_payloads = f"{navigation!r}{home['company']!r}{home['trust_summary']!r}".lower()
    for fabricated_fact in ("iso", "employees", "products available"):
        assert fabricated_fact not in serialized_payloads


@pytest.mark.asyncio
async def test_sitemap_xml_includes_eligible_aggregate_pages_only(
    public_collections_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    验证独立测试配置下 Sitemap XML 包含合格聚合页，并排除草稿旧试点。

    输入：隔离数据库会话工厂及 pytest 环境变量夹具。

    输出：None；聚合页缺失、草稿泄漏或正式 URL 序列化错误时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="screws", status="enabled")
        session.add_all([locale, category])
        await session.flush()
        session.add(
            ProductCategoryTranslation(
                category_id=category.id,
                locale_id=locale.id,
                name="螺杆",
            )
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=locale.id,
            path="/zh-cn/products/screws/",
        )

        for slug, status in (("published-screw", "published"), ("old-pilot", "draft")):
            product = Product(category_id=category.id, slug=slug, status="enabled")
            session.add(product)
            await session.flush()
            session.add(
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="公开螺杆" if status == "published" else "旧试点",
                )
            )
            _add_lifecycle(
                session,
                owner_type="product",
                owner_id=product.id,
                locale_id=locale.id,
                path=f"/zh-cn/products/screws/{slug}/",
                status=status,
                active=status == "published",
                indexable=status == "published",
            )

    monkeypatch.setenv("PUBLIC_SITEMAP_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    async with _public_client(public_collections_factory) as client:
        response = await client.get("/sitemap.xml")

    assert response.status_code == 200
    xml = response.text
    expected_urls = {
        "https://junhuiscrewbarrel.com/zh-cn/",
        "https://junhuiscrewbarrel.com/zh-cn/products/",
        "https://junhuiscrewbarrel.com/zh-cn/products/screws/",
        "https://junhuiscrewbarrel.com/zh-cn/products/screws/published-screw/",
    }
    assert all(f"<loc>{url}</loc>" in xml for url in expected_urls)
    assert xml.count("<url>") == len(expected_urls)
    assert "old-pilot" not in xml


@pytest.mark.asyncio
async def test_home_without_company_uses_webpage_schema_only(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """输入有公开产品但无 Company 的首页；输出仅 WebPage，禁止虚构 Organization。"""
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="qa-components", status="enabled")
        session.add_all([locale, category])
        await session.flush()
        session.add(
            ProductCategoryTranslation(
                category_id=category.id,
                locale_id=locale.id,
                name="QA Components",
            )
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=locale.id,
            path="/en/products/qa-components/",
        )
        product = Product(category_id=category.id, slug="qa-screw", status="enabled")
        session.add(product)
        await session.flush()
        session.add(ProductTranslation(product_id=product.id, locale_id=locale.id, name="QA Screw"))
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=product.id,
            locale_id=locale.id,
            path="/en/products/qa-components/qa-screw/",
        )

    async with _public_client(public_collections_factory) as client:
        response = await client.get("/api/v1/public/home/en")

    assert response.status_code == 200
    schemas = response.json()["data"]["schema"]
    schema_types = [item["@type"] for item in schemas]
    assert schema_types == ["WebPage"]

    def nested_types(value: object) -> list[str]:
        """输入 JSON-LD 对象；输出所有嵌套 @type，避免只检查顶层而漏判。"""
        if isinstance(value, dict):
            current = [value["@type"]] if isinstance(value.get("@type"), str) else []
            return current + [item for child in value.values() for item in nested_types(child)]
        if isinstance(value, list):
            return [item for child in value for item in nested_types(child)]
        return []

    assert "WebSite" not in nested_types(schemas)
    assert "Organization" not in nested_types(schemas)


@pytest.mark.asyncio
async def test_noindex_category_remains_accessible_with_backend_owned_seo(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """输入已发布 noindex 分类；输出 200、自身 canonical、自定义 SEO 与无 hreflang。"""
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="private-series", status="enabled")
        session.add_all([locale, category])
        await session.flush()
        session.add(
            ProductCategoryTranslation(
                category_id=category.id,
                locale_id=locale.id,
                name="Private Series",
                short_description="Fallback category description",
            )
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=locale.id,
            path="/en/products/private-series/",
            robots_index=False,
        )
        seo = await session.scalar(select(SeoDocument).where(SeoDocument.owner_id == category.id))
        assert seo is not None
        seo.seo_title = "Private Series SEO"
        seo.meta_description = "Backend category description"
        product = Product(category_id=category.id, slug="private-screw", status="enabled")
        session.add(product)
        await session.flush()
        session.add(
            ProductTranslation(product_id=product.id, locale_id=locale.id, name="Private Screw")
        )
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=product.id,
            locale_id=locale.id,
            path="/en/products/private-series/private-screw/",
        )

    async with _public_client(public_collections_factory) as client:
        listing = await client.get(
            "/api/v1/public/products/en", params={"category": "private-series"}
        )
        category_page = await client.get("/api/v1/public/product-categories/en/private-series")

    assert listing.status_code == 200
    payload = listing.json()["data"]
    assert payload["seo"] == {
        "title": "Private Series SEO",
        "description": "Backend category description",
        "canonical": "https://junhuiscrewbarrel.com/en/products/private-series/",
        "robots": "noindex, follow",
        "hreflang": {},
    }
    assert category_page.status_code == 200
    assert category_page.json()["data"]["seo"]["robots"] == "noindex, follow"


@pytest.mark.asyncio
async def test_category_hreflang_excludes_non_self_canonical_locale(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    输入英文 canonical 指向其他页的双语分类；输出不包含错误英文 alternate。
    """
    async with public_collections_factory() as session, session.begin():
        en = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=False,
            is_enabled=True,
        )
        zh = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="canonical-series", status="enabled")
        session.add_all([en, zh, category])
        await session.flush()
        session.add_all(
            [
                ProductCategoryTranslation(
                    category_id=category.id,
                    locale_id=en.id,
                    name="Canonical Series",
                ),
                ProductCategoryTranslation(
                    category_id=category.id,
                    locale_id=zh.id,
                    name="规范系列",
                ),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=en.id,
            path="/en/products/canonical-series/",
            canonical_override="https://junhuiscrewbarrel.com/en/products/other-series/",
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=zh.id,
            path="/zh-cn/products/canonical-series/",
        )
        product = Product(category_id=category.id, slug="canonical-product", status="enabled")
        session.add(product)
        await session.flush()
        session.add_all(
            [
                ProductTranslation(product_id=product.id, locale_id=en.id, name="Product"),
                ProductTranslation(product_id=product.id, locale_id=zh.id, name="产品"),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=product.id,
            locale_id=en.id,
            path="/en/products/canonical-series/canonical-product/",
        )
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=product.id,
            locale_id=zh.id,
            path="/zh-cn/products/canonical-series/canonical-product/",
        )

    async with _public_client(public_collections_factory) as client:
        response = await client.get(
            "/api/v1/public/products/zh-cn",
            params={"category": "canonical-series"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["seo"]["hreflang"] == {
        "zh-CN": "https://junhuiscrewbarrel.com/zh-cn/products/canonical-series/",
        "x-default": "https://junhuiscrewbarrel.com/zh-cn/products/canonical-series/",
    }


@pytest.mark.asyncio
async def test_home_hreflang_only_contains_equivalent_eligible_locales(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证双语首页 reciprocal hreflang 与中文 x-default 均来自真实已发布内容。

    输入：public_collections_factory，隔离数据库。
    输出：None；空语言或 About canonical 混入首页 metadata 时失败。
    """
    async with public_collections_factory() as session, session.begin():
        en = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=False,
            is_enabled=True,
        )
        zh = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="bilingual", status="enabled")
        session.add_all([en, zh, category])
        await session.flush()
        session.add_all(
            [
                ProductCategoryTranslation(
                    category_id=category.id, locale_id=en.id, name="Bilingual"
                ),
                ProductCategoryTranslation(
                    category_id=category.id, locale_id=zh.id, name="双语分类"
                ),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=en.id,
            path="/en/products/bilingual/",
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=zh.id,
            path="/zh-cn/products/bilingual/",
        )

    async with _public_client(public_collections_factory) as client:
        en_home = (await client.get("/api/v1/public/home/en")).json()["data"]
        zh_home = (await client.get("/api/v1/public/home/zh-cn")).json()["data"]

    expected = {
        "en": "https://junhuiscrewbarrel.com/en/",
        "zh-CN": "https://junhuiscrewbarrel.com/zh-cn/",
        "x-default": "https://junhuiscrewbarrel.com/zh-cn/",
    }
    assert en_home["seo"]["hreflang"] == expected
    assert zh_home["seo"]["hreflang"] == expected
    assert en_home["seo"]["canonical"] != "https://junhuiscrewbarrel.com/en/about/"


@pytest.mark.asyncio
async def test_only_navigation_and_home_receive_short_public_cache_headers(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证仅新增的导航与首页只读端点设置短期公开缓存策略。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；聚合端点缺少缓存或既有 Company 端点被误加缓存时失败。
    """
    async with public_collections_factory() as session, session.begin():
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

    async with _public_client(public_collections_factory) as client:
        navigation_response = await client.get("/api/v1/public/navigation/en")
        home_response = await client.get("/api/v1/public/home/en")
        company_response = await client.get("/api/v1/public/company-profile/en")

    cache_policy = "public, max-age=60, stale-while-revalidate=300"
    assert navigation_response.headers["cache-control"] == cache_policy
    assert home_response.headers["cache-control"] == cache_policy
    assert "cache-control" not in company_response.headers


@pytest.mark.asyncio
async def test_published_rows_use_one_query_and_stable_limit_order(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证集合门禁由单次 SQL 完成，且并列排序使用唯一 slug 稳定截断。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；出现 N+1 查询或 limit 结果随插入顺序抖动时失败。
    """
    from app.modules.discovery.public_collections import _published_rows

    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="stable-category", status="enabled")
        session.add_all([locale, category])
        await session.flush()
        tied_time = datetime(2026, 9, 5, tzinfo=UTC)
        for slug, status in (
            ("draft-one", "draft"),
            ("draft-two", "draft"),
            ("z-valid", "published"),
            ("a-valid", "published"),
        ):
            product = Product(
                category_id=category.id,
                slug=slug,
                status="enabled",
                featured=True,
                sort_order=1,
                created_at=tied_time,
                updated_at=tied_time,
            )
            session.add(product)
            await session.flush()
            session.add(
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name=slug,
                )
            )
            _add_lifecycle(
                session,
                owner_type="product",
                owner_id=product.id,
                locale_id=locale.id,
                path=f"/en/products/stable-category/{slug}/",
                status=status,
            )
        await session.flush()

        engine = session.bind
        assert isinstance(engine, AsyncEngine)
        select_statements = 0

        def count_selects(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            """输入：SQLAlchemy 执行上下文；输出：None，仅统计 SELECT 语句。"""
            nonlocal select_statements
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements += 1

        event.listen(engine.sync_engine, "before_cursor_execute", count_selects)
        try:
            rows = await _published_rows(session, "product", locale, 1, True)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_selects)

    assert [row["slug"] for row in rows] == ["a-valid"]
    assert select_statements == 1


@pytest.mark.asyncio
async def test_product_listing_filters_paginates_and_isolates_locale(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证产品列表仅接受公开筛选字段，并执行稳定分页、语言及发布门禁。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；筛选、分页上限、locale 隔离或公开卡片白名单失效时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        en = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        zh = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=False,
            is_enabled=True,
        )
        category = ProductCategory(slug="screws", status="enabled", sort_order=1)
        material = Material(slug="peek", status="enabled", featured=True)
        application = Application(slug="medical", status="enabled", featured=True)
        session.add_all([en, zh, category, material, application])
        await session.flush()

        for owner_type, owner_id, path in (
            ("product_category", category.id, "/en/products/screws/"),
            ("material", material.id, "/en/materials/peek/"),
            ("application", application.id, "/en/applications/medical/"),
        ):
            _add_lifecycle(
                session,
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=en.id,
                path=path,
            )
        session.add_all(
            [
                ProductCategoryTranslation(
                    category_id=category.id,
                    locale_id=en.id,
                    name="Screws",
                ),
                MaterialTranslation(
                    material_id=material.id,
                    locale_id=en.id,
                    name="PEEK",
                    definition="High performance polymer",
                ),
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=en.id,
                    name="Medical",
                    description="Medical processing",
                ),
            ]
        )

        product_specs = (
            ("filtered-product", "published", en, 1),
            ("second-product", "published", en, 2),
            ("draft-product", "draft", en, 3),
            ("zh-only-product", "published", zh, 4),
        )
        products: dict[str, Product] = {}
        for slug, publication_status, locale, sort_order in product_specs:
            product = Product(
                category_id=category.id,
                slug=slug,
                code=f"PRIVATE-{slug}",
                status="enabled",
                featured=True,
                sort_order=sort_order,
            )
            session.add(product)
            await session.flush()
            products[slug] = product
            session.add(
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name=f"{locale.slug} {slug}",
                    short_description=f"{slug} public summary",
                )
            )
            _add_lifecycle(
                session,
                owner_type="product",
                owner_id=product.id,
                locale_id=locale.id,
                path=f"/{locale.slug}/products/screws/{slug}/",
                status=publication_status,
            )
        session.add_all(
            [
                ProductMaterial(
                    product_id=products["filtered-product"].id,
                    material_id=material.id,
                ),
                ProductApplication(
                    product_id=products["filtered-product"].id,
                    application_id=application.id,
                ),
            ]
        )

    async with _public_client(public_collections_factory) as client:
        filtered_response = await client.get(
            "/api/v1/public/products/en",
            params={
                "category": "screws",
                "material": "peek",
                "application": "medical",
                "page": 1,
                "page_size": 1,
            },
        )
        second_page_response = await client.get(
            "/api/v1/public/products/en", params={"page": 2, "page_size": 1}
        )
        invalid_page_response = await client.get("/api/v1/public/products/en", params={"page": 0})
        oversized_page_response = await client.get(
            "/api/v1/public/products/en", params={"page_size": 49}
        )
        out_of_range_response = await client.get(
            "/api/v1/public/products/en", params={"page": 99, "page_size": 1}
        )
        unknown_filter_response = await client.get(
            "/api/v1/public/products/en", params={"material": "missing-material"}
        )

    assert filtered_response.status_code == 200
    payload = filtered_response.json()["data"]
    assert payload["items"] == [
        {
            "type": "product",
            "slug": "filtered-product",
            "name": "en filtered-product",
            "url": "/en/products/screws/filtered-product/",
            "summary": "filtered-product public summary",
            "media": None,
            "category": {
                "type": "product_category",
                "slug": "screws",
                "name": "Screws",
                "url": "/en/products/screws/",
                "summary": "",
            },
            "specifications": [],
        }
    ]
    assert {key: payload[key] for key in ("page", "page_size", "total", "pages", "filters")} == {
        "page": 1,
        "page_size": 1,
        "total": 1,
        "pages": 1,
        "filters": {
            "category": "screws",
            "material": "peek",
            "application": "medical",
        },
    }
    assert payload["seo"]["canonical"] == (
        "https://junhuiscrewbarrel.com/en/products/screws/"
        "?material=peek&application=medical&page_size=1"
    )
    assert payload["seo"]["robots"] == "noindex, follow"
    assert payload["seo"]["hreflang"] == {}
    assert payload["schema"][0]["url"] == payload["seo"]["canonical"]
    assert payload["breadcrumb"][-1]["url"] == payload["seo"]["canonical"]
    assert payload["schema"][1]["itemListElement"][-1]["item"] == (payload["breadcrumb"][-1]["url"])
    serialized = repr(payload)
    assert "PRIVATE-filtered-product" not in serialized
    assert "draft-product" not in serialized
    assert "zh-only-product" not in serialized
    assert second_page_response.status_code == 200
    second_page = second_page_response.json()["data"]
    assert second_page["items"][0]["slug"] == "second-product"
    assert second_page["seo"]["canonical"] == (
        "https://junhuiscrewbarrel.com/en/products/?page=2&page_size=1"
    )
    assert second_page["seo"]["robots"] == "noindex, follow"
    assert second_page["seo"]["hreflang"] == {}
    assert second_page["schema"][0]["url"] == second_page["seo"]["canonical"]
    assert invalid_page_response.status_code == 422
    assert oversized_page_response.status_code == 422
    assert out_of_range_response.status_code == 404
    assert unknown_filter_response.status_code == 404


@pytest.mark.asyncio
async def test_all_public_list_endpoints_return_the_common_clean_envelope(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证九类列表端点统一返回无内部标识的公共分页 envelope。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；端点缺失、合同不一致或专家公开资格被绕过时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="components", status="enabled")
        material = Material(slug="pvc", status="enabled")
        technology = Technology(slug="nitriding", status="enabled")
        application = Application(slug="extrusion", status="enabled")
        solution = Solution(slug="wear", status="enabled")
        case_study = CaseStudy(slug="wear-result", status="enabled")
        expert = AuthorExpert(
            slug="verified-engineer",
            status="enabled",
            role_type="expert",
            is_real_person_verified=True,
            public_profile_enabled=True,
        )
        hidden_expert = AuthorExpert(
            slug="private-engineer",
            status="enabled",
            role_type="expert",
            is_real_person_verified=True,
            public_profile_enabled=False,
        )
        unverified_expert = AuthorExpert(
            slug="unverified-engineer",
            status="enabled",
            role_type="expert",
            is_real_person_verified=False,
            public_profile_enabled=True,
        )
        knowledge_category = KnowledgeCategory(slug="guides", status="enabled")
        disabled_product_category = ProductCategory(slug="disabled-components", status="disabled")
        disabled_knowledge_category = KnowledgeCategory(slug="disabled-guides", status="disabled")
        session.add_all(
            [
                locale,
                category,
                material,
                technology,
                application,
                solution,
                case_study,
                expert,
                hidden_expert,
                unverified_expert,
                knowledge_category,
                disabled_product_category,
                disabled_knowledge_category,
            ]
        )
        await session.flush()
        product = Product(
            category_id=category.id,
            slug="mixing-head",
            status="enabled",
        )
        article = KnowledgeArticle(
            category_id=knowledge_category.id,
            slug="wear-guide",
            status="enabled",
            author_id=expert.id,
        )
        hidden_product = Product(
            category_id=disabled_product_category.id,
            slug="hidden-product",
            status="enabled",
        )
        disabled_category_article = KnowledgeArticle(
            category_id=disabled_knowledge_category.id,
            slug="disabled-category-guide",
            status="enabled",
            author_id=expert.id,
        )
        unverified_author_article = KnowledgeArticle(
            category_id=knowledge_category.id,
            slug="unverified-author-guide",
            status="enabled",
            author_id=unverified_expert.id,
        )
        session.add_all(
            [
                product,
                article,
                hidden_product,
                disabled_category_article,
                unverified_author_article,
            ]
        )
        await session.flush()
        translations_and_lifecycle = (
            (
                "product_category",
                category.id,
                ProductCategoryTranslation(
                    category_id=category.id, locale_id=locale.id, name="Components"
                ),
                "/en/products/components/",
            ),
            (
                "product",
                product.id,
                ProductTranslation(product_id=product.id, locale_id=locale.id, name="Mixing head"),
                "/en/products/components/mixing-head/",
            ),
            (
                "material",
                material.id,
                MaterialTranslation(material_id=material.id, locale_id=locale.id, name="PVC"),
                "/en/materials/pvc/",
            ),
            (
                "technology",
                technology.id,
                TechnologyTranslation(
                    technology_id=technology.id,
                    locale_id=locale.id,
                    name="Nitriding",
                ),
                "/en/technologies/nitriding/",
            ),
            (
                "application",
                application.id,
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=locale.id,
                    name="Extrusion",
                ),
                "/en/applications/extrusion/",
            ),
            (
                "solution",
                solution.id,
                SolutionTranslation(solution_id=solution.id, locale_id=locale.id, name="Wear"),
                "/en/solutions/wear/",
            ),
            (
                "case_study",
                case_study.id,
                CaseStudyTranslation(
                    case_study_id=case_study.id,
                    locale_id=locale.id,
                    title="Wear result",
                ),
                "/en/case-studies/wear-result/",
            ),
            (
                "knowledge_article",
                article.id,
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=locale.id,
                    title="Wear guide",
                    body_markdown="Published guide body",
                ),
                "/en/knowledge/guides/wear-guide/",
            ),
            (
                "author_expert",
                expert.id,
                AuthorExpertTranslation(
                    author_expert_id=expert.id,
                    locale_id=locale.id,
                    name="Verified Engineer",
                    expertise_json=["Wear"],
                ),
                "/en/experts/verified-engineer/",
            ),
            (
                "author_expert",
                hidden_expert.id,
                AuthorExpertTranslation(
                    author_expert_id=hidden_expert.id,
                    locale_id=locale.id,
                    name="Private Engineer",
                    expertise_json=["Private"],
                ),
                "/en/experts/private-engineer/",
            ),
            (
                "product",
                hidden_product.id,
                ProductTranslation(
                    product_id=hidden_product.id,
                    locale_id=locale.id,
                    name="Hidden product",
                ),
                "/en/products/disabled-components/hidden-product/",
            ),
            (
                "knowledge_article",
                disabled_category_article.id,
                KnowledgeArticleTranslation(
                    article_id=disabled_category_article.id,
                    locale_id=locale.id,
                    title="Disabled category guide",
                    body_markdown="Must not be linked.",
                ),
                "/en/knowledge/disabled-guides/disabled-category-guide/",
            ),
            (
                "knowledge_article",
                unverified_author_article.id,
                KnowledgeArticleTranslation(
                    article_id=unverified_author_article.id,
                    locale_id=locale.id,
                    title="Unverified author guide",
                    body_markdown="Must not be linked.",
                ),
                "/en/knowledge/guides/unverified-author-guide/",
            ),
            (
                "author_expert",
                unverified_expert.id,
                AuthorExpertTranslation(
                    author_expert_id=unverified_expert.id,
                    locale_id=locale.id,
                    name="Unverified Engineer",
                ),
                "/en/experts/unverified-engineer/",
            ),
        )
        session.add(
            KnowledgeCategoryTranslation(
                category_id=knowledge_category.id,
                locale_id=locale.id,
                name="Guides",
            )
        )
        for owner_type, owner_id, translation, path in translations_and_lifecycle:
            session.add(translation)
            _add_lifecycle(
                session,
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale.id,
                path=path,
            )
        # 四类详情只建立现有显式关系；公开 DTO 必须把目标再次通过发布门禁解析为 canonical Link。
        session.add_all(
            [
                ProductMaterial(product_id=product.id, material_id=material.id),
                ProductTechnology(product_id=product.id, technology_id=technology.id),
                ProductApplication(product_id=product.id, application_id=application.id),
                ProductSolution(product_id=product.id, solution_id=solution.id),
                MaterialTechnology(material_id=material.id, technology_id=technology.id),
                MaterialSolution(material_id=material.id, solution_id=solution.id),
                ApplicationSolution(application_id=application.id, solution_id=solution.id),
                CaseMaterial(case_study_id=case_study.id, material_id=material.id),
                CaseTechnology(case_study_id=case_study.id, technology_id=technology.id),
                CaseApplication(case_study_id=case_study.id, application_id=application.id),
                CaseSolution(case_study_id=case_study.id, solution_id=solution.id),
                ArticleMaterial(article_id=article.id, material_id=material.id),
                ArticleTechnology(article_id=article.id, technology_id=technology.id),
                ArticleApplication(article_id=article.id, application_id=application.id),
                ArticleSolution(article_id=article.id, solution_id=solution.id),
                ProductMaterial(product_id=hidden_product.id, material_id=material.id),
                ArticleMaterial(article_id=disabled_category_article.id, material_id=material.id),
                ArticleMaterial(article_id=unverified_author_article.id, material_id=material.id),
            ]
        )

    resources = (
        "products",
        "product-categories",
        "materials",
        "technologies",
        "applications",
        "solutions",
        "knowledge",
        "case-studies",
        "experts",
    )
    async with _public_client(public_collections_factory) as client:
        responses = {
            resource: await client.get(f"/api/v1/public/{resource}/en") for resource in resources
        }
        home_response = await client.get("/api/v1/public/home/en")
        material_page_two = await client.get(
            "/api/v1/public/materials/en", params={"page": 2, "page_size": 1}
        )
        detail_responses = {
            resource: await client.get(f"/api/v1/public/{resource}/en/{slug}")
            for resource, slug in (
                ("materials", "pvc"),
                ("technologies", "nitriding"),
                ("applications", "extrusion"),
                ("solutions", "wear"),
            )
        }
        category_detail_response = await client.get(
            "/api/v1/public/product-categories/en/components"
        )
        filtered_knowledge = await client.get(
            "/api/v1/public/knowledge/en", params={"category": "guides"}
        )
        missing_category = await client.get(
            "/api/v1/public/knowledge/en", params={"category": "missing-guides"}
        )
        filtered_experts = await client.get("/api/v1/public/experts/en", params={"type": "expert"})
        wrong_expert_type = await client.get("/api/v1/public/experts/en", params={"type": "author"})

    for resource, response in responses.items():
        assert response.status_code == 200, resource
        envelope = response.json()["data"]
        expected_envelope_keys = {
            "items",
            "page",
            "page_size",
            "total",
            "pages",
            "filters",
        }
        if resource == "products" or resource in {
            "materials",
            "technologies",
            "applications",
            "solutions",
            "knowledge",
            "case-studies",
            "experts",
        }:
            expected_envelope_keys.update({"seo", "schema", "breadcrumb"})
        assert set(envelope) == expected_envelope_keys
        assert envelope["total"] == 1, resource
        expected_item_keys = {"type", "slug", "name", "url", "summary"}
        if resource == "products":
            expected_item_keys.update({"media", "category", "specifications"})
        elif resource == "knowledge":
            expected_item_keys.update(
                {
                    "media",
                    "category",
                    "author",
                    "reviewer",
                    "published_at",
                    "updated_at",
                }
            )
        elif resource == "experts":
            expected_item_keys.update({"role_type"})
        assert set(envelope["items"][0]) == expected_item_keys
    assert responses["experts"].json()["data"]["items"][0]["slug"] == "verified-engineer"
    assert home_response.status_code == 200
    home_knowledge = home_response.json()["data"]["knowledge"][0]
    assert home_knowledge["author"] == "Verified Engineer"
    assert home_knowledge["published_at"] is not None
    assert "updated_at" in home_knowledge
    assert "private-engineer" not in repr(responses["experts"].json())
    assert filtered_knowledge.json()["data"]["total"] == 1
    assert missing_category.status_code == 404
    assert filtered_experts.json()["data"]["total"] == 1
    assert wrong_expert_type.status_code == 404
    assert filtered_knowledge.json()["data"]["filters"]["category"] == "guides"
    assert filtered_experts.json()["data"]["filters"]["type"] == "expert"
    assert category_detail_response.status_code == 200
    category_detail = category_detail_response.json()["data"]
    assert category_detail["relations"] == {}
    assert category_detail["breadcrumb"][-2]["url"] == (
        "https://junhuiscrewbarrel.com/en/products/"
    )
    assert material_page_two.status_code == 404

    # 每类详情都只输出已发布 canonical Link DTO，并在可见 Breadcrumb 中包含列表入口。
    expected_relation_groups = {
        "materials": {"products", "technologies", "solutions", "cases", "knowledge"},
        "technologies": {"products", "materials", "cases", "knowledge"},
        "applications": {"products", "solutions", "cases", "knowledge"},
        "solutions": {"products", "materials", "applications", "cases", "knowledge"},
    }
    for resource, response in detail_responses.items():
        assert response.status_code == 200, resource
        detail = response.json()["data"]
        assert set(detail["relations"]) == expected_relation_groups[resource]
        assert all(links for links in detail["relations"].values())
        assert all(
            set(link) == {"type", "slug", "name", "url", "summary"}
            and link["url"].startswith("/en/")
            for links in detail["relations"].values()
            for link in links
        )
        assert detail["breadcrumb"][-2]["url"] == f"https://junhuiscrewbarrel.com/en/{resource}/"
        assert "_id" not in repr(detail["relations"])
    material_relations = detail_responses["materials"].json()["data"]["relations"]
    assert "hidden-product" not in repr(material_relations)
    assert "disabled-category-guide" not in repr(material_relations)
    assert "unverified-author-guide" not in repr(material_relations)

    # Catalog 详情关系必须批量读取，查询数不能随关联目标数量线性膨胀。
    engine = public_collections_factory.kw["bind"]
    assert isinstance(engine, AsyncEngine)
    select_statements = 0

    def count_detail_selects(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        """输入：SQLAlchemy 执行上下文；输出：None，仅统计 Catalog 详情 SELECT。"""
        nonlocal select_statements
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_detail_selects)
    try:
        async with _public_client(public_collections_factory) as client:
            repeated_detail = await client.get("/api/v1/public/materials/en/pvc")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_detail_selects)
    assert repeated_detail.status_code == 200
    assert select_statements <= 22


@pytest.mark.asyncio
async def test_search_honors_type_allowlist_publication_locale_and_case_privacy(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证搜索覆盖八个批准内容族，并隔离草稿、其他语言和案例私密字段。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；类型白名单、统一门禁或 SQLite 确定性相关性失效时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        en = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        zh = Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=False,
            is_enabled=True,
        )
        category = ProductCategory(slug="search-products", status="enabled")
        material = Material(slug="precision-material", status="enabled")
        zh_material = Material(slug="zh-precision-material", status="enabled")
        application = Application(slug="precision-application", status="enabled")
        solution = Solution(slug="precision-solution", status="enabled")
        technology = Technology(slug="precision-technology", status="enabled")
        hidden_technology = Technology(slug="hidden-precision-technology", status="enabled")
        capability = ManufacturingCapability(
            slug="precision-capability",
            capability_type="inspection",
            status="enabled",
        )
        hidden_capability = ManufacturingCapability(
            slug="hidden-precision-capability",
            capability_type="inspection",
            status="enabled",
        )
        case_study = CaseStudy(
            slug="precision-case",
            status="enabled",
            client_name="private-secret-client",
            client_address="private-secret-address",
            client_name_public=False,
            client_address_public=False,
        )
        author = AuthorExpert(
            slug="search-author",
            status="enabled",
            role_type="author",
            is_real_person_verified=True,
            public_profile_enabled=False,
        )
        knowledge_category = KnowledgeCategory(slug="search-guides", status="enabled")
        session.add_all(
            [
                en,
                zh,
                category,
                material,
                zh_material,
                application,
                solution,
                technology,
                hidden_technology,
                capability,
                hidden_capability,
                case_study,
                author,
                knowledge_category,
            ]
        )
        await session.flush()
        product_title = Product(category_id=category.id, slug="precision-title", status="enabled")
        product_body = Product(category_id=category.id, slug="precision-body", status="enabled")
        draft_product = Product(category_id=category.id, slug="draft-precision", status="enabled")
        article = KnowledgeArticle(
            category_id=knowledge_category.id,
            slug="precision-knowledge",
            status="enabled",
            author_id=author.id,
        )
        session.add_all([product_title, product_body, draft_product, article])
        await session.flush()

        searchable_records = (
            (
                "product",
                product_title.id,
                ProductTranslation(
                    product_id=product_title.id,
                    locale_id=en.id,
                    name="Precision",
                    short_description="Title match",
                ),
                "/en/products/search-products/precision-title/",
                "published",
                en,
            ),
            (
                "product",
                product_body.id,
                ProductTranslation(
                    product_id=product_body.id,
                    locale_id=en.id,
                    name="General screw",
                    short_description="Precision appears only in the summary",
                ),
                "/en/products/search-products/precision-body/",
                "published",
                en,
            ),
            (
                "product",
                draft_product.id,
                ProductTranslation(
                    product_id=draft_product.id,
                    locale_id=en.id,
                    name="Precision draft secret",
                ),
                "/en/products/search-products/draft-precision/",
                "draft",
                en,
            ),
            (
                "material",
                material.id,
                MaterialTranslation(
                    material_id=material.id,
                    locale_id=en.id,
                    name="Precision polymer",
                ),
                "/en/materials/precision-material/",
                "published",
                en,
            ),
            (
                "material",
                zh_material.id,
                MaterialTranslation(
                    material_id=zh_material.id,
                    locale_id=zh.id,
                    name="Precision 中文材料",
                ),
                "/zh-cn/materials/zh-precision-material/",
                "published",
                zh,
            ),
            (
                "application",
                application.id,
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=en.id,
                    name="Precision molding",
                ),
                "/en/applications/precision-application/",
                "published",
                en,
            ),
            (
                "solution",
                solution.id,
                SolutionTranslation(
                    solution_id=solution.id,
                    locale_id=en.id,
                    name="Precision recovery",
                ),
                "/en/solutions/precision-solution/",
                "published",
                en,
            ),
            (
                "technology",
                technology.id,
                TechnologyTranslation(
                    technology_id=technology.id,
                    locale_id=en.id,
                    name="Precision nitriding",
                    definition="Published technology definition",
                ),
                "/en/technologies/precision-technology/",
                "published",
                en,
            ),
            (
                "manufacturing_capability",
                capability.id,
                ManufacturingCapabilityTranslation(
                    capability_id=capability.id,
                    locale_id=en.id,
                    name="Precision inspection capability",
                    summary="Published capability summary",
                ),
                "/en/capabilities/precision-capability/",
                "published",
                en,
            ),
            (
                "case_study",
                case_study.id,
                CaseStudyTranslation(
                    case_study_id=case_study.id,
                    locale_id=en.id,
                    title="Precision case",
                    summary="Public case outcome",
                ),
                "/en/case-studies/precision-case/",
                "published",
                en,
            ),
            (
                "knowledge_article",
                article.id,
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=en.id,
                    title="Precision guide",
                    body_markdown="Published body",
                ),
                "/en/knowledge/search-guides/precision-knowledge/",
                "published",
                en,
            ),
        )
        for owner_type, owner_id, translation, path, status, locale in searchable_records:
            session.add(translation)
            _add_lifecycle(
                session,
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale.id,
                path=path,
                status=status,
            )
        session.add_all(
            [
                TechnologyTranslation(
                    technology_id=hidden_technology.id,
                    locale_id=en.id,
                    name="Precision hidden technology",
                ),
                ManufacturingCapabilityTranslation(
                    capability_id=hidden_capability.id,
                    locale_id=en.id,
                    name="Precision hidden capability",
                ),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="technology",
            owner_id=hidden_technology.id,
            locale_id=en.id,
            path="/en/technologies/hidden-precision-technology/",
            robots_index=False,
        )
        _add_lifecycle(
            session,
            owner_type="manufacturing_capability",
            owner_id=hidden_capability.id,
            locale_id=en.id,
            path="/en/capabilities/hidden-precision-capability/",
            status="draft",
        )

    async with _public_client(public_collections_factory) as client:
        search_response = await client.get("/api/v1/public/search/en", params={"q": "precision"})
        product_only_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "product"},
        )
        technology_only_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "technology"},
        )
        capability_only_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "manufacturing_capability"},
        )
        first_page_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "page": 1, "page_size": 3},
        )
        second_page_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "page": 2, "page_size": 3},
        )
        literal_special_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "%_", "page": 1, "page_size": 12},
        )
        private_case_response = await client.get(
            "/api/v1/public/search/en", params={"q": "private-secret-client"}
        )
        invalid_type_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "privacy"},
        )

    assert search_response.status_code == 200
    search_payload = search_response.json()["data"]
    assert set(search_payload["groups"]) == {
        "product",
        "material",
        "application",
        "solution",
        "technology",
        "manufacturing_capability",
        "knowledge_article",
        "case_study",
    }
    assert [item["slug"] for item in search_payload["groups"]["product"]] == [
        "precision-title",
        "precision-body",
    ]
    serialized = repr(search_payload)
    for forbidden in (
        "draft-precision",
        "zh-precision-material",
        "private-secret-client",
        "private-secret-address",
    ):
        assert forbidden not in serialized
    assert product_only_response.status_code == 200
    assert set(product_only_response.json()["data"]["groups"]) == {"product"}
    assert technology_only_response.status_code == 200
    assert [
        item["slug"] for item in technology_only_response.json()["data"]["groups"]["technology"]
    ] == ["precision-technology"]
    assert capability_only_response.status_code == 200
    assert [
        item["slug"]
        for item in capability_only_response.json()["data"]["groups"][
            "manufacturing_capability"
        ]
    ] == ["precision-capability"]
    assert private_case_response.status_code == 200
    assert all(not items for items in private_case_response.json()["data"]["groups"].values())
    first_page = first_page_response.json()["data"]
    second_page = second_page_response.json()["data"]
    assert first_page["total"] == 8
    assert first_page["pages"] == 3
    assert first_page["page"] == 1
    assert first_page["page_size"] == 3
    assert len(first_page["items"]) == 3
    assert second_page["total"] == first_page["total"]
    assert second_page["pages"] == first_page["pages"]
    assert len(second_page["items"]) == 3
    assert {
        (item["type"], item["slug"]) for item in first_page["items"]
    }.isdisjoint({(item["type"], item["slug"]) for item in second_page["items"]})
    assert literal_special_response.status_code == 200
    assert literal_special_response.json()["data"]["total"] == 0
    assert invalid_type_response.status_code == 422


def test_search_migration_declares_trigram_extension_and_six_named_indexes() -> None:
    """
    验证搜索迁移只管理六个批准内容族的命名 trigram 索引。

    输入：无，读取固定 Alembic 迁移源码。

    输出：None；revision 链、索引字段或 downgrade 扩展策略不符合要求时失败。
    """
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "20260905_0010_phase36_search.py"
    )
    assert migration_path.exists()
    source = migration_path.read_text(encoding="utf-8")
    assert 'revision = "20260905_0010"' in source
    assert 'down_revision = "20260904_0009"' in source
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in source
    expected_indexes = {
        "ix_product_translations_name_trgm",
        "ix_material_translations_name_trgm",
        "ix_application_translations_name_trgm",
        "ix_solution_translations_name_trgm",
        "ix_knowledge_article_translations_title_trgm",
        "ix_case_study_translations_title_trgm",
    }
    assert expected_indexes <= set(source.split('"'))
    downgrade_source = source.split("def downgrade()", maxsplit=1)[1]
    assert "DROP EXTENSION" not in downgrade_source.upper()
    assert "drop_index" in downgrade_source


@pytest.mark.asyncio
async def test_lists_reject_empty_canonical_override_and_unrenderable_author_locale(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证列表严格复用索引源 canonical 规则，并过滤缺少作者当前语言翻译的文章。

    输入：
        public_collections_factory: async_sessionmaker[AsyncSession]，隔离数据库。

    输出：
        None；空 canonical 覆盖或点击后 404 的知识卡进入列表时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        product_category = ProductCategory(slug="strict-gate", status="enabled")
        knowledge_category = KnowledgeCategory(slug="strict-guides", status="enabled")
        untranslated_author = AuthorExpert(
            slug="untranslated-author",
            status="enabled",
            role_type="author",
            is_real_person_verified=True,
            public_profile_enabled=False,
        )
        session.add_all([locale, product_category, knowledge_category, untranslated_author])
        await session.flush()
        empty_canonical_product = Product(
            category_id=product_category.id,
            slug="empty-canonical",
            status="enabled",
        )
        unrenderable_article = KnowledgeArticle(
            category_id=knowledge_category.id,
            slug="unrenderable-article",
            status="enabled",
            author_id=untranslated_author.id,
        )
        session.add_all([empty_canonical_product, unrenderable_article])
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=empty_canonical_product.id,
                    locale_id=locale.id,
                    name="Empty canonical product",
                ),
                KnowledgeArticleTranslation(
                    article_id=unrenderable_article.id,
                    locale_id=locale.id,
                    title="Unrenderable article",
                    body_markdown="Public-looking body",
                ),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=empty_canonical_product.id,
            locale_id=locale.id,
            path="/en/products/strict-gate/empty-canonical/",
            canonical_override="",
        )
        _add_lifecycle(
            session,
            owner_type="knowledge_article",
            owner_id=unrenderable_article.id,
            locale_id=locale.id,
            path="/en/knowledge/strict-guides/unrenderable-article/",
        )

    async with _public_client(public_collections_factory) as client:
        product_response = await client.get("/api/v1/public/products/en")
        knowledge_response = await client.get("/api/v1/public/knowledge/en")

    assert product_response.status_code == 200
    assert knowledge_response.status_code == 200
    assert product_response.json()["data"]["items"] == []
    assert knowledge_response.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_rfq_multi_source_is_resolved_by_server_publication_gates(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证八类真实 CTA 来源由服务端解析为 canonical、owner 类型和内部 ID。

    输入：public_collections_factory，隔离公开内容数据库。
    输出：None；任何客户端值绕过发布门禁或归因不准确时测试失败。
    """
    async with public_collections_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="qa-category", status="enabled")
        knowledge_category = KnowledgeCategory(slug="qa-guides", status="enabled")
        expert = AuthorExpert(
            slug="qa-expert",
            status="enabled",
            role_type="expert",
            is_real_person_verified=True,
            public_profile_enabled=True,
        )
        entities = {
            "material": Material(slug="qa-material", status="enabled"),
            "technology": Technology(slug="qa-technology", status="enabled"),
            "application": Application(slug="qa-application", status="enabled"),
            "solution": Solution(slug="qa-solution", status="enabled"),
            "case_study": CaseStudy(slug="qa-case", status="enabled"),
            "manufacturing_capability": ManufacturingCapability(
                slug="qa-capability", capability_type="machining", status="enabled"
            ),
        }
        session.add_all([locale, category, knowledge_category, expert, *entities.values()])
        await session.flush()
        product = Product(category_id=category.id, slug="qa-product", status="enabled")
        article = KnowledgeArticle(
            category_id=knowledge_category.id,
            slug="qa-knowledge",
            status="enabled",
            author_id=expert.id,
        )
        entities.update({"product": product, "knowledge_article": article})
        session.add_all([product, article])
        await session.flush()
        session.add_all(
            [
                ProductTranslation(product_id=product.id, locale_id=locale.id, name="QA Product"),
                MaterialTranslation(
                    material_id=entities["material"].id, locale_id=locale.id, name="QA Material"
                ),
                TechnologyTranslation(
                    technology_id=entities["technology"].id,
                    locale_id=locale.id,
                    name="QA Technology",
                ),
                ApplicationTranslation(
                    application_id=entities["application"].id,
                    locale_id=locale.id,
                    name="QA Application",
                ),
                SolutionTranslation(
                    solution_id=entities["solution"].id, locale_id=locale.id, name="QA Solution"
                ),
                CaseStudyTranslation(
                    case_study_id=entities["case_study"].id, locale_id=locale.id, title="QA Case"
                ),
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=locale.id,
                    title="QA Knowledge",
                    body_markdown="QA body",
                ),
                AuthorExpertTranslation(
                    author_expert_id=expert.id, locale_id=locale.id, name="QA Expert"
                ),
                ManufacturingCapabilityTranslation(
                    capability_id=entities["manufacturing_capability"].id,
                    locale_id=locale.id,
                    name="QA Capability",
                ),
            ]
        )
        paths = {
            "product": "/en/products/qa-category/qa-product/",
            "material": "/en/materials/qa-material/",
            "technology": "/en/technologies/qa-technology/",
            "application": "/en/applications/qa-application/",
            "solution": "/en/solutions/qa-solution/",
            "case_study": "/en/case-studies/qa-case/",
            "knowledge_article": "/en/knowledge/qa-guides/qa-knowledge/",
            "manufacturing_capability": "/en/capabilities/qa-capability/",
        }
        for source_type, entity in entities.items():
            _add_lifecycle(
                session,
                owner_type=source_type,
                owner_id=entity.id,
                locale_id=locale.id,
                path=paths[source_type],
            )
        await session.flush()

        for source_type, entity in entities.items():
            payload = RFQCreate(
                company_name="QA Company",
                contact_name="QA Contact",
                email="qa@example.com",
                message="QA only",
                preferred_language="en",
                source_type=source_type,
                source_slug=entity.slug,
                consent_privacy=True,
            )
            canonical, owner_type, owner_id = await validate_source(session, payload)
            assert canonical == f"https://junhuiscrewbarrel.com{paths[source_type]}"
            assert owner_type == source_type
            assert owner_id == entity.id

        session.add(
            SeoDocument(
                owner_type="product",
                owner_id=product.id,
                locale_id=locale.id,
                canonical_override="https://junhuiscrewbarrel.com/en/products/other/product/",
                robots_index=True,
            )
        )
        await session.flush()
        non_self_payload = RFQCreate(
            company_name="QA Company",
            contact_name="QA Contact",
            email="qa@example.com",
            message="QA only",
            preferred_language="en",
            source_type="product",
            source_slug=product.slug,
            consent_privacy=True,
        )
        with pytest.raises(AppException) as failure:
            await validate_source(session, non_self_payload)
        assert failure.value.code == "invalid_rfq_source"


async def _seed_bilingual_product_listing(
    session: AsyncSession,
) -> dict[str, Locale]:
    """
    创建双语公开产品，供产品总列表 SitePage 门禁测试复用。

    输入：
        session: AsyncSession，隔离测试数据库会话。

    输出：
        dict[str, Locale]，按语言代码索引的测试语言。
    """
    locales = {
        "en": Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=False,
            is_enabled=True,
            sort_order=20,
        ),
        "zh-CN": Locale(
            code="zh-CN",
            slug="zh-cn",
            name="Chinese",
            native_name="简体中文",
            is_default=True,
            is_enabled=True,
            sort_order=10,
        ),
    }
    category = ProductCategory(slug="site-page-products", status="enabled")
    product = Product(category_id=category.id, slug="site-page-product", status="enabled")
    session.add_all([*locales.values(), category])
    await session.flush()
    product.category_id = category.id
    session.add(product)
    await session.flush()

    for locale in locales.values():
        session.add_all(
            [
                ProductCategoryTranslation(
                    category_id=category.id,
                    locale_id=locale.id,
                    name="Site page category",
                ),
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Site page product",
                ),
            ]
        )
        _add_lifecycle(
            session,
            owner_type="product_category",
            owner_id=category.id,
            locale_id=locale.id,
            path=f"/{locale.slug}/products/site-page-products/",
        )
        _add_lifecycle(
            session,
            owner_type="product",
            owner_id=product.id,
            locale_id=locale.id,
            path=f"/{locale.slug}/products/site-page-products/site-page-product/",
        )
    return locales


def _add_products_site_page_locale(
    session: AsyncSession,
    *,
    page: SitePage,
    locale: Locale,
    lifecycle_status: str = "published",
    include_translation: bool = True,
    route_active: bool = True,
    route_indexable: bool = True,
    robots_index: bool = True,
    canonical_override: str | None = None,
) -> None:
    """
    添加一个 Products 固定页语言及其公开生命周期测试记录。

    输入：
        session: AsyncSession，隔离测试数据库会话。
        page: SitePage，products 固定页。
        locale: Locale，目标语言。
        lifecycle_status: str，翻译及发布状态。
        include_translation: bool，是否创建真实页面翻译。
        route_active: bool，规范路由是否生效。
        route_indexable: bool，规范路由是否允许索引。
        robots_index: bool，SEO 文档是否允许索引。
        canonical_override: str | None，SEO canonical 覆盖值。

    输出：
        None，将测试记录加入当前事务。
    """
    if include_translation:
        session.add(
            SitePageTranslation(
                site_page_id=page.id,
                locale_id=locale.id,
                display_name="产品" if locale.code == "zh-CN" else "Products",
            )
        )
    _add_lifecycle(
        session,
        owner_type="site_page",
        owner_id=page.id,
        locale_id=locale.id,
        path=f"/{locale.slug}/products/",
        status=lifecycle_status,
        active=route_active,
        indexable=route_indexable,
    )
    session.add(
        SeoDocument(
            owner_type="site_page",
            owner_id=page.id,
            locale_id=locale.id,
            seo_title=PRODUCTS_SITE_PAGE_TITLE,
            meta_description=PRODUCTS_SITE_PAGE_DESCRIPTION,
            robots_index=robots_index,
            robots_follow=True,
            canonical_override=canonical_override,
        )
    )


@pytest.mark.asyncio
async def test_products_root_uses_only_fully_published_site_page_seo(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证合格 products SitePage 逐语言提供 SEO 和正式 reciprocal hreflang。

    输入：public_collections_factory，隔离数据库会话工厂。
    输出：None；公开 SEO 未来自 SitePage 或语言门禁不完整时失败。
    """
    async with public_collections_factory() as session, session.begin():
        locales = await _seed_bilingual_product_listing(session)
        page = SitePage(system_key="products", status="enabled")
        session.add(page)
        await session.flush()
        for locale in locales.values():
            _add_products_site_page_locale(session, page=page, locale=locale)

    async with _public_client(public_collections_factory) as client:
        response = await client.get("/api/v1/public/products/en")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["items"]
    assert payload["seo"] == {
        "title": PRODUCTS_SITE_PAGE_TITLE,
        "description": PRODUCTS_SITE_PAGE_DESCRIPTION,
        "canonical": "https://junhuiscrewbarrel.com/en/products/",
        "robots": "index, follow",
        "hreflang": {
            "en": "https://junhuiscrewbarrel.com/en/products/",
            "zh-CN": "https://junhuiscrewbarrel.com/zh-cn/products/",
            "x-default": "https://junhuiscrewbarrel.com/zh-cn/products/",
        },
    }


@pytest.mark.asyncio
async def test_products_root_keeps_legacy_fallback_when_site_page_does_not_exist(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证数据库完全没有 products SitePage 时保留既有合成 SEO 行为。

    输入：public_collections_factory，隔离数据库会话工厂。
    输出：None；兼容标题、索引资格或双语 alternate 回归时失败。
    """
    async with public_collections_factory() as session, session.begin():
        await _seed_bilingual_product_listing(session)

    async with _public_client(public_collections_factory) as client:
        response = await client.get("/api/v1/public/products/en")

    assert response.status_code == 200
    seo = response.json()["data"]["seo"]
    assert seo["title"] == "Products"
    assert seo["description"] is None
    assert seo["robots"] == "index, follow"
    assert seo["hreflang"] == {
        "en": "https://junhuiscrewbarrel.com/en/products/",
        "zh-CN": "https://junhuiscrewbarrel.com/zh-cn/products/",
        "x-default": "https://junhuiscrewbarrel.com/zh-cn/products/",
    }


@pytest.mark.parametrize(
    (
        "gate_case",
        "page_status",
        "lifecycle_status",
        "include_translation",
        "active",
        "indexable",
        "robots_index",
        "canonical_override",
    ),
    [
        ("draft", "enabled", "draft", True, True, True, True, None),
        ("disabled", "disabled", "published", True, True, True, True, None),
        ("missing_translation", "enabled", "published", False, True, True, True, None),
        ("inactive", "enabled", "published", True, False, True, True, None),
        ("noindex_route", "enabled", "published", True, True, False, True, None),
        ("noindex_seo", "enabled", "published", True, True, True, False, None),
        ("blank_canonical", "enabled", "published", True, True, True, True, ""),
        (
            "non_self_canonical",
            "enabled",
            "published",
            True,
            True,
            True,
            True,
            "https://junhuiscrewbarrel.com/en/products/other/",
        ),
    ],
)
@pytest.mark.asyncio
async def test_existing_ineligible_products_site_page_never_leaks_or_revives_seo(
    public_collections_factory: async_sessionmaker[AsyncSession],
    gate_case: str,
    page_status: str,
    lifecycle_status: str,
    include_translation: bool,
    active: bool,
    indexable: bool,
    robots_index: bool,
    canonical_override: str | None,
) -> None:
    """
    验证已登记但不合格的 SitePage 使用安全默认 SEO，且产品列表仍可读取。

    输入：隔离会话工厂及各生命周期门禁组合。
    输出：None；草稿字段泄漏、旧合成分支复活或列表不可用时失败。
    """
    async with public_collections_factory() as session, session.begin():
        locales = await _seed_bilingual_product_listing(session)
        page = SitePage(system_key="products", status=page_status)
        session.add(page)
        await session.flush()
        _add_products_site_page_locale(
            session,
            page=page,
            locale=locales["en"],
            lifecycle_status=lifecycle_status,
            include_translation=include_translation,
            route_active=active,
            route_indexable=indexable,
            robots_index=robots_index,
            canonical_override=canonical_override,
        )

    async with _public_client(public_collections_factory) as client:
        response = await client.get("/api/v1/public/products/en")

    assert response.status_code == 200, gate_case
    payload = response.json()["data"]
    assert payload["items"], gate_case
    assert payload["seo"] == {
        "title": "Products",
        "description": None,
        "canonical": "https://junhuiscrewbarrel.com/en/products/",
        "robots": "noindex, follow",
        "hreflang": {},
    }, gate_case
    assert PRODUCTS_SITE_PAGE_TITLE not in str(payload)
    assert PRODUCTS_SITE_PAGE_DESCRIPTION not in str(payload)


@pytest.mark.asyncio
async def test_site_page_sitemap_uses_real_routes_and_never_synthetic_revival(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 products SitePage 存在后只由合格真实路由生成产品总列表候选。

    输入：public_collections_factory，隔离数据库会话工厂。
    输出：None；不合格语言被产品详情合成复活或 URL 重复时失败。
    """
    from app.modules.content.services.indexable import list_sitemap_candidates

    async with public_collections_factory() as session, session.begin():
        locales = await _seed_bilingual_product_listing(session)
        page = SitePage(system_key="products", status="enabled")
        session.add(page)
        await session.flush()
        _add_products_site_page_locale(session, page=page, locale=locales["en"])
        _add_products_site_page_locale(
            session,
            page=page,
            locale=locales["zh-CN"],
            lifecycle_status="draft",
        )

    async with public_collections_factory() as session:
        candidates = await list_sitemap_candidates(session)

    paths = [candidate.path for candidate in candidates]
    assert paths.count("/en/products/") == 1
    assert "/zh-cn/products/" not in paths
    assert "/en/products/site-page-products/site-page-product/" in paths
    assert "/zh-cn/products/site-page-products/site-page-product/" in paths


@pytest.mark.parametrize(
    (
        "gate_case",
        "page_status",
        "lifecycle_status",
        "include_translation",
        "route_active",
        "route_indexable",
        "robots_index",
        "canonical_override",
        "wrong_path",
    ),
    [
        ("draft", "enabled", "draft", True, True, True, True, None, False),
        ("disabled", "disabled", "published", True, True, True, True, None, False),
        ("missing_translation", "enabled", "published", False, True, True, True, None, False),
        ("inactive", "enabled", "published", True, False, True, True, None, False),
        ("route_noindex", "enabled", "published", True, True, False, True, None, False),
        ("seo_noindex", "enabled", "published", True, True, True, False, None, False),
        ("blank_canonical", "enabled", "published", True, True, True, True, "", False),
        (
            "non_self_canonical",
            "enabled",
            "published",
            True,
            True,
            True,
            True,
            "https://junhuiscrewbarrel.com/en/products/other/",
            False,
        ),
        ("wrong_path", "enabled", "published", True, True, True, True, None, True),
    ],
)
@pytest.mark.asyncio
async def test_ineligible_site_page_never_enters_sitemap_via_synthetic_fallback(
    public_collections_factory: async_sessionmaker[AsyncSession],
    gate_case: str,
    page_status: str,
    lifecycle_status: str,
    include_translation: bool,
    route_active: bool,
    route_indexable: bool,
    robots_index: bool,
    canonical_override: str | None,
    wrong_path: bool,
) -> None:
    """
    验证每项真实 SitePage 资格门禁都能独立阻止 Sitemap 合成分支复活。

    输入：隔离数据库会话工厂及各门禁组合。
    输出：None；不合格 SitePage 的 Products 总列表进入候选时失败。
    """
    from app.modules.content.services.indexable import list_sitemap_candidates

    async with public_collections_factory() as session, session.begin():
        locales = await _seed_bilingual_product_listing(session)
        page = SitePage(system_key="products", status=page_status)
        session.add(page)
        await session.flush()
        _add_products_site_page_locale(
            session,
            page=page,
            locale=locales["en"],
            lifecycle_status=lifecycle_status,
            include_translation=include_translation,
            route_active=route_active,
            route_indexable=route_indexable,
            robots_index=robots_index,
            canonical_override=canonical_override,
        )
        if wrong_path:
            route = await session.scalar(
                select(ContentRoute).where(
                    ContentRoute.owner_type == "site_page",
                    ContentRoute.owner_id == page.id,
                )
            )
            assert route is not None
            route.path = "/en/products/wrong/"

    async with public_collections_factory() as session:
        paths = [item.path for item in await list_sitemap_candidates(session)]

    assert "/en/products/" not in paths, gate_case


@pytest.mark.asyncio
async def test_legacy_sitemap_aggregate_remains_when_products_site_page_is_absent(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证尚未迁入 SitePage 的数据库仍按已发布产品生成兼容总列表候选。

    输入：public_collections_factory，隔离数据库会话工厂。
    输出：None；旧部署升级前的 Products sitemap URL 消失时失败。
    """
    from app.modules.content.services.indexable import list_sitemap_candidates

    async with public_collections_factory() as session, session.begin():
        await _seed_bilingual_product_listing(session)

    async with public_collections_factory() as session:
        candidates = await list_sitemap_candidates(session)

    paths = [candidate.path for candidate in candidates]
    assert paths.count("/en/products/") == 1
    assert paths.count("/zh-cn/products/") == 1
