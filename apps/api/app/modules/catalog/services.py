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
    SpecificationGroupCreate,
    SpecificationValueCreate,
    TranslationInput,
)
from app.modules.content.models import ContentPublication, TranslationStatus
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import create_content_route
from app.modules.localization.models import Locale

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
    """在当前事务内创建翻译状态、草稿发布记录、canonical route、revision 和审计。"""
    translation_items = list(translations)
    translation_map = {item.locale_id: item for item in translation_items}
    if len(translation_map) != len(translation_items):
        raise AppException(409, "duplicate_translation", "同一请求不能重复提交语言翻译")
    locales = list((await session.scalars(select(Locale).order_by(Locale.id))).all())
    if not locales:
        raise AppException(409, "locale_required", "至少需要一个已配置语言")
    for locale in locales:
        item = translation_map.get(locale.id)
        translation_status = TranslationStatus(
            owner_type=owner_type,
            owner_id=entity.id,
            locale_id=locale.id,
            source_locale_id=locales[0].id,
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
        publication = ContentPublication(owner_type=owner_type, owner_id=entity.id, locale_id=locale.id, status="draft")
        session.add(publication)
        await session.flush()
        await create_content_route(
            session,
            owner_type,
            entity.id,
            locale,
            _route_path(owner_type, entity, locale, category_slug),
        )
    await session.flush()
    await store_revision(
        session,
        owner_type,
        entity.id,
        locales[0].id,
        jsonable_encoder({"master": {column.name: getattr(entity, column.name) for column in entity.__table__.columns if column.name not in {"created_at", "updated_at"}}, "translations": [item.model_dump(mode="json") for item in translation_map.values()]}),
        actor_id,
    )
    write_audit_log(session, action=action, target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={"slug": getattr(entity, "slug", getattr(entity, "code", None))})


async def _record_entity_revision(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    actor_id: uuid.UUID | None,
    extra: dict[str, Any] | None = None,
) -> None:
    """为更新、关系或规格变更写入默认语言快照。"""
    locale = await session.scalar(select(Locale).order_by(Locale.id))
    if locale is None:
        return
    snapshot: dict[str, Any] = {
        "master": {
            column.name: getattr(entity, column.name)
            for column in entity.__table__.columns
            if column.name not in {"created_at", "updated_at"}
        }
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
        await _upsert_translations(session, "product_category", category, ProductCategoryTranslation, "category_id", payload.translations)
    write_audit_log(session, action="product_category.update", target_type="product_category", user_id=actor_id, target_id=str(category.id), metadata={"fields": sorted(changes)})
    await session.flush()
    await _record_entity_revision(session, "product_category", category, actor_id)
    return category


async def _upsert_translations(session: AsyncSession, owner_type: str, entity: Any, model: type, owner_field: str, translations: list[TranslationInput]) -> None:
    """按 `(owner, locale)` 唯一键更新翻译并同步 TranslationStatus。"""
    for item in translations:
        existing = await session.scalar(select(model).where(getattr(model, owner_field) == entity.id, model.locale_id == item.locale_id).with_for_update())
        values = {"name": item.name}
        allowed = set(model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at", "name"}
        values.update({key: value for key, value in item.fields.items() if key in allowed})
        if existing is None:
            session.add(model(**{owner_field: entity.id, "locale_id": item.locale_id, **values}))
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        status = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == entity.id, TranslationStatus.locale_id == item.locale_id).with_for_update())
        if status:
            status.status = "draft"


async def create_product(session: AsyncSession, payload: ProductCreate, actor_id: uuid.UUID | None = None) -> Product:
    """创建产品并使用所属分类 slug 注册所有提供语言的路由。"""
    category = await session.get(ProductCategory, payload.category_id)
    if category is None or category.status != "enabled":
        raise AppException(404, "category_not_found", "产品分类不存在或未启用")
    product = Product(category_id=payload.category_id, code=payload.code, slug=payload.slug, status=payload.status, featured=payload.featured, sort_order=payload.sort_order)
    session.add(product)
    await session.flush()
    await _write_entity_content(session, owner_type="product", entity=product, translation_model=ProductTranslation, owner_field="product_id", translations=payload.translations, category_slug=category.slug, actor_id=actor_id, action="product.create")
    return product


async def update_product(session: AsyncSession, product_id: uuid.UUID, payload: ProductUpdate, actor_id: uuid.UUID | None = None) -> Product:
    """更新产品主字段/翻译并拒绝已发布 slug 原地变化。"""
    product = await session.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise AppException(404, "product_not_found", "产品不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"translations"})
    if changes.get("category_id") is not None and await session.get(ProductCategory, changes["category_id"]) is None:
        raise AppException(404, "category_not_found", "目标分类不存在")
    if changes.get("slug") and changes["slug"] != product.slug:
        published = await session.scalar(select(ContentPublication.id).where(ContentPublication.owner_type == "product", ContentPublication.owner_id == product.id, ContentPublication.status == "published"))
        if published:
            raise AppException(409, "published_slug_frozen", "已发布产品的 slug 不能直接修改")
    for key, value in changes.items():
        setattr(product, key, value)
    if payload.translations is not None:
        await _upsert_translations(session, "product", product, ProductTranslation, "product_id", payload.translations)
    write_audit_log(session, action="product.update", target_type="product", user_id=actor_id, target_id=str(product.id), metadata={"fields": sorted(changes)})
    await session.flush()
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
        await _upsert_translations(session, "product_model", model, ProductModelTranslation, "product_model_id", payload.translations)
    write_audit_log(session, action="product_model.update", target_type="product_model", user_id=actor_id, target_id=str(model.id), metadata={})
    await session.flush()
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
        await _upsert_translations(session, owner_type, entity, translation_model, owner_field, payload.translations)
    write_audit_log(session, action=f"{owner_type}.update", target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={"fields": sorted(changes)})
    await session.flush()
    await _record_entity_revision(session, owner_type, entity, actor_id)
    return entity


async def archive_entity(session: AsyncSession, owner_type: str, entity_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> Any:
    """用 retired 业务状态归档实体，不物理删除历史数据。"""
    model = _ENTITY_CONFIG[owner_type][0]
    entity = await session.scalar(select(model).where(model.id == entity_id).with_for_update())
    if entity is None:
        raise AppException(404, f"{owner_type}_not_found", "结构化实体不存在")
    entity.status = "retired"
    write_audit_log(session, action=f"{owner_type}.archive", target_type=owner_type, user_id=actor_id, target_id=str(entity.id), metadata={})
    await session.flush()
    return entity


async def create_specification_group(session: AsyncSession, payload: SpecificationGroupCreate, actor_id: uuid.UUID | None = None) -> SpecificationGroup:
    """创建规格分组及其翻译生命周期。"""
    group = SpecificationGroup(code=payload.code, status=payload.status, sort_order=payload.sort_order)
    session.add(group)
    await session.flush()
    await _write_entity_content(session, owner_type="specification_group", entity=group, translation_model=SpecificationGroupTranslation, owner_field="group_id", translations=payload.translations, actor_id=actor_id, action="specification.update")
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
