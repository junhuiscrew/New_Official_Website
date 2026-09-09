"""Demo R2 独立数据库的显式、幂等内容与媒体初始化器。"""

from __future__ import annotations

import mimetypes
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import (
    FAQ,
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
    FAQCreate,
    KnowledgeArticleCreate,
)
from app.modules.authority.services import (
    create_author_expert,
    create_case_study,
    create_faq,
    create_knowledge_article,
    replace_authority_relations,
)
from app.modules.catalog.models import (
    Application,
    Material,
    Product,
    ProductCategory,
    Solution,
    Technology,
)
from app.modules.catalog.schemas import (
    CategoryCreate,
    EntityCreate,
    ProductCreate,
    ProductModelCreate,
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
    create_product_model,
    create_specification_definition,
    create_specification_group,
    create_specification_value,
    replace_product_relations,
)
from app.modules.company.models import (
    CapabilityEquipment,
    Certificate,
    Equipment,
    Exhibition,
    ManufacturingCapability,
)
from app.modules.company.schemas import CompanyProfileInput, TrustEntityInput, TrustTranslation
from app.modules.company.services import create_trust_entity, upsert_company_profile
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.demo.models import ContentMediaLink, DemoContentRecord
from app.modules.demo.package import (
    DEMO_BATCH_ID,
    DemoPackage,
    DemoPackageError,
    DemoRecord,
    canonical_demo_slug,
    load_demo_package,
    record_fingerprint,
)
from app.modules.discovery.schemas import GeoDocumentUpsert, SeoDocumentUpsert
from app.modules.discovery.services import (
    initialize_products_site_page,
    publish_products_site_page,
    review_products_site_page,
    upsert_geo_document,
    upsert_seo_document,
)
from app.modules.localization.models import Locale
from app.modules.media.models import (
    DownloadResource,
    DownloadResourceTranslation,
    MediaAsset,
    MediaAssetTranslation,
)
from app.modules.media.services import validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter
from app.modules.presentation.registry import default_homepage_config
from app.modules.presentation.schemas import HomepageDraftUpdate
from app.modules.presentation.services import (
    apply_homepage_layout,
    get_homepage_language_detail,
    initialize_homepage,
    save_homepage_draft,
)
from app.modules.privacy.models import PrivacyNoticeVersion
from app.modules.rfq.models import RFQ, RFQItem
from app.modules.users.models import User
from app.seed import seed_database

_ENTITY_MODELS: dict[str, type[Any]] = {
    "category": ProductCategory,
    "product": Product,
    "material": Material,
    "technology": Technology,
    "application": Application,
    "solution": Solution,
    "case": CaseStudy,
    "article": KnowledgeArticle,
    "faq": FAQ,
    "capability": ManufacturingCapability,
    "equipment": Equipment,
    "proof_card": Certificate,
    "exhibition": Exhibition,
    "download": DownloadResource,
    "rfq": RFQ,
    # CLI 初始化路径也必须注册 RFQ 外键依赖的隐私版本表。
    "privacy_notice_version": PrivacyNoticeVersion,
}

_DEMO_MIME_FALLBACKS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


class DemoMediaManifestItem(BaseModel):
    """一个实际媒体文件及其可复用槽位映射。"""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1, max_length=160)
    file: str = Field(min_length=1, max_length=500)
    kind: Literal["image", "video", "document"]
    content_origin: Literal["approved_public_copy", "generated_demo", "licensed_demo"]
    slots: list[str] = Field(default_factory=list, min_length=1)
    alt_zh: str = Field(min_length=1, max_length=500)
    alt_en: str = Field(min_length=1, max_length=500)
    duration_seconds: float | None = Field(default=None, ge=0)


class DemoMediaManifest(BaseModel):
    """媒体制作完成后的实际文件清单。"""

    model_config = ConfigDict(extra="forbid")

    demo_batch_id: Literal["JH-DEMO-R2-V1"]
    assets: list[DemoMediaManifestItem] = Field(min_length=18)


class DemoSetupResult(BaseModel):
    """显式初始化结果；只输出安全计数与别名映射。"""

    demo_batch_id: str
    created: int
    no_op: int
    media_assets: int
    relations: int
    published_locales: int
    aliases: dict[str, str]


def _mime_type_for_demo_media(file_path: Path) -> str:
    """
    稳定解析Demo媒体MIME，避免依赖不同操作系统的可选注册表。

    输入：file_path，待导入媒体文件路径。
    输出：str，供统一媒体校验器再次核验的MIME；未知类型返回通用二进制。
    """
    guessed = mimetypes.guess_type(file_path.name)[0]
    return guessed or _DEMO_MIME_FALLBACKS.get(file_path.suffix.lower(), "application/octet-stream")


def _assert_demo_target() -> None:
    """
    确保初始化器只连接显式Demo模式和本地Compose数据库。

    输入：无，读取运行配置。
    输出：None；目标不符时停止。
    """
    settings = get_settings()
    database = urlparse(settings.database_url.replace("postgresql+asyncpg", "postgresql"))
    if (
        not settings.demo_mode
        or settings.demo_batch_id != DEMO_BATCH_ID
        or settings.app_env == "production"
        or database.hostname not in {"postgres", "localhost", "127.0.0.1"}
    ):
        raise AppException(409, "demo_target_invalid", "Demo初始化器只能运行在显式本地隔离环境")


def _load_media_manifest(path: Path, media_root: Path) -> DemoMediaManifest:
    """
    读取并核验实际媒体清单及文件边界。

    输入：path，清单路径；media_root，允许读取的媒体根目录。
    输出：DemoMediaManifest，文件和槽位均可用的清单。
    """
    try:
        manifest = DemoMediaManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DemoPackageError("demo_media_manifest_invalid") from exc
    root = media_root.resolve()
    seen_slots: set[str] = set()
    for asset in manifest.assets:
        candidate = (root / asset.file).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise DemoPackageError("demo_media_path_escapes_root") from exc
        if not candidate.is_file():
            raise DemoPackageError(f"demo_media_missing:{asset.alias}")
        overlap = seen_slots.intersection(asset.slots)
        if overlap:
            raise DemoPackageError(f"demo_media_slot_duplicate:{sorted(overlap)[0]}")
        seen_slots.update(asset.slots)
        if asset.kind == "video" and not asset.duration_seconds:
            raise DemoPackageError(f"demo_video_duration_required:{asset.alias}")
    return manifest


