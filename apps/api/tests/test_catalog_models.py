"""Structured Core 模型与数据库约束的先行测试。"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database.base import Base
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.catalog.enums import SpecificationValueType
from app.modules.catalog.models import (
    Product,
    ProductCategory,
    ProductModel,
    ProductSpecValue,
    SpecificationDefinition,
    SpecificationGroup,
)
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.localization import models as _localization_models  # noqa: F401
from app.modules.users import models as _user_models  # noqa: F401


def test_catalog_tables_and_value_type_enum_are_declared() -> None:
    """模型必须声明交接文件要求的 Structured Core 表。"""
    expected = {
        "product_categories",
        "products",
        "product_models",
        "specification_groups",
        "specification_definitions",
        "product_spec_values",
        "materials",
        "technologies",
        "applications",
        "solutions",
        "product_materials",
        "product_technologies",
        "product_applications",
        "product_solutions",
        "material_technologies",
        "material_solutions",
        "application_solutions",
    }
    assert expected.issubset(set(Base.metadata.tables))
    assert {item.value for item in SpecificationValueType} == {
        "text",
        "number",
        "range",
        "boolean",
        "enum",
    }


@pytest.mark.asyncio
async def test_product_spec_value_requires_exactly_one_owner(sqlite_database_url: str) -> None:
    """产品规格值必须由 Product 或 ProductModel 恰好一个拥有。"""
    from app.core.database import create_database_engine, create_session_factory

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async_session_factory = create_session_factory(engine)
    category = ProductCategory(slug="test-category", status="enabled")
    async with async_session_factory() as session, session.begin():
        session.add(category)
        await session.flush()
        product = Product(category_id=category.id, slug="test-product", status="enabled")
        group = SpecificationGroup(code="dimensions", status="enabled")
        session.add_all([product, group])
        await session.flush()
        definition = SpecificationDefinition(
            group_id=group.id,
            code="diameter",
            value_type="number",
            status="enabled",
        )
        session.add(definition)
        await session.flush()
        session.add(
            ProductSpecValue(
                product_id=product.id,
                product_model_id=uuid.uuid4(),
                definition_id=definition.id,
                value_number=10,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
    await engine.dispose()


def test_product_model_code_is_scoped_to_product() -> None:
    """ProductModel 的重复型号约束必须由同一 Product 范围决定。"""
    table = ProductModel.__table__
    constraints = {tuple(column.name for column in item.columns) for item in table.constraints}
    assert ("product_id", "model_code") in constraints


def test_explicit_relation_tables_have_composite_keys() -> None:
    """核心关系必须是显式关联表而不是通用 entity_links。"""
    for table_name in (
        "product_materials",
        "product_technologies",
        "product_applications",
        "product_solutions",
        "material_technologies",
        "material_solutions",
        "application_solutions",
    ):
        table = Base.metadata.tables[table_name]
        assert len(table.primary_key.columns) == 2


def test_all_core_entities_have_translation_classes() -> None:
    """每个核心实体均必须拥有独立 Translation ORM 类。"""
    from app.modules.catalog.models import CORE_TRANSLATION_MODELS

    assert {model.__tablename__ for model in CORE_TRANSLATION_MODELS} == {
        "product_category_translations",
        "product_translations",
        "product_model_translations",
        "specification_group_translations",
        "specification_definition_translations",
        "material_translations",
        "technology_translations",
        "application_translations",
        "solution_translations",
    }
