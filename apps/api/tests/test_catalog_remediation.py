"""Phase 3.3 Remediation 的生命周期、索引、路由与修订回归测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog.models import (
    Product,
    ProductMaterial,
)
from app.modules.catalog.schemas import (
    CategoryCreate,
    EntityCreate,
    EntityUpdate,
    ProductCreate,
    ProductModelCreate,
    ProductUpdate,
    RelationUpdate,
    SpecificationDefinitionCreate,
    SpecificationGroupCreate,
    TranslationInput,
)
from app.modules.catalog.services import (
    archive_entity,
    create_category,
    create_core_entity,
    create_product,
    create_product_model,
    create_specification_definition,
    create_specification_group,
    replace_product_relations,
    update_core_entity,
    update_product,
)
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    TranslationStatus,
)
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.content.services.publication import transition_publication
from app.modules.localization.models import Locale
from app.modules.users import models as user_models  # noqa: F401

EN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ZH_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


@pytest.fixture
async def remediation_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建默认中文、英文 UUID 排序在前的隔离数据库。

    输入：sqlite_database_url，测试数据库地址。
    输出：async_sessionmaker，可验证业务逻辑不能依赖 Locale UUID 排序。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add_all(
            [
                Locale(
                    id=EN_ID,
                    code="en",
                    slug="en",
                    name="English",
                    native_name="English",
                    is_default=False,
                    is_enabled=True,
                    sort_order=20,
                ),
                Locale(
                    id=ZH_ID,
                    code="zh-CN",
                    slug="zh-cn",
                    name="Simplified Chinese",
                    native_name="简体中文",
                    is_default=True,
                    is_enabled=True,
                    sort_order=10,
                ),
            ]
        )
    yield factory
    await engine.dispose()


async def _create_product_fixture(
    session: AsyncSession,
    *,
    slug: str = "demo-product",
    include_en: bool = False,
) -> tuple[Product, uuid.UUID]:
    """
    创建中文分类与产品测试数据。

    输入：session、产品 slug、是否同时创建英文翻译。
    输出：(Product, category_id)，已写入当前事务的产品与分类标识。
    """
    category = await create_category(
        session,
        CategoryCreate(
            slug=f"category-{slug}",
            translations=[TranslationInput(locale_id=ZH_ID, name="产品分类")],
        ),
    )
    translations = [TranslationInput(locale_id=ZH_ID, name="演示产品")]
    if include_en:
        translations.append(TranslationInput(locale_id=EN_ID, name="Demo Product"))
    product = await create_product(
        session,
        ProductCreate(category_id=category.id, slug=slug, translations=translations),
    )
    return product, category.id


async def _publish_owner_locale(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> None:
    """
    通过统一发布服务将指定内容语言发布。

    输入：session、owner_type、owner_id、locale_id。
    输出：None；Publication、TranslationStatus 和 Route 同步进入公开状态。
    """
    publication = await session.scalar(
        select(ContentPublication).where(
            ContentPublication.owner_type == owner_type,
            ContentPublication.owner_id == owner_id,
            ContentPublication.locale_id == locale_id,
        )
    )
    translation = await session.scalar(
        select(TranslationStatus).where(
            TranslationStatus.owner_type == owner_type,
            TranslationStatus.owner_id == owner_id,
            TranslationStatus.locale_id == locale_id,
        )
    )
    route = await session.scalar(
        select(ContentRoute).where(
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == owner_id,
            ContentRoute.locale_id == locale_id,
            ContentRoute.is_canonical.is_(True),
        )
    )
    assert publication is not None and translation is not None and route is not None
    translation.status = "human_reviewed"
    translation.reviewed_by = uuid.uuid4()
    publication.status = "review"
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


async def test_published_translation_edit_withdraws_public_index(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """已发布正文修改后必须回到草稿并立即退出统一索引源。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        await _publish_owner_locale(session, "product", product.id, ZH_ID)
        assert len(await list_indexable_routes(session)) == 1
        await update_product(
            session,
            product.id,
            ProductUpdate(
                translations=[
                    TranslationInput(
                        locale_id=ZH_ID,
                        name="修改后的产品",
                        fields={"description": "新正文"},
                    )
                ]
            ),
        )
        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product.id,
                TranslationStatus.locale_id == ZH_ID,
            )
        )
        publication = await session.scalar(
            select(ContentPublication).where(ContentPublication.owner_id == product.id)
        )
        route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_id == product.id))
        assert status_row is not None and status_row.status == "draft"
        assert status_row.reviewed_by is None and status_row.published_at is None
        assert publication is not None and publication.status == "review"
        assert route is not None and route.active is False and route.indexable is False
        assert await list_indexable_routes(session) == []
        status_row.status = "human_reviewed"
        status_row.reviewed_by = uuid.uuid4()
        await transition_publication(
            session,
            publication=publication,
            translation=status_row,
            route=route,
            target_status=PublicationStatus.PUBLISHED,
            actor_permissions={"content.publish"},
            actor_id=None,
        )
        assert [item.path for item in await list_indexable_routes(session)] == [route.path]