def _locale_content(record: DemoRecord, locale_code: str) -> dict[str, Any]:
    """输入演示记录和语言代码；输出该语言经过复制的字段字典。"""
    return dict(record.locale_content[locale_code])


def _catalog_translations(
    record: DemoRecord,
    locales: dict[str, Locale],
    owner_type: str,
) -> list[TranslationInput]:
    """
    把统一演示文字映射到现有Catalog字段，不把包JSON直接当API请求体。

    输入：record、语言映射和目标owner类型。
    输出：list[TranslationInput]，现有领域服务可验证的双语输入。
    """
    result: list[TranslationInput] = []
    for locale_code in ("zh-CN", "en"):
        content = _locale_content(record, locale_code)
        summary = str(content.get("summary") or "")
        body = str(content.get("body") or summary)
        fields: dict[str, Any]
        if owner_type == "product_category":
            fields = {"short_description": summary, "description": summary}
        elif owner_type == "product":
            fields = {
                "short_description": summary,
                "description": body,
                "highlights_jsonb": ["DEMO / 演示内容"],
            }
        elif owner_type == "material":
            fields = {
                "definition": summary,
                "processing_characteristics": body,
                "recommendations": "DEMO / 演示建议，不用于真实选型。",
                "limitations": "示例数据需由负责人替换后方可用于生产判断。",
            }
        elif owner_type == "technology":
            fields = {
                "definition": summary,
                "process_description": body,
                "benefits": summary,
                "limitations": "DEMO / 演示工艺，不代表真实能力或参数。",
            }
        elif owner_type == "application":
            fields = {
                "description": body,
                "technical_requirements": summary,
                "common_problems": "DEMO / 演示问题路径。",
            }
        elif owner_type == "solution":
            steps = record.model_extra.get("steps_zh" if locale_code == "zh-CN" else "steps_en") or []
            fields = {
                "definition": summary,
                "symptoms": summary,
                "causes": summary,
                "diagnosis": "\n".join(str(item) for item in steps),
                "solution": body,
                "limitations": "DEMO / 演示方案，不构成技术承诺。",
            }
        else:
            raise DemoPackageError(f"demo_catalog_owner_unsupported:{owner_type}")
        result.append(
            TranslationInput(
                locale_id=locales[locale_code].id,
                name=str(content["name"]),
                fields=fields,
            )
        )
    return result


def _authority_translations(
    record: DemoRecord,
    locales: dict[str, Locale],
    owner_type: str,
) -> list[AuthorityTranslationInput]:
    """
    将案例、文章和FAQ演示文案映射到现有Authority字段。

    输入：record、语言映射和owner类型。
    输出：list[AuthorityTranslationInput]，严格双语领域输入。
    """
    result: list[AuthorityTranslationInput] = []
    for locale_code in ("zh-CN", "en"):
        content = _locale_content(record, locale_code)
        name = str(content["name"])
        summary = str(content.get("summary") or "")
        body = str(content.get("body") or summary)
        if owner_type == "case_study":
            fields = {
                "title": name,
                "summary": summary,
                "client_description": "虚构演示项目 / Fictional demo project",
                "problem": summary,
                "analysis": "DEMO / 演示检查过程。",
                "solution": summary,
                "result": str(
                    record.model_extra.get("result_zh" if locale_code == "zh-CN" else "result_en")
                    or summary
                ),
                "engineer_comment": "演示内容，不代表已完成真实项目。",
            }
        elif owner_type == "knowledge_article":
            fields = {"title": name, "summary": summary, "body_markdown": body}
        elif owner_type == "faq":
            fields = {"question": name, "answer": summary}
        else:
            raise DemoPackageError(f"demo_authority_owner_unsupported:{owner_type}")
        result.append(AuthorityTranslationInput(locale_id=locales[locale_code].id, fields=fields))
    return result


def _trust_translations(
    record: DemoRecord,
    locales: dict[str, Locale],
    owner_type: str,
) -> list[TrustTranslation]:
    """
    将能力、设备、证据卡和展会映射到现有Trust翻译字段。

    输入：record、语言映射和owner类型。
    输出：list[TrustTranslation]，不包含虚构证书编号或真实能力断言。
    """
    result: list[TrustTranslation] = []
    for locale_code in ("zh-CN", "en"):
        content = _locale_content(record, locale_code)
        name = str(content["name"])
        summary = str(content.get("summary") or "")
        if owner_type == "manufacturing_capability":
            fields = {
                "name": name,
                "summary": summary,
                "description": summary,
                "key_facts_json": ["DEMO / 演示流程，不是能力证明"],
            }
        elif owner_type == "equipment":
            fields = {
                "name": name,
                "summary": summary,
                "description": summary,
                "public_specs_json": {"status": "DEMO_ONLY"},
            }
        elif owner_type == "certificate":
            fields = {"name": name, "summary": summary, "scope": "SAMPLE / 无效演示样张"}
        elif owner_type == "exhibition":
            fields = {"title": name, "summary": summary, "description": summary}
        else:
            raise DemoPackageError(f"demo_trust_owner_unsupported:{owner_type}")
        result.append(TrustTranslation(locale_id=locales[locale_code].id, fields=fields))
    return result


async def _publish_routed_owner(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locales: dict[str, Locale],
    actor_id: uuid.UUID,
) -> int:
    """
    通过统一Publication状态机审核并发布一个双语演示实体。

    输入：会话、owner类型/ID、语言和真实本地操作人ID。
    输出：int，实际处理的语言数。
    """
    count = 0
    for locale in locales.values():
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.owner_type == owner_type,
                ContentPublication.owner_id == owner_id,
                ContentPublication.locale_id == locale.id,
            )
        )
        translation = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == owner_type,
                TranslationStatus.owner_id == owner_id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        route = await session.scalar(
            select(ContentRoute).where(
                ContentRoute.owner_type == owner_type,
                ContentRoute.owner_id == owner_id,
                ContentRoute.locale_id == locale.id,
                ContentRoute.is_canonical.is_(True),
            )
        )
        if publication is None or translation is None or route is None:
            raise DemoPackageError(f"demo_lifecycle_missing:{owner_type}:{locale.code}")
        if publication.status == "published":
            continue
        if publication.status == "draft":
            translation.status = "human_reviewed"
            translation.reviewed_by = actor_id
            write_audit_log(
                session,
                action="translation.review",
                target_type=owner_type,
                target_id=str(owner_id),
                user_id=actor_id,
                metadata={"demo_batch_id": DEMO_BATCH_ID, "locale": locale.code},
            )
            await transition_publication(
                session,
                publication=publication,
                translation=translation,
                route=route,
                target_status=PublicationStatus.REVIEW,
                actor_permissions={"content.review"},
                actor_id=actor_id,
            )
        await transition_publication(
            session,
            publication=publication,
            translation=translation,
            route=route,
            target_status=PublicationStatus.PUBLISHED,
            actor_permissions={"content.publish"},
            actor_id=actor_id,
        )
        count += 1
    return count


