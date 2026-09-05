"""Phase 3.6 导航与首页公开聚合接口回归测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

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
from app.modules.authority.models import CaseStudy, CaseStudyTranslation
from app.modules.catalog.models import (
    Product,
    ProductCategory,
    ProductCategoryTranslation,
    ProductTranslation,
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
