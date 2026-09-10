"""Structured Core Catalog 管理 API；写入统一受 Auth、RBAC、CSRF 与审计保护。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import case, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.pagination import PaginationParams
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import get_current_user, require_csrf, require_permission
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
)
from app.modules.catalog.services import (
    archive_entity,
    create_category,
    create_core_entity,
    create_product,
    create_product_model,
    create_specification_definition,
    create_specification_group,
    create_specification_value,
    delete_specification_definition,
    delete_specification_group,
    delete_specification_value,
    replace_product_relations,
    update_category,
    update_core_entity,
    update_product,
    update_product_model,
    update_specification_definition,
    update_specification_group,
    update_specification_value,
)
from app.modules.content.enums import PublicationStatus, TranslationState
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.localization.models import Locale
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/catalog", tags=["catalog"])
_ENTITY_MODELS = {
    "materials": ("material", Material, MaterialTranslation, "material_id"),
    "technologies": ("technology", Technology, TechnologyTranslation, "technology_id"),
    "applications": ("application", Application, ApplicationTranslation, "application_id"),
    "solutions": ("solution", Solution, SolutionTranslation, "solution_id"),
}
_CATALOG_LIFECYCLE_MODELS: dict[str, tuple[str, type]] = {
    "categories": ("product_category", ProductCategory),
    "products": ("product", Product),
    "materials": ("material", Material),
    "technologies": ("technology", Technology),
    "applications": ("application", Application),
    "solutions": ("solution", Solution),
}

_CATALOG_NAME_PROJECTIONS: dict[str, tuple[type, str]] = {
    ProductCategory.__tablename__: (ProductCategoryTranslation, "category_id"),
    Product.__tablename__: (ProductTranslation, "product_id"),
    Material.__tablename__: (MaterialTranslation, "material_id"),
    Technology.__tablename__: (TechnologyTranslation, "technology_id"),
    Application.__tablename__: (ApplicationTranslation, "application_id"),
    Solution.__tablename__: (SolutionTranslation, "solution_id"),
    SpecificationGroup.__tablename__: (SpecificationGroupTranslation, "group_id"),
    SpecificationDefinition.__tablename__: (
        SpecificationDefinitionTranslation,
        "definition_id",
    ),
}
_PUBLICATION_PERMISSION_ACTIONS: dict[PublicationStatus, str] = {
    PublicationStatus.REVIEW: "review",
    PublicationStatus.SCHEDULED: "publish",
    PublicationStatus.PUBLISHED: "publish",
    PublicationStatus.ARCHIVED: "archive",
    PublicationStatus.DRAFT: "update",
}


def _require_catalog_permission(user: User, code: str) -> set[str]:
    """
    校验 Catalog 动态生命周期操作的服务端权限。

    输入：
        user: User，当前认证用户。
        code: str，必须具备的权限代码。

    输出：
        set[str]，当前用户的完整权限集合。
    """
    _roles, permissions = collect_authorization(user)
    if code not in permissions:
        raise AppException(403, "permission_denied", "没有执行此操作的权限")
    return set(permissions)


def _catalog_lifecycle_config(resource: str) -> tuple[str, type]:
    """
    解析允许进入统一生命周期的 Catalog 资源。

    输入：
        resource: str，API 使用的资源复数名。

    输出：
        tuple[str, type]，owner_type 与对应 Master Entity 模型。
    """
    config = _CATALOG_LIFECYCLE_MODELS.get(resource)
    if config is None:
        raise AppException(404, "catalog_resource_not_found", "Catalog 资源不存在")
    return config


async def _catalog_lifecycle_records(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> tuple[ContentPublication, TranslationStatus, ContentRoute]:
    """
    读取同一 Catalog 内容语言的发布、翻译与 canonical Route。

    输入：
        session: AsyncSession，数据库会话。
        owner_type: str，Catalog owner 类型。
        owner_id: uuid.UUID，Master Entity ID。
        locale_id: uuid.UUID，目标语言 ID。

    输出：
        tuple[ContentPublication, TranslationStatus, ContentRoute]，统一生命周期记录。
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
    if publication is None or translation is None or route is None:
        raise AppException(
            409,
            "publication_records_required",
            "发布、翻译与 canonical Route 必须完整",
        )
    return publication, translation, route


