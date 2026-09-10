"""Media Library 管理 API：公开资产上传与私有资产隔离。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import (
    FAQ,
    AuthorExpert,
    AuthorExpertTranslation,
    CaseStudy,
    CaseStudyTranslation,
    FAQTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
)
from app.modules.catalog.models import (
    Application,
    ApplicationTranslation,
    Material,
    MaterialTranslation,
    Product,
    ProductCategory,
    ProductCategoryTranslation,
    ProductTranslation,
    Solution,
    SolutionTranslation,
    Technology,
    TechnologyTranslation,
)
from app.modules.company.models import (
    Certificate,
    CertificateTranslation,
    CompanyProfile,
    CompanyProfileTranslation,
    Equipment,
    EquipmentTranslation,
    Exhibition,
    ExhibitionTranslation,
    Honor,
    HonorTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
    Patent,
    PatentTranslation,
)
from app.modules.demo.models import ContentMediaLink
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.localization.models import Locale
from app.modules.media.models import (
    DownloadResource,
    DownloadResourceTranslation,
    MediaAsset,
    MediaAssetTranslation,
)
from app.modules.media.services import refresh_public_image_dimensions, validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/media", tags=["media"])
public_router = APIRouter(prefix="/public/media", tags=["public-media"])


@dataclass(frozen=True)
class _MediaOwnerSpec:
    """
    描述一种可公开维护内容的媒体引用解析规则。

    输入：ORM 主实体/翻译模型、翻译外键、名称字段、权限和后台入口。
    输出：不可变配置，供使用位置接口按白名单解析，避免动态访问任意 owner。
    """

    model: type[Any]
    translation_model: type[Any]
    translation_owner_field: str
    name_field: str
    permission: str
    location: str
    admin_url: str
    fallback_field: str | None = "slug"
    public_flag_field: str | None = None


_MEDIA_OWNER_SPECS: dict[str, _MediaOwnerSpec] = {
    "company_profile": _MediaOwnerSpec(
        CompanyProfile,
        CompanyProfileTranslation,
        "company_profile_id",
        "company_name",
        "company.read",
        "企业资料",
        "/trust/company",
        fallback_field=None,
    ),
    "product_category": _MediaOwnerSpec(
        ProductCategory,
        ProductCategoryTranslation,
        "category_id",
        "name",
        "catalog.read",
        "产品分类",
        "/catalog/categories",
    ),
    "product": _MediaOwnerSpec(
        Product,
        ProductTranslation,
        "product_id",
        "name",
        "catalog.read",
        "产品",
        "/catalog/products",
    ),
    "material": _MediaOwnerSpec(
        Material,
        MaterialTranslation,
        "material_id",
        "name",
        "material.read",
        "材料",
        "/catalog/materials",
    ),
    "technology": _MediaOwnerSpec(
        Technology,
        TechnologyTranslation,
        "technology_id",
        "name",
        "technology.read",
        "技术工艺",
        "/catalog/technologies",
    ),
    "application": _MediaOwnerSpec(
        Application,
        ApplicationTranslation,
        "application_id",
        "name",
        "application.read",
        "应用场景",
        "/catalog/applications",
    ),
    "solution": _MediaOwnerSpec(
        Solution,
        SolutionTranslation,
        "solution_id",
        "name",
        "solution.read",
        "解决方案",
        "/catalog/solutions",
    ),
    "case_study": _MediaOwnerSpec(
        CaseStudy,
        CaseStudyTranslation,
        "case_study_id",
        "title",
        "case.read",
        "客户案例",
        "/cases",
    ),
    "knowledge_article": _MediaOwnerSpec(
        KnowledgeArticle,
        KnowledgeArticleTranslation,
        "article_id",
        "title",
        "knowledge.read",
        "知识文章",
        "/knowledge",
    ),
    "faq": _MediaOwnerSpec(
        FAQ,
        FAQTranslation,
        "faq_id",
        "question",
        "faq.read",
        "常见问题",
        "/faqs",
        fallback_field=None,
    ),
    "author_expert": _MediaOwnerSpec(
        AuthorExpert,
        AuthorExpertTranslation,
        "author_expert_id",
        "name",
        "expert.read",
        "作者与专家",
        "/experts",
        fallback_field=None,
        public_flag_field="public_profile_enabled",
    ),
    "manufacturing_capability": _MediaOwnerSpec(
        ManufacturingCapability,
        ManufacturingCapabilityTranslation,
        "capability_id",
        "name",
        "capability.read",
        "制造能力",
        "/trust/capabilities",
    ),
    "equipment": _MediaOwnerSpec(
        Equipment,
        EquipmentTranslation,
        "equipment_id",
        "name",
        "equipment.read",
        "设备",
        "/trust/equipment",
    ),
    "certificate": _MediaOwnerSpec(
        Certificate,
        CertificateTranslation,
        "certificate_id",
        "name",
        "certificate.read",
        "证书",
        "/trust/certificates",
    ),
    "patent": _MediaOwnerSpec(
        Patent,
        PatentTranslation,
        "patent_id",
        "title",
        "patent.read",
        "专利",
        "/trust/patents",
    ),
    "honor": _MediaOwnerSpec(
        Honor,
        HonorTranslation,
        "honor_id",
        "title",
        "honor.read",
        "荣誉",
        "/trust/honors",
    ),
    "exhibition": _MediaOwnerSpec(
        Exhibition,
        ExhibitionTranslation,
        "exhibition_id",
        "title",
        "exhibition.read",
        "展会",
        "/trust/exhibitions",
        fallback_field="event_name",
    ),
    "download_resource": _MediaOwnerSpec(
        DownloadResource,
        DownloadResourceTranslation,
        "download_resource_id",
        "title",
        "download.read",
        "下载资料",
        "/downloads",
    ),
}

_MEDIA_DIRECT_REFERENCES: tuple[tuple[str, str, str], ...] = (
    ("company_profile", "logo_media_id", "logo"),
    ("company_profile", "primary_factory_media_id", "factory_primary"),
    ("product_category", "cover_media_id", "cover"),
    ("product", "primary_media_id", "primary"),
    ("case_study", "primary_media_id", "primary"),
    ("knowledge_article", "primary_media_id", "primary"),
    ("author_expert", "profile_media_id", "profile"),
    ("manufacturing_capability", "primary_media_id", "primary"),
    ("equipment", "primary_media_id", "primary"),
    ("certificate", "primary_media_id", "primary"),
    ("certificate", "public_file_media_id", "download"),
    ("patent", "primary_media_id", "primary"),
    ("patent", "public_file_media_id", "download"),
    ("honor", "primary_media_id", "primary"),
    ("exhibition", "primary_media_id", "primary"),
    ("download_resource", "media_asset_id", "download"),
)


async def _media_usage_row(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    role: str,
    locale_priority: dict[uuid.UUID, int],
) -> dict[str, str] | None:
    """
    将一条白名单 owner 引用解析为员工可读的维护位置。

    输入：数据库会话、owner 类型/ID、媒体用途和语言优先级。
    输出：可读位置、内容名称、用途和后台入口；不可见、无权或未知 owner 返回 None。
    """
    spec = _MEDIA_OWNER_SPECS.get(owner_type)
    if spec is None:
        return None
    entity = await session.get(spec.model, owner_id)
    if entity is None or getattr(entity, "status", "disabled") != "enabled":
        return None
    if spec.public_flag_field and not bool(getattr(entity, spec.public_flag_field, False)):
        return None

    translation_owner_column = getattr(spec.translation_model, spec.translation_owner_field)
    translations = list(
        (
            await session.scalars(
                select(spec.translation_model).where(translation_owner_column == owner_id)
            )
        ).all()
    )
    translations.sort(key=lambda item: locale_priority.get(item.locale_id, 100))
    content_name = next(
        (
            str(value).strip()
            for item in translations
            if (value := getattr(item, spec.name_field, None)) and str(value).strip()
        ),
        "",
    )
    if not content_name and spec.fallback_field:
        content_name = str(getattr(entity, spec.fallback_field, "") or "").strip()
    if not content_name:
        content_name = f"未填写{spec.location}名称"

    return {
        "location": spec.location,
        "content_name": content_name,
        "role": role,
        "admin_url": spec.admin_url,
    }


def _public_dto(asset: MediaAsset) -> dict[str, object]:
    """生成不泄露 storage credential 的媒体 DTO。"""
    return {
        "id": str(asset.id),
        "type": asset.media_type,
        "filename": asset.original_filename,
        "url": f"/api/v1/public/media/{asset.id}" if asset.visibility == "public" else None,
        "mime_type": asset.mime_type,
        "file_extension": asset.file_extension,
        "file_size_bytes": asset.file_size_bytes,
        "width": asset.width,
        "height": asset.height,
        "duration_seconds": asset.duration_seconds,
        "visibility": asset.visibility,
        "upload_status": asset.upload_status,
    }


def _media_detail_dto(
    asset: MediaAsset,
    translations: Sequence[MediaAssetTranslation],
    locales: Sequence[Locale],
) -> dict[str, object]:
    """
    生成后台可重开的媒体详情，且不暴露对象存储凭据。

    输入：
        asset: MediaAsset，公开媒体资产。
        translations: Sequence[MediaAssetTranslation]，资产已有的本地化元数据。
        locales: Sequence[Locale]，系统支持的语言。

    输出：
        dict[str, object]，公开媒体字段和每种语言的 Alt、标题、图注。
    """
    translations_by_locale = {translation.locale_id: translation for translation in translations}
    detail = _public_dto(asset)
    detail["translations"] = [
        {
            "locale_id": str(locale.id),
            "locale_code": locale.code,
            "locale_name": locale.native_name,
            "alt_text": translations_by_locale.get(locale.id).alt_text
            if translations_by_locale.get(locale.id)
            else "",
            "title": translations_by_locale.get(locale.id).title
            if translations_by_locale.get(locale.id)
            else "",
            "caption": translations_by_locale.get(locale.id).caption
            if translations_by_locale.get(locale.id)
            else "",
        }
        for locale in locales
    ]
    return detail


@router.get("", response_model=ApiResponse[list[dict[str, object]]])
async def list_media(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("media.read")),
) -> ApiResponse[list[dict[str, object]]]:
    """只列出公开媒体资产；私有 RFQ 文件通过 RFQ 权限访问。"""
    assets = list(
        (
            await session.scalars(
                select(MediaAsset)
                .where(MediaAsset.visibility == "public")
                .order_by(MediaAsset.created_at.desc())
            )
        ).all()
    )
    return success_response([_public_dto(asset) for asset in assets])


@router.get("/{asset_id}/usage", response_model=ApiResponse[list[dict[str, str]]])
async def get_media_usage(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("media.read")),
) -> ApiResponse[list[dict[str, str]]]:
    """
    读取公开媒体在后台内容中的实际引用位置。

    输入：asset_id，媒体资产 UUID；session，数据库会话；user，具备 media.read 的用户。
    输出：ApiResponse[list[dict[str, str]]]，返回授权范围内的具体名称、用途和后台入口，不返回实体 UUID、私有 RFQ 关系或对象存储凭据。
    """
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public":
        raise AppException(404, "media_not_found", "公开媒体不存在")

    _actor_roles, actor_permissions = collect_authorization(user)
    permission_set = set(actor_permissions)
    usage_keys: set[tuple[str, uuid.UUID, str]] = set()

    # 关系表和主实体外键都可能登记同一个引用；以 owner 身份和用途去除真重复。
    links = list(
        (
            await session.scalars(
                select(ContentMediaLink).where(ContentMediaLink.media_asset_id == asset.id)
            )
        ).all()
    )
    for link in links:
        spec = _MEDIA_OWNER_SPECS.get(link.owner_type)
        if spec is not None and spec.permission in permission_set:
            usage_keys.add((link.owner_type, link.owner_id, link.role))

    for owner_type, field_name, role in _MEDIA_DIRECT_REFERENCES:
        spec = _MEDIA_OWNER_SPECS[owner_type]
        if spec.permission not in permission_set:
            continue
        media_column = getattr(spec.model, field_name)
        owners = list(
            (await session.scalars(select(spec.model).where(media_column == asset.id))).all()
        )
        usage_keys.update((owner_type, owner.id, role) for owner in owners)

    locales = list((await session.scalars(select(Locale))).all())
    locale_priority = {
        locale.id: 0 if locale.code == "zh-CN" else 1 if locale.code == "en" else 2
        for locale in locales
    }
    usage_rows = [
        row
        for owner_type, owner_id, role in usage_keys
        if (
            row := await _media_usage_row(
                session,
                owner_type=owner_type,
                owner_id=owner_id,
                role=role,
                locale_priority=locale_priority,
            )
        )
        is not None
    ]
    usage_rows.sort(key=lambda row: (row["location"], row["content_name"], row["role"]))
    return success_response(usage_rows)


@router.get("/{asset_id}", response_model=ApiResponse[dict[str, object]])
async def get_media_detail(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("media.read")),
) -> ApiResponse[dict[str, object]]:
    """
    读取公开媒体及其双语元数据，供后台选择记录后稳定回填。

    输入：媒体ID、数据库会话和具备 media.read 权限的用户。
    输出：脱敏媒体详情；不存在或非公开资产返回404。
    """
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public":
        raise AppException(404, "media_not_found", "公开媒体不存在")
    locales = list(
        (await session.scalars(select(Locale).order_by(Locale.sort_order, Locale.code))).all()
    )
    translations = list(
        (
            await session.scalars(
                select(MediaAssetTranslation).where(
                    MediaAssetTranslation.media_asset_id == asset.id
                )
            )
        ).all()
    )
    return success_response(_media_detail_dto(asset, translations, locales))


@router.post("/assets", response_model=ApiResponse[dict[str, object]], status_code=201)
async def upload_public_media(
    file: UploadFile = File(...),
    visibility: str = Form("public"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("media.upload")),
    _csrf: None = Depends(require_csrf),
    storage: MinioStorageAdapter = Depends(get_storage_adapter),
) -> ApiResponse[dict[str, object]]:
    """上传并校验公开媒体；private 资产必须由 RFQ 专用流程创建。"""
    if visibility != "public":
        from app.core.exceptions.handlers import AppException

        raise AppException(403, "private_media_requires_rfq", "私有文件只能通过 RFQ 附件流程上传")
    content = await file.read()
    metadata = validate_upload_bytes(file.filename or "file", file.content_type or "", content)
    from app.core.config import get_settings

    settings = get_settings()
    storage_key = f"public/{uuid.uuid4()}/{metadata['sanitized_filename']}"
    await storage.put_object(
        settings.minio_public_bucket, storage_key, content, str(metadata["mime_type"])
    )
    asset = MediaAsset(
        visibility="public",
        storage_bucket=settings.minio_public_bucket,
        storage_key=storage_key,
        checksum_verified=True,
        malware_scan_status="not_required",
        upload_status="ready",
        uploaded_by=user.id,
        **metadata,
    )
    session.add(asset)
    try:
        await session.flush()
        write_audit_log(
            session,
            action="media.upload",
            target_type="media_asset",
            target_id=str(asset.id),
            user_id=user.id,
            metadata={"sha256": asset.sha256},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete_object(settings.minio_public_bucket, storage_key)
        raise
    return success_response(_public_dto(asset))


@router.patch("/{asset_id}/translations/{locale_id}", response_model=ApiResponse[dict[str, object]])
async def update_media_translation(
    asset_id: uuid.UUID,
    locale_id: uuid.UUID,
    alt_text: str | None = Form(None),
    title: str | None = Form(None),
    caption: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("media.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """更新公开媒体的多语言元数据，图片 Alt 文本由编辑人员显式维护。"""
    asset = await session.get(MediaAsset, asset_id)
    locale = await session.get(Locale, locale_id)
    if asset is None or asset.visibility != "public" or locale is None:
        from app.core.exceptions.handlers import AppException

        raise AppException(404, "media_translation_target_not_found", "媒体或语言不存在")
    translation = await session.scalar(
        select(MediaAssetTranslation).where(
            MediaAssetTranslation.media_asset_id == asset.id,
            MediaAssetTranslation.locale_id == locale.id,
        )
    )
    if translation is None:
        translation = MediaAssetTranslation(media_asset_id=asset.id, locale_id=locale.id)
        session.add(translation)
    translation.alt_text = alt_text
    translation.title = title
    translation.caption = caption
    write_audit_log(
        session,
        action="media.translation_update",
        target_type="media_asset",
        target_id=str(asset.id),
        user_id=user.id,
        metadata={"locale_id": str(locale.id)},
    )
    await session.commit()
    return success_response(
        {
            "media_asset_id": str(asset.id),
            "locale_id": str(locale.id),
            "alt_text": alt_text,
            "title": title,
            "caption": caption,
        }
    )


@router.post(
    "/{asset_id}/refresh-image-metadata",
    response_model=ApiResponse[dict[str, object]],
)
async def refresh_image_metadata(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("media.update")),
    _csrf: None = Depends(require_csrf),
    storage: MinioStorageAdapter = Depends(get_storage_adapter),
) -> ApiResponse[dict[str, object]]:
    """
    从现有对象真实解码并补齐公开图片尺寸，同值请求保持幂等。

    输入：媒体 ID、数据库会话、具备 media.update 的用户、CSRF 校验及对象存储。
    输出：脱敏后的媒体尺寸和 changed 标记；不返回桶、对象键或哈希。
    """
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None:
        raise AppException(404, "media_not_found", "媒体不存在")

    before = {"width": asset.width, "height": asset.height}
    width, height, changed = await refresh_public_image_dimensions(asset, storage=storage)
    if changed:
        write_audit_log(
            session,
            action="media.metadata_refresh",
            target_type="media_asset",
            target_id=str(asset.id),
            user_id=user.id,
            metadata={"before": before, "after": {"width": width, "height": height}},
        )
        await session.commit()
    return success_response(
        {"media_asset_id": str(asset.id), "width": width, "height": height, "changed": changed}
    )


@public_router.get("/{asset_id}", include_in_schema=False)
async def deliver_public_media(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    storage: MinioStorageAdapter = Depends(get_storage_adapter),
) -> Response:
    """安全代理 public-media 对象，浏览器永远看不到 Docker 内部 MinIO 地址。"""
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if (
        asset is None
        or asset.visibility != "public"
        or asset.storage_bucket != "public-media"
        or asset.upload_status != "ready"
    ):
        raise AppException(404, "media_not_found", "公开媒体不存在")
    if not await storage.object_exists(asset.storage_bucket, asset.storage_key):
        raise AppException(404, "media_object_missing", "公开媒体对象不存在")
    return Response(
        await storage.get_object(asset.storage_bucket, asset.storage_key),
        media_type=asset.mime_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )
