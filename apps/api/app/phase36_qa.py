"""Phase 3.6 Remediation 的本地有内容浏览器 QA 数据准备器。"""

from __future__ import annotations

import os
import re
import struct
import uuid
import zlib
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.models import AuditLog
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import (
    AuthorExpert,
    CaseStudy,
    KnowledgeArticle,
    KnowledgeCategory,
)
from app.modules.authority.schemas import (
    AuthorExpertCreate,
    AuthorityRelationUpdate,
    AuthorityTranslationInput,
    CaseStudyCreate,
    KnowledgeArticleCreate,
    KnowledgeCategoryCreate,
)
from app.modules.authority.services import (
    create_author_expert,
    create_case_study,
    create_knowledge_article,
    create_knowledge_category,
    replace_authority_relations,
)
from app.modules.catalog.models import (
    Application,
    Material,
    Product,
    ProductCategory,
    ProductSpecValue,
    ProductTranslation,
    Solution,
    SpecificationDefinition,
    SpecificationGroup,
    Technology,
)
from app.modules.catalog.schemas import (
    CategoryCreate,
    EntityCreate,
    ProductCreate,
    ProductUpdate,
    RelationUpdate,
    SpecificationDefinitionCreate,
    SpecificationGroupCreate,
    SpecificationValueCreate,
    TranslationInput,
)
from app.modules.catalog.services import (
    create_category,
    create_core_entity,
    create_product,
    create_specification_definition,
    create_specification_group,
    create_specification_value,
    replace_product_relations,
    update_product,
)
from app.modules.company.models import (
    CapabilityEquipment,
    CompanyProfile,
    CompanyProfileTranslation,
    Equipment,
    ManufacturingCapability,
)
from app.modules.company.schemas import (
    CompanyProfileInput,
    TrustEntityInput,
    TrustTranslation,
)
from app.modules.company.services import create_trust_entity, upsert_company_profile
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    TranslationStatus,
)
from app.modules.content.services.publication import transition_publication
from app.modules.discovery.models import GeoDocument, SeoDocument, SourceCitation
from app.modules.localization.models import Locale
from app.modules.media.models import (
    DownloadResource,
    DownloadResourceTranslation,
    MediaAsset,
    MediaAssetTranslation,
)
from app.modules.media.services import validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter
from app.modules.rfq.models import RFQ, RFQFile

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")
_QA_CONFIRMATION = "LOCAL_QA_ONLY"
_QA_ISOLATION = "LOCAL_COMPOSE_ONLY"
_LOCAL_SERVICE_HOSTS = {"localhost", "127.0.0.1", "postgres", "redis", "minio"}
def _build_qa_png() -> bytes:
    """
    生成本地 QA 专用的正常尺寸 PNG 测试图。

    输入：无。
    输出：bytes，1200×800 的非敏感 QA 图片，带蓝色边框和浅色背景。
    """
    width, height = 1200, 800
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # PNG 无滤波行标记
        for x in range(width):
            is_border = x < 12 or x >= width - 12 or y < 12 or y >= height - 12
            rows.extend((22, 82, 140) if is_border else (235, 245, 255))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        """构造带 CRC 的 PNG 数据块。"""
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + chunk(b"IEND", b"")
    )


# 公开样本图片只用于本地 E2E；字节经过正常签名/SHA256 校验并真实写入 MinIO。
_QA_PNG = _build_qa_png()
_QA_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<<>>\n%%EOF\n"

_CORE_MODELS = {
    "material": Material,
    "technology": Technology,
    "application": Application,
    "solution": Solution,
}


class Phase36QaManifest(BaseModel):
    """可提交的脱敏 QA 清单；不包含凭据、RFQ token 或私有签名 URL。"""

    run_id: str
    product_slug: str
    product_category_slug: str
    knowledge_slug: str
    knowledge_category_slug: str
    missing_translation_slug: str
    material_slug: str
    technology_slug: str
    application_slug: str
    solution_slug: str
    capability_slug: str
    equipment_slug: str
    case_slug: str
    expert_slug: str
    draft_slug: str
    noindex_slug: str
    unmatched_material_slug: str
    download_slug: str
    public_object_keys: list[str]
    company_profile_marker: str
    specification_code_prefix: str
    rfq_email_markers: list[str]
    rate_limit_namespace: str
    resource_slugs: dict[str, list[str]]
    product_count: int
    specification_types: list[str]


class Phase36QaCleanupResult(BaseModel):
    """本地 QA 精确清理结果；只输出计数，不泄露客户或存储标识。"""

    run_id: str
    deleted: dict[str, int]


class Phase36QaVerificationResult(BaseModel):
    """QA 旅程持久化核验结果；不输出 UUID、公开编号或私有 URL。"""

    run_id: str
    rfq_count: int
    source_persistence: dict[str, bool]
    attachment_records: int
    private_objects_exist: bool


def _qa_identifiers(run_id: str, *, product_count: int = 26) -> dict[str, object]:
    """
    生成一个 QA run 唯一且可重建的资源标识。

    输入：run_id: str，已校验的运行标识；product_count: int，分页样本产品数。
    输出：dict[str, object]，只含可公开的 slug、标记和限流命名空间。
    """
    slugs = {
        "category": f"qa36-{run_id}-screws",
        "product": f"qa36-{run_id}-extrusion-screw",
        "knowledge_category": f"qa36-{run_id}-guides",
        "knowledge": f"qa36-{run_id}-screw-selection",
        "missing_translation": f"qa36-{run_id}-english-only",
        "material": f"qa36-{run_id}-material",
        "technology": f"qa36-{run_id}-technology",
        "application": f"qa36-{run_id}-application",
        "solution": f"qa36-{run_id}-solution",
        "capability": f"qa36-{run_id}-capability",
        "equipment": f"qa36-{run_id}-equipment",
        "case_study": f"qa36-{run_id}-anonymous-case",
        "expert": f"qa36-{run_id}-verified-author",
        "draft": f"qa36-{run_id}-draft-product",
        "noindex": f"qa36-{run_id}-noindex-product",
        "unmatched_material": f"qa36-{run_id}-unmatched-material",
        "download": f"qa36-{run_id}-datasheet",
    }
    return {
        "slugs": slugs,
        "company_profile_marker": f"QA ONLY Junhui {run_id}",
        "specification_code_prefix": f"qa36-{run_id}-",
        "public_object_keys": [
            f"qa/phase36/{run_id}/product.png",
            f"qa/phase36/{run_id}/qa-datasheet.pdf",
        ],
        "rfq_email_markers": [
            f"phase36-{run_id}-product@example.com",
            f"phase36-{run_id}-knowledge@example.com",
            f"phase36-{run_id}-case@example.com",
        ],
        "rate_limit_namespace": f"rfq:public:qa36:{run_id}",
        "product_slugs": [
            str(slugs["product"]),
            *[
                f"qa36-{run_id}-product-{index:02d}"
                for index in range(1, product_count)
            ],
            str(slugs["draft"]),
            str(slugs["noindex"]),
        ],
    }


