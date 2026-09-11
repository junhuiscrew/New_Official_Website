"""真实 PostgreSQL 的 CITEXT、partial index、Seed 与 Authentication 集成测试。"""

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.main import create_app
from app.modules.auth.models import AuthSession
from app.modules.catalog.models import Product, ProductCategory, ProductTranslation
from app.modules.catalog.schemas import (
    CategoryCreate,
    EntityCreate,
    ProductCreate,
    ProductUpdate,
    TranslationInput,
)
from app.modules.catalog.services import (
    archive_entity,
    create_category,
    create_core_entity,
    create_product,
    update_product,
)
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    SitePage,
    SitePageTranslation,
    TranslationStatus,
)
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.content.services.publication import transition_publication
from app.modules.content.services.revisions import store_revision
from app.modules.discovery.services import initialize_products_site_page
from app.modules.localization.models import Locale
from app.modules.localization.schemas import LocaleUpdate
from app.modules.localization.service import set_default_locale, update_locale
from app.modules.users.bootstrap import create_super_admin
from app.modules.users.models import Permission, User
from app.seed import seed_database

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要 Docker PostgreSQL integration profile"),
]


async def test_postgresql_schema_seed_and_case_insensitive_email() -> None:
    """
    验证真实 PostgreSQL schema、完整权限、单默认语言和 CITEXT 唯一性。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；断言数据库原生能力生效。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    await seed_database(factory)
    await seed_database(factory)

    async with engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    assert {"auth_sessions", "content_routes", "audit_logs"}.issubset(table_names)

    async with factory() as session:
        permission_count = await session.scalar(select(func.count()).select_from(Permission))
        default_count = await session.scalar(
            select(func.count()).select_from(Locale).where(Locale.is_default.is_(True))
        )
    from app.seed import PERMISSIONS

    assert permission_count == len(PERMISSIONS)
    assert default_count == 1

    email_suffix = uuid.uuid4().hex
    normalized_email = f"case-{email_suffix}@example.com"
    async with factory() as session, session.begin():
        session.add(User(email=normalized_email, password_hash="not-used", is_active=True))
    async with factory() as session:
        session.add(User(email=normalized_email.upper(), password_hash="not-used", is_active=True))
        with pytest.raises(IntegrityError):
            await session.commit()

    # PostgreSQL partial unique index 必须在并发写入时也阻止第二个默认语言。
    async with factory() as session:
        session.add(
            Locale(
                code="fr",
                slug="fr",
                name="French",
                native_name="Français",
                is_default=True,
                is_enabled=True,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()


async def test_postgresql_authentication_creates_revocable_session() -> None:
    """
    验证 Authentication 在真实 PostgreSQL 上登录并创建服务端 refresh session。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；断言登录、current-user 和 auth_sessions 持久化。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    owner_email = f"integration-owner-{uuid.uuid4().hex}@example.com"
    await create_super_admin(
        factory,
        email=owner_email,
        password="IntegrationPassword!2026",
        display_name="Integration Owner",
    )
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": owner_email.upper(),
                "password": "IntegrationPassword!2026",
            },
        )
        current_user = await client.get("/api/v1/auth/me")
    async with factory() as session:
        session_count = await session.scalar(select(func.count()).select_from(AuthSession))
    assert login.status_code == 200
    assert current_user.status_code == 200
    assert session_count >= 1
    await engine.dispose()


