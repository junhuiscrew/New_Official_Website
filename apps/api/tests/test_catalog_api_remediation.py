"""Phase 3.3 Remediation 的 Catalog 聚合 DTO 与细粒度 RBAC API 测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory, get_session
from app.core.security.passwords import hash_password
from app.main import create_app
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users.models import Role, User, UserRole
from app.seed import seed_database

PASSWORD = "CatalogPassword!2026"


@pytest.fixture
async def catalog_remediation_api_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建含 content_admin、seo_manager 与 sales 的隔离 API 数据库。

    输入：sqlite_database_url，测试数据库地址。
    输出：async_sessionmaker，预置三类 RBAC 用户。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    async with factory() as session, session.begin():
        for role_name in ("content_admin", "editor", "seo_manager", "sales"):
            role = await session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            user = User(
                email=f"{role_name}@example.com",
                password_hash=hash_password(PASSWORD),
                display_name=role_name,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
    yield factory
    await engine.dispose()


@asynccontextmanager
async def _role_client(
    session_factory: async_sessionmaker[AsyncSession],
    role_name: str,
) -> AsyncIterator[AsyncClient]:
    """
    创建指定系统角色的已登录 API 客户端。

    输入：session_factory、role_name。
    输出：AsyncClient，自动携带 Cookie 与 CSRF Header。
    """
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{role_name}@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies.get("junhui_csrf") or ""
        yield client


@pytest.mark.parametrize(
    ("resource", "permission_prefix"),
    [
        ("materials", "material"),
        ("technologies", "technology"),
        ("applications", "application"),
        ("solutions", "solution"),
    ],
)
async def test_structured_entities_enforce_granular_permissions(
    catalog_remediation_api_factory: async_sessionmaker[AsyncSession],
    resource: str,
    permission_prefix: str,
) -> None:
    """四类知识实体必须使用各自 read/create 权限，而不是通用 catalog 权限。"""
    payload = {"slug": f"{permission_prefix}-rbac-test", "translations": []}
    async with _role_client(catalog_remediation_api_factory, "sales") as client:
        sales_write = await client.post(f"/api/v1/catalog/{resource}", json=payload)
    async with _role_client(catalog_remediation_api_factory, "editor") as client:
        editor_write = await client.post(f"/api/v1/catalog/{resource}", json=payload)
    async with _role_client(catalog_remediation_api_factory, "seo_manager") as client:
        seo_read = await client.get(f"/api/v1/catalog/{resource}")
        seo_write = await client.post(f"/api/v1/catalog/{resource}", json=payload)
    async with _role_client(catalog_remediation_api_factory, "content_admin") as client:
        admin_write = await client.post(f"/api/v1/catalog/{resource}", json=payload)

    assert sales_write.status_code == 403
    assert editor_write.status_code == 403
    assert seo_read.status_code == 200
    assert seo_write.status_code == 403
    assert admin_write.status_code == 201


async def test_product_and_material_detail_return_complete_editor_dto(
    catalog_remediation_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Product 与 Material detail 必须一次返回 Admin 编辑页所需生命周期和关系数据。"""
    async with _role_client(catalog_remediation_api_factory, "content_admin") as client:
        locales = (await client.get("/api/v1/locales")).json()["data"]
        zh_id = next(item["id"] for item in locales if item["code"] == "zh-CN")
        category = await client.post(
            "/api/v1/catalog/categories",
            json={
                "slug": "editor-category",
                "translations": [{"locale_id": zh_id, "name": "编辑分类"}],
            },
        )
        product = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category.json()["data"]["id"],
                "slug": "editor-product",
                "translations": [
                    {
                        "locale_id": zh_id,
                        "name": "编辑产品",
                        "fields": {"description": "产品正文"},
                    }
                ],
            },
        )
        product_id = product.json()["data"]["id"]
        material = await client.post(
            "/api/v1/catalog/materials",
            json={
                "slug": "editor-material",
                "translations": [{"locale_id": zh_id, "name": "编辑材料"}],
            },
        )
        material_id = material.json()["data"]["id"]
        await client.post(
            f"/api/v1/catalog/products/{product_id}/models",
            json={
                "model_code": "EDITOR-01",
                "translations": [{"locale_id": zh_id, "name": "编辑型号"}],
            },
        )
        await client.put(
            f"/api/v1/catalog/products/{product_id}/relations",
            json={"material_ids": [material_id]},
        )
        group = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={
                "code": "editor-group",
                "translations": [{"locale_id": zh_id, "name": "编辑规格组"}],
            },
        )
        definition = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": group.json()["data"]["id"],
                "code": "editor-number",
                "value_type": "number",
                "translations": [{"locale_id": zh_id, "name": "编辑数值"}],
            },
        )
        await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": product_id,
                "definition_id": definition.json()["data"]["id"],
                "value_number": 42,
            },
        )
        product_detail = await client.get(f"/api/v1/catalog/products/{product_id}")
        material_detail = await client.get(f"/api/v1/catalog/materials/{material_id}")

    assert product_detail.status_code == 200
    product_data = product_detail.json()["data"]
    assert product_data["translations"][0]["name"] == "编辑产品"
    assert product_data["models"][0]["model_code"] == "EDITOR-01"
    assert product_data["specifications"][0]["value_number"] == 42
    assert product_data["relations"]["material_ids"] == [material_id]
    product_zh_status = next(
        item for item in product_data["translation_statuses"] if item["locale_id"] == zh_id
    )
    assert product_zh_status["status"] == "draft"
    assert product_data["publications"][0]["status"] == "draft"
    assert product_data["routes"][0]["is_canonical"] is True

    assert material_detail.status_code == 200
    material_data = material_detail.json()["data"]
    assert material_data["translations"][0]["name"] == "编辑材料"
    material_zh_status = next(
        item for item in material_data["translation_statuses"] if item["locale_id"] == zh_id
    )
    assert material_zh_status["status"] == "draft"
    assert material_data["publications"][0]["status"] == "draft"
    assert material_data["routes"][0]["is_canonical"] is True