async def _review_catalog_lifecycle(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    user: User,
) -> dict[str, str]:
    """
    审核 Catalog 翻译并将 draft Publication 原子提交至 review。

    输入：
        session: AsyncSession，数据库会话。
        owner_type: str，Catalog owner 类型。
        owner_id: uuid.UUID，Master Entity ID。
        locale_id: uuid.UUID，目标语言 ID。
        user: User，当前审核用户。

    输出：
        dict[str, str]，翻译状态与 Publication 状态。
    """
    permissions = _require_catalog_permission(user, "catalog.review")
    _require_catalog_permission(user, "translation.review")
    _require_catalog_permission(user, "content.review")
    publication, translation, route = await _catalog_lifecycle_records(
        session,
        owner_type=owner_type,
        owner_id=owner_id,
        locale_id=locale_id,
    )
    if publication.status == PublicationStatus.PUBLISHED.value:
        raise AppException(409, "published_translation_locked", "已发布翻译无需重复审核")
    if translation.status in {
        TranslationState.MISSING.value,
        TranslationState.PUBLISHED.value,
    }:
        raise AppException(409, "translation_not_reviewable", "只有已有草稿翻译可以人工审核")
    if publication.status not in {
        PublicationStatus.DRAFT.value,
        PublicationStatus.REVIEW.value,
    }:
        raise AppException(409, "publication_not_reviewable", "当前发布状态不能执行翻译审核")

    translation.status = TranslationState.HUMAN_REVIEWED.value
    translation.reviewed_by = user.id
    write_audit_log(
        session,
        action="translation.review",
        target_type=owner_type,
        target_id=str(owner_id),
        user_id=user.id,
        metadata={"locale_id": str(locale_id)},
    )
    if publication.status == PublicationStatus.DRAFT.value:
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.REVIEW,
            actor_permissions=permissions,
            actor_id=user.id,
        )
    await session.flush()
    return {
        "translation_status": translation.status,
        "publication_status": publication.status,
    }


async def _transition_catalog_lifecycle(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    target_status: PublicationStatus,
    user: User,
) -> str:
    """
    使用实体权限与全局内容权限转换 Catalog Publication。

    输入：数据库会话、owner 标识、语言、目标状态与当前用户。
    输出：str，转换后的 Publication 状态。
    """
    permission_action = _PUBLICATION_PERMISSION_ACTIONS[target_status]
    permissions = _require_catalog_permission(user, f"catalog.{permission_action}")
    if target_status is PublicationStatus.REVIEW:
        _require_catalog_permission(user, "translation.review")
    if target_status in {PublicationStatus.SCHEDULED, PublicationStatus.PUBLISHED}:
        _require_catalog_permission(user, "translation.publish")
    publication, translation, route = await _catalog_lifecycle_records(
        session,
        owner_type=owner_type,
        owner_id=owner_id,
        locale_id=locale_id,
    )
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=target_status,
        actor_permissions=permissions,
        actor_id=user.id,
    )
    return publication.status


def _serialize(entity: Any) -> dict[str, Any]:
    """将 ORM 实体转换成无敏感字段的 JSON 对象。"""
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _list_entities(session: AsyncSession, model: type, pagination: PaginationParams) -> dict[str, Any]:
    """
    分页读取目录实体，并批量补充中文优先的可读名称。

    输入：session、目录主模型和分页参数。
    输出：dict，包含列表、分页信息及中英文名称投影。
    """
    total = await session.scalar(select(func.count()).select_from(model))
    rows = list((await session.scalars(select(model).order_by(model.sort_order, model.id).offset(pagination.offset).limit(pagination.page_size))).all())
    items = [
        {
            **_serialize(row),
            "display_name": None,
            "display_name_en": None,
            "translation_count": 0,
        }
        for row in rows
    ]
    projection = _CATALOG_NAME_PROJECTIONS.get(model.__tablename__)
    if projection and rows:
        translation_model, owner_field = projection
        # 一次查询当前页全部翻译，避免后台列表逐条请求详情；显示顺序不改变 Locale 原始代码。
        translation_rows = (
            await session.execute(
                select(translation_model, Locale.code)
                .join(Locale, Locale.id == translation_model.locale_id)
                .where(getattr(translation_model, owner_field).in_([row.id for row in rows]))
                .order_by(
                    case(
                        (Locale.code == "zh-CN", 0),
                        (Locale.code == "en", 1),
                        else_=2,
                    ),
                    Locale.sort_order,
                    translation_model.id,
                )
            )
        ).all()
        names: dict[uuid.UUID, dict[str, Any]] = {}
        for translation, locale_code in translation_rows:
            owner_id = getattr(translation, owner_field)
            entry = names.setdefault(
                owner_id,
                {"first": translation.name, "zh-CN": None, "en": None, "count": 0},
            )
            entry["count"] += 1
            if locale_code in {"zh-CN", "en"}:
                entry[locale_code] = translation.name
        for item, row in zip(items, rows, strict=True):
            entry = names.get(row.id, {})
            item.update(
                display_name=entry.get("zh-CN") or entry.get("en") or entry.get("first"),
                display_name_en=entry.get("en"),
                translation_count=entry.get("count", 0),
            )
    return {"items": items, "page": pagination.page, "page_size": pagination.page_size, "total": total or 0}