def _assert_qa_allowed(run_id: str) -> str:
    """
    验证隔离 QA 命令的环境和显式确认。

    输入：run_id: str，调用方指定的短期运行标识。
    输出：str，校验后的运行标识；不安全时抛出 AppException。
    """
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise AppException(409, "qa_forbidden_environment", "QA 数据命令仅允许本地开发或测试环境")
    if os.getenv("PHASE36_QA_CONFIRM") != _QA_CONFIRMATION:
        raise AppException(409, "qa_confirmation_required", "必须显式确认本地 QA 数据准备")
    if os.getenv("PHASE36_QA_ISOLATION") != _QA_ISOLATION:
        raise AppException(409, "qa_isolation_required", "必须显式确认使用本地 Compose 隔离资源")

    # 除环境名外再次校验实际连接目标，避免误把 QA 样本写入远端 DB/Redis/MinIO。
    database_url = make_url(settings.database_url)
    database_host = (database_url.host or "").lower()
    redis_host = (urlparse(settings.redis_url).hostname or "").lower()
    minio_host = (urlparse(f"//{settings.minio_endpoint}").hostname or "").lower()
    if (
        database_host not in _LOCAL_SERVICE_HOSTS
        or redis_host not in _LOCAL_SERVICE_HOSTS
        or minio_host not in _LOCAL_SERVICE_HOSTS
        or settings.minio_public_bucket != "public-media"
        or settings.minio_private_bucket != "private-rfq"
    ):
        raise AppException(409, "qa_target_not_local", "QA 连接目标不是受控本地 Compose 资源")
    normalized = run_id.strip().lower()
    if not _RUN_ID.fullmatch(normalized):
        raise AppException(
            422, "qa_run_id_invalid", "QA run-id 必须是 3~40 位小写字母、数字或连字符"
        )
    expected_database_name = os.getenv("PHASE36_QA_DATABASE_NAME", "").strip()
    if not expected_database_name or database_url.database != expected_database_name:
        raise AppException(
            409,
            "qa_database_name_required",
            "QA 必须显式声明并匹配当前本地数据库名",
        )
    expected_namespace = f"rfq:public:qa36:{normalized}"
    if settings.rfq_rate_limit_namespace != expected_namespace:
        raise AppException(
            409,
            "qa_rate_limit_namespace_required",
            "QA 必须使用与 run-id 完全一致的独立限流命名空间",
        )
    return normalized