async def test_postgresql_content_integrity_under_concurrency() -> None:
    """
    验证 PostgreSQL 规范路由唯一索引及并发修订序号分配。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；断言数据库约束和咨询锁共同保持一致性。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    async with factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert locale is not None
        locale_id = locale.id

    route_owner_id = uuid.uuid4()
    route_suffix = route_owner_id.hex
    async with factory() as session:
        session.add_all(
            [
                ContentRoute(
                    owner_type="page",
                    owner_id=route_owner_id,
                    locale_id=locale_id,
                    path=f"/en/integration-route-{route_suffix}-a/",
                    is_canonical=True,
                    active=False,
                    indexable=False,
                ),
                ContentRoute(
                    owner_type="page",
                    owner_id=route_owner_id,
                    locale_id=locale_id,
                    path=f"/en/integration-route-{route_suffix}-b/",
                    is_canonical=True,
                    active=False,
                    indexable=False,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    revision_owner_id = uuid.uuid4()
    first_written = asyncio.Event()

    async def write_revision(title: str, hold_lock: bool) -> int:
        """在独立事务中保存修订，并按需短暂持有同一 owner 的咨询锁。"""
        async with factory() as session, session.begin():
            revision = await store_revision(
                session,
                "page",
                revision_owner_id,
                locale_id,
                {"title": title},
                None,
            )
            if hold_lock:
                first_written.set()
                await asyncio.sleep(0.2)
            return revision.revision_no

    first_task = asyncio.create_task(write_revision("First", True))
    await first_written.wait()
    second_task = asyncio.create_task(write_revision("Second", False))
    revision_numbers = await asyncio.gather(first_task, second_task)

    async with factory() as session:
        stored_numbers = list(
            (
                await session.scalars(
                    select(ContentRevision.revision_no)
                    .where(ContentRevision.owner_id == revision_owner_id)
                    .order_by(ContentRevision.revision_no)
                )
            ).all()
        )
    assert revision_numbers == [1, 2]
    assert stored_numbers == [1, 2]
    await engine.dispose()


async def test_postgresql_locale_disable_and_publish_are_serialized() -> None:
    """
    验证停用 Locale 与发布内容的并发事务不能共同成功。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；断言最终不存在 disabled locale + published route 的分裂状态。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    locale_code = f"x-{uuid.uuid4().hex[:8]}"
    owner_id = uuid.uuid4()
    async with factory() as session, session.begin():
        locale = Locale(
            code=locale_code,
            slug=locale_code,
            name="Concurrency Test",
            native_name="Concurrency Test",
            is_default=False,
            is_enabled=True,
        )
        session.add(locale)
        await session.flush()
        publication = ContentPublication(
            owner_type="page",
            owner_id=owner_id,
            locale_id=locale.id,
            status="review",
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
            path=f"/{locale_code}/concurrency-test/",
            is_canonical=True,
            active=False,
            indexable=False,
        )
        session.add_all([publication, translation, route])
        await session.flush()
        locale_id = locale.id
        publication_id = publication.id
        translation_id = translation.id
        route_id = route.id

    locale_locked = asyncio.Event()

    async def disable_locale() -> None:
        """锁定并停用测试 Locale，短暂保留事务以制造真实竞争。"""
        async with factory() as session, session.begin():
            await update_locale(session, locale_id, LocaleUpdate(is_enabled=False))
            locale_locked.set()
            await asyncio.sleep(0.2)

    async def publish_content() -> str:
        """在另一事务尝试发布同一 Locale 的内容。"""
        await locale_locked.wait()
        async with factory() as session, session.begin():
            publication = await session.get(ContentPublication, publication_id)
            translation = await session.get(TranslationStatus, translation_id)
            route = await session.get(ContentRoute, route_id)
            assert publication is not None and translation is not None and route is not None
            try:
                await transition_publication(
                    session,
                    publication=publication,
                    translation=translation,
                    route=route,
                    target_status=PublicationStatus.PUBLISHED,
                    actor_permissions={"content.publish"},
                    actor_id=None,
                )
            except AppException as exc:
                return exc.code
        return "published"

    disable_task = asyncio.create_task(disable_locale())
    publish_task = asyncio.create_task(publish_content())
    _disabled, publish_result = await asyncio.gather(disable_task, publish_task)

    async with factory() as session:
        stored_locale = await session.get(Locale, locale_id)
        stored_publication = await session.get(ContentPublication, publication_id)
        stored_route = await session.get(ContentRoute, route_id)
    assert publish_result == "locale_disabled"
    assert stored_locale is not None and stored_locale.is_enabled is False
    assert stored_publication is not None and stored_publication.status == "review"
    assert (
        stored_route is not None
        and stored_route.active is False
        and stored_route.indexable is False
    )
    await engine.dispose()