async def _publish_non_routed_owner(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locales: dict[str, Locale],
    actor_id: uuid.UUID,
) -> int:
    """
    发布没有独立Route的FAQ、设备和演示证据卡翻译状态。

    输入：会话、owner类型/ID、语言和真实本地操作人ID。
    输出：int，实际更新语言数。
    """
    count = 0
    for locale in locales.values():
        status = await session.scalar(
            select(TranslationStatus).where(
                TranslationStatus.owner_type == owner_type,
                TranslationStatus.owner_id == owner_id,
                TranslationStatus.locale_id == locale.id,
            )
        )
        if status is None:
            raise DemoPackageError(f"demo_translation_status_missing:{owner_type}:{locale.code}")
        if status.status == "published":
            continue
        status.status = "published"
        status.reviewed_by = actor_id
        status.published_at = datetime.now(UTC)
        write_audit_log(
            session,
            action="translation.publish",
            target_type=owner_type,
            target_id=str(owner_id),
            user_id=actor_id,
            metadata={"demo_batch_id": DEMO_BATCH_ID, "locale": locale.code},
        )
        count += 1
    await session.flush()
    return count


async def _import_media(
    session: AsyncSession,
    *,
    manifest: DemoMediaManifest,
    media_root: Path,
    locales: dict[str, Locale],
    actor_id: uuid.UUID,
    storage: MinioStorageAdapter,
) -> tuple[dict[str, MediaAsset], int]:
    """
    校验并上传实际媒体字节，建立可公开媒体和双语alt。

    输入：会话、媒体清单/根目录、语言、操作人和MinIO适配器。
    输出：tuple[槽位到媒体映射, 新建媒体数量]。
    """
    slot_map: dict[str, MediaAsset] = {}
    created = 0
    for item in manifest.assets:
        file_path = (media_root / item.file).resolve()
        content = file_path.read_bytes()
        mime_type = _mime_type_for_demo_media(file_path)
        metadata = validate_upload_bytes(file_path.name, mime_type, content)
        storage_key = f"demo-r2/{metadata['sha256'][:16]}/{metadata['sanitized_filename']}"
        asset = await session.scalar(
            select(MediaAsset).where(
                MediaAsset.storage_bucket == "public-media",
                MediaAsset.storage_key == storage_key,
            )
        )
        if asset is None:
            await storage.put_object("public-media", storage_key, content, mime_type)
            asset = MediaAsset(
                visibility="public",
                storage_bucket="public-media",
                storage_key=storage_key,
                checksum_verified=True,
                malware_scan_status="not_required",
                upload_status="ready",
                duration_seconds=item.duration_seconds,
                uploaded_by=actor_id,
                **metadata,
            )
            session.add(asset)
            await session.flush()
            for locale_code, alt in (("zh-CN", item.alt_zh), ("en", item.alt_en)):
                session.add(
                    MediaAssetTranslation(
                        media_asset_id=asset.id,
                        locale_id=locales[locale_code].id,
                        alt_text=alt,
                        title=alt,
                        caption=(
                            "DEMO / 演示素材；并非工厂、客户或证书实拍。"
                            if item.content_origin != "approved_public_copy"
                            else "已批准公开素材的只读副本。"
                        ),
                    )
                )
            write_audit_log(
                session,
                action="media.upload",
                target_type="media_asset",
                target_id=str(asset.id),
                user_id=actor_id,
                metadata={
                    "demo_batch_id": DEMO_BATCH_ID,
                    "content_origin": item.content_origin,
                    "alias": item.alias,
                },
            )
            created += 1
        elif asset.sha256 != metadata["sha256"] or asset.upload_status != "ready":
            raise DemoPackageError(f"demo_media_conflict:{item.alias}")
        for slot in item.slots:
            slot_map[slot] = asset
    return slot_map, created


async def _existing_aliases(session: AsyncSession, package: DemoPackage) -> tuple[dict[str, uuid.UUID], int]:
    """
    读取已导入别名并验证批次指纹，保证重复运行不会覆盖后台人工修改。

    输入：会话和已验证内容包。
    输出：tuple[别名到实体ID, no-op数量]。
    """
    records = list(
        (
            await session.scalars(
                select(DemoContentRecord).where(DemoContentRecord.batch_id == DEMO_BATCH_ID)
            )
        ).all()
    )
    package_by_alias = {record.alias: record for record in package.records}
    aliases: dict[str, uuid.UUID] = {}
    for existing in records:
        source = package_by_alias.get(existing.alias)
        if source is None or record_fingerprint(source) != existing.initial_fingerprint:
            existing.replacement_status = "conflict"
            raise DemoPackageError(f"demo_content_conflict:{existing.alias}")
        aliases[existing.alias] = existing.entity_id
    return aliases, len(aliases)


async def _register_record(
    session: AsyncSession,
    record: DemoRecord,
    entity_id: uuid.UUID,
) -> None:
    """
    记录演示实体来源和初始指纹，不复制正文为第二内容源。

    输入：会话、包内记录和实际业务实体ID。
    输出：None；来源记录加入当前事务。
    """
    session.add(
        DemoContentRecord(
            batch_id=DEMO_BATCH_ID,
            alias=record.alias,
            entity_type=record.kind,
            entity_id=entity_id,
            content_origin=record.content_origin.lower(),
            initial_fingerprint=record_fingerprint(record),
            replacement_status="demo_active",
            source_metadata_jsonb={
                "source": "DEMO-CONTENT-R2-V1",
                "kind": record.kind,
                "replaces_real_data": record.replaces_real_data,
            },
        )
    )
    await session.flush()