async def _publish_owner_locale(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> None:
    """
    通过统一 Publication 状态机发布一个本地 QA 语言版本。

    输入：session、owner_type、owner_id、locale_id。
    输出：None；缺少既有 Translation/Publication/Route 时闭合失败。
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
        raise AppException(409, "qa_lifecycle_missing", "QA 内容缺少统一发布生命周期记录")

    # QA 不创建后台用户；仍记录明确审核审计，并复用正式 Publication 状态机。
    translation.status = "human_reviewed"
    write_audit_log(
        session,
        action="translation.review",
        target_type=owner_type,
        target_id=str(owner_id),
        metadata={"qa_run": True, "locale_id": str(locale_id)},
    )
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=PublicationStatus.REVIEW,
        actor_permissions={"content.review"},
        actor_id=None,
    )
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=PublicationStatus.PUBLISHED,
        actor_permissions={"content.publish"},
        actor_id=None,
    )


async def _publish_many(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locales: Sequence[Locale],
) -> None:
    """输入会话、owner 和语言集合；输出 None，并逐语言走正式发布状态机。"""
    for locale in locales:
        await _publish_owner_locale(
            session,
            owner_type=owner_type,
            owner_id=owner_id,
            locale_id=locale.id,
        )


async def _ensure_representative_product_copy(
    session: AsyncSession,
    *,
    product: Product,
    locales: Sequence[Locale],
) -> None:
    """
    让重复执行的既有 QA 产品收敛到长标题与完整正文，并重新走审核发布流程。

    输入：session、代表产品与 en/zh-CN 语言集合。
    输出：None；内容无变化时不写库，有变化时通过正式 Product 更新和 Publication 状态机发布。
    """
    translations = list(
        (
            await session.scalars(
                select(ProductTranslation).where(ProductTranslation.product_id == product.id)
            )
        ).all()
    )
    by_locale = {translation.locale_id: translation for translation in translations}
    expected_names = {
        "en": "QA ONLY Long-title Extrusion Screw for Responsive Browser Validation",
        "zh-CN": "仅测试：用于响应式浏览器验收的长标题挤出机螺杆",
    }
    copy_is_current = all(
        by_locale.get(locale.id) is not None
        and by_locale[locale.id].name == expected_names[locale.code]
        for locale in locales
    )
    if not copy_is_current:
        payload_translations: list[TranslationInput] = []
        for locale in locales:
            existing = by_locale.get(locale.id)
            if existing is None:
                raise AppException(
                    409,
                    "qa_product_translation_missing",
                    "既有 QA 产品缺少双语翻译",
                )
            payload_translations.append(
                TranslationInput(
                    locale_id=locale.id,
                    name=expected_names[locale.code],
                    fields={
                        "short_description": existing.short_description,
                        "description": existing.description,
                        "highlights_jsonb": existing.highlights_jsonb,
                    },
                )
            )
        # 正式更新服务会撤销已发布正文，不直接改翻译表。
        await update_product(
            session,
            product.id,
            ProductUpdate(translations=payload_translations),
        )

    for locale in locales:
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == "product",
                ContentPublication.owner_id == product.id,
                ContentPublication.locale_id == locale.id,
            )
        )
        translation_status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == "product",
                TranslationStatus.owner_id == product.id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == "product",
                ContentRoute.owner_id == product.id,
                ContentRoute.locale_id == locale.id,
                ContentRoute.is_canonical.is_(True),
            )
        )
        if publication is None or translation_status is None or route is None:
            raise AppException(409, "qa_lifecycle_missing", "既有 QA 产品缺少发布生命周期")
        if (
            publication.status == PublicationStatus.PUBLISHED.value
            and translation_status.status == "published"
            and route.active
            and route.indexable
        ):
            continue

        # 中断的任意合法状态都经统一状态机收敛，不直接伪造 published。
        all_permissions = {
            "content.review",
            "content.publish",
            "content.archive",
            "content.update",
        }
        if publication.status == PublicationStatus.PUBLISHED.value:
            await transition_publication(
                session,
                publication=publication,
                translation=translation_status,
                route=route,
                target_status=PublicationStatus.ARCHIVED,
                actor_permissions=all_permissions,
                actor_id=None,
            )
        if publication.status == PublicationStatus.ARCHIVED.value:
            await transition_publication(
                session,
                publication=publication,
                translation=translation_status,
                route=route,
                target_status=PublicationStatus.DRAFT,
                actor_permissions=all_permissions,
                actor_id=None,
            )
        translation_status.status = "human_reviewed"
        write_audit_log(
            session,
            action="translation.review",
            target_type="product",
            target_id=str(product.id),
            metadata={"qa_run": True, "locale_id": str(locale.id)},
        )
        if publication.status == PublicationStatus.DRAFT.value:
            await transition_publication(
                session,
                publication=publication,
                translation=translation_status,
                route=route,
                target_status=PublicationStatus.REVIEW,
                actor_permissions=all_permissions,
                actor_id=None,
            )
        if publication.status in {
            PublicationStatus.REVIEW.value,
            PublicationStatus.SCHEDULED.value,
        }:
            await transition_publication(
                session,
                publication=publication,
                translation=translation_status,
                route=route,
                target_status=PublicationStatus.PUBLISHED,
                actor_permissions=all_permissions,
                actor_id=None,
            )


async def _create_public_media(
    session: AsyncSession,
    storage: MinioStorageAdapter,
    run_id: str,
    locales: Sequence[Locale],
) -> MediaAsset:
    """
    创建真实 public-media 对象及数据库记录。

    输入：数据库会话、MinIO 适配器、run_id、语言集合。
    输出：MediaAsset，可供首页与详情页公共 DTO 使用。
    """
    key = f"qa/phase36/{run_id}/product.png"
    existing = await session.scalar(
        select(MediaAsset).where(
            MediaAsset.storage_bucket == "public-media",
            MediaAsset.storage_key == key,
        )
    )
    if existing is not None:
        if not await storage.object_exists("public-media", key):
            await storage.put_object("public-media", key, _QA_PNG, "image/png")
        return existing
    metadata = validate_upload_bytes("phase36-product.png", "image/png", _QA_PNG)
    await storage.put_object("public-media", key, _QA_PNG, "image/png")
    asset = MediaAsset(
        visibility="public",
        storage_bucket="public-media",
        storage_key=key,
        checksum_verified=True,
        malware_scan_status="not_required",
        upload_status="ready",
        width=1200,
        height=800,
        **metadata,
    )
    session.add(asset)
    await session.flush()
    for locale in locales:
        session.add(
            MediaAssetTranslation(
                media_asset_id=asset.id,
                locale_id=locale.id,
                alt_text=(
                    "Phase 3.6 QA extrusion screw sample"
                    if locale.code == "en"
                    else "Phase 3.6 QA 挤出机螺杆样本"
                ),
                caption="Local QA only",
            )
        )
    await session.flush()
    return asset


async def _create_public_pdf(
    session: AsyncSession,
    storage: MinioStorageAdapter,
    run_id: str,
    locales: Sequence[Locale],
) -> tuple[MediaAsset, DownloadResource]:
    """
    创建真实 public-media PDF 与公开下载记录。

    输入：数据库会话、MinIO 适配器、run_id 和语言集合。
    输出：tuple[MediaAsset, DownloadResource]，可由公开下载页读取的真实对象和资源。
    """
    key = f"qa/phase36/{run_id}/qa-datasheet.pdf"
    slug = f"qa36-{run_id}-datasheet"
    asset = await session.scalar(
        select(MediaAsset).where(
            MediaAsset.storage_bucket == "public-media",
            MediaAsset.storage_key == key,
        )
    )
    if asset is None:
        metadata = validate_upload_bytes("qa-datasheet.pdf", "application/pdf", _QA_PDF)
        await storage.put_object("public-media", key, _QA_PDF, "application/pdf")
        asset = MediaAsset(
            visibility="public",
            storage_bucket="public-media",
            storage_key=key,
            checksum_verified=True,
            malware_scan_status="not_required",
            upload_status="ready",
            **metadata,
        )
        session.add(asset)
        await session.flush()
    elif not await storage.object_exists("public-media", key):
        await storage.put_object("public-media", key, _QA_PDF, "application/pdf")

    resource = await session.scalar(select(DownloadResource).where(DownloadResource.slug == slug))
    if resource is None:
        resource = DownloadResource(
            slug=slug,
            resource_type="document",
            media_asset_id=asset.id,
            status="enabled",
            version_label="QA ONLY",
        )
        session.add(resource)
        await session.flush()
        for locale in locales:
            session.add(
                DownloadResourceTranslation(
                    download_resource_id=resource.id,
                    locale_id=locale.id,
                    title=(
                        "QA ONLY technical datasheet" if locale.code == "en" else "仅测试技术资料"
                    ),
                    summary="Local isolated browser QA file.",
                )
            )
        await session.flush()
    return asset, resource


async def _ensure_core_entity(
    session: AsyncSession,
    *,
    owner_type: str,
    slug: str,
    locales: Sequence[Locale],
) -> object:
    """
    通过 Catalog 服务幂等创建并发布一个结构化核心实体。

    输入：session、owner_type、slug 与双语 Locale。
    输出：object，已完成统一生命周期的 Material/Technology/Application/Solution。
    """
    model = _CORE_MODELS[owner_type]
    entity = await session.scalar(select(model).where(model.slug == slug))
    if entity is None:
        label = owner_type.replace("_", " ").title()
        entity = await create_core_entity(
            session,
            owner_type,
            EntityCreate(
                slug=slug,
                featured=True,
                translations=_catalog_translations(
                    locales,
                    f"QA ONLY {label}",
                    f"仅测试 {label}",
                ),
            ),
        )
        await _publish_many(session, owner_type, entity.id, locales)
    return entity


async def _publish_non_route_translation(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locales: Sequence[Locale],
) -> None:
    """
    发布无独立 Route/Publication 的 Trust TranslationStatus。

    输入：数据库会话、owner 类型/ID 与语言集合。
    输出：None；状态与现有 FAQ-style review/publish 流程一致并写入审计。
    """
    for locale in locales:
        status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == owner_type,
                TranslationStatus.owner_id == owner_id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        if status is None:
            raise AppException(409, "qa_translation_status_missing", "QA Trust 翻译状态不存在")
        status.status = "published"
        status.published_at = datetime.now(UTC)
        write_audit_log(
            session,
            action="translation.publish",
            target_type=owner_type,
            target_id=str(owner_id),
            metadata={"qa_run": True, "locale_id": str(locale.id)},
        )
    await session.flush()


async def _ensure_extended_qa_content(
    session: AsyncSession,
    *,
    storage: MinioStorageAdapter,
    run_id: str,
    locales: Sequence[Locale],
    category: object,
    product: Product,
    media: MediaAsset,
) -> dict[str, object]:
    """
    补齐 Company/Core/Trust/Case/Download 与负向发布样本。

    输入：会话、对象存储、run-id、语言、代表分类/产品/媒体。
    输出：dict[str, object]，manifest 和浏览器旅程所需的精确资源清单。
    """
    identifiers = _qa_identifiers(run_id)
    slugs = identifiers["slugs"]
    assert isinstance(slugs, dict)
    material = await _ensure_core_entity(
        session, owner_type="material", slug=slugs["material"], locales=locales
    )
    technology = await _ensure_core_entity(
        session, owner_type="technology", slug=slugs["technology"], locales=locales
    )
    application = await _ensure_core_entity(
        session, owner_type="application", slug=slugs["application"], locales=locales
    )
    solution = await _ensure_core_entity(
        session, owner_type="solution", slug=slugs["solution"], locales=locales
    )
    unmatched_material = await _ensure_core_entity(
        session,
        owner_type="material",
        slug=slugs["unmatched_material"],
        locales=locales,
    )
    await replace_product_relations(
        session,
        product.id,
        RelationUpdate(
            material_ids=[material.id],
            technology_ids=[technology.id],
            application_ids=[application.id],
            solution_ids=[solution.id],
        ),
    )

    # Company Profile 是单例；隔离库若已有非本轮档案则拒绝覆盖，避免破坏人工数据。
    company = await session.scalar(select(CompanyProfileTranslation).limit(1))
    expected_company_name = str(identifiers["company_profile_marker"])
    if company is not None and company.company_name != expected_company_name:
        raise AppException(409, "qa_company_conflict", "隔离库已有非本轮 Company Profile")
    if company is None:
        profile = await upsert_company_profile(
            session,
            CompanyProfileInput(
                status="enabled",
                primary_factory_media_id=media.id,
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={
                            "company_name": expected_company_name,
                            "short_intro": "Local isolated QA company profile.",
                            "full_intro": "QA ONLY content used to verify the public homepage lifecycle.",
                            "advantages_json": ["QA lifecycle evidence"],
                        },
                    )
                    for locale in locales
                ],
            ),
            None,
        )
        await _publish_many(session, "company_profile", profile.id, locales)

    capability = await session.scalar(
        select(ManufacturingCapability).where(ManufacturingCapability.slug == slugs["capability"])
    )
    if capability is None:
        capability = await create_trust_entity(
            session,
            "capabilities",
            TrustEntityInput(
                slug=slugs["capability"],
                fields={"capability_type": "qa-validation", "primary_media_id": media.id},
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={
                            "name": "QA ONLY Manufacturing Capability",
                            "summary": "Local isolated capability sample.",
                            "description": "QA ONLY structured capability content.",
                            "key_facts_json": ["QA-only evidence"],
                        },
                    )
                    for locale in locales
                ],
            ),
            None,
        )
        await _publish_many(session, "manufacturing_capability", capability.id, locales)

    equipment = await session.scalar(select(Equipment).where(Equipment.slug == slugs["equipment"]))
    if equipment is None:
        equipment = await create_trust_entity(
            session,
            "equipment",
            TrustEntityInput(
                slug=slugs["equipment"],
                fields={"equipment_type": "qa-machine", "manufacturer": "QA ONLY"},
                translations=[
                    TrustTranslation(
                        locale_id=locale.id,
                        fields={
                            "name": "QA ONLY Equipment",
                            "summary": "Local isolated equipment sample.",
                        },
                    )
                    for locale in locales
                ],
            ),
            None,
        )
        await _publish_non_route_translation(
            session,
            owner_type="equipment",
            owner_id=equipment.id,
            locales=locales,
        )
    capability_equipment = await session.scalar(
        select(CapabilityEquipment).where(
            CapabilityEquipment.capability_id == capability.id,
            CapabilityEquipment.equipment_id == equipment.id,
        )
    )
    if capability_equipment is None:
        session.add(CapabilityEquipment(capability_id=capability.id, equipment_id=equipment.id))

    case_study = await session.scalar(
        select(CaseStudy).where(CaseStudy.slug == slugs["case_study"])
    )
    if case_study is None:
        case_study = await create_case_study(
            session,
            CaseStudyCreate(
                slug=slugs["case_study"],
                country_code="ZZ",
                client_name="QA PRIVATE CLIENT",
                client_address="QA PRIVATE ADDRESS",
                client_name_public=False,
                client_address_public=False,
                featured=True,
                primary_media_id=media.id,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={
                            "title": "QA ONLY Anonymous Case",
                            "summary": "An anonymized local QA case.",
                            "problem": "QA-only validation problem.",
                            "solution": "QA-only validation solution.",
                            "result": "QA-only validation result.",
                        },
                    )
                    for locale in locales
                ],
            ),
        )
        await replace_authority_relations(
            session,
            "case_study",
            case_study.id,
            AuthorityRelationUpdate(
                product_ids=[product.id],
                material_ids=[material.id],
                technology_ids=[technology.id],
                application_ids=[application.id],
                solution_ids=[solution.id],
            ),
        )
        await _publish_many(session, "case_study", case_study.id, locales)

    draft = await session.scalar(select(Product).where(Product.slug == slugs["draft"]))
    if draft is None:
        draft = await create_product(
            session,
            ProductCreate(
                category_id=category.id,
                code=f"QA36-{run_id.upper()}-DRAFT",
                slug=slugs["draft"],
                translations=_catalog_translations(
                    locales, "QA ONLY Draft Product", "仅测试草稿产品"
                ),
            ),
        )
    noindex = await session.scalar(select(Product).where(Product.slug == slugs["noindex"]))
    if noindex is None:
        noindex = await create_product(
            session,
            ProductCreate(
                category_id=category.id,
                code=f"QA36-{run_id.upper()}-NOINDEX",
                slug=slugs["noindex"],
                translations=_catalog_translations(
                    locales, "QA ONLY Noindex Product", "仅测试不索引产品"
                ),
            ),
        )
        await _publish_many(session, "product", noindex.id, locales)
        for locale in locales:
            session.add(
                SeoDocument(
                    owner_type="product",
                    owner_id=noindex.id,
                    locale_id=locale.id,
                    robots_index=False,
                    robots_follow=True,
                )
            )

    _pdf_asset, download = await _create_public_pdf(session, storage, run_id, locales)
    await session.flush()
    return {
        "slugs": slugs,
        "material": material,
        "technology": technology,
        "application": application,
        "solution": solution,
        "unmatched_material": unmatched_material,
        "capability": capability,
        "equipment": equipment,
        "case_study": case_study,
        "draft": draft,
        "noindex": noindex,
        "download": download,
    }


async def _ensure_knowledge_source(
    session: AsyncSession,
    *,
    article: KnowledgeArticle,
) -> None:
    """
    为 QA Knowledge 添加真实可见 SourceCitation 记录。

    输入：数据库会话与知识文章。
    输出：None；已有引用时保持幂等。
    """
    citation = await session.scalar(
        select(SourceCitation).where(
            SourceCitation.article_id == article.id,
            SourceCitation.url == "https://example.com/qa-only-source",
        )
    )
    if citation is None:
        session.add(
            SourceCitation(
                article_id=article.id,
                title="QA ONLY public source",
                url="https://example.com/qa-only-source",
                publisher="Example QA Publisher",
                source_type="official",
            )
        )
        await session.flush()


def _build_manifest(
    *,
    run_id: str,
    category_slug: str,
    product_slug: str,
    knowledge_category_slug: str,
    knowledge_slug: str,
    missing_translation_slug: str,
    specification_types: list[str],
    product_count: int,
    extended: dict[str, object],
) -> Phase36QaManifest:
    """
    生成不含数据库 UUID 或凭据的精确 QA 资源清单。

    输入：run-id、页面 slug、规格类型、数量与扩展资源。
    输出：Phase36QaManifest，可用于复验和按 manifest 精确清理。
    """
    identifiers = _qa_identifiers(run_id, product_count=product_count)
    identifier_slugs = identifiers["slugs"]
    assert isinstance(identifier_slugs, dict)
    slugs = extended["slugs"]
    assert isinstance(slugs, dict)
    expert_slug = str(identifier_slugs["expert"])
    download_slug = str(identifier_slugs["download"])
    product_slugs = identifiers["product_slugs"]
    assert isinstance(product_slugs, list)
    public_object_keys = identifiers["public_object_keys"]
    rfq_email_markers = identifiers["rfq_email_markers"]
    assert isinstance(public_object_keys, list)
    assert isinstance(rfq_email_markers, list)
    return Phase36QaManifest(
        run_id=run_id,
        product_slug=product_slug,
        product_category_slug=category_slug,
        knowledge_slug=knowledge_slug,
        knowledge_category_slug=knowledge_category_slug,
        missing_translation_slug=missing_translation_slug,
        material_slug=str(slugs["material"]),
        technology_slug=str(slugs["technology"]),
        application_slug=str(slugs["application"]),
        solution_slug=str(slugs["solution"]),
        capability_slug=str(slugs["capability"]),
        equipment_slug=str(slugs["equipment"]),
        case_slug=str(slugs["case_study"]),
        expert_slug=expert_slug,
        draft_slug=str(slugs["draft"]),
        noindex_slug=str(slugs["noindex"]),
        unmatched_material_slug=str(slugs["unmatched_material"]),
        download_slug=download_slug,
        public_object_keys=public_object_keys,
        company_profile_marker=str(identifiers["company_profile_marker"]),
        specification_code_prefix=str(identifiers["specification_code_prefix"]),
        rfq_email_markers=rfq_email_markers,
        rate_limit_namespace=str(identifiers["rate_limit_namespace"]),
        resource_slugs={
            "company_profile_marker": [f"QA ONLY Junhui {run_id}"],
            "product_category": [category_slug],
            "product": product_slugs,
            "material": [str(slugs["material"]), str(slugs["unmatched_material"])],
            "technology": [str(slugs["technology"])],
            "application": [str(slugs["application"])],
            "solution": [str(slugs["solution"])],
            "manufacturing_capability": [str(slugs["capability"])],
            "equipment": [str(slugs["equipment"])],
            "case_study": [str(slugs["case_study"])],
            "author_expert": [expert_slug],
            "knowledge_category": [knowledge_category_slug],
            "knowledge_article": [knowledge_slug, missing_translation_slug],
            "download_resource": [download_slug],
        },
        product_count=product_count,
        specification_types=specification_types,
    )


def _catalog_translations(
    locales: Sequence[Locale], en_name: str, zh_name: str
) -> list[TranslationInput]:
    """输入语言和中英文名称；输出 Catalog 服务可验证的双语 TranslationInput。"""
    return [
        TranslationInput(
            locale_id=locale.id,
            name=en_name if locale.code == "en" else zh_name,
            fields={
                "short_description": (
                    "Isolated Phase 3.6 browser QA sample."
                    if locale.code == "en"
                    else "隔离的 Phase 3.6 浏览器 QA 样本。"
                ),
                "description": (
                    "This local-only record verifies SSR, RFQ attribution and published routes."
                    if locale.code == "en"
                    else "此仅本地记录用于验证 SSR、RFQ 来源和发布路由。"
                ),
            },
        )
        for locale in locales
    ]


async def _ensure_product_specifications(
    session: AsyncSession,
    *,
    run_id: str,
    product: Product,
    locales: Sequence[Locale],
) -> list[str]:
    """
    通过正式 Catalog 服务为代表产品准备五类结构化规格。

    输入：session、run_id、product、locales。
    输出：list[str]，实际存在的 text/number/range/boolean/enum 类型。
    """
    group_code = f"qa36-{run_id}-specifications"
    group = await session.scalar(
        select(SpecificationGroup).where(SpecificationGroup.code == group_code)
    )
    if group is None:
        group = await create_specification_group(
            session,
            SpecificationGroupCreate(
                code=group_code,
                translations=_catalog_translations(
                    locales,
                    "QA Product Specifications",
                    "QA 产品规格",
                ),
            ),
        )

    typed_values: dict[str, dict[str, object]] = {
        "text": {"value_text": "QA alloy steel"},
        "number": {"value_number": 65.0, "unit_override": "mm"},
        "range": {"value_min": 20.0, "value_max": 80.0, "unit_override": "mm"},
        "boolean": {"value_boolean": True},
        "enum": {"enum_value": "QA nitrided"},
    }
    names = {
        "text": ("QA Material Note", "QA 材料说明"),
        "number": ("QA Diameter", "QA 直径"),
        "range": ("QA Working Range", "QA 工作范围"),
        "boolean": ("QA Cooling", "QA 冷却"),
        "enum": ("QA Surface", "QA 表面处理"),
    }
    for sort_order, value_type in enumerate(typed_values):
        definition_code = f"qa36-{run_id}-{value_type}"
        definition = await session.scalar(
            select(SpecificationDefinition).where(
                SpecificationDefinition.group_id == group.id,
                SpecificationDefinition.code == definition_code,
            )
        )
        if definition is None:
            en_name, zh_name = names[value_type]
            definition = await create_specification_definition(
                session,
                SpecificationDefinitionCreate(
                    group_id=group.id,
                    code=definition_code,
                    value_type=value_type,
                    sort_order=sort_order,
                    translations=_catalog_translations(locales, en_name, zh_name),
                ),
            )
        existing_value = await session.scalar(
            select(ProductSpecValue).where(
                ProductSpecValue.product_id == product.id,
                ProductSpecValue.definition_id == definition.id,
            )
        )
        if existing_value is None:
            await create_specification_value(
                session,
                SpecificationValueCreate(
                    product_id=product.id,
                    definition_id=definition.id,
                    sort_order=sort_order,
                    **typed_values[value_type],
                ),
            )
    await session.flush()
    return list(typed_values)


async def _prepare_phase36_qa(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    storage: MinioStorageAdapter,
) -> Phase36QaManifest:
    """
    使用现有服务和生命周期准备代表性内容。

    输入：数据库会话工厂、已校验 run_id、真实 MinIO 适配器。
    输出：Phase36QaManifest，供浏览器 QA 驱动页面路径。
    """
    async with factory() as session, session.begin():
        locales = list(
            (
                await session.scalars(
                    select(Locale).where(Locale.code.in_(["en", "zh-CN"])).order_by(Locale.code)
                )
            ).all()
        )
        if {locale.code for locale in locales} != {"en", "zh-CN"}:
            raise AppException(409, "qa_locales_missing", "QA 需要已启用的 en 与 zh-CN")

        category_slug = f"qa36-{run_id}-screws"
        product_slug = f"qa36-{run_id}-extrusion-screw"
        knowledge_category_slug = f"qa36-{run_id}-guides"
        knowledge_slug = f"qa36-{run_id}-screw-selection"
        missing_translation_slug = f"qa36-{run_id}-english-only"
        existing_product = await session.scalar(select(Product).where(Product.slug == product_slug))
        if existing_product is not None:
            # 已存在 run 仍重新核对 MinIO 对象并幂等补齐后来新增的 QA 场景。
            media = await _create_public_media(session, storage, run_id, locales)
            existing_category = await session.scalar(
                select(ProductCategory).where(ProductCategory.slug == category_slug)
            )
            if existing_category is None:
                raise AppException(409, "qa_category_missing", "既有 QA 产品缺少对应分类")
            existing_category.cover_media_id = media.id
            expected_product_slugs = _qa_identifiers(run_id)["product_slugs"]
            assert isinstance(expected_product_slugs, list)
            products = list(
                (
                    await session.scalars(
                        select(Product).where(Product.slug.in_(expected_product_slugs))
                    )
                ).all()
            )
            products_by_slug = {item.slug: item for item in products}
            # 中断的 setup 可能只写入了部分分页样本；重跑时精确补齐缺失项。
            for index in range(26):
                slug = product_slug if index == 0 else f"qa36-{run_id}-product-{index:02d}"
                if slug in products_by_slug:
                    continue
                product = await create_product(
                    session,
                    ProductCreate(
                        category_id=existing_category.id,
                        code=f"QA36-{run_id.upper()}-{index:02d}",
                        slug=slug,
                        featured=index == 0,
                        sort_order=index,
                        translations=_catalog_translations(
                            locales,
                            (
                                "QA ONLY Long-title Extrusion Screw for Responsive Browser Validation"
                                if index == 0
                                else f"QA Product {index:02d}"
                            ),
                            (
                                "仅测试：用于响应式浏览器验收的长标题挤出机螺杆"
                                if index == 0
                                else f"QA 产品 {index:02d}"
                            ),
                        ),
                    ),
                )
                await _publish_many(session, "product", product.id, locales)
                products.append(product)
                products_by_slug[slug] = product
            if set(products_by_slug) != set(expected_product_slugs):
                raise AppException(409, "qa_product_set_invalid", "QA 产品集合不完整")
            await _ensure_representative_product_copy(
                session,
                product=existing_product,
                locales=locales,
            )
            specification_types = await _ensure_product_specifications(
                session,
                run_id=run_id,
                product=existing_product,
                locales=locales,
            )
            extended = await _ensure_extended_qa_content(
                session,
                storage=storage,
                run_id=run_id,
                locales=locales,
                category=existing_category,
                product=existing_product,
                media=media,
            )
            article = await session.scalar(
                select(KnowledgeArticle).where(KnowledgeArticle.slug == knowledge_slug)
            )
            if article is not None:
                await _ensure_knowledge_source(session, article=article)
            return _build_manifest(
                run_id=run_id,
                category_slug=category_slug,
                product_slug=product_slug,
                knowledge_category_slug=knowledge_category_slug,
                knowledge_slug=knowledge_slug,
                missing_translation_slug=missing_translation_slug,
                specification_types=specification_types,
                # manifest 的 product_count 只计入 26 条分页样本，不把 draft/noindex 负向样本混入。
                product_count=len(expected_product_slugs) - 2,
                extended=extended,
            )

        media = await _create_public_media(session, storage, run_id, locales)
        category = await create_category(
            session,
            CategoryCreate(
                slug=category_slug,
                translations=_catalog_translations(locales, "QA Screw Components", "QA 螺杆部件"),
            ),
        )
        category.cover_media_id = media.id
        await _publish_many(session, "product_category", category.id, locales)

        products: list[Product] = []
        for index in range(26):
            slug = product_slug if index == 0 else f"qa36-{run_id}-product-{index:02d}"
            product = await create_product(
                session,
                ProductCreate(
                    category_id=category.id,
                    code=f"QA36-{run_id.upper()}-{index:02d}",
                    slug=slug,
                    featured=index == 0,
                    sort_order=index,
                    translations=_catalog_translations(
                        locales,
                        (
                            "QA ONLY Long-title Extrusion Screw for Responsive Browser Validation"
                            if index == 0
                            else f"QA Product {index:02d}"
                        ),
                        (
                            "仅测试：用于响应式浏览器验收的长标题挤出机螺杆"
                            if index == 0
                            else f"QA 产品 {index:02d}"
                        ),
                    ),
                ),
            )
            if index == 0:
                product.primary_media_id = media.id
            await _publish_many(session, "product", product.id, locales)
            products.append(product)

        # 产品关系由正式服务维护；本地 QA 不创建任何虚构公开材料事实。
        await replace_product_relations(session, products[0].id, RelationUpdate())
        specification_types = await _ensure_product_specifications(
            session,
            run_id=run_id,
            product=products[0],
            locales=locales,
        )

        knowledge_category = await create_knowledge_category(
            session,
            KnowledgeCategoryCreate(
                slug=knowledge_category_slug,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={
                            "name": "QA Guides" if locale.code == "en" else "QA 指南",
                            "description": "Local browser QA category",
                        },
                    )
                    for locale in locales
                ],
            ),
        )
        expert = await create_author_expert(
            session,
            AuthorExpertCreate(
                slug=f"qa36-{run_id}-verified-author",
                role_type="author_expert",
                is_real_person_verified=True,
                public_profile_enabled=True,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={
                            "name": "QA Verified Author"
                            if locale.code == "en"
                            else "QA 已核验作者",
                            "job_title": "Local QA profile",
                            "short_bio": "Synthetic local QA identity; never production content.",
                            "expertise_json": ["QA"],
                        },
                    )
                    for locale in locales
                ],
            ),
        )
        await _publish_many(session, "author_expert", expert.id, locales)

        article = await create_knowledge_article(
            session,
            KnowledgeArticleCreate(
                category_id=knowledge_category.id,
                slug=knowledge_slug,
                author_id=expert.id,
                reviewer_id=expert.id,
                featured=True,
                primary_media_id=media.id,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locale.id,
                        fields={
                            "title": (
                                "QA Extrusion Screw Selection"
                                if locale.code == "en"
                                else "QA 挤出机螺杆选型"
                            ),
                            "summary": "Phase 3.6 local search and relation sample.",
                            "body_markdown": (
                                "Use the related QA product link to continue the verified browser journey."
                            ),
                        },
                    )
                    for locale in locales
                ],
            ),
        )
        await replace_authority_relations(
            session,
            "knowledge_article",
            article.id,
            AuthorityRelationUpdate(product_ids=[products[0].id]),
        )
        await _publish_many(session, "knowledge_article", article.id, locales)
        await _ensure_knowledge_source(session, article=article)

        # 只发布英文版本，用于验证缺少 alternate 时语言切换安全回退首页。
        en_locale = next(locale for locale in locales if locale.code == "en")
        english_only = await create_knowledge_article(
            session,
            KnowledgeArticleCreate(
                category_id=knowledge_category.id,
                slug=missing_translation_slug,
                author_id=expert.id,
                reviewer_id=expert.id,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=en_locale.id,
                        fields={
                            "title": "QA English-only Translation",
                            "summary": "Verifies safe locale fallback.",
                            "body_markdown": "This page deliberately has no published Chinese alternate.",
                        },
                    )
                ],
            ),
        )
        await _publish_owner_locale(
            session,
            owner_type="knowledge_article",
            owner_id=english_only.id,
            locale_id=en_locale.id,
        )

        extended = await _ensure_extended_qa_content(
            session,
            storage=storage,
            run_id=run_id,
            locales=locales,
            category=category,
            product=products[0],
            media=media,
        )
        return _build_manifest(
            run_id=run_id,
            category_slug=category_slug,
            product_slug=product_slug,
            knowledge_category_slug=knowledge_category_slug,
            knowledge_slug=knowledge_slug,
            missing_translation_slug=missing_translation_slug,
            specification_types=specification_types,
            product_count=len(products),
            extended=extended,
        )


async def prepare_phase36_qa(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
) -> Phase36QaManifest:
    """
    公开入口：校验本地 opt-in 后准备 QA 数据。

    输入：factory: async_sessionmaker；run_id: str，隔离标识。
    输出：Phase36QaManifest，脱敏页面路径清单。
    """
    normalized = _assert_qa_allowed(run_id)
    return await _prepare_phase36_qa(
        factory,
        run_id=normalized,
        storage=MinioStorageAdapter(),
    )


async def _delete_qa_objects(
    storage: MinioStorageAdapter,
    objects: Sequence[tuple[str, str]],
) -> int:
    """
    删除已经过所有权校验的 QA 对象。

    输入：storage: MinioStorageAdapter；objects: Sequence[(bucket, key)]。
    输出：int，实际存在并删除的对象数。
    """
    deleted_count = 0
    for bucket, key in objects:
        if await storage.object_exists(bucket, key):
            await storage.delete_object(bucket, key)
            deleted_count += 1
    return deleted_count


async def _delete_qa_lifecycle(
    session: AsyncSession,
    owners: Sequence[tuple[str, uuid.UUID]],
) -> int:
    """
    按精确 owner type/ID 删除 QA 的通用生命周期记录。

    输入：session；owners，已验证归属的实体元组。
    输出：int，实际删除的发布、路由、修订、SEO/GEO 与翻译状态数。
    """
    deleted_count = 0
    lifecycle_models = (
        ContentRevision,
        ContentRoute,
        ContentPublication,
        TranslationStatus,
        SeoDocument,
        GeoDocument,
    )
    for owner_type, owner_id in owners:
        for model in lifecycle_models:
            result = await session.execute(
                delete(model).where(
                    model.owner_type == owner_type,
                    model.owner_id == owner_id,
                )
            )
            deleted_count += max(result.rowcount or 0, 0)
    return deleted_count


async def cleanup_phase36_qa(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
) -> Phase36QaCleanupResult:
    """
    仅按同一 manifest 可重建标识清理本地 Phase 3.6 QA 数据。

    输入：factory: async_sessionmaker；run_id: str，隔离 QA 运行标识。
    输出：Phase36QaCleanupResult，仅含脱敏删除计数。
    """
    normalized = _assert_qa_allowed(run_id)
    identifiers = _qa_identifiers(normalized)
    slugs = identifiers["slugs"]
    product_slugs = identifiers["product_slugs"]
    public_object_keys = identifiers["public_object_keys"]
    rfq_email_markers = identifiers["rfq_email_markers"]
    assert isinstance(slugs, dict)
    assert isinstance(product_slugs, list)
    assert isinstance(public_object_keys, list)
    assert isinstance(rfq_email_markers, list)
    storage = MinioStorageAdapter()

    async with factory() as session, session.begin():
        products = list(
            (
                await session.scalars(
                    select(Product).where(Product.slug.in_(product_slugs))
                )
            ).all()
        )
        expected_code_prefix = f"QA36-{normalized.upper()}-"
        if any(not product.code.startswith(expected_code_prefix) for product in products):
            raise AppException(409, "qa_cleanup_conflict", "QA 产品标识与 run-id 冲突")

        category = await session.scalar(
            select(ProductCategory).where(ProductCategory.slug == slugs["category"])
        )
        core_entities: dict[str, list[object]] = {}
        for owner_type, model in _CORE_MODELS.items():
            target_slugs = (
                [slugs["material"], slugs["unmatched_material"]]
                if owner_type == "material"
                else [slugs[owner_type]]
            )
            core_entities[owner_type] = list(
                (await session.scalars(select(model).where(model.slug.in_(target_slugs)))).all()
            )

        capability = await session.scalar(
            select(ManufacturingCapability).where(
                ManufacturingCapability.slug == slugs["capability"]
            )
        )
        if capability is not None and capability.capability_type != "qa-validation":
            raise AppException(409, "qa_cleanup_conflict", "QA 能力标记与 run-id 冲突")
        equipment = await session.scalar(
            select(Equipment).where(Equipment.slug == slugs["equipment"])
        )
        if equipment is not None and equipment.manufacturer != "QA ONLY":
            raise AppException(409, "qa_cleanup_conflict", "QA 设备标记与 run-id 冲突")
        case_study = await session.scalar(
            select(CaseStudy).where(CaseStudy.slug == slugs["case_study"])
        )
        if case_study is not None and case_study.client_name != "QA PRIVATE CLIENT":
            raise AppException(409, "qa_cleanup_conflict", "QA 案例标记与 run-id 冲突")
        expert = await session.scalar(
            select(AuthorExpert).where(AuthorExpert.slug == slugs["expert"])
        )
        if expert is not None and (
            not expert.is_real_person_verified or expert.role_type != "author_expert"
        ):
            raise AppException(409, "qa_cleanup_conflict", "QA 作者标记与 run-id 冲突")
        knowledge_category = await session.scalar(
            select(KnowledgeCategory).where(
                KnowledgeCategory.slug == slugs["knowledge_category"]
            )
        )
        knowledge_articles = list(
            (
                await session.scalars(
                    select(KnowledgeArticle).where(
                        KnowledgeArticle.slug.in_(
                            [slugs["knowledge"], slugs["missing_translation"]]
                        )
                    )
                )
            ).all()
        )
        download = await session.scalar(
            select(DownloadResource).where(DownloadResource.slug == slugs["download"])
        )
        if download is not None and download.version_label != "QA ONLY":
            raise AppException(409, "qa_cleanup_conflict", "QA 下载标记与 run-id 冲突")

        company_translation = await session.scalar(
            select(CompanyProfileTranslation).where(
                CompanyProfileTranslation.company_name
                == identifiers["company_profile_marker"]
            )
        )
        company_profile = (
            await session.get(CompanyProfile, company_translation.company_profile_id)
            if company_translation is not None
            else None
        )

        rfqs = list(
            (await session.scalars(select(RFQ).where(RFQ.email.in_(rfq_email_markers)))).all()
        )
        expected_companies = {
            f"Phase36 {normalized} Product QA",
            f"Phase36 {normalized} Knowledge QA",
            f"Phase36 {normalized} Case QA",
        }
        if any(rfq.company_name not in expected_companies for rfq in rfqs):
            raise AppException(409, "qa_cleanup_conflict", "QA RFQ 标记与 run-id 冲突")
        rfq_ids = [rfq.id for rfq in rfqs]
        rfq_files = (
            list((await session.scalars(select(RFQFile).where(RFQFile.rfq_id.in_(rfq_ids)))).all())
            if rfq_ids
            else []
        )
        private_asset_ids = [rfq_file.media_asset_id for rfq_file in rfq_files]
        private_assets = (
            list(
                (
                    await session.scalars(
                        select(MediaAsset).where(MediaAsset.id.in_(private_asset_ids))
                    )
                ).all()
            )
            if private_asset_ids
            else []
        )
        for asset in private_assets:
            if (
                asset.visibility != "private"
                or asset.storage_bucket != "private-rfq"
                or not any(
                    asset.storage_key.startswith(f"rfq/{rfq_id}/") for rfq_id in rfq_ids
                )
            ):
                raise AppException(409, "qa_cleanup_conflict", "QA 私有对象归属冲突")

        public_assets = list(
            (
                await session.scalars(
                    select(MediaAsset).where(
                        MediaAsset.storage_bucket == "public-media",
                        MediaAsset.storage_key.in_(public_object_keys),
                    )
                )
            ).all()
        )
        if any(asset.visibility != "public" for asset in public_assets):
            raise AppException(409, "qa_cleanup_conflict", "QA 公开对象归属冲突")

        owners: list[tuple[str, uuid.UUID]] = [
            *(("product", product.id) for product in products),
            *((owner_type, entity.id) for owner_type, rows in core_entities.items() for entity in rows),
            *(("knowledge_article", article.id) for article in knowledge_articles),
        ]
        optional_owners = (
            ("product_category", category),
            ("manufacturing_capability", capability),
            ("equipment", equipment),
            ("case_study", case_study),
            ("author_expert", expert),
            ("knowledge_category", knowledge_category),
            ("company_profile", company_profile),
        )
        owners.extend(
            (owner_type, entity.id)
            for owner_type, entity in optional_owners
            if entity is not None
        )

        private_objects = [
            (asset.storage_bucket, asset.storage_key) for asset in private_assets
        ]
        public_objects = [("public-media", str(key)) for key in public_object_keys]
        deleted_private_objects = await _delete_qa_objects(storage, private_objects)
        deleted_public_objects = await _delete_qa_objects(storage, public_objects)

        lifecycle_count = await _delete_qa_lifecycle(session, owners)
        target_ids = [str(owner_id) for _owner_type, owner_id in owners]
        target_ids.extend(str(rfq_id) for rfq_id in rfq_ids)
        if target_ids:
            await session.execute(delete(AuditLog).where(AuditLog.target_id.in_(target_ids)))

        if rfq_ids:
            await session.execute(delete(RFQ).where(RFQ.id.in_(rfq_ids)))
        if private_asset_ids:
            await session.execute(delete(MediaAsset).where(MediaAsset.id.in_(private_asset_ids)))
        if download is not None:
            await session.execute(delete(DownloadResource).where(DownloadResource.id == download.id))
        if knowledge_articles:
            await session.execute(
                delete(KnowledgeArticle).where(
                    KnowledgeArticle.id.in_([article.id for article in knowledge_articles])
                )
            )
        if case_study is not None:
            await session.execute(delete(CaseStudy).where(CaseStudy.id == case_study.id))
        if capability is not None:
            await session.execute(
                delete(ManufacturingCapability).where(
                    ManufacturingCapability.id == capability.id
                )
            )
        if equipment is not None:
            await session.execute(delete(Equipment).where(Equipment.id == equipment.id))
        if products:
            await session.execute(
                delete(Product).where(Product.id.in_([product.id for product in products]))
            )
        for owner_type, model in _CORE_MODELS.items():
            entity_ids = [entity.id for entity in core_entities[owner_type]]
            if entity_ids:
                await session.execute(delete(model).where(model.id.in_(entity_ids)))
        specification_prefix = str(identifiers["specification_code_prefix"])
        definitions = list(
            (
                await session.scalars(
                    select(SpecificationDefinition).where(
                        SpecificationDefinition.code.startswith(specification_prefix)
                    )
                )
            ).all()
        )
        if definitions:
            await session.execute(
                delete(SpecificationDefinition).where(
                    SpecificationDefinition.id.in_([item.id for item in definitions])
                )
            )
        groups = list(
            (
                await session.scalars(
                    select(SpecificationGroup).where(
                        SpecificationGroup.code
                        == f"qa36-{normalized}-specifications"
                    )
                )
            ).all()
        )
        if groups:
            await session.execute(
                delete(SpecificationGroup).where(
                    SpecificationGroup.id.in_([item.id for item in groups])
                )
            )
        if category is not None:
            await session.execute(
                delete(ProductCategory).where(ProductCategory.id == category.id)
            )
        if knowledge_category is not None:
            await session.execute(
                delete(KnowledgeCategory).where(
                    KnowledgeCategory.id == knowledge_category.id
                )
            )
        if expert is not None:
            await session.execute(delete(AuthorExpert).where(AuthorExpert.id == expert.id))
        if company_profile is not None:
            await session.execute(
                delete(CompanyProfile).where(CompanyProfile.id == company_profile.id)
            )
        public_asset_ids = [asset.id for asset in public_assets]
        if public_asset_ids:
            await session.execute(
                delete(MediaAsset).where(MediaAsset.id.in_(public_asset_ids))
            )

        content_count = (
            len(products)
            + sum(len(rows) for rows in core_entities.values())
            + len(knowledge_articles)
            + sum(entity is not None for _owner_type, entity in optional_owners)
            + (1 if download is not None else 0)
        )
        specification_count = len(definitions) + len(groups)

    redis_client = Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        namespace = str(identifiers["rate_limit_namespace"])
        redis_keys = [key async for key in redis_client.scan_iter(match=f"{namespace}:*")]
        redis_count = await redis_client.delete(*redis_keys) if redis_keys else 0
    finally:
        await redis_client.aclose()

    return Phase36QaCleanupResult(
        run_id=normalized,
        deleted={
            "rfqs": len(rfqs),
            "private_objects": deleted_private_objects,
            "content_entities": content_count,
            "lifecycle_records": lifecycle_count,
            "specification_records": specification_count,
            "public_objects": deleted_public_objects,
            "redis_keys": int(redis_count),
        },
    )


async def verify_phase36_qa(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
) -> Phase36QaVerificationResult:
    """
    从数据库和 MinIO 核验真实浏览器旅程的 RFQ 持久化结果。

    输入：factory: async_sessionmaker；run_id: str，隔离 QA 运行标识。
    输出：Phase36QaVerificationResult，仅含脱敏计数和布尔断言。
    """
    normalized = _assert_qa_allowed(run_id)
    identifiers = _qa_identifiers(normalized)
    slugs = identifiers["slugs"]
    email_markers = identifiers["rfq_email_markers"]
    assert isinstance(slugs, dict)
    assert isinstance(email_markers, list)
    expected_sources = {
        str(email_markers[0]): (
            "product",
            str(slugs["product"]),
            f"/en/products/{slugs['category']}/{slugs['product']}/",
        ),
        str(email_markers[1]): (
            "knowledge_article",
            str(slugs["knowledge"]),
            f"/en/knowledge/{slugs['knowledge_category']}/{slugs['knowledge']}/",
        ),
        str(email_markers[2]): (
            "case_study",
            str(slugs["case_study"]),
            f"/en/case-studies/{slugs['case_study']}/",
        ),
    }
    models = {
        "product": Product,
        "knowledge_article": KnowledgeArticle,
        "case_study": CaseStudy,
    }
    storage = MinioStorageAdapter()
    source_persistence: dict[str, bool] = {}
    private_objects_exist = True
    attachment_records = 0
    async with factory() as session:
        rfqs = list(
            (await session.scalars(select(RFQ).where(RFQ.email.in_(email_markers)))).all()
        )
        for email, (owner_type, slug, expected_path) in expected_sources.items():
            entity = await session.scalar(
                select(models[owner_type]).where(models[owner_type].slug == slug)
            )
            matches = [
                rfq
                for rfq in rfqs
                if rfq.email == email
                and entity is not None
                and rfq.source_owner_type == owner_type
                and rfq.source_owner_id == entity.id
                and rfq.source_page_url == f"https://junhuiscrewbarrel.com{expected_path}"
            ]
            source_persistence[owner_type] = bool(matches)

        product_rfqs = [rfq for rfq in rfqs if rfq.email == email_markers[0]]
        product_rfq_ids = [rfq.id for rfq in product_rfqs]
        files = (
            list(
                (
                    await session.scalars(
                        select(RFQFile).where(RFQFile.rfq_id.in_(product_rfq_ids))
                    )
                ).all()
            )
            if product_rfq_ids
            else []
        )
        attachment_records = len(files)
        for file_record in files:
            asset = await session.get(MediaAsset, file_record.media_asset_id)
            if (
                asset is None
                or asset.visibility != "private"
                or asset.storage_bucket != "private-rfq"
                or not await storage.object_exists(asset.storage_bucket, asset.storage_key)
            ):
                private_objects_exist = False
        if not files:
            private_objects_exist = False

    return Phase36QaVerificationResult(
        run_id=normalized,
        rfq_count=len(rfqs),
        source_persistence=source_persistence,
        attachment_records=attachment_records,
        private_objects_exist=private_objects_exist,
    )