async def test_postgresql_competing_publication_transitions_are_serialized() -> None:
    """
    验证基于同一 review 状态的并发发布决策会在加锁后重新校验。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；一个转换成功，另一个以非法转换失败，跨表状态保持一致。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    async with factory() as session:
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert locale is not None
        locale_id = locale.id
    owner_id = uuid.uuid4()
    async with factory() as session, session.begin():
        publication = ContentPublication(
            owner_type="page", owner_id=owner_id, locale_id=locale_id, status="review"
        )
        translation = TranslationStatus(
            owner_type="page",
            owner_id=owner_id,
            locale_id=locale_id,
            source_locale_id=locale_id,
            status="human_reviewed",
        )
        route = ContentRoute(
            owner_type="page",
            owner_id=owner_id,
            locale_id=locale_id,
            path=f"/en/concurrent-publication-{owner_id.hex}/",
            is_canonical=True,
            active=False,
            indexable=False,
        )
        session.add_all([publication, translation, route])
        await session.flush()
        record_ids = (publication.id, translation.id, route.id)

    first_transitioned = asyncio.Event()

    async def run_transition(target: PublicationStatus, hold_lock: bool) -> str:
        """在独立事务中加载记录并执行一个发布转换。"""
        if not hold_lock:
            await first_transitioned.wait()
        async with factory() as session, session.begin():
            publication = await session.get(ContentPublication, record_ids[0])
            translation = await session.get(TranslationStatus, record_ids[1])
            route = await session.get(ContentRoute, record_ids[2])
            assert publication is not None and translation is not None and route is not None
            try:
                await transition_publication(
                    session,
                    publication=publication,
                    translation=translation,
                    route=route,
                    target_status=target,
                    actor_permissions={"content.publish"},
                    actor_id=None,
                )
                if hold_lock:
                    first_transitioned.set()
                    await asyncio.sleep(0.2)
                return target.value
            except AppException as exc:
                return exc.code

    published, competing = await asyncio.gather(
        asyncio.create_task(run_transition(PublicationStatus.PUBLISHED, True)),
        asyncio.create_task(run_transition(PublicationStatus.SCHEDULED, False)),
    )
    async with factory() as session:
        stored_publication = await session.get(ContentPublication, record_ids[0])
        stored_translation = await session.get(TranslationStatus, record_ids[1])
        stored_route = await session.get(ContentRoute, record_ids[2])
    assert published == "published"
    assert competing == "invalid_publication_transition"
    assert stored_publication is not None and stored_publication.status == "published"
    assert stored_translation is not None and stored_translation.status == "published"
    assert stored_route is not None and stored_route.active and stored_route.indexable
    await engine.dispose()


async def test_postgresql_competing_default_locale_switches_are_serialized() -> None:
    """
    验证两个不同目标的默认语言切换采用固定锁顺序且不会死锁。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；两个事务均完成且数据库最终始终只有一个默认 Locale。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    async with factory() as session:
        locales = list(
            (
                await session.scalars(
                    select(Locale).where(Locale.code.in_(("zh-CN", "en"))).order_by(Locale.id)
                )
            ).all()
        )
    assert len(locales) == 2

    # 多轮同时起跑增加真实数据库调度交错，旧的“先锁目标再全表更新”会有死锁风险。
    for round_number in range(6):
        start = asyncio.Event()

        async def switch_default(
            target_id: uuid.UUID, start_event: asyncio.Event = start
        ) -> uuid.UUID:
            """等待共同起点后，在独立事务内切换默认语言。"""
            await start_event.wait()
            async with factory() as session, session.begin():
                selected = await set_default_locale(session, target_id)
                return selected.id

        first_target = locales[round_number % 2].id
        second_target = locales[(round_number + 1) % 2].id
        tasks = [
            asyncio.create_task(switch_default(first_target)),
            asyncio.create_task(switch_default(second_target)),
        ]
        start.set()
        switched_ids = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        assert set(switched_ids) == {first_target, second_target}

        async with factory() as session:
            default_count = await session.scalar(
                select(func.count()).select_from(Locale).where(Locale.is_default.is_(True))
            )
        assert default_count == 1
    await engine.dispose()