async def _lifecycle_detail(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
) -> dict[str, list[dict[str, Any]]]:
    """
    聚合指定实体全部语言的翻译、发布与 canonical Route 状态。

    输入：session、owner_type、owner_id。
    输出：dict，包含 translation_statuses、publications 与 routes。
    """
    translation_statuses = list(
        (
            await session.scalars(
                select(TranslationStatus)
                .where(
                    TranslationStatus.owner_type == owner_type,
                    TranslationStatus.owner_id == owner_id,
                )
                .order_by(TranslationStatus.locale_id)
            )
        ).all()
    )
    publications = list(
        (
            await session.scalars(
                select(ContentPublication)
                .where(
                    ContentPublication.owner_type == owner_type,
                    ContentPublication.owner_id == owner_id,
                )
                .order_by(ContentPublication.locale_id)
            )
        ).all()
    )
    routes = list(
        (
            await session.scalars(
                select(ContentRoute)
                .where(
                    ContentRoute.owner_type == owner_type,
                    ContentRoute.owner_id == owner_id,
                    ContentRoute.is_canonical.is_(True),
                )
                .order_by(ContentRoute.locale_id)
            )
        ).all()
    )
    return {
        "translation_statuses": [_serialize(item) for item in translation_statuses],
        "publications": [_serialize(item) for item in publications],
        "routes": [_serialize(item) for item in routes],
    }


async def _entity_detail(
    session: AsyncSession,
    *,
    owner_type: str,
    entity: Any,
    translation_model: type,
    owner_field: str,
) -> dict[str, Any]:
    """
    构造知识实体 Admin 编辑页所需聚合 DTO。

    输入：session、owner 配置、实体与翻译模型。
    输出：dict，包含 master、translations 和完整公开生命周期状态。
    """
    translations = list(
        (
            await session.scalars(
                select(translation_model)
                .where(getattr(translation_model, owner_field) == entity.id)
                .order_by(translation_model.locale_id)
            )
        ).all()
    )
    data = _serialize(entity)
    data["translations"] = [_serialize(item) for item in translations]
    data.update(await _lifecycle_detail(session, owner_type, entity.id))
    return data


async def _write_result(session: AsyncSession, operation: Any) -> Any:
    """
    提交 Catalog 事务，并保证 ORM 返回值可在异步响应层安全序列化。

    输入：
        session: AsyncSession，当前请求的数据库会话。
        operation: Any，返回 ORM 实体、标量或 None 的异步写操作。

    输出：
        Any，提交后的写操作结果；ORM 实体会先主动刷新。
    """
    try:
        result = await operation
        await session.commit()
        # 真实 PostgreSQL 生命周期更新可能使实体过期；在异步上下文内主动刷新，
        # 避免响应序列化阶段触发隐式 IO 并抛出 MissingGreenlet。
        if inspect(result, raiseerr=False) is not None:
            await session.refresh(result)
        return result
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(409, "catalog_constraint", "Catalog 数据完整性约束不允许该操作") from exc