async def test_editor_can_read_product_dependencies_and_edit_relations_without_creating_knowledge(
    catalog_remediation_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 editor 可读取 Product 编辑依赖并修改产品关系，但不能创建基础知识实体。

    输入：catalog_remediation_api_factory，已 Seed 角色和用户的数据库工厂。
    输出：None；断言读取/产品编辑成功，四类知识实体创建均为 403。
    """
    async with _role_client(catalog_remediation_api_factory, "content_admin") as client:
        category = await client.post(
            "/api/v1/catalog/categories",
            json={"slug": "editor-access-category", "translations": []},
        )
        product = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category.json()["data"]["id"],
                "slug": "editor-access-product",
                "translations": [],
            },
        )
        resource_ids: dict[str, str] = {}
        for resource in ("materials", "technologies", "applications", "solutions"):
            created = await client.post(
                f"/api/v1/catalog/{resource}",
                json={"slug": f"editor-access-{resource}", "translations": []},
            )
            assert created.status_code == 201
            resource_ids[resource] = created.json()["data"]["id"]
        group = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={"code": "editor-access-group", "translations": []},
        )
        definition = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": group.json()["data"]["id"],
                "code": "editor-access-text",
                "value_type": "text",
                "translations": [],
            },
        )
        value = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": product.json()["data"]["id"],
                "definition_id": definition.json()["data"]["id"],
                "value_text": "editor-visible",
            },
        )
        assert value.status_code == 201

    product_id = product.json()["data"]["id"]
    async with _role_client(catalog_remediation_api_factory, "editor") as client:
        read_paths = [
            "/api/v1/catalog/categories",
            f"/api/v1/catalog/products/{product_id}",
            "/api/v1/catalog/specifications/groups",
            "/api/v1/catalog/specifications/definitions",
            "/api/v1/catalog/specifications/values",
            "/api/v1/catalog/materials",
            "/api/v1/catalog/technologies",
            "/api/v1/catalog/applications",
            "/api/v1/catalog/solutions",
        ]
        read_responses = [await client.get(path) for path in read_paths]
        product_update = await client.patch(
            f"/api/v1/catalog/products/{product_id}",
            json={"is_featured": True},
        )
        relation_update = await client.put(
            f"/api/v1/catalog/products/{product_id}/relations",
            json={
                "material_ids": [resource_ids["materials"]],
                "technology_ids": [resource_ids["technologies"]],
                "application_ids": [resource_ids["applications"]],
                "solution_ids": [resource_ids["solutions"]],
            },
        )
        forbidden_creates = [
            await client.post(
                f"/api/v1/catalog/{resource}",
                json={"slug": f"editor-forbidden-{resource}", "translations": []},
            )
            for resource in ("materials", "technologies", "applications", "solutions")
        ]

    assert [response.status_code for response in read_responses] == [200] * len(read_paths)
    assert product_update.status_code == 200
    assert relation_update.status_code == 200
    assert [response.status_code for response in forbidden_creates] == [403, 403, 403, 403]


async def test_specification_dictionary_supports_safe_edit_disable_clear_and_delete(
    catalog_remediation_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证规格字典可维护，并保护已被产品值引用的单位、类型和删除操作。

    输入：catalog_remediation_api_factory，带 content_admin 的隔离测试数据库。
    输出：None；字段维护、引用保护或产品值清空任一失效时测试失败。
    """
    async with _role_client(catalog_remediation_api_factory, "content_admin") as client:
        locales = (await client.get("/api/v1/locales")).json()["data"]
        zh_id = next(item["id"] for item in locales if item["code"] == "zh-CN")
        en_id = next(item["id"] for item in locales if item["code"] == "en")

        group_response = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={
                "code": "batch01-test-group",
                "sort_order": 1,
                "translations": [
                    {"locale_id": zh_id, "name": "测试参数组"},
                    {"locale_id": en_id, "name": "Test specification group"},
                ],
            },
        )
        group_id = group_response.json()["data"]["id"]
        group_update = await client.patch(
            f"/api/v1/catalog/specifications/groups/{group_id}",
            json={
                "sort_order": 2,
                "translations": [
                    {"locale_id": zh_id, "name": "测试参数组（已编辑）"},
                    {"locale_id": en_id, "name": "Edited test specification group"},
                ],
            },
        )
        group_detail = await client.get(f"/api/v1/catalog/specifications/groups/{group_id}")

        definition_response = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": group_id,
                "code": "batch01-test-length",
                "value_type": "number",
                "default_unit": "mm",
                "sort_order": 1,
                "translations": [
                    {
                        "locale_id": zh_id,
                        "name": "测试长度",
                        "fields": {"help_text": "仅用于字段管理测试"},
                    }
                ],
            },
        )
        definition_id = definition_response.json()["data"]["id"]

        category_response = await client.post(
            "/api/v1/catalog/categories",
            json={
                "slug": "batch01-test-category",
                "translations": [{"locale_id": zh_id, "name": "测试分类"}],
            },
        )
        product_response = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category_response.json()["data"]["id"],
                "slug": "batch01-test-product",
                "translations": [{"locale_id": zh_id, "name": "测试产品"}],
            },
        )
        product_id = product_response.json()["data"]["id"]
        value_response = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": product_id,
                "definition_id": definition_id,
                "value_number": 12.5,
            },
        )
        value_id = value_response.json()["data"]["id"]

        unit_change = await client.patch(
            f"/api/v1/catalog/specifications/definitions/{definition_id}",
            json={"default_unit": "cm"},
        )
        type_change = await client.patch(
            f"/api/v1/catalog/specifications/definitions/{definition_id}",
            json={"value_type": "range"},
        )
        allowed_definition_update = await client.patch(
            f"/api/v1/catalog/specifications/definitions/{definition_id}",
            json={
                "status": "disabled",
                "sort_order": 7,
                "translations": [
                    {
                        "locale_id": zh_id,
                        "name": "测试长度（停用）",
                        "fields": {"help_text": "保留历史值，不再供新录入选择"},
                    }
                ],
            },
        )
        filtered_values = await client.get(
            "/api/v1/catalog/specifications/values",
            params={"product_id": product_id},
        )
        referenced_definition_delete = await client.delete(
            f"/api/v1/catalog/specifications/definitions/{definition_id}"
        )
        referenced_group_delete = await client.delete(
            f"/api/v1/catalog/specifications/groups/{group_id}"
        )
        cleared_value = await client.delete(f"/api/v1/catalog/specifications/values/{value_id}")
        definition_delete = await client.delete(
            f"/api/v1/catalog/specifications/definitions/{definition_id}"
        )
        group_delete = await client.delete(f"/api/v1/catalog/specifications/groups/{group_id}")

    assert group_response.status_code == 201
    assert group_update.status_code == 200
    assert group_detail.status_code == 200
    assert group_detail.json()["data"]["sort_order"] == 2
    assert {item["name"] for item in group_detail.json()["data"]["translations"]} == {
        "测试参数组（已编辑）",
        "Edited test specification group",
    }
    assert unit_change.status_code == 409
    assert unit_change.json()["error"]["code"] == "specification_definition_in_use"
    assert type_change.status_code == 409
    assert type_change.json()["error"]["code"] == "specification_definition_in_use"
    assert allowed_definition_update.status_code == 200
    assert allowed_definition_update.json()["data"]["status"] == "disabled"
    assert filtered_values.status_code == 200
    assert [item["id"] for item in filtered_values.json()["data"]["items"]] == [value_id]
    assert referenced_definition_delete.status_code == 409
    assert referenced_group_delete.status_code == 409
    assert cleared_value.status_code == 200
    assert cleared_value.json()["data"] == {"deleted": True, "id": value_id}
    assert definition_delete.status_code == 200
    assert group_delete.status_code == 200


