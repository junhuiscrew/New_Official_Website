"""Structured Core Catalog 管理 API；写入统一受 Auth、RBAC、CSRF 与审计保护。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.pagination import PaginationParams
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.catalog.models import (
    Application,
    Material,
    Product,
    ProductCategory,
    ProductModel,
    Solution,
    Technology,
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
    replace_product_relations,
    update_category,
    update_core_entity,
    update_product,
    update_product_model,
)
from app.modules.users.models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])
_ENTITY_MODELS = {"materials": ("material", Material), "technologies": ("technology", Technology), "applications": ("application", Application), "solutions": ("solution", Solution)}


def _serialize(entity: Any) -> dict[str, Any]:
    """将 ORM 实体转换成无敏感字段的 JSON 对象。"""
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _list_entities(session: AsyncSession, model: type, pagination: PaginationParams) -> dict[str, Any]:
    """执行稳定排序分页查询，避免默认预加载全部关联。"""
    total = await session.scalar(select(func.count()).select_from(model))
    rows = list((await session.scalars(select(model).order_by(model.sort_order, model.id).offset(pagination.offset).limit(pagination.page_size))).all())
    return {"items": [_serialize(row) for row in rows], "page": pagination.page, "page_size": pagination.page_size, "total": total or 0}


async def _write_result(session: AsyncSession, operation: Any) -> Any:
    """提交 Catalog 事务并把唯一/FK 冲突转换为稳定业务错误。"""
    try:
        result = await operation
        await session.commit()
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
    """读取产品详情和关联型号。"""
    product = await session.get(Product, product_id)
    if product is None:
        raise AppException(404, "product_not_found", "产品不存在")
    models = list((await session.scalars(select(ProductModel).where(ProductModel.product_id == product_id).order_by(ProductModel.sort_order, ProductModel.id))).all())
    data = _serialize(product)
    data["models"] = [_serialize(model) for model in models]
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


@router.post("/specifications/groups", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_group(payload: SpecificationGroupCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建规格分组。"""
    result = await _write_result(session, create_specification_group(session, payload, user.id))
    return success_response(_serialize(result))


@router.post("/specifications/definitions", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_definition(payload: SpecificationDefinitionCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建动态规格定义。"""
    result = await _write_result(session, create_specification_definition(session, payload, user.id))
    return success_response(_serialize(result))


@router.post("/specifications/values", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_specification_value(payload: SpecificationValueCreate, request: Request, session: AsyncSession = Depends(get_session), user: User = Depends(require_permission("specification.manage")), _csrf: None = Depends(require_csrf)) -> ApiResponse[dict[str, Any]]:
    """创建经 value_type 校验的产品规格值。"""
    result = await _write_result(session, create_specification_value(session, payload, user.id))
    return success_response(_serialize(result))


def _register_entity_routes(table_name: str, owner_type: str, model: type) -> None:
    """为四类知识实体注册一致的 list/create/update/archive 路由。"""

    async def list_handler(
        pagination: PaginationParams = Depends(),
        session: AsyncSession = Depends(get_session),
        _user: User = Depends(require_permission("catalog.read")),
    ) -> ApiResponse[dict[str, Any]]:
        """分页列出结构化实体。"""
        return success_response(await _list_entities(session, model, pagination))

    async def create_handler(
        payload: EntityCreate,
        request: Request,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(require_permission("catalog.create")),
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
        user: User = Depends(require_permission("catalog.update")),
        _csrf: None = Depends(require_csrf),
    ) -> ApiResponse[dict[str, Any]]:
        """更新结构化实体。"""
        result = await _write_result(session, update_core_entity(session, owner_type, entity_id, payload, user.id))
        return success_response(_serialize(result))

    async def archive_handler(
        entity_id: uuid.UUID,
        request: Request,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(require_permission("catalog.archive")),
        _csrf: None = Depends(require_csrf),
    ) -> ApiResponse[dict[str, Any]]:
        """退役结构化实体。"""
        result = await _write_result(session, archive_entity(session, owner_type, entity_id, user.id))
        return success_response(_serialize(result))

    router.add_api_route(f"/{table_name}", list_handler, methods=["GET"], response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}", create_handler, methods=["POST"], status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}/{{entity_id}}", update_handler, methods=["PATCH"], response_model=ApiResponse[dict[str, Any]])
    router.add_api_route(f"/{table_name}/{{entity_id}}/archive", archive_handler, methods=["POST"], response_model=ApiResponse[dict[str, Any]])


for _table_name, (_owner_type, _model) in _ENTITY_MODELS.items():
    _register_entity_routes(_table_name, _owner_type, _model)