@router.get("/categories", response_model=ApiResponse[dict[str, Any]])
async def list_categories(pagination: PaginationParams = Depends(), session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("catalog.read"))) -> ApiResponse[dict[str, Any]]:
    """分页列出产品分类。"""
    return success_response(await _list_entities(session, ProductCategory, pagination))


@router.get("/categories/tree", response_model=ApiResponse[list[dict[str, Any]]])
async def category_tree(session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("catalog.read"))) -> ApiResponse[list[dict[str, Any]]]:
    """返回按 sort_order/id 稳定排序的分类树。"""
    rows = list((await session.scalars(select(ProductCategory).order_by(ProductCategory.sort_order, ProductCategory.id))).all())
    nodes = {row.id: {**_serialize(row), "children": []} for row in rows}
    roots: list[dict[str, Any]] = []
    for row in rows:
        (nodes[row.parent_id]["children"] if row.parent_id in nodes else roots).append(nodes[row.id])
    return success_response(roots)


@router.get("/categories/{category_id}", response_model=ApiResponse[dict[str, Any]])
async def get_category(
    category_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("catalog.read")),
) -> ApiResponse[dict[str, Any]]:
    """返回分类主字段、翻译与完整语言生命周期。"""
    category = await session.get(ProductCategory, category_id)
    if category is None:
        raise AppException(404, "category_not_found", "产品分类不存在")
    return success_response(
        await _entity_detail(
            session,
            owner_type="product_category",
            entity=category,
            translation_model=ProductCategoryTranslation,
            owner_field="category_id",
        )
    )