async def _attach_record_media(
    session: AsyncSession,
    *,
    record: DemoRecord,
    entity_id: uuid.UUID,
    owner_type: str,
    slot_map: dict[str, MediaAsset],
) -> None:
    """
    将记录媒体槽位写入统一跨内容媒体关系。

    输入：会话、记录、owner和槽位映射。
    输出：None；缺少已生产槽位时失败。
    """
    slots = list(record.model_extra.get("media_slots") or [])
    for index, slot in enumerate(slots):
        asset = slot_map.get(str(slot))
        if asset is None:
            raise DemoPackageError(f"demo_media_slot_missing:{slot}")
        session.add(
            ContentMediaLink(
                owner_type=owner_type,
                owner_id=entity_id,
                media_asset_id=asset.id,
                role="primary" if index == 0 else "gallery",
                sort_order=index,
            )
        )


def _first_media(record: DemoRecord, slot_map: dict[str, MediaAsset]) -> uuid.UUID | None:
    """输入记录和槽位映射；输出首张媒体UUID或None。"""
    slots = list(record.model_extra.get("media_slots") or [])
    return slot_map[str(slots[0])].id if slots else None


async def _create_catalog_records(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    slot_map: dict[str, MediaAsset],
    actor_id: uuid.UUID,
) -> tuple[int, int, set[str]]:
    """
    按依赖顺序创建分类、核心实体和产品。

    输入：会话、包、语言、别名、媒体和操作人。
    输出：tuple[新建数, 发布语言数, 本轮新别名集合]。
    """
    created = 0
    published = 0
    created_aliases: set[str] = set()
    kind_order = ("category", "material", "technology", "application", "solution", "product")
    for kind in kind_order:
        for index, record in enumerate((item for item in package.records if item.kind == kind), start=1):
            if record.alias in aliases:
                continue
            slug = canonical_demo_slug(record.alias, record.model_extra.get("slug"))
            if kind == "category":
                entity = await create_category(
                    session,
                    CategoryCreate(
                        slug=slug,
                        sort_order=index * 10,
                        translations=_catalog_translations(record, locales, "product_category"),
                    ),
                    actor_id,
                )
                owner_type = "product_category"
            elif kind in {"material", "technology", "application", "solution"}:
                entity = await create_core_entity(
                    session,
                    kind,
                    EntityCreate(
                        slug=slug,
                        featured=True,
                        sort_order=index * 10,
                        translations=_catalog_translations(record, locales, kind),
                    ),
                    actor_id,
                )
                owner_type = kind
            else:
                category_alias = str(record.model_extra["category"])
                category_id = aliases.get(category_alias)
                if category_id is None:
                    raise DemoPackageError(f"demo_category_alias_missing:{category_alias}")
                entity = await create_product(
                    session,
                    ProductCreate(
                        category_id=category_id,
                        code=str(record.model_extra.get("code") or record.alias),
                        slug=slug,
                        featured=True,
                        sort_order=index * 10,
                        primary_media_id=_first_media(record, slot_map),
                        translations=_catalog_translations(record, locales, "product"),
                    ),
                    actor_id,
                )
                owner_type = "product"
                for model_index, model_data in enumerate(record.model_extra.get("models") or [], start=1):
                    label = str(model_data["label"])
                    await create_product_model(
                        session,
                        entity.id,
                        ProductModelCreate(
                            model_code=str(model_data["code"]),
                            sort_order=model_index * 10,
                            translations=[
                                TranslationInput(locale_id=locale.id, name=label, fields={"description": "DEMO / 演示型号"})
                                for locale in locales.values()
                            ],
                        ),
                        actor_id,
                    )
            aliases[record.alias] = entity.id
            created_aliases.add(record.alias)
            await _register_record(session, record, entity.id)
            await _attach_record_media(
                session,
                record=record,
                entity_id=entity.id,
                owner_type=owner_type,
                slot_map=slot_map,
            )
            published += await _publish_routed_owner(
                session,
                owner_type=owner_type,
                owner_id=entity.id,
                locales=locales,
                actor_id=actor_id,
            )
            created += 1
    return created, published, created_aliases


async def _create_demo_specifications(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    created_aliases: set[str],
    actor_id: uuid.UUID,
) -> None:
    """
    为本轮新产品创建真实动态规格定义和值。

    输入：会话、包、语言、别名、新建集合和操作人。
    输出：None；已有记录不重写，保护后台人工调整。
    """
    products = [record for record in package.records if record.kind == "product" and record.alias in created_aliases]
    if not products:
        return
    group = await create_specification_group(
        session,
        SpecificationGroupCreate(
            code="demo-r2-specifications",
            sort_order=900,
            translations=[
                TranslationInput(locale_id=locales["zh-CN"].id, name="DEMO 演示规格"),
                TranslationInput(locale_id=locales["en"].id, name="DEMO specifications"),
            ],
        ),
        actor_id,
    )
    definitions: dict[tuple[str, str, str | None], Any] = {}
    for record in products:
        for spec in record.model_extra.get("demo_specifications") or []:
            key = (str(spec["label_zh"]), str(spec["type"]), spec.get("unit"))
            if key in definitions:
                continue
            code = canonical_demo_slug(f"{key[0]}-{key[1]}", None).removeprefix("demo-")[:100]
            definition = await create_specification_definition(
                session,
                SpecificationDefinitionCreate(
                    group_id=group.id,
                    code=code,
                    value_type=key[1],
                    default_unit=key[2],
                    sort_order=len(definitions) * 10,
                    translations=[
                        TranslationInput(locale_id=locales["zh-CN"].id, name=key[0]),
                        TranslationInput(locale_id=locales["en"].id, name=str(spec["label_en"])),
                    ],
                ),
                actor_id,
            )
            definitions[key] = definition
    for record in products:
        for index, spec in enumerate(record.model_extra.get("demo_specifications") or []):
            key = (str(spec["label_zh"]), str(spec["type"]), spec.get("unit"))
            values: dict[str, Any] = {}
            if spec["type"] == "number":
                values["value_number"] = spec["value"]
            elif spec["type"] == "range":
                values.update(value_min=spec.get("min"), value_max=spec.get("max"))
            elif spec["type"] == "boolean":
                values["value_boolean"] = spec["value"]
            elif spec["type"] == "enum":
                values["enum_value"] = str(spec["value"])
            else:
                values["value_text"] = str(spec["value"])
            await create_specification_value(
                session,
                SpecificationValueCreate(
                    product_id=aliases[record.alias],
                    definition_id=definitions[key].id,
                    unit_override=spec.get("unit"),
                    sort_order=index * 10,
                    **values,
                ),
                actor_id,
            )


