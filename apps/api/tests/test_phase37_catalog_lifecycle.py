"""Phase 3.7 Catalog 翻译审核与统一发布闭环回归测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.catalog.schemas import CategoryCreate, ProductCreate, TranslationInput
from app.modules.catalog.services import create_category, create_product
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.localization.models import Locale
from app.modules.users import models as _user_models  # noqa: F401
from app.seed import ROLE_PERMISSION_MATRIX


@pytest.fixture
async def catalog_lifecycle_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建 Catalog 生命周期隔离数据库。

    输入：
        sqlite_database_url: str，测试专用 SQLite 数据库地址。

    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，预置启用的中英文语言。
    """
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


async def _create_product_sample(
    session: AsyncSession,
    *,
    slug: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """
    创建带英文草稿翻译的分类与产品。

    输入：
        session: AsyncSession，当前数据库会话。
        slug: str，产品及测试分类使用的唯一 slug。

    输出：
        tuple[uuid.UUID, uuid.UUID]，产品 ID 与英文 Locale ID。
    """
    locale = await session.scalar(select(Locale).where(Locale.code == "en"))
    assert locale is not None
    category = await create_category(
        session,
        CategoryCreate(
            slug=f"category-{slug}",
            translations=[TranslationInput(locale_id=locale.id, name="Injection Barrels")],
        ),
    )
    product = await create_product(
        session,
        ProductCreate(
            category_id=category.id,
            slug=slug,
            translations=[TranslationInput(locale_id=locale.id, name="Nitrided Barrel")],
        ),
    )
    await session.commit()
    return product.id, locale.id


def test_reviewer_seed_can_review_and_publish_catalog_without_update() -> None:
    """Reviewer 可审核/发布 Catalog，但不得获得 Catalog 创建、更新或归档权限。"""
    reviewer = ROLE_PERMISSION_MATRIX["reviewer"]
    assert {"catalog.read", "catalog.review", "catalog.publish"}.issubset(reviewer)
    assert not {"catalog.create", "catalog.update", "catalog.archive"}.intersection(reviewer)


def test_catalog_lifecycle_routes_are_registered() -> None:
    """OpenAPI 必须暴露 Catalog Translation Review 与 Publication Transition。"""
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/catalog/{resource}/{entity_id}/translations/{locale_id}/review" in paths
    assert (
        "/api/v1/catalog/{resource}/{entity_id}/publications/{locale_id}/{target_status}"
        in paths
    )


async def test_reviewer_can_review_and_publish_product_with_global_permissions(
    catalog_lifecycle_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer 使用实体权限和全局权限完成 Product draft → review → published。"""
    from app.api.v1 import catalog as catalog_api

    review_translation = getattr(catalog_api, "review_catalog_translation", None)
    transition_publication = getattr(catalog_api, "transition_catalog_publication", None)
    assert callable(review_translation)
    assert callable(transition_publication)

    async with catalog_lifecycle_factory() as session:
        product_id, locale_id = await _create_product_sample(session, slug="lifecycle-product")
        reviewer = SimpleNamespace(id=uuid.uuid4())
        reviewer_permissions = set(ROLE_PERMISSION_MATRIX["reviewer"])
        monkeypatch.setattr(
            catalog_api,
            "collect_authorization",
            lambda _user: (set(), reviewer_permissions),
        )

        reviewed = await review_translation(
            "products", product_id, locale_id, session, reviewer, None
        )
        assert reviewed.data == {
            "translation_status": "human_reviewed",
            "publication_status": "review",
        }

        published = await transition_publication(
            "products",
            product_id,
            locale_id,
            PublicationStatus.PUBLISHED,
            session,
            reviewer,
            None,
        )
        assert published.data == {"status": "published"}

        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product_id,
                TranslationStatus.locale_id == locale_id,
            )
        )
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product_id,
                ContentPublication.locale_id == locale_id,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "product",
                ContentRoute.owner_id == product_id,
                ContentRoute.locale_id == locale_id,
                ContentRoute.is_canonical.is_(True),
            )
        )
        assert status_row is not None and status_row.status == "published"
        assert publication is not None and publication.status == "published"
        assert route is not None and route.active is True and route.indexable is True


async def test_editor_update_permission_cannot_review_or_publish_product(
    catalog_lifecycle_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editor 的 Catalog/content update 权限不能替代审核与发布权限。"""
    from app.api.v1 import catalog as catalog_api

    review_translation = getattr(catalog_api, "review_catalog_translation", None)
    transition_publication = getattr(catalog_api, "transition_catalog_publication", None)
    assert callable(review_translation)
    assert callable(transition_publication)

    async with catalog_lifecycle_factory() as session:
        product_id, locale_id = await _create_product_sample(session, slug="editor-product")
        editor = SimpleNamespace(id=uuid.uuid4())
        editor_permissions = set(ROLE_PERMISSION_MATRIX["editor"])
        monkeypatch.setattr(
            catalog_api,
            "collect_authorization",
            lambda _user: (set(), editor_permissions),
        )

        with pytest.raises(AppException) as review_error:
            await review_translation(
                "products", product_id, locale_id, session, editor, None
            )
        assert review_error.value.status_code == 403

        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product_id,
                TranslationStatus.locale_id == locale_id,
            )
        )
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product_id,
                ContentPublication.locale_id == locale_id,
            )
        )
        assert status_row is not None and publication is not None
        status_row.status = "human_reviewed"
        publication.status = "review"
        await session.commit()

        with pytest.raises(AppException) as publish_error:
            await transition_publication(
                "products",
                product_id,
                locale_id,
                PublicationStatus.PUBLISHED,
                session,
                editor,
                None,
            )
        assert publish_error.value.status_code == 403