async def test_human_reviewed_translation_edit_clears_reviewer(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """人工审核正文再次修改后必须回到 draft 并清空审核人。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        status_row = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product.id,
                TranslationStatus.locale_id == ZH_ID,
            )
        )
        assert status_row is not None
        status_row.status = "human_reviewed"
        status_row.reviewed_by = uuid.uuid4()
        await update_product(
            session,
            product.id,
            ProductUpdate(
                translations=[TranslationInput(locale_id=ZH_ID, name="再次修改的正文")]
            ),
        )
        assert status_row.status == "draft"
        assert status_row.reviewed_by is None


async def test_first_missing_locale_translation_creates_lifecycle_idempotently(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """首次补英文翻译时必须幂等创建 draft Publication 与 canonical Route。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        update = ProductUpdate(
            translations=[TranslationInput(locale_id=EN_ID, name="English Product")]
        )
        await update_product(session, product.id, update)
        await update_product(session, product.id, update)
        publication_count = await session.scalar(
            select(func.count())
            .select_from(ContentPublication)
            .where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product.id,
                ContentPublication.locale_id == EN_ID,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "product",
                ContentRoute.owner_id == product.id,
                ContentRoute.locale_id == EN_ID,
                ContentRoute.is_canonical.is_(True),
            )
        )
        assert publication_count == 1
        assert route is not None and route.path == "/en/products/category-demo-product/demo-product/"
        assert route.active is False and route.indexable is False