@router.post("/categories", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_category(payload: CategoryCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.create")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建分类及其翻译/发布基础记录。"""
    result = await _write_result(session, create_category(session, payload, user.id))
    return success_response(_serialize(result))


@router.patch("/categories/{category_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_category(category_id: uuid.UUID, payload: CategoryUpdate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """更新分类并写入审计。"""
    result = await _write_result(session, update_category(session, category_id, payload, user.id))
    return success_response(_serialize(result))


@router.get("/products", response_model=ApiResponse[dict[str, Any]])
async def list_products(pagination: PaginationParams = Depends(), session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("catalog.read"))) -> ApiResponse[dict[str, Any]]:
    """分页列出产品主实体。"""
    return success_response(await _list_entities(session, Product, pagination))


@router.get("/products/{product_id}", response_model=ApiResponse[dict[str, Any]])
async def get_product(product_id: uuid.UUID, session: AsyncSession = Depends(get_session), _user: User = Depends(require_permission("catalog.read"))) -> ApiResponse[dict[str, Any]]:
    """一次读取产品编辑所需翻译、型号、规格、关系与发布路由状态。"""
    product = await session.get(Product, product_id)
    if product is None:
        raise AppException(404, "product_not_found", "产品不存在")
    models = list((await session.scalars(select(ProductModel).where(ProductModel.product_id == product_id).order_by(ProductModel.sort_order, ProductModel.id))).all())
    model_items: list[dict[str, Any]] = []
    for model in models:
        model_data = _serialize(model)
        model_translations = list(
            (
                await session.scalars(
                    select(ProductModelTranslation)
                    .where(ProductModelTranslation.product_model_id == model.id)
                    .order_by(ProductModelTranslation.locale_id)
                )
            ).all()
        )
        model_specs = list(
            (
                await session.scalars(
                    select(ProductSpecValue)
                    .where(ProductSpecValue.product_model_id == model.id)
                    .order_by(ProductSpecValue.sort_order, ProductSpecValue.id)
                )
            ).all()
        )
        model_data["translations"] = [_serialize(item) for item in model_translations]
        model_data["specifications"] = [_serialize(item) for item in model_specs]
        model_items.append(model_data)
    specifications = list(
        (
            await session.scalars(
                select(ProductSpecValue)
                .where(ProductSpecValue.product_id == product_id)
                .order_by(ProductSpecValue.sort_order, ProductSpecValue.id)
            )
        ).all()
    )
    relation_config = {
        "material_ids": (ProductMaterial, "material_id"),
        "technology_ids": (ProductTechnology, "technology_id"),
        "application_ids": (ProductApplication, "application_id"),
        "solution_ids": (ProductSolution, "solution_id"),
    }
    relations: dict[str, list[str]] = {}
    for field_name, (relation_model, target_field) in relation_config.items():
        relations[field_name] = [
            str(item)
            for item in (
                await session.scalars(
                    select(getattr(relation_model, target_field))
                    .where(relation_model.product_id == product_id)
                    .order_by(relation_model.sort_order, getattr(relation_model, target_field))
                )
            ).all()
        ]
    data = await _entity_detail(
        session,
        owner_type="product",
        entity=product,
        translation_model=ProductTranslation,
        owner_field="product_id",
    )
    data["models"] = model_items
    data["specifications"] = [_serialize(item) for item in specifications]
    data["relations"] = relations
    return success_response(data)


@router.post("/products", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_product(payload: ProductCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.create")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建产品及其统一内容生命周期。"""
    result = await _write_result(session, create_product(session, payload, user.id))
    return success_response(_serialize(result))


@router.patch("/products/{product_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_product(product_id: uuid.UUID, payload: ProductUpdate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """更新产品主字段和翻译。"""
    result = await _write_result(session, update_product(session, product_id, payload, user.id))
    return success_response(_serialize(result))


@router.post(
    "/{resource}/{entity_id}/translations/{locale_id}/review",
    response_model=ApiResponse[dict[str, str]],
)
async def review_catalog_translation(
    resource: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    审核 Catalog Translation，并同步把 draft Publication 提交 review。

    输入：资源名、实体/语言 ID、数据库会话与当前用户。
    输出：ApiResponse，翻译与 Publication 的最新状态。
    """
    owner_type, model = _catalog_lifecycle_config(resource)
    if await session.get(model, entity_id) is None:
        raise AppException(404, f"{owner_type}_not_found", "Catalog 实体不存在")
    result = await _write_result(
        session,
        _review_catalog_lifecycle(
            session,
            owner_type=owner_type,
            owner_id=entity_id,
            locale_id=locale_id,
            user=user,
        ),
    )
    return success_response(result)


@router.post(
    "/{resource}/{entity_id}/publications/{locale_id}/{target_status}",
    response_model=ApiResponse[dict[str, str]],
)
async def transition_catalog_publication(
    resource: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    target_status: PublicationStatus,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    通过统一事务服务转换 Catalog Publication。

    输入：资源名、实体/语言 ID、目标状态、数据库会话与当前用户。
    输出：ApiResponse，转换后的 Publication 状态。
    """
    owner_type, model = _catalog_lifecycle_config(resource)
    if await session.get(model, entity_id) is None:
        raise AppException(404, f"{owner_type}_not_found", "Catalog 实体不存在")
    result = await _write_result(
        session,
        _transition_catalog_lifecycle(
            session,
            owner_type=owner_type,
            owner_id=entity_id,
            locale_id=locale_id,
            target_status=target_status,
            user=user,
        ),
    )
    return success_response({"status": result})


@router.post("/products/{product_id}/archive", response_model=ApiResponse[dict[str, Any]])
async def archive_product(product_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.archive")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """以 retired 状态归档产品。"""
    result = await _write_result(session, archive_entity(session, "product", product_id, user.id))
    return success_response(_serialize(result))


@router.post("/products/{product_id}/models", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_product_model(product_id: uuid.UUID, payload: ProductModelCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.create")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建产品范围内唯一型号。"""
    result = await _write_result(session, create_product_model(session, product_id, payload, user.id))
    return success_response(_serialize(result))


@router.patch("/product-models/{model_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_product_model(model_id: uuid.UUID, payload: ProductModelUpdate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """更新或退役产品型号。"""
    result = await _write_result(session, update_product_model(session, model_id, payload, user.id))
    return success_response(_serialize(result))


@router.put("/products/{product_id}/relations", response_model=ApiResponse[dict[str, Any]])
async def put_product_relations(product_id: uuid.UUID, payload: RelationUpdate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("catalog.update")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """事务化替换产品与材料/技术/应用/方案的显式关系。"""
    await _write_result(session, replace_product_relations(session, product_id, payload, user.id))
    return success_response({"product_id": str(product_id), **payload.model_dump(mode="json")})


@router.get("/specifications/groups", response_model=ApiResponse[dict[str, Any]])
async def list_specification_groups(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("specification.read")),
) -> ApiResponse[dict[str, Any]]:
    """分页列出规格分组。"""
    return success_response(await _list_entities(session, SpecificationGroup, pagination))


@router.post("/specifications/groups", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_group(payload: SpecificationGroupCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建规格分组。"""
    result = await _write_result(session, create_specification_group(session, payload, user.id))
    return success_response(_serialize(result))


@router.get("/specifications/groups/{group_id}", response_model=ApiResponse[dict[str, Any]])
async def get_specification_group(
    group_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("specification.read")),
) -> ApiResponse[dict[str, Any]]:
    """返回规格分组及多语言编辑数据。"""
    group = await session.get(SpecificationGroup, group_id)
    if group is None:
        raise AppException(404, "specification_group_not_found", "规格分组不存在")
    return success_response(
        await _entity_detail(
            session,
            owner_type="specification_group",
            entity=group,
            translation_model=SpecificationGroupTranslation,
            owner_field="group_id",
        )
    )


@router.patch("/specifications/groups/{group_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_specification_group(
    group_id: uuid.UUID,
    payload: SpecificationGroupUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """编辑规格分组名称、状态和排序。"""
    result = await _write_result(session, update_specification_group(session, group_id, payload, user.id))
    return success_response(_serialize(result))


@router.delete("/specifications/groups/{group_id}", response_model=ApiResponse[dict[str, Any]])
async def remove_specification_group(
    group_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """安全删除不含定义的空规格分组。"""
    deleted_id = await _write_result(session, delete_specification_group(session, group_id, user.id))
    return success_response({"deleted": True, "id": str(deleted_id)})


@router.get("/specifications/definitions", response_model=ApiResponse[dict[str, Any]])
async def list_specification_definitions(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("specification.read")),
) -> ApiResponse[dict[str, Any]]:
    """分页列出动态规格定义。"""
    return success_response(await _list_entities(session, SpecificationDefinition, pagination))


@router.post("/specifications/definitions", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_definition(payload: SpecificationDefinitionCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建动态规格定义。"""
    result = await _write_result(session, create_specification_definition(session, payload, user.id))
    return success_response(_serialize(result))


@router.get("/specifications/definitions/{definition_id}", response_model=ApiResponse[dict[str, Any]])
async def get_specification_definition(
    definition_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("specification.read")),
) -> ApiResponse[dict[str, Any]]:
    """返回规格定义及多语言编辑数据。"""
    definition = await session.get(SpecificationDefinition, definition_id)
    if definition is None:
        raise AppException(404, "specification_definition_not_found", "规格定义不存在")
    return success_response(
        await _entity_detail(
            session,
            owner_type="specification_definition",
            entity=definition,
            translation_model=SpecificationDefinitionTranslation,
            owner_field="definition_id",
        )
    )


@router.patch("/specifications/definitions/{definition_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_specification_definition(
    definition_id: uuid.UUID,
    payload: SpecificationDefinitionUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """编辑规格定义，并保护已有值的类型与单位。"""
    result = await _write_result(
        session,
        update_specification_definition(session, definition_id, payload, user.id),
    )
    return success_response(_serialize(result))


@router.delete("/specifications/definitions/{definition_id}", response_model=ApiResponse[dict[str, Any]])
async def remove_specification_definition(
    definition_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """安全删除没有任何参数值引用的规格定义。"""
    deleted_id = await _write_result(
        session,
        delete_specification_definition(session, definition_id, user.id),
    )
    return success_response({"deleted": True, "id": str(deleted_id)})


@router.get("/specifications/values", response_model=ApiResponse[dict[str, Any]])
async def list_specification_values(
    pagination: PaginationParams = Depends(),
    product_id: uuid.UUID | None = None,
    product_model_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("specification.read")),
) -> ApiResponse[dict[str, Any]]:
    """分页列出 Product 与 ProductModel 的规格值。"""
    conditions = []
    if product_id is not None:
        conditions.append(ProductSpecValue.product_id == product_id)
    if product_model_id is not None:
        conditions.append(ProductSpecValue.product_model_id == product_model_id)
    total = await session.scalar(
        select(func.count()).select_from(ProductSpecValue).where(*conditions)
    )
    values = list(
        (
            await session.scalars(
                select(ProductSpecValue)
                .where(*conditions)
                .order_by(ProductSpecValue.sort_order, ProductSpecValue.id)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()
    )
    return success_response(
        {
            "items": [_serialize(value) for value in values],
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": total or 0,
        }
    )


@router.post("/specifications/values", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_value(payload: SpecificationValueCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建经 value_type 校验的产品规格值。"""
    result = await _write_result(session, create_specification_value(session, payload, user.id))
    return success_response(_serialize(result))


@router.patch("/specifications/values/{value_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_specification_value(
    value_id: uuid.UUID,
    payload: SpecificationValueUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """更新已有 Product/ProductModel 规格值。"""
    result = await _write_result(
        session,
        update_specification_value(session, value_id, payload, user.id),
    )
    return success_response(_serialize(result))


@router.delete("/specifications/values/{value_id}", response_model=ApiResponse[dict[str, Any]])
async def remove_specification_value(
    value_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("specification.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """清空产品或型号的单个规格赋值。"""
    deleted_id = await _write_result(session, delete_specification_value(session, value_id, user.id))
    return success_response({"deleted": True, "id": str(deleted_id)})


def _register_entity_routes(
    table_name: str,
    owner_type: str,
    model: type,
    translation_model: type,
    owner_field: str,
) -> None:
    """为四类知识实体注册使用各自原子权限的真实 CRUD 路由。"""

    async def list_handler(
        pagination: PaginationParams = Depends(),
        session: AsyncSession = Depends(get_session),
        _user: User = Depends(require_permission(f"{owner_type}.read")),
    ) -> ApiResponse[dict[str, Any]]:
        """分页列出结构化实体。"""
        return success_response(await _list_entities(session, model, pagination))

    async def detail_handler(
        entity_id: uuid.UUID,
        session: AsyncSession = Depends(get_session),
        _user: User = Depends(require_permission(f"{owner_type}.read")),
    ) -> ApiResponse[dict[str, Any]]:
        """返回知识实体及其翻译、发布和 canonical Route 聚合详情。"""
        entity = await session.get(model, entity_id)
        if entity is None:
            raise AppException(404, f"{owner_type}_not_found", "结构化实体不存在")
        return success_response(
            await _entity_detail(
                session,
                owner_type=owner_type,
                entity=entity,
                translation_model=translation_model,
                owner_field=owner_field,
            )
        )

    async def create_handler(
        payload: EntityCreate,
        request: Request,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(require_permission(f"{owner_type}.create")),
        _csrf: None = Depends(require_csrf),
    ) -> ApiResponse[dict[str, Any]]:
        """创建结构化实体。"""
        result = await _write_result(session, create_core_entity(session, owner_type, payload, user.id))
        return success_response(_serialize(result))

    async def update_handler(
        entity_id: uuid.UUID,
        payload: EntityUpdate,
        request: Request,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(require_permission(f"{owner_type}.update")),
        _csrf: None = Depends(require_csrf),
    ) -> ApiResponse[dict[str, Any]]:
        """更新结构化实体。"""
        result = await _write_result(session, update_core_entity(session, owner_type, entity_id, payload, user.id))
        return success_response(_serialize(result))

    async def archive_handler(
        entity_id: uuid.UUID,
        request: Request,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(require_permission(f"{owner_type}.archive")),
        _csrf: None = Depends(require_csrf),
    ) -> ApiResponse[dict[str, Any]]:
        """退役结构化实体。"""
        result = await _write_result(session, archive_entity(session, owner_type, entity_id, user.id))
        return success_response(_serialize(result))

    router.add_api_route(f"/{table_name}", list_handler, methods=["GET"], response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}", create_handler, methods=["POST"], status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}/{{entity_id}}", detail_handler, methods=["GET"], response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}/{{entity_id}}", update_handler, methods=["PATCH"], response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}/{{entity_id}}/archive", archive_handler, methods=["POST"], response_model=ApiResponse[dict[str, Any]])


for _table_name, (_owner_type, _model, _translation_model, _owner_field) in _ENTITY_MODELS.items():
    _register_entity_routes(
        _table_name,
        _owner_type,
        _model,
        _translation_model,
        _owner_field,
    )