async def _create_authority_records(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    slot_map: dict[str, MediaAsset],
    actor_id: uuid.UUID,
) -> tuple[int, int, set[str]]:
    """
    创建案例、FAQ和知识文章，并使用Demo编辑组织而非虚构真人。

    输入：会话、包、语言、别名、媒体和操作人。
    输出：tuple[新建数, 发布语言数, 本轮新别名集合]。
    """
    author = await session.scalar(select(AuthorExpert).where(AuthorExpert.slug == "demo-editorial-team"))
    if author is None:
        author = await create_author_expert(
            session,
            AuthorExpertCreate(
                slug="demo-editorial-team",
                role_type="author",
                identity_kind="organization",
                is_real_person_verified=False,
                public_profile_enabled=False,
                translations=[
                    AuthorityTranslationInput(
                        locale_id=locales["zh-CN"].id,
                        fields={"name": "DEMO 内容编辑组", "job_title": "演示内容维护组织", "short_bio": "非真实人物，不代表专家核验。"},
                    ),
                    AuthorityTranslationInput(
                        locale_id=locales["en"].id,
                        fields={"name": "DEMO editorial team", "job_title": "Demonstration content organization", "short_bio": "Not a real person or verified expert."},
                    ),
                ],
            ),
            actor_id,
        )
        await _publish_non_routed_owner(
            session,
            owner_type="author_expert",
            owner_id=author.id,
            locales=locales,
            actor_id=actor_id,
        )
    category = await session.scalar(
        select(KnowledgeCategory).where(KnowledgeCategory.slug == "technical-guides")
    )
    if category is None:
        raise DemoPackageError("demo_knowledge_category_missing")

    created = 0
    published = 0
    created_aliases: set[str] = set()
    for kind in ("case", "faq", "article"):
        for index, record in enumerate((item for item in package.records if item.kind == kind), start=1):
            if record.alias in aliases:
                continue
            if kind == "case":
                entity = await create_case_study(
                    session,
                    CaseStudyCreate(
                        slug=canonical_demo_slug(record.alias, None),
                        client_name=str(record.model_extra.get("customer_name") or "DEMO fictional project"),
                        client_name_public=False,
                        featured=True,
                        sort_order=index * 10,
                        primary_media_id=_first_media(record, slot_map),
                        translations=_authority_translations(record, locales, "case_study"),
                    ),
                    actor_id,
                )
                owner_type = "case_study"
                routed = True
            elif kind == "faq":
                entity = await create_faq(
                    session,
                    FAQCreate(
                        sort_order=index * 10,
                        translations=_authority_translations(record, locales, "faq"),
                    ),
                    actor_id,
                )
                owner_type = "faq"
                routed = False
            else:
                entity = await create_knowledge_article(
                    session,
                    KnowledgeArticleCreate(
                        category_id=category.id,
                        slug=canonical_demo_slug(record.alias, None),
                        author_id=author.id,
                        reviewer_id=None,
                        featured=True,
                        sort_order=index * 10,
                        primary_media_id=_first_media(record, slot_map),
                        translations=_authority_translations(record, locales, "knowledge_article"),
                    ),
                    actor_id,
                )
                owner_type = "knowledge_article"
                routed = True
            aliases[record.alias] = entity.id
            created_aliases.add(record.alias)
            await _register_record(session, record, entity.id)
            await _attach_record_media(
                session,
                record=record,
                entity_id=entity.id,
                owner_type=owner_type,
                slot_map=slot_map,
            )
            if routed:
                published += await _publish_routed_owner(
                    session,
                    owner_type=owner_type,
                    owner_id=entity.id,
                    locales=locales,
                    actor_id=actor_id,
                )
            else:
                published += await _publish_non_routed_owner(
                    session,
                    owner_type=owner_type,
                    owner_id=entity.id,
                    locales=locales,
                    actor_id=actor_id,
                )
            created += 1
    return created, published, created_aliases


async def _create_trust_records(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    slot_map: dict[str, MediaAsset],
    actor_id: uuid.UUID,
) -> tuple[int, int, set[str]]:
    """
    创建能力、设备、无效样例证据卡和演示展会。

    输入：会话、包、语言、别名、媒体和操作人。
    输出：tuple[新建数, 发布语言数, 本轮新别名集合]。
    """
    mapping = {
        "capability": ("capabilities", "manufacturing_capability", True),
        "equipment": ("equipment", "equipment", False),
        "proof_card": ("certificates", "certificate", False),
        "exhibition": ("exhibitions", "exhibition", True),
    }
    created = 0
    published = 0
    created_aliases: set[str] = set()
    for kind, (resource, owner_type, routed) in mapping.items():
        for index, record in enumerate((item for item in package.records if item.kind == kind), start=1):
            if record.alias in aliases:
                continue
            primary_media_id = _first_media(record, slot_map)
            fields: dict[str, Any]
            if kind == "capability":
                fields = {"capability_type": "demo-workflow", "primary_media_id": primary_media_id}
            elif kind == "equipment":
                fields = {
                    "equipment_type": "demo-illustration",
                    "featured": True,
                    "primary_media_id": primary_media_id,
                }
            elif kind == "proof_card":
                fields = {
                    "certificate_type": "demo-sample",
                    "certificate_number": None,
                    "issuer": "DEMO SAMPLE — no issuing authority",
                    "verification_url": None,
                    "primary_media_id": primary_media_id,
                }
            else:
                fields = {"event_name": "DEMO illustrative event", "primary_media_id": primary_media_id}
            entity = await create_trust_entity(
                session,
                resource,
                TrustEntityInput(
                    slug=canonical_demo_slug(record.alias, None),
                    sort_order=index * 10,
                    fields=fields,
                    translations=_trust_translations(record, locales, owner_type),
                ),
                actor_id,
            )
            aliases[record.alias] = entity.id
            created_aliases.add(record.alias)
            await _register_record(session, record, entity.id)
            await _attach_record_media(
                session,
                record=record,
                entity_id=entity.id,
                owner_type=owner_type,
                slot_map=slot_map,
            )
            if routed:
                published += await _publish_routed_owner(
                    session,
                    owner_type=owner_type,
                    owner_id=entity.id,
                    locales=locales,
                    actor_id=actor_id,
                )
            else:
                published += await _publish_non_routed_owner(
                    session,
                    owner_type=owner_type,
                    owner_id=entity.id,
                    locales=locales,
                    actor_id=actor_id,
                )
            created += 1
    return created, published, created_aliases


