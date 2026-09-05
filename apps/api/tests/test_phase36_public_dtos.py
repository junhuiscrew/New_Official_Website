"""Phase 3.6 公开 Product DTO 白名单与规格序列化契约测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory


@pytest.fixture
async def phase36_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建包含 Phase 3.6 所需模型的隔离数据库。

    输入：
        sqlite_database_url: str，测试数据库地址。

    输出：
        AsyncIterator[async_sessionmaker[AsyncSession]]，异步会话工厂。
    """
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


def _spec_value(**overrides: object) -> SimpleNamespace:
    """
    构造规格值测试替身。

    输入：
        overrides: object，覆盖默认空值的规格字段。

    输出：
        SimpleNamespace，具备五类存储列的规格值替身。
    """
    values: dict[str, object | None] = {
        "value_text": None,
        "value_number": None,
        "value_min": None,
        "value_max": None,
        "value_boolean": None,
        "enum_value": None,
        "unit_override": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_public_schema_models_are_exact_allowlists() -> None:
    """
    验证公开 DTO 仅允许约定字段，并拒绝内部标识。

    输入：公开媒体和规格字段。
    输出：None；字段缺失、额外字段被接受或内部字段泄漏时失败。
    """
    from app.modules.discovery.public_schemas import PublicMediaDto, PublicSpecDto

    media = PublicMediaDto(
        src="/api/v1/public/media/asset-id",
        type="image",
        mime_type="image/webp",
        width=1200,
        height=800,
        alt="挤出机螺杆",
        caption="公开产品图",
        loading="eager",
    )
    specification = PublicSpecDto(
        name="直径",
        value="120.5",
        unit="mm",
        group="尺寸",
        type="number",
    )

    assert set(media.model_dump()) == {
        "src",
        "type",
        "mime_type",
        "width",
        "height",
        "alt",
        "caption",
        "loading",
    }
    assert set(specification.model_dump()) == {"name", "value", "unit", "group", "type"}
    with pytest.raises(ValidationError):
        PublicSpecDto(
            name="直径",
            value="120.5",
            unit="mm",
            group="尺寸",
            type="number",
            definition_id="internal-id",
        )
    with pytest.raises(ValidationError):
        PublicMediaDto(
            src="/api/v1/public/media/asset-id",
            type="image",
            mime_type="image/webp",
            alt=None,
        )


def test_all_spec_value_types_serialize_without_internal_fields() -> None:
    """
    验证 text、number、range、boolean、enum 均输出翻译后的干净 DTO。

    输入：五种规格存储值、翻译名称和单位。
    输出：None；值格式错误、单位错误或 ORM 内部字段泄漏时失败。
    """
    from app.modules.discovery.public_specs import serialize_public_spec

    definition_translation = SimpleNamespace(name="规格名称")
    group_translation = SimpleNamespace(name="技术参数")
    cases = (
        ("text", _spec_value(value_text="38CrMoAlA"), None, "38CrMoAlA"),
        (
            "number",
            _spec_value(value_number=Decimal("120.500000"), unit_override="rpm"),
            "mm",
            "120.5",
        ),
        (
            "range",
            _spec_value(value_min=Decimal("1.250000"), value_max=Decimal("3.500000")),
            "mm",
            "1.25–3.5",
        ),
        ("boolean", _spec_value(value_boolean=False), None, "No"),
        ("enum", _spec_value(enum_value="nitrided"), None, "nitrided"),
    )

    serialized = []
    for value_type, value, default_unit, expected_value in cases:
        definition = SimpleNamespace(value_type=value_type, default_unit=default_unit)
        dto = serialize_public_spec(
            value,
            definition,
            definition_translation,
            group_translation,
            "en",
        )
        assert dto is not None
        result = dto.model_dump()
        assert result == {
            "name": "规格名称",
            "value": expected_value,
            "unit": value.unit_override or default_unit,
            "group": "技术参数",
            "type": value_type,
        }
        serialized.append(result)

    assert all(set(item) == {"name", "value", "unit", "group", "type"} for item in serialized)

    chinese_boolean = serialize_public_spec(
        _spec_value(value_boolean=True),
        SimpleNamespace(value_type="boolean", default_unit=None),
        definition_translation,
        group_translation,
        "zh-cn",
    )
    assert chinese_boolean is not None
    assert chinese_boolean.value == "是"


def test_impossible_spec_storage_combination_is_filtered() -> None:
    """
    验证规格类型与存储列不一致时不会输出原始数据。

    输入：boolean 定义配 text 存储列的非法组合。
    输出：None；非法组合未被过滤时失败。
    """
    from app.modules.discovery.public_specs import serialize_public_spec

    result = serialize_public_spec(
        _spec_value(value_text='{"unsafe": "raw-json"}'),
        SimpleNamespace(value_type="boolean", default_unit=None),
        SimpleNamespace(name="非法规格"),
        SimpleNamespace(name="技术参数"),
        "en",
    )

    assert result is None


@pytest.mark.asyncio
async def test_public_product_uses_proxy_media_and_clean_specifications(
    phase36_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 Product 仅交付 public-media 代理 DTO 和干净规格 DTO。

    输入：严格已发布产品、公开/私有媒体及本地化规格。
    输出：None；门禁失效、内部存储字段泄漏或私有媒体公开时失败。
    """
    from app.modules.catalog.models import (
        Product,
        ProductCategory,
        ProductCategoryTranslation,
        ProductSpecValue,
        ProductTranslation,
        SpecificationDefinition,
        SpecificationDefinitionTranslation,
        SpecificationGroup,
        SpecificationGroupTranslation,
    )
    from app.modules.company.models import (
        CompanyProfile,
        CompanyProfileTranslation,
        ManufacturingCapability,
        ManufacturingCapabilityTranslation,
    )
    from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
    from app.modules.discovery.public_collections import get_public_listing
    from app.modules.discovery.public_delivery import get_public_product
    from app.modules.localization.models import Locale
    from app.modules.media.models import MediaAsset, MediaAssetTranslation

    async with phase36_factory() as session, session.begin():
        locale = Locale(
            code="en",
            slug="en",
            name="English",
            native_name="English",
            is_default=True,
            is_enabled=True,
        )
        category = ProductCategory(slug="screws", status="enabled")
        group = SpecificationGroup(code="dimensions", status="enabled")
        unpublished_company = CompanyProfile(status="enabled", founded_year=1900)
        company = CompanyProfile(
            status="enabled",
            founded_year=1985,
            years_experience=40,
            annual_capacity_text="Published annual capacity",
        )
        capability = ManufacturingCapability(
            slug="precision-machining",
            capability_type="machining",
            status="enabled",
            sort_order=8,
        )
        unpublished_capabilities = [
            ManufacturingCapability(
                slug=f"draft-capability-{index}",
                capability_type="machining",
                status="enabled",
                sort_order=index,
            )
            for index in range(8)
        ]
        session.add_all(
            [
                locale,
                category,
                group,
                unpublished_company,
                company,
                *unpublished_capabilities,
                capability,
            ]
        )
        await session.flush()

        public_asset = MediaAsset(
            visibility="public",
            media_type="image",
            storage_bucket="public-media",
            storage_key="public/products/extrusion-screw.webp",
            original_filename="extrusion-screw.webp",
            sanitized_filename="extrusion-screw.webp",
            mime_type="image/webp",
            file_extension="webp",
            file_size_bytes=1024,
            sha256="a" * 64,
            width=1600,
            height=900,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status="ready",
        )
        private_asset = MediaAsset(
            visibility="private",
            media_type="image",
            storage_bucket="private-rfq",
            storage_key="minio:9000/private-rfq/customer-secret.webp",
            original_filename="customer-secret.webp",
            sanitized_filename="customer-secret.webp",
            mime_type="image/webp",
            file_extension="webp",
            file_size_bytes=512,
            sha256="b" * 64,
            width=640,
            height=480,
            checksum_verified=True,
            malware_scan_status="clean",
            upload_status="ready",
        )
        session.add_all([public_asset, private_asset])
        await session.flush()

        product = Product(
            category_id=category.id,
            slug="extrusion-screw",
            status="enabled",
            primary_media_id=public_asset.id,
        )
        definition = SpecificationDefinition(
            group_id=group.id,
            code="diameter",
            value_type="number",
            default_unit="mm",
            status="enabled",
        )
        session.add_all([product, definition])
        await session.flush()
        session.add_all(
            [
                ProductTranslation(
                    product_id=product.id,
                    locale_id=locale.id,
                    name="Extrusion screw",
                    short_description="Visible product",
                ),
                ProductCategoryTranslation(
                    category_id=category.id,
                    locale_id=locale.id,
                    name="Screws",
                ),
                CompanyProfileTranslation(
                    company_profile_id=company.id,
                    locale_id=locale.id,
                    company_name="Junhui",
                    short_intro="Published company profile",
                    full_intro="Published company details",
                ),
                ManufacturingCapabilityTranslation(
                    capability_id=capability.id,
                    locale_id=locale.id,
                    name="Precision machining",
                    summary="Published capability",
                ),
                SpecificationGroupTranslation(
                    group_id=group.id,
                    locale_id=locale.id,
                    name="Dimensions",
                ),
                SpecificationDefinitionTranslation(
                    definition_id=definition.id,
                    locale_id=locale.id,
                    name="Diameter",
                ),
                ProductSpecValue(
                    product_id=product.id,
                    definition_id=definition.id,
                    value_number=Decimal("120.500000"),
                    is_public=True,
                ),
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
                    path="/en/products/screws/extrusion-screw/",
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
                TranslationStatus(
                    owner_type="product_category",
                    owner_id=category.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="product_category",
                    owner_id=category.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="product_category",
                    owner_id=category.id,
                    locale_id=locale.id,
                    path="/en/products/screws/",
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
                TranslationStatus(
                    owner_type="company_profile",
                    owner_id=company.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="company_profile",
                    owner_id=company.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="company_profile",
                    owner_id=company.id,
                    locale_id=locale.id,
                    path="/en/about/",
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
                TranslationStatus(
                    owner_type="manufacturing_capability",
                    owner_id=capability.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentPublication(
                    owner_type="manufacturing_capability",
                    owner_id=capability.id,
                    locale_id=locale.id,
                    status="published",
                ),
                ContentRoute(
                    owner_type="manufacturing_capability",
                    owner_id=capability.id,
                    locale_id=locale.id,
                    path="/en/capabilities/precision-machining/",
                    is_canonical=True,
                    active=True,
                    indexable=True,
                ),
            ]
        )
        await session.flush()

        payload = await get_public_product(session, "en", "screws", "extrusion-screw")
        expected_media = {
            "src": f"/api/v1/public/media/{public_asset.id}",
            "type": "image",
            "mime_type": "image/webp",
            "width": 1600,
            "height": 900,
            "alt": "Extrusion screw",
            "caption": None,
            "loading": "eager",
        }
        # 缺少媒体翻译时，图片 alt 必须回退到当前语言的产品名称。
        assert payload["primary_media"] == expected_media
        assert payload["media"] == [expected_media]
        assert payload["specifications"] == [
            {
                "name": "Diameter",
                "value": "120.5",
                "unit": "mm",
                "group": "Dimensions",
                "type": "number",
            }
        ]
        assert "minio:9000" not in repr(payload)
        assert "storage_key" not in repr(payload)
        assert "definition_id" not in repr(payload)
        assert payload["alternates"]["en"].endswith("/en/products/screws/extrusion-screw/")
        assert payload["relations"]["capabilities"] == [
            {
                "type": "manufacturing_capability",
                "slug": "precision-machining",
                "name": "Precision machining",
                "url": "/en/capabilities/precision-machining/",
                "summary": "Published capability",
            }
        ]
        assert payload["trust_summary"] == {
            "founded_year": 1985,
            "years_experience": 40,
            "annual_capacity_text": "Published annual capacity",
        }
        assert payload["schema"]

        listing = await get_public_listing(session, "product", "en", 1, 24)
        assert listing["items"] == [
            {
                "type": "product",
                "slug": "extrusion-screw",
                "name": "Extrusion screw",
                "url": "/en/products/screws/extrusion-screw/",
                "summary": "Visible product",
                "media": {**expected_media, "loading": "lazy"},
                "category": {
                    "type": "product_category",
                    "slug": "screws",
                    "name": "Screws",
                    "url": "/en/products/screws/",
                    "summary": "",
                },
                "specifications": payload["specifications"],
            }
        ]
        assert listing["seo"]["canonical"] == "https://junhuiscrewbarrel.com/en/products/"
        assert listing["seo"]["robots"] == "index, follow"

        media_translation = MediaAssetTranslation(
            media_asset_id=public_asset.id,
            locale_id=locale.id,
            alt_text=None,
            caption="Public product image",
        )
        session.add(media_translation)
        await session.flush()
        null_alt_payload = await get_public_product(
            session,
            "en",
            "screws",
            "extrusion-screw",
        )
        assert null_alt_payload["primary_media"]["alt"] == "Extrusion screw"

        # 空白 alt 与空值同样不可公开，必须使用产品本地化名称。
        media_translation.alt_text = "  \t"
        await session.flush()
        blank_alt_payload = await get_public_product(
            session,
            "en",
            "screws",
            "extrusion-screw",
        )
        assert blank_alt_payload["primary_media"]["alt"] == "Extrusion screw"

        # 即使产品记录错误引用 private-rfq，也必须闭合失败为无媒体。
        product.primary_media_id = private_asset.id
        await session.flush()
        private_payload = await get_public_product(
            session,
            "en",
            "screws",
            "extrusion-screw",
        )
        assert private_payload["primary_media"] is None
        assert private_payload["media"] == []
        assert "customer-secret" not in repr(private_payload)

        stored_product = await session.scalar(select(Product).where(Product.id == product.id))
        assert stored_product is not None