async def test_retired_product_and_disabled_material_are_not_indexable(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """业务实体退役或停用时必须归档发布记录并退出索引。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        material = await create_core_entity(
            session,
            "material",
            EntityCreate(
                slug="hardened-steel",
                translations=[TranslationInput(locale_id=ZH_ID, name="合金钢")],
            ),
        )
        await _publish_owner_locale(session, "product", product.id, ZH_ID)
        await _publish_owner_locale(session, "material", material.id, ZH_ID)
        assert len(await list_indexable_routes(session)) == 2
        await archive_entity(session, "product", product.id)
        await update_core_entity(
            session,
            "material",
            material.id,
            EntityUpdate(status="disabled"),
        )
        assert await list_indexable_routes(session) == []
        publications = list(
            (
                await session.scalars(
                    select(ContentPublication).where(
                        ContentPublication.owner_id.in_([product.id, material.id])
                    )
                )
            ).all()
        )
        assert {publication.status for publication in publications} == {"archived"}


async def test_revisions_use_default_or_actual_translation_locale(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Master Revision 使用默认中文，英文正文 Revision 使用实际英文 Locale。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session, include_en=True)
        first_revision = await session.scalar(
            select(ContentRevision)
            .where(ContentRevision.owner_type == "product", ContentRevision.owner_id == product.id)
            .order_by(ContentRevision.created_at, ContentRevision.id)
        )
        assert first_revision is not None and first_revision.locale_id == ZH_ID
        await update_product(
            session,
            product.id,
            ProductUpdate(
                translations=[
                    TranslationInput(
                        locale_id=EN_ID,
                        name="Updated English Product",
                        fields={"description": "Changed English body"},
                    )
                ]
            ),
        )
        latest_revision = await session.scalar(
            select(ContentRevision)
            .where(ContentRevision.owner_type == "product", ContentRevision.owner_id == product.id)
            .order_by(ContentRevision.created_at.desc(), ContentRevision.revision_no.desc())
        )
        assert latest_revision is not None and latest_revision.locale_id == EN_ID
        assert latest_revision.snapshot_jsonb["translation"]["name"] == "Updated English Product"
        assert latest_revision.snapshot_jsonb["translation"]["description"] == "Changed English body"


async def test_draft_category_change_updates_route_and_published_change_is_rejected(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """草稿产品换分类同步 Route；已发布产品换分类返回冻结冲突。"""
    async with remediation_session_factory() as session, session.begin():
        product, original_category_id = await _create_product_fixture(session)
        target = await create_category(
            session,
            CategoryCreate(
                slug="new-category",
                translations=[TranslationInput(locale_id=ZH_ID, name="新分类")],
            ),
        )
        await update_product(session, product.id, ProductUpdate(category_id=target.id))
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "product",
                ContentRoute.owner_id == product.id,
                ContentRoute.locale_id == ZH_ID,
            )
        )
        assert route is not None and route.path == "/zh-cn/products/new-category/demo-product/"
        await _publish_owner_locale(session, "product", product.id, ZH_ID)
        with pytest.raises(AppException) as raised:
            await update_product(
                session,
                product.id,
                ProductUpdate(category_id=original_category_id),
            )
        assert raised.value.status_code == 409
        assert raised.value.code == "published_category_frozen"


async def test_product_model_and_specification_metadata_have_no_public_lifecycle(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ProductModel 与规格元数据保留翻译/修订/审计，但不创建公开发布或路由。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        model = await create_product_model(
            session,
            product.id,
            ProductModelCreate(
                model_code="DM-001",
                translations=[TranslationInput(locale_id=ZH_ID, name="型号一")],
            ),
        )
        group = await create_specification_group(
            session,
            SpecificationGroupCreate(
                code="dimensions",
                translations=[TranslationInput(locale_id=ZH_ID, name="尺寸")],
            ),
        )
        definition = await create_specification_definition(
            session,
            SpecificationDefinitionCreate(
                group_id=group.id,
                code="diameter",
                value_type="number",
                translations=[TranslationInput(locale_id=ZH_ID, name="直径")],
            ),
        )
        internal_ids = [model.id, group.id, definition.id]
        publication_count = await session.scalar(
            select(func.count())
            .select_from(ContentPublication)
            .where(ContentPublication.owner_id.in_(internal_ids))
        )
        route_count = await session.scalar(
            select(func.count()).select_from(ContentRoute).where(ContentRoute.owner_id.in_(internal_ids))
        )
        revision_count = await session.scalar(
            select(func.count())
            .select_from(ContentRevision)
            .where(ContentRevision.owner_id.in_(internal_ids))
        )
        assert publication_count == 0
        assert route_count == 0
        assert revision_count == 3


async def test_relation_revision_contains_actual_relation_ids(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """产品关系变更 Revision 必须保存实际关联 ID，而非只有字段名称。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        material = await create_core_entity(
            session,
            "material",
            EntityCreate(slug="tool-steel", translations=[]),
        )
        await replace_product_relations(
            session,
            product.id,
            RelationUpdate(material_ids=[material.id]),
        )
        relation = await session.scalar(
            select(ProductMaterial).where(ProductMaterial.product_id == product.id)
        )
        latest_revision = await session.scalar(
            select(ContentRevision)
            .where(ContentRevision.owner_type == "product", ContentRevision.owner_id == product.id)
            .order_by(ContentRevision.created_at.desc(), ContentRevision.revision_no.desc())
        )
        assert relation is not None
        assert latest_revision is not None
        assert latest_revision.snapshot_jsonb["relations"]["material_ids"] == [str(material.id)]


async def test_indexable_source_requires_translation_publication_route_locale_and_business_status(
    remediation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """统一索引源必须同时验证七项冻结条件。"""
    async with remediation_session_factory() as session, session.begin():
        product, _ = await _create_product_fixture(session)
        await _publish_owner_locale(session, "product", product.id, ZH_ID)
        translation_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product.id,
                TranslationStatus.locale_id == ZH_ID,
            )
        )
        assert translation_status is not None
        translation_status.status = "draft"
        assert await list_indexable_routes(session) == []
        translation_status.status = "published"
        product.status = "disabled"
        assert await list_indexable_routes(session) == []