_DEMO_RFQ_STATUS_BY_SCENARIO = {
    "new": "new",
    "in_review": "in_progress",
    "follow_up": "waiting_customer",
    "qualified": "qualified",
    "quoted": "quoted",
    "won": "won",
    "lost": "lost",
    "closed": "closed",
}


def _apply_demo_rfq_scenario(entity: RFQ, record: DemoRecord) -> bool:
    """
    将虚构询盘同步为用户内容包指定的看板状态。

    输入：entity，Demo隔离库中的询盘；record，带status_scenario的包内记录。
    输出：bool；状态发生变化时为True，已一致时为False。
    """
    scenario = str(record.model_extra.get("status_scenario") or "new")
    expected_status = _DEMO_RFQ_STATUS_BY_SCENARIO.get(scenario, "new")
    if entity.status == expected_status:
        return False
    entity.status = expected_status
    return True


async def _create_downloads_and_rfqs(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    slot_map: dict[str, MediaAsset],
    actor_id: uuid.UUID,
) -> tuple[int, set[str]]:
    """
    建立三份真实下载文件记录与十二条明确标记的虚构询盘。

    输入：会话、包、语言、别名、媒体和操作人。
    输出：tuple[新建数, 本轮新别名集合]；不发送邮件、不创建附件。
    """
    created = 0
    created_aliases: set[str] = set()
    downloads = [record for record in package.records if record.kind == "download"]
    for index, record in enumerate(downloads, start=1):
        if record.alias in aliases:
            continue
        asset = slot_map.get(f"FILE-DOWNLOAD-{index:02d}")
        if asset is None:
            raise DemoPackageError(f"demo_download_media_missing:{index}")
        entity = DownloadResource(
            slug=canonical_demo_slug(record.alias, None),
            resource_type="document",
            status="enabled",
            media_asset_id=asset.id,
            version_label="SAMPLE / DEMO R2",
            requires_form=False,
            sort_order=index * 10,
        )
        session.add(entity)
        await session.flush()
        for locale_code in ("zh-CN", "en"):
            content = _locale_content(record, locale_code)
            session.add(
                DownloadResourceTranslation(
                    download_resource_id=entity.id,
                    locale_id=locales[locale_code].id,
                    title=str(content["name"]),
                    summary=str(content.get("summary") or ""),
                )
            )
        aliases[record.alias] = entity.id
        created_aliases.add(record.alias)
        await _register_record(session, record, entity.id)
        session.add(
            ContentMediaLink(
                owner_type="download_resource",
                owner_id=entity.id,
                media_asset_id=asset.id,
                role="download",
                sort_order=0,
            )
        )
        write_audit_log(
            session,
            action="download.create",
            target_type="download_resource",
            target_id=str(entity.id),
            user_id=actor_id,
            metadata={"demo_batch_id": DEMO_BATCH_ID},
        )
        created += 1

    rfqs = [record for record in package.records if record.kind == "rfq"]
    for index, record in enumerate(rfqs, start=1):
        if record.alias in aliases:
            existing = await session.get(RFQ, aliases[record.alias])
            if existing is None:
                raise DemoPackageError(f"demo_rfq_registry_target_missing:{record.alias}")
            previous_status = existing.status
            if _apply_demo_rfq_scenario(existing, record):
                write_audit_log(
                    session,
                    action="rfq.demo_fixture.reconcile",
                    target_type="rfq",
                    target_id=str(existing.id),
                    user_id=actor_id,
                    metadata={
                        "demo_batch_id": DEMO_BATCH_ID,
                        "previous_status": previous_status,
                        "next_status": existing.status,
                        "email_sent": False,
                    },
                )
            continue
        product_alias = str(record.model_extra.get("product_alias") or "")
        product_id = aliases.get(product_alias)
        entity = RFQ(
            public_reference=f"DEMO-R2-{index:03d}",
            status="new",
            priority="normal",
            company_name=f"DEMO — {record.model_extra.get('company') or 'fictional company'}",
            contact_name=str(record.model_extra.get("contact") or "Demo contact"),
            email=str(record.model_extra.get("email") or "contact@demo.example"),
            message=str(_locale_content(record, "en").get("summary") or "DEMO ONLY"),
            preferred_language="en",
            source_page_url="https://demo.junhuiscrewbarrel.com/en/request-a-quote/",
            source_owner_type="product" if product_id else None,
            source_owner_id=product_id,
            consent_privacy=False,
            consent_marketing=False,
            submitted_ip="127.0.0.1",
            user_agent="Demo R2 offline fixture",
        )
        _apply_demo_rfq_scenario(entity, record)
        session.add(entity)
        await session.flush()
        session.add(
            RFQItem(
                rfq_id=entity.id,
                item_type="product" if product_id else "custom",
                product_id=product_id,
                product_name_text=product_alias or "DEMO request",
                requirements="DEMO ONLY — no email is sent and no customer file is attached.",
                sort_order=0,
            )
        )
        aliases[record.alias] = entity.id
        created_aliases.add(record.alias)
        await _register_record(session, record, entity.id)
        write_audit_log(
            session,
            action="rfq.demo_fixture.create",
            target_type="rfq",
            target_id=str(entity.id),
            user_id=actor_id,
            metadata={"demo_batch_id": DEMO_BATCH_ID, "email_sent": False},
        )
        created += 1
    return created, created_aliases