async def test_postgresql_catalog_remediation_lifecycle_is_atomic() -> None:
    """
    验证真实 PostgreSQL 中正文撤回、missing locale 补齐与业务退役保持原子一致。

    输入：TEST_DATABASE_URL 环境变量。
    输出：None；断言统一索引源不会返回审核失效或退役内容。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    unique = uuid.uuid4().hex
    async with factory() as session, session.begin():
        zh = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        en = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert zh is not None and en is not None
        category = await create_category(
            session,
            CategoryCreate(
                slug=f"pg-category-{unique}",
                translations=[TranslationInput(locale_id=zh.id, name="PG 分类")],
            ),
        )
        product = await create_product(
            session,
            ProductCreate(
                category_id=category.id,
                slug=f"pg-product-{unique}",
                translations=[TranslationInput(locale_id=zh.id, name="PG 产品")],
            ),
        )
        material = await create_core_entity(
            session,
            "material",
            EntityCreate(
                slug=f"pg-material-{unique}",
                translations=[TranslationInput(locale_id=zh.id, name="PG 材料")],
            ),
        )

        async def publish(owner_type: str, owner_id: uuid.UUID) -> None:
            """加载并发布同一 owner 的中文生命周期记录。"""
            publication = await session.scalar(
                select(ContentPublication).where(
                    ContentPublication.owner_type == owner_type,
                    ContentPublication.owner_id == owner_id,
                    ContentPublication.locale_id == zh.id,
                )
            )
            translation = await session.scalar(
                select(TranslationStatus).where(
                    TranslationStatus.owner_type == owner_type,
                    TranslationStatus.owner_id == owner_id,
                    TranslationStatus.locale_id == zh.id,
                )
            )
            route = await session.scalar(
                select(ContentRoute).where(
                    ContentRoute.owner_type == owner_type,
                    ContentRoute.owner_id == owner_id,
                    ContentRoute.locale_id == zh.id,
                )
            )
            assert publication is not None and translation is not None and route is not None
            publication.status = "review"
            translation.status = "human_reviewed"
            await session.flush()
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions={"content.publish"},
                actor_id=None,
            )

        await publish("product", product.id)
        await publish("material", material.id)
        indexed_owner_ids = {route.owner_id for route in await list_indexable_routes(session)}
        assert {product.id, material.id} <= indexed_owner_ids

        await update_product(
            session,
            product.id,
            ProductUpdate(translations=[TranslationInput(locale_id=zh.id, name="PG 产品已修改")]),
        )
        await update_product(
            session,
            product.id,
            ProductUpdate(translations=[TranslationInput(locale_id=en.id, name="PG Product")]),
        )
        await archive_entity(session, "material", material.id)
        indexed_owner_ids = {route.owner_id for route in await list_indexable_routes(session)}
        assert product.id not in indexed_owner_ids
        assert material.id not in indexed_owner_ids

        en_publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product.id,
                ContentPublication.locale_id == en.id,
            )
        )
        en_route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "product",
                ContentRoute.owner_id == product.id,
                ContentRoute.locale_id == en.id,
            )
        )
        assert en_publication is not None and en_publication.status == "draft"
        assert en_route is not None and en_route.active is False and en_route.indexable is False
    await engine.dispose()


async def test_postgresql_public_search_prefers_title_and_has_trigram_indexes() -> None:
    """
    验证真实 PostgreSQL 搜索将名称命中排在摘要命中前，并已安装六个 trigram 索引。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；FTS 排序、统一发布门禁或迁移索引缺失时测试失败。
    """
    from app.modules.discovery.public_collections import search_public_content

    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    unique = uuid.uuid4().hex
    # test profile 会保留 PostgreSQL volume；完整 UUID 可避免旧测试标题因公共前缀触发 trigram 模糊命中。
    needle = f"precision{unique}"
    async with factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "en"))
        assert locale is not None
        category = ProductCategory(slug=f"pg-search-category-{unique}", status="enabled")
        session.add(category)
        await session.flush()
        title_product = Product(
            category_id=category.id,
            slug=f"pg-title-{unique}",
            status="enabled",
            sort_order=1,
        )
        body_product = Product(
            category_id=category.id,
            slug=f"pg-body-{unique}",
            status="enabled",
            sort_order=2,
        )
        session.add_all([title_product, body_product])
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=title_product.id,
                    locale_id=locale.id,
                    name=needle,
                    short_description="Generic title-match summary",
                ),
                ProductTranslation(
                    product_id=body_product.id,
                    locale_id=locale.id,
                    name="Generic PostgreSQL screw",
                    short_description=f"The summary contains {needle}",
                ),
            ]
        )
        for product in (title_product, body_product):
            session.add_all(
                [
                    TranslationStatus(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        status="published",
                    ),
                    ContentPublication(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        status="published",
                    ),
                    ContentRoute(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        path=(f"/en/products/{category.slug}/{product.slug}/"),
                        is_canonical=True,
                        active=True,
                        indexable=True,
                    ),
                ]
            )

    async with factory() as session:
        search_payload = await search_public_content(
            session,
            "en",
            needle,
            ("product",),
            10,
        )

    assert [item["slug"] for item in search_payload["groups"]["product"]] == [
        title_product.slug,
        body_product.slug,
    ]

    expected_indexes = {
        "ix_product_translations_name_trgm",
        "ix_material_translations_name_trgm",
        "ix_application_translations_name_trgm",
        "ix_solution_translations_name_trgm",
        "ix_knowledge_article_translations_title_trgm",
        "ix_case_study_translations_title_trgm",
    }
    async with engine.connect() as connection:
        index_rows = (
            await connection.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                    """
                )
            )
        ).mappings()
        index_definitions = {
            row["indexname"]: row["indexdef"]
            for row in index_rows
            if row["indexname"] in expected_indexes
        }
    assert expected_indexes == set(index_definitions)
    assert all("USING gin" in definition for definition in index_definitions.values())
    assert all("gin_trgm_ops" in definition for definition in index_definitions.values())
    await engine.dispose()


