"""Phase 3.6 导航与首页公开聚合接口回归测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.database import (
    Base,
    create_database_engine,
    create_session_factory,
    get_session,
)
from app.main import create_app
from app.modules.authority.models import (
    AuthorExpert,
    AuthorExpertTranslation,
    CaseStudy,
    CaseStudyTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
    KnowledgeCategory,
)
from app.modules.catalog.models import (
    Application,
    ApplicationTranslation,
    Material,
    MaterialTranslation,
    Product,
    ProductApplication,
    ProductCategory,
    ProductCategoryTranslation,
    ProductMaterial,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.company.models import CompanyProfile, CompanyProfileTranslation
from app.modules.content.models import (
    ContentPublication,
    ContentRoute,
    TranslationStatus,
)
from app.modules.discovery.models import SeoDocument
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation


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

    assert navigation_response.status_code == 200
    assert home_response.status_code == 200
    navigation = navigation_response.json()["data"]
    home = home_response.json()["data"]

    assert navigation["locale"] == "en"
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
    assert navigation["solutions"] == {"featured": [], "problems": []}
    assert navigation["materials"] == []
    assert navigation["applications"] == []
    assert navigation["company"] is None
    assert home == {
        "locale": "en",
        "company": None,
        "hero_media": None,
        "product_categories": [],
        "featured_products": [],
        "materials": [],
        "solutions": [],
        "capabilities": [],
        "applications": [],
        "cases": [],
        "knowledge": [],
        "trust_summary": None,
    }
    serialized_payloads = f"{navigation!r}{home!r}".lower()
    for fabricated_fact in ("iso", "certificate", "employees", "products available"):
        assert fabricated_fact not in serialized_payloads


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

    assert filtered_response.status_code == 200
    payload = filtered_response.json()["data"]
    assert payload == {
        "items": [
            {
                "type": "product",
                "slug": "filtered-product",
                "name": "en filtered-product",
                "url": "/en/products/screws/filtered-product/",
                "summary": "filtered-product public summary",
            }
        ],
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
    serialized = repr(payload)
    assert "PRIVATE-filtered-product" not in serialized
    assert "draft-product" not in serialized
    assert "zh-only-product" not in serialized
    assert second_page_response.status_code == 200
    assert second_page_response.json()["data"]["items"][0]["slug"] == "second-product"
    assert invalid_page_response.status_code == 422
    assert oversized_page_response.status_code == 422


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
        knowledge_category = KnowledgeCategory(slug="guides", status="enabled")
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
                knowledge_category,
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
        session.add_all([product, article])
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

    for resource, response in responses.items():
        assert response.status_code == 200, resource
        envelope = response.json()["data"]
        assert set(envelope) == {
            "items",
            "page",
            "page_size",
            "total",
            "pages",
            "filters",
        }
        assert envelope["total"] == 1, resource
        assert set(envelope["items"][0]) == {"type", "slug", "name", "url", "summary"}
    assert responses["experts"].json()["data"]["items"][0]["slug"] == "verified-engineer"
    assert "private-engineer" not in repr(responses["experts"].json())


@pytest.mark.asyncio
async def test_search_honors_type_allowlist_publication_locale_and_case_privacy(
    public_collections_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证搜索只覆盖六个批准内容族，并隔离草稿、其他语言和案例私密字段。

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

    async with _public_client(public_collections_factory) as client:
        search_response = await client.get("/api/v1/public/search/en", params={"q": "precision"})
        product_only_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "product"},
        )
        private_case_response = await client.get(
            "/api/v1/public/search/en", params={"q": "private-secret-client"}
        )
        invalid_type_response = await client.get(
            "/api/v1/public/search/en",
            params={"q": "precision", "types": "technology"},
        )

    assert search_response.status_code == 200
    search_payload = search_response.json()["data"]
    assert set(search_payload["groups"]) == {
        "product",
        "material",
        "application",
        "solution",
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
    assert private_case_response.status_code == 200
    assert all(not items for items in private_case_response.json()["data"]["groups"].values())
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