async def _apply_relations(
    session: AsyncSession,
    *,
    package: DemoPackage,
    aliases: dict[str, uuid.UUID],
    created_aliases: set[str],
    actor_id: uuid.UUID,
) -> int:
    """
    将72条别名关系映射到现有产品、Authority和能力设备关系表。

    输入：会话、包、别名、本轮新建别名和操作人。
    输出：int，实际应用的包内关系数。
    """
    grouped: dict[str, dict[str, list[uuid.UUID]]] = defaultdict(lambda: defaultdict(list))
    relation_count = 0
    for relation in package.relations:
        if relation.from_alias not in created_aliases:
            continue
        grouped[relation.from_alias][relation.relation].append(aliases[relation.to_alias])
        relation_count += 1

    record_by_alias = {record.alias: record for record in package.records}
    for source_alias, target_groups in grouped.items():
        source = record_by_alias[source_alias]
        if source.kind == "product":
            await replace_product_relations(
                session,
                aliases[source_alias],
                RelationUpdate(
                    material_ids=target_groups.get("material", []),
                    technology_ids=target_groups.get("technology", []),
                    application_ids=target_groups.get("application", []),
                    solution_ids=target_groups.get("solution", []),
                ),
                actor_id,
            )
        elif source.kind in {"case", "article", "faq"}:
            owner_type = {"case": "case_study", "article": "knowledge_article", "faq": "faq"}[source.kind]
            await replace_authority_relations(
                session,
                owner_type,
                aliases[source_alias],
                AuthorityRelationUpdate(
                    product_ids=target_groups.get("product", []),
                    material_ids=target_groups.get("material", []),
                    technology_ids=target_groups.get("technology", []),
                    application_ids=target_groups.get("application", []),
                    solution_ids=target_groups.get("solution", []),
                    case_ids=target_groups.get("case", []),
                    faq_ids=target_groups.get("faq", []),
                ),
                actor_id,
            )
        elif source.kind == "capability":
            for order, equipment_id in enumerate(target_groups.get("equipment", [])):
                session.add(
                    CapabilityEquipment(
                        capability_id=aliases[source_alias],
                        equipment_id=equipment_id,
                        sort_order=order,
                        notes="DEMO_RELATION_NOT_REAL_COMPATIBILITY",
                    )
                )
    await session.flush()
    return relation_count


async def _apply_seo_geo(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    created_aliases: set[str],
    actor_id: uuid.UUID,
) -> None:
    """
    将包内产品和文章SEO/GEO写入统一文档体系。

    输入：会话、包、语言、别名、新建集合和操作人。
    输出：None；不为没有候选的页面虚构元数据。
    """
    for record in package.records:
        if record.alias not in created_aliases or record.kind not in {"product", "article"}:
            continue
        owner_type = "product" if record.kind == "product" else "knowledge_article"
        seo_by_locale = record.model_extra.get("seo") or {}
        geo_by_locale = record.model_extra.get("geo") or {}
        for locale_code in ("zh-CN", "en"):
            seo = seo_by_locale.get(locale_code)
            if seo:
                await upsert_seo_document(
                    session,
                    owner_type,
                    aliases[record.alias],
                    locales[locale_code].id,
                    SeoDocumentUpsert(
                        seo_title=str(seo.get("title") or ""),
                        meta_description=str(seo.get("description") or ""),
                        robots_index=True,
                        robots_follow=True,
                    ),
                    actor_id,
                )
            geo = geo_by_locale.get(locale_code)
            if geo:
                await upsert_geo_document(
                    session,
                    owner_type,
                    aliases[record.alias],
                    locales[locale_code].id,
                    GeoDocumentUpsert(
                        direct_answer=str(geo.get("direct_answer") or ""),
                        target_questions_json=[str(geo.get("target_question") or "")],
                    ),
                    actor_id,
                )


async def _ensure_demo_site_shell(
    session: AsyncSession,
    *,
    package: DemoPackage,
    locales: dict[str, Locale],
    aliases: dict[str, uuid.UUID],
    slot_map: dict[str, MediaAsset],
    actor_id: uuid.UUID,
) -> int:
    """
    建立Demo公司首页、Products固定页和十四模块应用布局。

    输入：会话、包、语言、内容/媒体映射和操作人。
    输出：int，新增发布语言计数。
    """
    hero_media = slot_map.get("IMAGE-HERO")
    logo_media = slot_map.get("BRAND-LOGO")
    home_copy = package.demo_page_copy["home"]
    company = await upsert_company_profile(
        session,
        CompanyProfileInput(
            status="enabled",
            logo_media_id=logo_media.id if logo_media else None,
            primary_factory_media_id=hero_media.id if hero_media else None,
            export_markets_json=[
                f"DEMO · {region}"
                for region in package.demo_page_copy["global_markets"][
                    "display_regions_illustrative"
                ]
            ],
            public_email=str(package.demo_page_copy["contact"]["email_display"]),
            translations=[
                TrustTranslation(
                    locale_id=locales[locale_code].id,
                    fields={
                        "company_name": "舟山骏辉塑料机械有限公司" if locale_code == "zh-CN" else "Zhoushan Junhui Plastic Machinery Co., Ltd.",
                        "short_intro": str(home_copy[locale_code]["intro"]),
                        "full_intro": str(home_copy[locale_code]["intro"]),
                        "mission": str(home_copy[locale_code]["headline"]),
                        "advantages_json": ["演示目录", "双语内容", "可替换媒体"],
                    },
                )
                for locale_code in ("zh-CN", "en")
            ],
        ),
        actor_id,
    )
    # 视频与海报通过统一媒体关系持久化；前台和后台共用同一关联，不使用静态URL。
    for role, order, slot in (
        ("video", 0, "VIDEO-01"),
        ("video_poster", 0, "IMAGE-FACTORY-WIDE"),
        ("video", 1, "VIDEO-02"),
        ("video_poster", 1, "IMAGE-HERO"),
    ):
        asset = slot_map.get(slot)
        if asset is None:
            raise DemoPackageError(f"demo_presentation_media_missing:{slot}")
        session.add(
            ContentMediaLink(
                owner_type="company_profile",
                owner_id=company.id,
                media_asset_id=asset.id,
                role=role,
                sort_order=order,
            )
        )
    published = await _publish_routed_owner(
        session,
        owner_type="company_profile",
        owner_id=company.id,
        locales=locales,
        actor_id=actor_id,
    )

    products_page = await initialize_products_site_page(
        session,
        system_key="products",
        actor_id=actor_id,
    )
    products_copy = {
        "zh-CN": ("产品目录演示", "浏览可替换的螺杆、机筒和配件演示目录。"),
        "en": ("Product catalog demo", "Explore the replaceable screw, barrel and component demonstration catalog."),
    }
    permissions = {"translation.review", "translation.publish", "content.review", "content.publish"}
    for locale_code in ("zh-CN", "en"):
        title, description = products_copy[locale_code]
        await upsert_seo_document(
            session,
            "site_page",
            products_page.id,
            locales[locale_code].id,
            SeoDocumentUpsert(
                seo_title=title,
                meta_description=description,
                robots_index=True,
                robots_follow=True,
            ),
            actor_id,
            allow_site_page=True,
        )
        await review_products_site_page(
            session,
            system_key="products",
            locale_code=locale_code,
            actor_permissions=permissions,
            actor_id=actor_id,
        )
        await publish_products_site_page(
            session,
            system_key="products",
            locale_code=locale_code,
            actor_permissions=permissions,
            actor_id=actor_id,
        )
        published += 1

    await initialize_homepage(session, actor_id=actor_id)
    product_slugs = [
        canonical_demo_slug(record.alias, record.model_extra.get("slug"))
        for record in package.records
        if record.kind == "product"
    ][:3]
    default = default_homepage_config()
    for module in default["modules"]:
        if module["key"] in {"hero", "core_product_families"}:
            module["product_slugs"] = product_slugs
        if module["key"] in {"hero", "technologies", "global_markets", "rfq_cta"}:
            allowed = {
                "hero": "navy",
                "technologies": "navy",
                "global_markets": "navy",
                "rfq_cta": "navy",
            }
            module["variant"] = allowed[module["key"]]
        module["visible"] = True
    for locale_code in ("zh-CN", "en"):
        current = await get_homepage_language_detail(session, locale_code)
        payload = HomepageDraftUpdate(
            expected_revision=current["layout"]["draft_revision"],
            modules=default["modules"],
        )
        saved = await save_homepage_draft(
            session,
            locale_code=locale_code,
            payload=payload,
            actor_id=actor_id,
        )
        await apply_homepage_layout(
            session,
            locale_code=locale_code,
            expected_revision=saved["layout"]["draft_revision"],
            actor_id=actor_id,
        )
    return published