async def test_new_specification_value_requires_enabled_definition_and_group(
    catalog_remediation_api_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证新增规格值只允许启用的定义及所属分组。

    输入：catalog_remediation_api_factory，带 content_admin 的隔离测试数据库。
    输出：None；停用/退役定义或停用分组仍接受新值时测试失败。
    """
    async with _role_client(catalog_remediation_api_factory, "content_admin") as client:
        locales = (await client.get("/api/v1/locales")).json()["data"]
        zh_id = next(item["id"] for item in locales if item["code"] == "zh-CN")
        enabled_group = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={
                "code": "batch01-status-enabled-group",
                "status": "enabled",
                "translations": [{"locale_id": zh_id, "name": "启用测试组"}],
            },
        )
        category = await client.post(
            "/api/v1/catalog/categories",
            json={
                "slug": "batch01-status-category",
                "translations": [{"locale_id": zh_id, "name": "状态测试分类"}],
            },
        )
        product = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category.json()["data"]["id"],
                "slug": "batch01-status-product",
                "translations": [{"locale_id": zh_id, "name": "状态测试产品"}],
            },
        )
        blocked_product = await client.post(
            "/api/v1/catalog/products",
            json={
                "category_id": category.json()["data"]["id"],
                "slug": "batch01-status-blocked-product",
                "translations": [{"locale_id": zh_id, "name": "停用门禁测试产品"}],
            },
        )
        definition = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": enabled_group.json()["data"]["id"],
                "code": "batch01-status-definition",
                "value_type": "text",
                "translations": [{"locale_id": zh_id, "name": "状态测试字段"}],
            },
        )
        product_id = product.json()["data"]["id"]
        blocked_product_id = blocked_product.json()["data"]["id"]
        definition_id = definition.json()["data"]["id"]
        created_value = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": product_id,
                "definition_id": definition_id,
                "value_text": "历史值保留",
            },
        )

        disabled_definition = await client.patch(
            f"/api/v1/catalog/specifications/definitions/{definition_id}",
            json={"status": "disabled"},
        )
        disabled_definition_detail = await client.get(
            f"/api/v1/catalog/specifications/definitions/{definition_id}"
        )
        rejected_disabled = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": blocked_product_id,
                "definition_id": definition_id,
                "value_text": "不得新增",
            },
        )
        retired_definition = await client.patch(
            f"/api/v1/catalog/specifications/definitions/{definition_id}",
            json={"status": "retired"},
        )
        rejected_retired = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": blocked_product_id,
                "definition_id": definition_id,
                "value_text": "不得新增",
            },
        )

        disabled_group = await client.post(
            "/api/v1/catalog/specifications/groups",
            json={
                "code": "batch01-status-disabled-group",
                "status": "disabled",
                "translations": [{"locale_id": zh_id, "name": "停用测试组"}],
            },
        )
        disabled_group_definition = await client.post(
            "/api/v1/catalog/specifications/definitions",
            json={
                "group_id": disabled_group.json()["data"]["id"],
                "code": "batch01-status-group-definition",
                "value_type": "number",
                "translations": [{"locale_id": zh_id, "name": "停用组字段"}],
            },
        )
        rejected_group = await client.post(
            "/api/v1/catalog/specifications/values",
            json={
                "product_id": blocked_product_id,
                "definition_id": disabled_group_definition.json()["data"]["id"],
                "value_number": 1.0,
            },
        )
        retained_values = await client.get(
            "/api/v1/catalog/specifications/values",
            params={"product_id": product_id},
        )

    assert enabled_group.status_code == 201
    assert category.status_code == 201
    assert product.status_code == 201
    assert blocked_product.status_code == 201
    assert definition.status_code == 201
    assert created_value.status_code == 201
    assert disabled_definition.status_code == 200
    assert disabled_definition.json()["data"]["status"] == "disabled"
    assert disabled_definition_detail.json()["data"]["status"] == "disabled"
    assert rejected_disabled.status_code == 409
    assert rejected_disabled.json()["error"]["code"] == "specification_definition_inactive"
    assert retired_definition.status_code == 200
    assert rejected_retired.status_code == 409
    assert rejected_retired.json()["error"]["code"] == "specification_definition_inactive"
    assert disabled_group.status_code == 201
    assert disabled_group_definition.status_code == 201
    assert rejected_group.status_code == 409
    assert rejected_group.json()["error"]["code"] == "specification_group_inactive"
    assert retained_values.status_code == 200
    assert [item["id"] for item in retained_values.json()["data"]["items"]] == [
        created_value.json()["data"]["id"]
    ]