async def test_postgresql_products_site_page_initialization_is_concurrent_and_retryable() -> None:
    """
    验证两个真实 PostgreSQL 事务并发初始化时只产生一套 Products 页面记录。

    输入：TEST_DATABASE_URL 环境变量，必须指向独立临时 PostgreSQL。
    输出：None；断言 advisory lock、唯一约束、幂等回读及失败事务后的重试能力。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    await seed_database(factory)
    first_initialized = asyncio.Event()

    async def initialize(hold_lock: bool) -> uuid.UUID:
        """输入是否短暂持锁；输出当前唯一 Products SitePage ID。"""
        async with factory() as session, session.begin():
            page = await initialize_products_site_page(
                session,
                system_key="products",
                actor_id=None,
            )
            if hold_lock:
                first_initialized.set()
                await asyncio.sleep(0.2)
            return page.id

    first_task = asyncio.create_task(initialize(True))
    await first_initialized.wait()
    second_task = asyncio.create_task(initialize(False))
    first_id, second_id = await asyncio.wait_for(
        asyncio.gather(first_task, second_task),
        timeout=5,
    )
    assert first_id == second_id

    async with factory() as session:
        # 中央 seed 还会建立 Privacy 固定页；这里只核对 Products 页面自身，避免跨功能计数耦合。
        assert await session.scalar(
            select(func.count())
            .select_from(SitePage)
            .where(SitePage.system_key == "products")
        ) == 1
        assert await session.scalar(
            select(func.count())
            .select_from(SitePageTranslation)
            .where(SitePageTranslation.site_page_id == first_id)
        ) == 2
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ContentRoute)
                .where(
                    ContentRoute.owner_type == "site_page",
                    ContentRoute.owner_id == first_id,
                )
            )
            == 2
        )

    # 唯一冲突回滚后，同一新会话仍能幂等回读既有页面。
    async with factory() as session:
        session.add(SitePage(system_key="products", status="enabled"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
    assert await initialize(False) == first_id
    await engine.dispose()


async def test_postgresql_fixed_utility_site_pages_initialize_with_distinct_identity() -> None:
    """
    验证 Contact 与 RFQ 在真实 PostgreSQL 中使用独立锁、真实 UUID 和固定路径。

    输入：TEST_DATABASE_URL 环境变量，必须指向独立临时 PostgreSQL。
    输出：None；并发初始化、页面身份或双语 Route 不一致时失败。
    """
    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    await seed_database(factory)

    async def initialize(system_key: str) -> uuid.UUID:
        """
        初始化指定测试固定页。

        输入：system_key: str，contact 或 request-a-quote。
        输出：uuid.UUID，初始化后真实页面 ID。
        """
        async with factory() as session, session.begin():
            page = await initialize_products_site_page(
                session,
                system_key=system_key,
                actor_id=None,
            )
            return page.id

    contact_first, contact_second, rfq_first, rfq_second = await asyncio.gather(
        initialize("contact"),
        initialize("contact"),
        initialize("request-a-quote"),
        initialize("request-a-quote"),
    )
    assert contact_first == contact_second
    assert rfq_first == rfq_second
    assert contact_first != rfq_first

    async with factory() as session:
        routes = list(
            (
                await session.scalars(
                    select(ContentRoute)
                    .where(
                        ContentRoute.owner_type == "site_page",
                        ContentRoute.owner_id.in_({contact_first, rfq_first}),
                    )
                    .order_by(ContentRoute.path)
                )
            ).all()
        )
    assert {route.path for route in routes} == {
        "/zh-cn/contact/",
        "/en/contact/",
        "/zh-cn/request-a-quote/",
        "/en/request-a-quote/",
    }
    assert all(not route.active and not route.indexable for route in routes)
    await engine.dispose()


async def test_postgresql_public_search_matches_cjk_substrings_without_relaxing_gates() -> None:
    """
    验证真实 PostgreSQL 对中文标题和正文做字面子串补充匹配，并继续执行公开门禁。

    输入：TEST_DATABASE_URL 环境变量。

    输出：None；中文检索失效、特殊字符被当通配符或隐藏内容泄漏时测试失败。
    """
    from app.modules.discovery.public_collections import search_public_content

    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    unique = uuid.uuid4().hex
    async with factory() as session, session.begin():
        locale = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        assert locale is not None
        category = ProductCategory(slug=f"pg-cjk-category-{unique}", status="enabled")
        session.add(category)
        await session.flush()

        product_specs = (
            ("title", "精密氮化螺杆", "公开摘要", "published", True, True),
            ("body", "精密挤出部件", "采用氮化处理的公开说明", "published", True, True),
            ("draft", "旧试点氮化螺杆", "不得公开", "draft", False, False),
            ("closed", "关闭路由氮化螺杆", "不得公开", "published", False, False),
            ("noindex", "不可索引氮化螺杆", "不得公开", "published", True, False),
        )
        products: dict[str, Product] = {}
        for position, (marker, name, summary, status, active, indexable) in enumerate(
            product_specs, start=1
        ):
            product = Product(
                category_id=category.id,
                slug=f"pg-cjk-{marker}-{unique}",
                status="enabled",
                sort_order=position,
            )
            products[marker] = product
            session.add(product)
            await session.flush()
            session.add_all(
                [
                    ProductTranslation(
                        product_id=product.id,
                        locale_id=locale.id,
                        name=name,
                        short_description=summary,
                    ),
                    TranslationStatus(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        status=status,
                    ),
                    ContentPublication(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        status=status,
                    ),
                    ContentRoute(
                        owner_type="product",
                        owner_id=product.id,
                        locale_id=locale.id,
                        path=f"/zh-cn/products/{category.slug}/{product.slug}/",
                        is_canonical=True,
                        active=active,
                        indexable=indexable,
                    ),
                ]
            )

    async with factory() as session:
        payload = await search_public_content(session, "zh-cn", "氮化", ("product",), 100)
        literal_percent = await search_public_content(session, "zh-cn", "%", ("product",), 100)

    slugs = [item["slug"] for item in payload["groups"]["product"]]
    assert products["title"].slug in slugs
    assert products["body"].slug in slugs
    assert slugs.index(products["title"].slug) < slugs.index(products["body"].slug)
    assert products["draft"].slug not in slugs
    assert products["closed"].slug not in slugs
    assert products["noindex"].slug not in slugs
    assert literal_percent["groups"]["product"] == []
    await engine.dispose()


async def test_postgresql_public_search_covers_eight_types_and_privacy_gates() -> None:
    """
    验证真实 PostgreSQL 搜索的八类覆盖、统一分页及公开边界。

    输入：TEST_DATABASE_URL 环境变量，必须指向独立临时 PostgreSQL。

    输出：None；八类命中、跨类型分页、语言隔离、特殊字符或隐私门禁失效时测试失败。
    """
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
        Solution,
        SolutionTranslation,
        Technology,
        TechnologyTranslation,
    )
    from app.modules.company.models import (
        ManufacturingCapability,
        ManufacturingCapabilityTranslation,
    )
    from app.modules.discovery.models import SeoDocument
    from app.modules.discovery.public_collections import search_public_content

    engine = create_database_engine(TEST_DATABASE_URL or "")
    factory = create_session_factory(engine)
    unique = uuid.uuid4().hex
    needle = f"coverage{unique}"
    # 各类反向检索词使用独立随机值，避免长 UUID 的共同 trigram 触发合法模糊命中。
    blocked_needle = f"blocked{uuid.uuid4().hex}"
    private_needle = f"private{uuid.uuid4().hex}"
    zh_needle = f"氮化隔离{uuid.uuid4().hex}"

    async with factory() as session, session.begin():
        # 测试自行建立最小语言数据，不调用默认 Seed，也不依赖其他用例的执行顺序。
        en = await session.scalar(select(Locale).where(Locale.code == "en"))
        if en is None:
            has_default = bool(
                await session.scalar(
                    select(func.count()).select_from(Locale).where(Locale.is_default.is_(True))
                )
            )
            en = Locale(
                code="en",
                slug="en",
                name="English",
                native_name="English",
                is_default=not has_default,
                is_enabled=True,
            )
            session.add(en)
            await session.flush()
        zh = await session.scalar(select(Locale).where(Locale.code == "zh-CN"))
        if zh is None:
            zh = Locale(
                code="zh-CN",
                slug="zh-cn",
                name="Simplified Chinese",
                native_name="简体中文",
                is_default=False,
                is_enabled=True,
            )
            session.add(zh)
            await session.flush()
        disabled_locale = Locale(
            code=f"x-{unique[:8]}",
            slug=f"x-{unique[:8]}",
            name="Disabled test locale",
            native_name="禁用测试语言",
            is_default=False,
            is_enabled=False,
        )
        session.add(disabled_locale)

        category = ProductCategory(slug=f"coverage-category-{unique}", status="enabled")
        knowledge_category = KnowledgeCategory(
            slug=f"coverage-knowledge-{unique}", status="enabled"
        )
        author = AuthorExpert(
            slug=f"coverage-author-{unique}",
            status="enabled",
            role_type="author",
            identity_kind="person",
            is_real_person_verified=True,
            public_profile_enabled=True,
        )
        session.add_all([category, knowledge_category, author])
        await session.flush()
        session.add(
            AuthorExpertTranslation(
                author_expert_id=author.id,
                locale_id=en.id,
                name="Verified integration author",
                expertise_json=[],
            )
        )

        async def register_lifecycle(
            owner_type: str,
            owner_id: uuid.UUID,
            locale_id: uuid.UUID,
            path: str,
            *,
            translation_status: str = "published",
            publication_status: str = "published",
            active: bool = True,
            indexable: bool = True,
            is_canonical: bool = True,
            robots_index: bool | None = None,
            canonical_override: str | None = None,
        ) -> ContentPublication:
            """
            为搜索样本登记翻译、发布、路由和可选 SEO 门禁。

            输入：实体类型、实体ID、语言ID、公开路径及各门禁状态。
            输出：ContentPublication，本用例后续用于模拟已发布内容撤回。
            """
            publication = ContentPublication(
                owner_type=owner_type,
                owner_id=owner_id,
                locale_id=locale_id,
                status=publication_status,
            )
            session.add_all(
                [
                    TranslationStatus(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale_id,
                        status=translation_status,
                    ),
                    publication,
                    ContentRoute(
                        owner_type=owner_type,
                        owner_id=owner_id,
                        locale_id=locale_id,
                        path=path,
                        is_canonical=is_canonical,
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
                        robots_follow=True,
                        canonical_override=canonical_override,
                    )
                )
            return publication

        # 八类正向样本使用同一唯一检索词，便于证明全局计数与分页来自同一集合。
        product = Product(
            category_id=category.id,
            slug=f"coverage-product-{unique}",
            status="enabled",
        )
        material = Material(slug=f"coverage-material-{unique}", status="enabled")
        technology = Technology(slug=f"coverage-technology-{unique}", status="enabled")
        application = Application(slug=f"coverage-application-{unique}", status="enabled")
        solution = Solution(slug=f"coverage-solution-{unique}", status="enabled")
        capability = ManufacturingCapability(
            slug=f"coverage-capability-{unique}",
            capability_type="machining",
            status="enabled",
        )
        case_study = CaseStudy(
            slug=f"coverage-case-{unique}",
            status="enabled",
            client_name=private_needle,
            client_address=f"{private_needle} address",
        )
        article = KnowledgeArticle(
            category_id=knowledge_category.id,
            author_id=author.id,
            slug=f"coverage-article-{unique}",
            status="enabled",
        )
        session.add_all(
            [
                product,
                material,
                technology,
                application,
                solution,
                capability,
                case_study,
                article,
            ]
        )
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=product.id,
                    locale_id=en.id,
                    name=f"{needle} product",
                    short_description="Public product summary",
                ),
                MaterialTranslation(
                    material_id=material.id,
                    locale_id=en.id,
                    name=f"{needle} material",
                    definition="Public material summary",
                ),
                TechnologyTranslation(
                    technology_id=technology.id,
                    locale_id=en.id,
                    name=f"{needle} technology",
                    definition="Public technology summary",
                ),
                ApplicationTranslation(
                    application_id=application.id,
                    locale_id=en.id,
                    name=f"{needle} application",
                    description="Public application summary",
                ),
                SolutionTranslation(
                    solution_id=solution.id,
                    locale_id=en.id,
                    name=f"{needle} solution",
                    definition="Public solution summary",
                ),
                ManufacturingCapabilityTranslation(
                    capability_id=capability.id,
                    locale_id=en.id,
                    name=f"{needle} capability",
                    summary="Public capability summary",
                ),
                CaseStudyTranslation(
                    case_study_id=case_study.id,
                    locale_id=en.id,
                    title=f"{needle} case",
                    summary="Public anonymized case summary",
                ),
                KnowledgeArticleTranslation(
                    article_id=article.id,
                    locale_id=en.id,
                    title=f"{needle} article",
                    summary="Public article summary",
                    body_markdown="Public article body",
                ),
            ]
        )
        positive_paths = {
            "product": f"/en/products/{category.slug}/{product.slug}/",
            "material": f"/en/materials/{material.slug}/",
            "technology": f"/en/technologies/{technology.slug}/",
            "application": f"/en/applications/{application.slug}/",
            "solution": f"/en/solutions/{solution.slug}/",
            "manufacturing_capability": f"/en/capabilities/{capability.slug}/",
            "case_study": f"/en/case-studies/{case_study.slug}/",
            "knowledge_article": (
                f"/en/knowledge/{knowledge_category.slug}/{article.slug}/"
            ),
        }
        positive_entities = {
            "product": product,
            "material": material,
            "technology": technology,
            "application": application,
            "solution": solution,
            "manufacturing_capability": capability,
            "case_study": case_study,
            "knowledge_article": article,
        }
        positive_publications: dict[str, ContentPublication] = {}
        for owner_type, entity in positive_entities.items():
            positive_publications[owner_type] = await register_lifecycle(
                owner_type,
                entity.id,
                en.id,
                positive_paths[owner_type],
            )

        # 各类反向样本分别覆盖草稿、停用、归档、路由关闭、noindex 和非自规范。
        hidden_specs = (
            ("technology", "draft", "enabled", "draft", "draft", True, True, True, None, None),
            ("manufacturing_capability", "disabled", "disabled", "published", "published", True, True, True, None, None),
            ("technology", "archived", "enabled", "published", "archived", True, True, True, None, None),
            ("manufacturing_capability", "inactive", "enabled", "published", "published", False, True, True, None, None),
            ("technology", "route-noindex", "enabled", "published", "published", True, False, True, None, None),
            ("manufacturing_capability", "not-canonical", "enabled", "published", "published", True, True, False, None, None),
            ("technology", "robots-noindex", "enabled", "published", "published", True, True, True, False, None),
            ("manufacturing_capability", "wrong-canonical", "enabled", "published", "published", True, True, True, True, "https://example.invalid/private"),
        )
        for (
            owner_type,
            marker,
            entity_status,
            translation_status,
            publication_status,
            active,
            indexable,
            is_canonical,
            robots_index,
            canonical_override,
        ) in hidden_specs:
            if owner_type == "technology":
                hidden_entity = Technology(
                    slug=f"coverage-hidden-{marker}-{unique}", status=entity_status
                )
            else:
                hidden_entity = ManufacturingCapability(
                    slug=f"coverage-hidden-{marker}-{unique}",
                    capability_type="test",
                    status=entity_status,
                )
            session.add(hidden_entity)
            await session.flush()
            if owner_type == "technology":
                session.add(
                    TechnologyTranslation(
                        technology_id=hidden_entity.id,
                        locale_id=en.id,
                        name=f"{blocked_needle} {marker}",
                        definition="Must remain private",
                    )
                )
                hidden_path = f"/en/technologies/{hidden_entity.slug}/"
            else:
                session.add(
                    ManufacturingCapabilityTranslation(
                        capability_id=hidden_entity.id,
                        locale_id=en.id,
                        name=f"{blocked_needle} {marker}",
                        summary="Must remain private",
                    )
                )
                hidden_path = f"/en/capabilities/{hidden_entity.slug}/"
            await register_lifecycle(
                owner_type,
                hidden_entity.id,
                en.id,
                hidden_path,
                translation_status=translation_status,
                publication_status=publication_status,
                active=active,
                indexable=indexable,
                is_canonical=is_canonical,
                robots_index=robots_index,
                canonical_override=canonical_override,
            )

        # 同一中文词只登记中文翻译，证明英文查询不会读取其他语言内容。
        zh_technology = Technology(
            slug=f"coverage-zh-technology-{unique}", status="enabled"
        )
        session.add(zh_technology)
        await session.flush()
        session.add(
            TechnologyTranslation(
                technology_id=zh_technology.id,
                locale_id=zh.id,
                name=zh_needle,
                definition="仅用于语言隔离验证的公开工艺说明",
            )
        )
        await register_lifecycle(
            "technology",
            zh_technology.id,
            zh.id,
            f"/zh-cn/technologies/{zh_technology.slug}/",
        )

    async with factory() as session:
        first_page = await search_public_content(session, "en", needle, page_size=3, page=1)
        second_page = await search_public_content(session, "en", needle, page_size=3, page=2)
        third_page = await search_public_content(session, "en", needle, page_size=3, page=3)
        narrowed = await search_public_content(
            session,
            "en",
            needle,
            ("technology", "manufacturing_capability"),
            page_size=12,
        )
        special = await search_public_content(session, "en", "%_", page_size=12)
        blocked = await search_public_content(session, "en", blocked_needle, page_size=48)
        private = await search_public_content(session, "en", private_needle, page_size=48)
        language_leak = await search_public_content(session, "en", zh_needle, page_size=12)
        zh_result = await search_public_content(session, "zh-cn", zh_needle, page_size=12)
        with pytest.raises(AppException):
            await search_public_content(
                session, disabled_locale.slug, needle, page_size=12
            )

    expected_types = {
        "product",
        "material",
        "technology",
        "application",
        "solution",
        "manufacturing_capability",
        "case_study",
        "knowledge_article",
    }
    paged_items = first_page["items"] + second_page["items"] + third_page["items"]
    assert first_page["total"] == second_page["total"] == third_page["total"] == 8
    assert first_page["pages"] == second_page["pages"] == third_page["pages"] == 3
    assert [len(first_page["items"]), len(second_page["items"]), len(third_page["items"])] == [3, 3, 2]
    assert {item["type"] for item in paged_items} == expected_types
    assert len({(item["type"], item["slug"]) for item in paged_items}) == 8
    assert all(item["url"].startswith("/en/") for item in paged_items)
    assert all(item["name"] and item["summary"] for item in paged_items)
    assert narrowed["total"] == 2
    assert {item["type"] for item in narrowed["items"]} == {
        "technology",
        "manufacturing_capability",
    }
    assert special["total"] == 0
    assert blocked["total"] == 0
    assert private["total"] == 0
    assert language_leak["total"] == 0
    assert zh_result["total"] == 1
    assert zh_result["items"][0]["type"] == "technology"

    # 发布状态和业务状态变化后再次查询，确认撤回与停用立即从同一合格集合剔除。
    async with factory() as session, session.begin():
        publication = await session.get(
            ContentPublication,
            positive_publications["technology"].id,
        )
        capability_row = await session.get(ManufacturingCapability, capability.id)
        assert publication is not None and capability_row is not None
        publication.status = "archived"
        capability_row.status = "disabled"
    async with factory() as session:
        after_withdrawal = await search_public_content(
            session, "en", needle, page_size=12, page=1
        )
    assert after_withdrawal["total"] == 6
    assert {item["type"] for item in after_withdrawal["items"]}.isdisjoint(
        {"technology", "manufacturing_capability"}
    )
    await engine.dispose()