async def prepare_demo_r2(
    factory: async_sessionmaker[AsyncSession],
    *,
    content_path: Path,
    media_manifest_path: Path,
    media_root: Path,
    actor_email: str,
) -> DemoSetupResult:
    """
    显式初始化完整Demo R2，不在API普通启动或主实例中自动运行。

    输入：session factory、内容包、媒体清单/根目录和真实本地管理员邮箱。
    输出：DemoSetupResult，安全计数和别名映射。
    """
    _assert_demo_target()
    package = load_demo_package(content_path)
    media_manifest = _load_media_manifest(media_manifest_path, media_root)
    await seed_database(factory)
    storage = MinioStorageAdapter()
    async with factory() as session, session.begin():
        actor = await session.scalar(select(User).where(User.email == actor_email.strip().lower()))
        if actor is None or not actor.is_active:
            raise DemoPackageError("demo_actor_unavailable")
        locales = {
            locale.code: locale
            for locale in (
                await session.scalars(
                    select(Locale).where(Locale.code.in_(["zh-CN", "en"]), Locale.is_enabled.is_(True))
                )
            ).all()
        }
        if set(locales) != {"zh-CN", "en"}:
            raise DemoPackageError("demo_locales_missing")
        aliases, no_op = await _existing_aliases(session, package)
        slot_map, media_created = await _import_media(
            session,
            manifest=media_manifest,
            media_root=media_root,
            locales=locales,
            actor_id=actor.id,
            storage=storage,
        )
        package_slots = {
            str(slot)
            for record in package.records
            for slot in (record.model_extra.get("media_slots") or [])
        }
        required_slots = package_slots | {
            "IMAGE-HERO",
            "IMAGE-FACTORY-WIDE",
            "VIDEO-01",
            "VIDEO-02",
            "FILE-DOWNLOAD-01",
            "FILE-DOWNLOAD-02",
            "FILE-DOWNLOAD-03",
        }
        missing_slots = sorted(required_slots - set(slot_map))
        if missing_slots:
            raise DemoPackageError(f"demo_media_slots_incomplete:{','.join(missing_slots)}")

        created = 0
        published = 0
        created_aliases: set[str] = set()
        count, locale_count, batch = await _create_catalog_records(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            slot_map=slot_map,
            actor_id=actor.id,
        )
        created += count
        published += locale_count
        created_aliases.update(batch)
        await _create_demo_specifications(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            created_aliases=created_aliases,
            actor_id=actor.id,
        )

        count, locale_count, batch = await _create_authority_records(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            slot_map=slot_map,
            actor_id=actor.id,
        )
        created += count
        published += locale_count
        created_aliases.update(batch)
        count, locale_count, batch = await _create_trust_records(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            slot_map=slot_map,
            actor_id=actor.id,
        )
        created += count
        published += locale_count
        created_aliases.update(batch)
        count, batch = await _create_downloads_and_rfqs(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            slot_map=slot_map,
            actor_id=actor.id,
        )
        created += count
        created_aliases.update(batch)
        relations = await _apply_relations(
            session,
            package=package,
            aliases=aliases,
            created_aliases=created_aliases,
            actor_id=actor.id,
        )
        await _apply_seo_geo(
            session,
            package=package,
            locales=locales,
            aliases=aliases,
            created_aliases=created_aliases,
            actor_id=actor.id,
        )
        # 完整批次已存在时保持真正no-op，避免重写后台人工调整过的公司与首页配置。
        if created:
            published += await _ensure_demo_site_shell(
                session,
                package=package,
                locales=locales,
                aliases=aliases,
                slot_map=slot_map,
                actor_id=actor.id,
            )
        if len(aliases) != package.record_count:
            raise DemoPackageError("demo_alias_manifest_incomplete")
        return DemoSetupResult(
            demo_batch_id=DEMO_BATCH_ID,
            created=created,
            no_op=no_op,
            media_assets=media_created,
            relations=relations,
            published_locales=published,
            aliases={key: str(value) for key, value in sorted(aliases.items())},
        )
