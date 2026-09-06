"""Structured Core Catalog 的事务服务、树校验、规格校验与关系维护。"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.catalog.enums import SpecificationValueType
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
    ProductModel,
    ProductModelTranslation,
    ProductSolution,
    ProductSpecValue,
    ProductTechnology,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    SpecificationDefinition,
    SpecificationDefinitionTranslation,
    SpecificationGroup,
    SpecificationGroupTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    EntityCreate,
    EntityUpdate,
    ProductCreate,
    ProductModelCreate,
    ProductModelUpdate,
    ProductUpdate,
    RelationUpdate,
    SpecificationDefinitionCreate,
    SpecificationDefinitionUpdate,
    SpecificationGroupCreate,
    SpecificationGroupUpdate,
    SpecificationValueCreate,
    SpecificationValueUpdate,
    TranslationInput,
)
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import invalidate_publication_after_translation_edit
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import create_content_route
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset

_ENTITY_CONFIG: dict[str, tuple[type, type, str, str]] = {
    "product_category": (ProductCategory, ProductCategoryTranslation, "category_id", "products"),
    "product": (Product, ProductTranslation, "product_id", "products"),
    "product_model": (ProductModel, ProductModelTranslation, "product_model_id", "models"),
    "material": (Material, MaterialTranslation, "material_id", "materials"),
    "technology": (Technology, TechnologyTranslation, "technology_id", "technologies"),
    "application": (Application, ApplicationTranslation, "application_id", "applications"),
    "solution": (Solution, SolutionTranslation, "solution_id", "solutions"),
    "specification_group": (SpecificationGroup, SpecificationGroupTranslation, "group_id", "specification-groups"),
    "specification_definition": (SpecificationDefinition, SpecificationDefinitionTranslation, "definition_id", "specifications"),
}

# 只有这些主实体拥有独立公开页面；型号和规格元数据只随 Product Detail 输出。
PUBLIC_OWNER_TYPES = frozenset(
    {
        "product_category",
        "product",
        "material",
        "technology",
        "application",
        "solution",
    }
)


async def _get_default_locale(session: AsyncSession) -> Locale:
    """
    获取业务默认语言，禁止使用 UUID 排序推断默认语言。

    输入：session，当前数据库会话。
    输出：Locale，明确标记 `is_default=true` 的语言。
    """
    locale = await session.scalar(select(Locale).where(Locale.is_default.is_(True)))
    if locale is None:
        raise AppException(409, "default_locale_required", "必须配置一个默认语言")
    return locale


async def _validate_primary_media(
    session: AsyncSession,
    media_id: uuid.UUID | None,
) -> None:
    """
    验证产品主媒体可以通过公开媒体代理交付。

    输入：
        session: AsyncSession，当前数据库会话。
        media_id: uuid.UUID | None，可空的媒体资产ID。

    输出：
        None，合法或未设置时返回；非法媒体抛出稳定业务异常。
    """
    if media_id is None:
        return
    asset = await session.get(MediaAsset, media_id)
    if (
        asset is None
        or asset.visibility != "public"
        or asset.storage_bucket != "public-media"
        or asset.upload_status != "ready"
    ):
        raise AppException(
            422,
            "product_primary_media_invalid",
            "产品主媒体必须是可用的公开媒体",
        )


def _entity_snapshot(entity: Any) -> dict[str, Any]:
    """
    构造不含自动时间字段的主实体快照。

    输入：entity，SQLAlchemy 主实体。
    输出：dict，适合保存到 Revision 的 JSON 数据。
    """
    return {
        column.name: getattr(entity, column.name)
        for column in entity.__table__.columns
        if column.name not in {"created_at", "updated_at"}
    }


def _translation_snapshot(translation: Any) -> dict[str, Any]:
    """
    构造指定语言正文的完整 Revision 快照。

    输入：translation，翻译 ORM 实体。
    输出：dict，包含实际修改后的所有正文列。
    """
    return {
        column.name: getattr(translation, column.name)
        for column in translation.__table__.columns
        if column.name not in {"created_at", "updated_at"}
    }


def _route_path(owner_type: str, entity: Any, locale: Locale, category_slug: str | None = None) -> str:
    """根据实体类型构造稳定的语言前缀 canonical 路径。"""
    # ProductModel 使用 model_code，其余实体优先使用稳定 slug，再回退到 code。
    entity_slug = getattr(
        entity,
        "slug",
        getattr(entity, "code", getattr(entity, "model_code", None)),
    )
    # code/model_code 不是 URL slug，统一转为稳定小写 kebab-case 路由段。
    entity_slug = re.sub(r"[^a-z0-9]+", "-", str(entity_slug).strip().lower()).strip("-")
    if not entity_slug:
        raise AppException(409, "route_slug_required", "实体必须能生成稳定路由段")
    if owner_type == "product":
        if not category_slug:
            raise AppException(409, "category_required", "产品路由需要分类 slug")
        return f"/{locale.slug}/products/{category_slug}/{entity_slug}/"
    if owner_type == "product_category":
        return f"/{locale.slug}/products/{entity_slug}/"
    return f"/{locale.slug}/{_ENTITY_CONFIG[owner_type][3]}/{entity_slug}/"


async def _write_entity_content(
    session: AsyncSession,
    *,
    owner_type: str,
    entity: Any,
    translation_model: type,
    owner_field: str,
    translations: Iterable[TranslationInput],
    category_slug: str | None = None,
    actor_id: uuid.UUID | None = None,
    action: str,
) -> None:
    """
    在当前事务内创建翻译状态、Revision，并仅为公开实体创建发布与路由。

    输入：实体配置、翻译集合、可选分类 slug、操作者和审计动作。
    输出：None；全部内容生命周期记录加入当前事务。
    """
    translation_items = list(translations)
    translation_map = {item.locale_id: item for item in translation_items}
    if len(translation_map) != len(translation_items):
        raise AppException(409, "duplicate_translation", "同一请求不能重复提交语言翻译")
    locales = list((await session.scalars(select(Locale).order_by(Locale.sort_order, Locale.code))).all())
    if not locales:
        raise AppException(409, "locale_required", "至少需要一个已配置语言")
    default_locale = await _get_default_locale(session)
    for locale in locales:
        item = translation_map.get(locale.id)
        translation_status = TranslationStatus(
            owner_type=owner_type,
            owner_id=entity.id,
            locale_id=locale.id,
            source_locale_id=default_locale.id,
            status="draft" if item else "missing",
        )
        session.add(translation_status)
        if item is None:
            continue
        if not locale.is_enabled:
            raise AppException(409, "locale_disabled", "不能向停用语言写入公开内容")
        values = {owner_field: entity.id, "locale_id": locale.id, "name": item.name}
        allowed = set(translation_model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at"}
        values.update({key: value for key, value in item.fields.items() if key in allowed})
        session.add(translation_model(**values))
        if owner_type in PUBLIC_OWNER_TYPES:
            await ensure_locale_content_lifecycle(
                session,
                owner_type=owner_type,
                entity=entity,
                locale=locale,
                category_slug=category_slug,
            )
    await session.flush()
    await store_revision(
        session,
        owner_type,
        entity.id,
        default_locale.id,
        jsonable_encoder(
            {
                "master": _entity_snapshot(entity),
                "translations": [item.model_dump(mode="json") for item in translation_map.values()],
            }
        ),
        actor_id,
    )
    write_audit_log(session, action=action, target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={"slug": getattr(entity, "slug", getattr(entity, "code", None))})


async def ensure_locale_content_lifecycle(
    session: AsyncSession,
    *,
    owner_type: str,
    entity: Any,
    locale: Locale,
    category_slug: str | None = None,
) -> tuple[ContentPublication, ContentRoute]:
    """
    幂等保证公开实体指定语言具备草稿 Publication 与 canonical Route。

    输入：session、owner_type、entity、locale，以及 Product 所需 category_slug。
    输出：(ContentPublication, ContentRoute)，已存在则复用，不存在则创建。
    """
    if owner_type not in PUBLIC_OWNER_TYPES:
        raise AppException(409, "public_lifecycle_not_supported", "内部实体没有独立公开生命周期")
    publication = await session.scalar(
        select(ContentPublication)
        .where(
            ContentPublication.owner_type == owner_type,
            ContentPublication.owner_id == entity.id,
            ContentPublication.locale_id == locale.id,
        )
        .with_for_update()
    )
    if publication is None:
        publication = ContentPublication(
            owner_type=owner_type,
            owner_id=entity.id,
            locale_id=locale.id,
            status="draft",
        )
        session.add(publication)
    route = await session.scalar(
        select(ContentRoute)
        .where(
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == entity.id,
            ContentRoute.locale_id == locale.id,
            ContentRoute.is_canonical.is_(True),
        )
        .with_for_update()
    )
    if route is None:
        route = await create_content_route(
            session,
            owner_type,
            entity.id,
            locale,
            _route_path(owner_type, entity, locale, category_slug),
        )
    route.active = False
    route.indexable = False
    await session.flush()
    return publication, route


async def _record_entity_revision(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    actor_id: uuid.UUID | None,
    extra: dict[str, Any] | None = None,
) -> None:
    """为更新、关系或规格变更写入默认语言快照。"""
    locale = await _get_default_locale(session)
    snapshot: dict[str, Any] = {
        "master": _entity_snapshot(entity)
    }
    if extra:
        snapshot.update(extra)
    await store_revision(
        session,
        owner_type,
        entity.id,
        locale.id,
        jsonable_encoder(snapshot),
        actor_id,
    )


async def _withdraw_entity_from_publication(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
) -> None:
    """
    将停用或退役业务实体的所有语言归档并关闭公开路由。

    输入：session、owner_type、owner_id。
    输出：None；Publication 变为 archived，Route 变为 inactive/noindex。
    """
    publications = list(
        (
            await session.scalars(
                select(ContentPublication)
                .where(
                    ContentPublication.owner_type == owner_type,
                    ContentPublication.owner_id == owner_id,
                )
                .with_for_update()
            )
        ).all()
    )
    for publication in publications:
        publication.status = "archived"
        publication.scheduled_at = None
    routes = list(
        (
            await session.scalars(
                select(ContentRoute)
                .where(
                    ContentRoute.owner_type == owner_type,
                    ContentRoute.owner_id == owner_id,
                )
                .with_for_update()
            )
        ).all()
    )
    for route in routes:
        route.active = False
        route.indexable = False


async def _update_product_draft_routes(
    session: AsyncSession,
    product: Product,
    category_slug: str,
) -> None:
    """
    在 Product 尚未发布时同步更新已有 canonical Route 路径。

    输入：session、product、目标分类 slug。
    输出：None；所有已存在语言的草稿规范路径被原地更新，不创建 Redirect。
    """
    routes = list(
        (
            await session.scalars(
                select(ContentRoute)
                .where(
                    ContentRoute.owner_type == "product",
                    ContentRoute.owner_id == product.id,
                    ContentRoute.is_canonical.is_(True),
                )
                .with_for_update()
            )
        ).all()
    )
    for route in routes:
        locale = await session.get(Locale, route.locale_id)
        if locale is None:
            raise AppException(409, "route_locale_missing", "产品路由关联语言不存在")
        path = _route_path("product", product, locale, category_slug)
        conflict = await session.scalar(
            select(ContentRoute.id).where(ContentRoute.path == path, ContentRoute.id != route.id)
        )
        if conflict is not None:
            raise AppException(409, "route_conflict", "目标产品路径已被占用")
        route.path = path
        route.active = False
        route.indexable = False


async def _check_category_cycle(session: AsyncSession, category_id: uuid.UUID, parent_id: uuid.UUID | None) -> None:
    """锁定父链并拒绝 self-parent 或任何可达循环。"""
    visited: set[uuid.UUID] = {category_id}
    current = parent_id
    while current is not None:
        if current in visited:
            raise AppException(409, "category_cycle", "分类 parent_id 会形成循环")
        visited.add(current)
        parent = await session.scalar(select(ProductCategory).where(ProductCategory.id == current).with_for_update())
        if parent is None:
            raise AppException(404, "parent_category_not_found", "父分类不存在")
        current = parent.parent_id


async def create_category(session: AsyncSession, payload: CategoryCreate, actor_id: uuid.UUID | None = None) -> ProductCategory:
    """创建分类并初始化其多语言内容生命周期。"""
    if payload.parent_id is not None:
        await _check_category_cycle(session, uuid.uuid4(), payload.parent_id)
    category = ProductCategory(parent_id=payload.parent_id, slug=payload.slug, status=payload.status, sort_order=payload.sort_order)
    session.add(category)
    await session.flush()
    await _write_entity_content(session, owner_type="product_category", entity=category, translation_model=ProductCategoryTranslation, owner_field="category_id", translations=payload.translations, actor_id=actor_id, action="product_category.create")
    return category


async def update_category(session: AsyncSession, category_id: uuid.UUID, payload: CategoryUpdate, actor_id: uuid.UUID | None = None) -> ProductCategory:
    """更新分类，检测 parent 循环并对已发布 slug 提供保护。"""
    category = await session.scalar(select(ProductCategory).where(ProductCategory.id == category_id).with_for_update())
    if category is None:
        raise AppException(404, "category_not_found", "产品分类不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    if "parent_id" in changes:
        await _check_category_cycle(session, category.id, changes["parent_id"])
    if changes.get("slug") and changes["slug"] != category.slug:
        published = await session.scalar(select(ContentPublication.id).where(ContentPublication.owner_type == "product_category", ContentPublication.owner_id == category.id, ContentPublication.status == "published"))
        if published:
            raise AppException(409, "published_slug_frozen", "已发布分类的 slug 不能直接修改")
    for key, value in changes.items():
        setattr(category, key, value)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            "product_category",
            category,
            ProductCategoryTranslation,
            "category_id",
            payload.translations,
            actor_id=actor_id,
        )
    if category.status in {"disabled", "retired"}:
        await _withdraw_entity_from_publication(session, "product_category", category.id)
    write_audit_log(session, action="product_category.update", target_type="product_category", user_id=actor_id, target_id=str(category.id), metadata={"fields": sorted(changes)})
    await session.flush()
    if changes:
        await _record_entity_revision(session, "product_category", category, actor_id)
    return category


async def _upsert_translations(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    model: type,
    owner_field: str,
    translations: list[TranslationInput],
    *,
    actor_id: uuid.UUID | None = None,
    category_slug: str | None = None,
) -> None:
    """
    更新翻译、撤销旧审核/发布状态，并为首次翻译补齐公开生命周期。

    输入：session、owner 配置、翻译集合、操作者，以及 Product 分类 slug。
    输出：None；每个修改语言写入独立 Revision 与 Audit。
    """
    if len({item.locale_id for item in translations}) != len(translations):
        raise AppException(409, "duplicate_translation", "同一请求不能重复提交语言翻译")
    default_locale = await _get_default_locale(session)
    for item in translations:
        locale = await session.scalar(select(Locale).where(Locale.id == item.locale_id))
        if locale is None or not locale.is_enabled:
            raise AppException(409, "locale_disabled", "不能向停用或不存在的语言写入内容")
        existing = await session.scalar(select(model).where(getattr(model, owner_field) == entity.id, model.locale_id == item.locale_id).with_for_update())
        values = {"name": item.name}
        allowed = set(model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at", "name"}
        values.update({key: value for key, value in item.fields.items() if key in allowed})
        if existing is None:
            existing = model(**{owner_field: entity.id, "locale_id": item.locale_id, **values})
            session.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == entity.id, TranslationStatus.locale_id == item.locale_id).with_for_update())
        if status is None:
            status = TranslationStatus(
                owner_type=owner_type,
                owner_id=entity.id,
                locale_id=item.locale_id,
                source_locale_id=default_locale.id,
                status="draft",
            )
            session.add(status)
        status.source_locale_id = default_locale.id
        status.translated_by = actor_id

        if owner_type in PUBLIC_OWNER_TYPES:
            publication, route = await ensure_locale_content_lifecycle(
                session,
                owner_type=owner_type,
                entity=entity,
                locale=locale,
                category_slug=category_slug,
            )
            await invalidate_publication_after_translation_edit(
                session,
                publication=publication,
                translation=status,
                route=route,
                actor_id=actor_id,
            )
        else:
            status.status = "draft"
            status.reviewed_by = None
            status.published_at = None

        await session.flush()
        await store_revision(
            session,
            owner_type,
            entity.id,
            item.locale_id,
            jsonable_encoder(
                {
                    "master": _entity_snapshot(entity),
                    "translation": _translation_snapshot(existing),
                }
            ),
            actor_id,
        )
        write_audit_log(
            session,
            action="translation.edited",
            target_type=owner_type,
            user_id=actor_id,
            target_id=str(entity.id),
            metadata={"locale_id": str(item.locale_id)},
        )


async def create_product(session: AsyncSession, payload: ProductCreate, actor_id: uuid.UUID | None = None) -> Product:
    """创建产品并使用所属分类 slug 注册所有提供语言的路由。"""
    category = await session.get(ProductCategory, payload.category_id)
    if category is None or category.status != "enabled":
        raise AppException(404, "category_not_found", "产品分类不存在或未启用")
    await _validate_primary_media(session, payload.primary_media_id)
    product = Product(
        category_id=payload.category_id,
        code=payload.code,
        slug=payload.slug,
        status=payload.status,
        featured=payload.featured,
        sort_order=payload.sort_order,
        primary_media_id=payload.primary_media_id,
    )
    session.add(product)
    await session.flush()
    await _write_entity_content(session, owner_type="product", entity=product, translation_model=ProductTranslation, owner_field="product_id", translations=payload.translations, category_slug=category.slug, actor_id=actor_id, action="product.create")
    return product


async def update_product(session: AsyncSession, product_id: uuid.UUID, payload: ProductUpdate, actor_id: uuid.UUID | None = None) -> Product:
    """更新产品主字段/翻译，并保持 Category 与 draft canonical Route 一致。"""
    product = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise AppException(404, "product_not_found", "产品不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    if "primary_media_id" in changes:
        await _validate_primary_media(session, changes["primary_media_id"])
    target_category_id = changes.get("category_id", product.category_id)
    target_category = await session.get(ProductCategory, target_category_id)
    if target_category is None or target_category.status != "enabled":
        raise AppException(404, "category_not_found", "目标分类不存在或未启用")
    category_changed = target_category_id != product.category_id
    slug_changed = bool(changes.get("slug") and changes["slug"] != product.slug)
    if category_changed or slug_changed:
        published = await session.scalar(
            select(ContentPublication.id).where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product.id,
                ContentPublication.status == "published",
            )
        )
        if published and category_changed:
            raise AppException(409, "published_category_frozen", "已发布产品不能直接更换分类")
        if published and slug_changed:
            raise AppException(409, "published_slug_frozen", "已发布产品的 slug 不能直接修改")
    for key, value in changes.items():
        setattr(product, key, value)
    if category_changed or slug_changed:
        await _update_product_draft_routes(session, product, target_category.slug)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            "product",
            product,
            ProductTranslation,
            "product_id",
            payload.translations,
            actor_id=actor_id,
            category_slug=target_category.slug,
        )
    if product.status in {"disabled", "retired"}:
        await _withdraw_entity_from_publication(session, "product", product.id)
    write_audit_log(session, action="product.update", target_type="product", user_id=actor_id, target_id=str(product.id), metadata={"fields": sorted(changes)})
    await session.flush()
    if changes:
        await _record_entity_revision(session, "product", product, actor_id)
    return product


async def create_product_model(session: AsyncSession, product_id: uuid.UUID, payload: ProductModelCreate, actor_id: uuid.UUID | None = None) -> ProductModel:
    """创建产品范围内唯一的型号并初始化翻译生命周期。"""
    if await session.get(Product, product_id) is None:
        raise AppException(404, "product_not_found", "产品不存在")
    model = ProductModel(product_id=product_id, model_code=payload.model_code.strip(), status=payload.status, sort_order=payload.sort_order)
    session.add(model)
    await session.flush()
    await _write_entity_content(session, owner_type="product_model", entity=model, translation_model=ProductModelTranslation, owner_field="product_model_id", translations=payload.translations, actor_id=actor_id, action="product_model.create")
    return model


async def update_product_model(session: AsyncSession, model_id: uuid.UUID, payload: ProductModelUpdate, actor_id: uuid.UUID | None = None) -> ProductModel:
    """更新或退役产品型号。"""
    model = await session.scalar(select(ProductModel).where(ProductModel.id == model_id).with_for_update())
    if model is None:
        raise AppException(404, "product_model_not_found", "产品型号不存在")
    for key, value in payload.model_dump(exclude_unset=True, exclude={"translations"}).items():
        setattr(model, key, value.strip() if key == "model_code" and isinstance(value, str) else value)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            "product_model",
            model,
            ProductModelTranslation,
            "product_model_id",
            payload.translations,
            actor_id=actor_id,
        )
    write_audit_log(session, action="product_model.update", target_type="product_model", user_id=actor_id, target_id=str(model.id), metadata={})
    await session.flush()
    if payload.model_dump(exclude_unset=True, exclude={"translations"}):
        await _record_entity_revision(session, "product_model", model, actor_id)
    return model


async def create_core_entity(session: AsyncSession, owner_type: str, payload: EntityCreate, actor_id: uuid.UUID | None = None) -> Any:
    """创建 Material/Technology/Application/Solution 通用主实体。"""
    model, translation_model, owner_field, _ = _ENTITY_CONFIG[owner_type]
    entity = model(slug=payload.slug, status=payload.status, featured=payload.featured, sort_order=payload.sort_order)
    session.add(entity)
    await session.flush()
    await _write_entity_content(session, owner_type=owner_type, entity=entity, translation_model=translation_model, owner_field=owner_field, translations=payload.translations, actor_id=actor_id, action=f"{owner_type}.create")
    return entity


async def update_core_entity(session: AsyncSession, owner_type: str, entity_id: uuid.UUID, payload: EntityUpdate, actor_id: uuid.UUID | None = None) -> Any:
    """更新或退役 Material/Technology/Application/Solution。"""
    model, translation_model, owner_field, _ = _ENTITY_CONFIG[owner_type]
    entity = await session.scalar(select(model).where(model.id == entity_id).with_for_update())
    if entity is None:
        raise AppException(404, f"{owner_type}_not_found", "结构化实体不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    if changes.get("slug") and changes["slug"] != entity.slug:
        published = await session.scalar(select(ContentPublication.id).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == entity.id, ContentPublication.status == "published"))
        if published:
            raise AppException(409, "published_slug_frozen", "已发布实体的 slug 不能直接修改")
    for key, value in changes.items():
        setattr(entity, key, value)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            owner_type,
            entity,
            translation_model,
            owner_field,
            payload.translations,
            actor_id=actor_id,
        )
    if entity.status in {"disabled", "retired"}:
        await _withdraw_entity_from_publication(session, owner_type, entity.id)
    write_audit_log(session, action=f"{owner_type}.update", target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={"fields": sorted(changes)})
    await session.flush()
    if changes:
        await _record_entity_revision(session, owner_type, entity, actor_id)
    return entity


async def archive_entity(session: AsyncSession, owner_type: str, entity_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> Any:
    """用 retired 业务状态归档实体，不物理删除历史数据。"""
    model = _ENTITY_CONFIG[owner_type][0]
    entity = await session.scalar(select(model).where(model.id == entity_id).with_for_update())
    if entity is None:
        raise AppException(404, f"{owner_type}_not_found", "结构化实体不存在")
    entity.status = "retired"
    if owner_type in PUBLIC_OWNER_TYPES:
        await _withdraw_entity_from_publication(session, owner_type, entity.id)
    write_audit_log(session, action=f"{owner_type}.archive", target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={})
    await session.flush()
    await _record_entity_revision(session, owner_type, entity, actor_id)
    return entity


async def create_specification_group(session: AsyncSession, payload: SpecificationGroupCreate, actor_id: uuid.UUID | None = None) -> SpecificationGroup:
    """创建规格分组及其翻译生命周期。"""
    group = SpecificationGroup(code=payload.code, status=payload.status, sort_order=payload.sort_order)
    session.add(group)
    await session.flush()
    await _write_entity_content(session, owner_type="specification_group", entity=group, translation_model=SpecificationGroupTranslation, owner_field="group_id", translations=payload.translations, actor_id=actor_id, action="specification.update")
    return group


async def update_specification_group(
    session: AsyncSession,
    group_id: uuid.UUID,
    payload: SpecificationGroupUpdate,
    actor_id: uuid.UUID | None = None,
) -> SpecificationGroup:
    """
    编辑规格分组的名称、状态和展示顺序。

    输入：session、group_id、局部更新 payload、actor_id。
    输出：SpecificationGroup，已更新并写入 Revision/Audit 的规格分组。
    """
    group = await session.scalar(
        select(SpecificationGroup).where(SpecificationGroup.id == group_id).with_for_update()
    )
    if group is None:
        raise AppException(404, "specification_group_not_found", "规格分组不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    for field_name, value in changes.items():
        if value is not None:
            setattr(group, field_name, value)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            "specification_group",
            group,
            SpecificationGroupTranslation,
            "group_id",
            payload.translations,
            actor_id=actor_id,
        )
    write_audit_log(
        session,
        action="specification.update",
        target_type="specification_group",
        user_id=actor_id,
        target_id=str(group.id),
        metadata={"fields": sorted(changes)},
    )
    await session.flush()
    if changes:
        await _record_entity_revision(session, "specification_group", group, actor_id)
    # 刷新数据库生成的 updated_at，避免事务提交后序列化触发异步懒加载。
    await session.refresh(group)
    return group


async def create_specification_definition(session: AsyncSession, payload: SpecificationDefinitionCreate, actor_id: uuid.UUID | None = None) -> SpecificationDefinition:
    """创建动态规格定义。"""
    if await session.get(SpecificationGroup, payload.group_id) is None:
        raise AppException(404, "specification_group_not_found", "规格分组不存在")
    definition = SpecificationDefinition(group_id=payload.group_id, code=payload.code, value_type=payload.value_type, default_unit=payload.default_unit, is_filterable=payload.is_filterable, sort_order=payload.sort_order, status=payload.status)
    session.add(definition)
    await session.flush()
    await _write_entity_content(session, owner_type="specification_definition", entity=definition, translation_model=SpecificationDefinitionTranslation, owner_field="definition_id", translations=payload.translations, actor_id=actor_id, action="specification.update")
    return definition


async def update_specification_definition(
    session: AsyncSession,
    definition_id: uuid.UUID,
    payload: SpecificationDefinitionUpdate,
    actor_id: uuid.UUID | None = None,
) -> SpecificationDefinition:
    """
    编辑规格定义，并在已有规格值时冻结值类型和默认单位。

    输入：session、definition_id、局部更新 payload、actor_id。
    输出：SpecificationDefinition，安全更新后的规格定义。
    """
    definition = await session.scalar(
        select(SpecificationDefinition)
        .where(SpecificationDefinition.id == definition_id)
        .with_for_update()
    )
    if definition is None:
        raise AppException(404, "specification_definition_not_found", "规格定义不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    if "group_id" in changes:
        group_id = changes["group_id"]
        if group_id is None or await session.get(SpecificationGroup, group_id) is None:
            raise AppException(404, "specification_group_not_found", "规格分组不存在")
    referenced = await session.scalar(
        select(ProductSpecValue.id).where(ProductSpecValue.definition_id == definition.id).limit(1)
    )
    protected_change = any(
        field_name in changes and changes[field_name] != getattr(definition, field_name)
        for field_name in ("value_type", "default_unit")
    )
    if referenced is not None and protected_change:
        raise AppException(
            409,
            "specification_definition_in_use",
            "已有产品参数值引用该定义，不能修改值类型或单位",
        )
    for field_name, value in changes.items():
        if field_name != "default_unit" and value is None:
            continue
        setattr(definition, field_name, value)
    if payload.translations is not None:
        await _upsert_translations(
            session,
            "specification_definition",
            definition,
            SpecificationDefinitionTranslation,
            "definition_id",
            payload.translations,
            actor_id=actor_id,
        )
    write_audit_log(
        session,
        action="specification.update",
        target_type="specification_definition",
        user_id=actor_id,
        target_id=str(definition.id),
        metadata={"fields": sorted(changes)},
    )
    await session.flush()
    if changes:
        await _record_entity_revision(session, "specification_definition", definition, actor_id)
    # 刷新数据库生成的 updated_at，避免事务提交后序列化触发异步懒加载。
    await session.refresh(definition)
    return definition


async def delete_specification_definition(
    session: AsyncSession,
    definition_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """
    删除未被任何产品参数值引用的规格定义。

    输入：session、definition_id、actor_id。
    输出：uuid.UUID，被安全删除的规格定义 ID。
    """
    definition = await session.scalar(
        select(SpecificationDefinition)
        .where(SpecificationDefinition.id == definition_id)
        .with_for_update()
    )
    if definition is None:
        raise AppException(404, "specification_definition_not_found", "规格定义不存在")
    referenced = await session.scalar(
        select(ProductSpecValue.id).where(ProductSpecValue.definition_id == definition.id).limit(1)
    )
    if referenced is not None:
        raise AppException(409, "specification_definition_in_use", "规格定义已有参数值引用，不能删除")
    write_audit_log(
        session,
        action="specification.delete",
        target_type="specification_definition",
        user_id=actor_id,
        target_id=str(definition.id),
        metadata={"code": definition.code},
    )
    await session.delete(definition)
    await session.flush()
    return definition_id


async def delete_specification_group(
    session: AsyncSession,
    group_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """
    删除不含任何规格定义的空分组，防止数据库级联误删字典。

    输入：session、group_id、actor_id。
    输出：uuid.UUID，被安全删除的分组 ID。
    """
    group = await session.scalar(
        select(SpecificationGroup).where(SpecificationGroup.id == group_id).with_for_update()
    )
    if group is None:
        raise AppException(404, "specification_group_not_found", "规格分组不存在")
    definition_id = await session.scalar(
        select(SpecificationDefinition.id)
        .where(SpecificationDefinition.group_id == group.id)
        .limit(1)
    )
    if definition_id is not None:
        raise AppException(409, "specification_group_in_use", "规格分组仍包含定义，不能删除")
    write_audit_log(
        session,
        action="specification.delete",
        target_type="specification_group",
        user_id=actor_id,
        target_id=str(group.id),
        metadata={"code": group.code},
    )
    await session.delete(group)
    await session.flush()
    return group_id


async def create_specification_value(session: AsyncSession, payload: SpecificationValueCreate, actor_id: uuid.UUID | None = None) -> ProductSpecValue:
    """根据 Definition.value_type 校验并保存动态规格值。"""
    definition = await session.get(SpecificationDefinition, payload.definition_id)
    if definition is None:
        raise AppException(404, "specification_definition_not_found", "规格定义不存在")
    type_to_value = {
        SpecificationValueType.TEXT.value: payload.value_text,
        SpecificationValueType.NUMBER.value: payload.value_number,
        SpecificationValueType.RANGE.value: payload.value_min if payload.value_min is not None or payload.value_max is not None else None,
        SpecificationValueType.BOOLEAN.value: payload.value_boolean,
        SpecificationValueType.ENUM.value: payload.enum_value,
    }
    if type_to_value[definition.value_type] is None:
        raise AppException(422, "specification_type_mismatch", "提供的值与规格定义类型不匹配")
    values = payload.model_dump(exclude={"product_id", "product_model_id", "definition_id"})
    value = ProductSpecValue(product_id=payload.product_id, product_model_id=payload.product_model_id, definition_id=payload.definition_id, **values)
    session.add(value)
    await session.flush()
    write_audit_log(session, action="specification.update", target_type="product_spec_value", user_id=actor_id, target_id=str(value.id), metadata={"definition": definition.code})
    await _record_entity_revision(session, "product_spec_value", value, actor_id)
    return value


async def update_specification_value(
    session: AsyncSession,
    value_id: uuid.UUID,
    payload: SpecificationValueUpdate,
    actor_id: uuid.UUID | None = None,
) -> ProductSpecValue:
    """
    按 Definition.value_type 更新已有动态规格值。

    输入：session、value_id、局部更新 payload、actor_id。
    输出：ProductSpecValue，完成类型校验并写入 Revision/Audit 的规格值。
    """
    value = await session.scalar(
        select(ProductSpecValue).where(ProductSpecValue.id == value_id).with_for_update()
    )
    if value is None:
        raise AppException(404, "specification_value_not_found", "规格值不存在")
    definition = await session.get(SpecificationDefinition, value.definition_id)
    if definition is None:
        raise AppException(404, "specification_definition_not_found", "规格定义不存在")
    changes = payload.model_dump(exclude_unset=True)
    value_fields = {
        "value_text",
        "value_number",
        "value_min",
        "value_max",
        "value_boolean",
        "enum_value",
    }
    if value_fields.intersection(changes):
        for field_name in value_fields:
            setattr(value, field_name, changes.get(field_name))
    for field_name in {"unit_override", "sort_order", "is_public"}.intersection(changes):
        setattr(value, field_name, changes[field_name])
    typed_values = {
        SpecificationValueType.TEXT.value: value.value_text,
        SpecificationValueType.NUMBER.value: value.value_number,
        SpecificationValueType.RANGE.value: (
            value.value_min if value.value_min is not None or value.value_max is not None else None
        ),
        SpecificationValueType.BOOLEAN.value: value.value_boolean,
        SpecificationValueType.ENUM.value: value.enum_value,
    }
    if typed_values[definition.value_type] is None:
        raise AppException(422, "specification_type_mismatch", "提供的值与规格定义类型不匹配")
    if value.value_min is not None and value.value_max is not None and value.value_min > value.value_max:
        raise AppException(422, "specification_range_invalid", "范围下限不能大于上限")
    await session.flush()
    write_audit_log(
        session,
        action="specification.update",
        target_type="product_spec_value",
        user_id=actor_id,
        target_id=str(value.id),
        metadata={"definition": definition.code},
    )
    await _record_entity_revision(session, "product_spec_value", value, actor_id)
    return value


async def delete_specification_value(
    session: AsyncSession,
    value_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """
    清空单个产品或型号的规格赋值，同时保留 Revision 与 Audit 轨迹。

    输入：session、value_id、actor_id。
    输出：uuid.UUID，被删除的规格值 ID。
    """
    value = await session.scalar(
        select(ProductSpecValue).where(ProductSpecValue.id == value_id).with_for_update()
    )
    if value is None:
        raise AppException(404, "specification_value_not_found", "规格值不存在")
    await _record_entity_revision(
        session,
        "product_spec_value",
        value,
        actor_id,
        extra={"operation": "deleted"},
    )
    write_audit_log(
        session,
        action="specification.delete",
        target_type="product_spec_value",
        user_id=actor_id,
        target_id=str(value.id),
        metadata={"definition_id": str(value.definition_id)},
    )
    await session.delete(value)
    await session.flush()
    return value_id


_RELATIONS: dict[str, tuple[type, str, type]] = {
    "material_ids": (ProductMaterial, "material_id", Material),
    "technology_ids": (ProductTechnology, "technology_id", Technology),
    "application_ids": (ProductApplication, "application_id", Application),
    "solution_ids": (ProductSolution, "solution_id", Solution),
}


async def replace_product_relations(session: AsyncSession, product_id: uuid.UUID, payload: RelationUpdate, actor_id: uuid.UUID | None = None) -> None:
    """在单一事务内替换 Product 到四类实体的显式关系。"""
    if await session.get(Product, product_id) is None:
        raise AppException(404, "product_not_found", "产品不存在")
    for field_name, (relation_model, target_field, target_model) in _RELATIONS.items():
        ids = list(dict.fromkeys(getattr(payload, field_name)))
        if ids:
            existing_ids = set((await session.scalars(select(target_model.id).where(target_model.id.in_(ids)))).all())
            if existing_ids != set(ids):
                raise AppException(404, "relation_target_not_found", "关系目标实体不存在")
        await session.execute(delete(relation_model).where(relation_model.product_id == product_id))
        for index, target_id in enumerate(ids):
            session.add(relation_model(product_id=product_id, **{target_field: target_id}, sort_order=index))
    write_audit_log(session, action="relation.change", target_type="product", user_id=actor_id, target_id=str(product_id), metadata={"fields": sorted(payload.model_dump())})
    await session.flush()
    product = await session.get(Product, product_id)
    if product is not None:
        await _record_entity_revision(session, "product", product, actor_id, {"relations": payload.model_dump(mode="json")})
