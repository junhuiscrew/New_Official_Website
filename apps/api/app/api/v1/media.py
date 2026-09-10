"""Media Library 管理 API：公开资产上传与私有资产隔离。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import AuthorExpert, CaseStudy, KnowledgeArticle
from app.modules.catalog.models import Product, ProductCategory
from app.modules.company.models import (
    Certificate,
    CompanyProfile,
    Equipment,
    Exhibition,
    Honor,
    ManufacturingCapability,
    Patent,
)
from app.modules.demo.models import ContentMediaLink
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.localization.models import Locale
from app.modules.media.models import DownloadResource, MediaAsset, MediaAssetTranslation
from app.modules.media.services import refresh_public_image_dimensions, validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter
from app.modules.users.models import User

router = APIRouter(prefix="/media", tags=["media"])
public_router = APIRouter(prefix="/public/media", tags=["public-media"])


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
    _user: User = Depends(require_permission("media.read")),
) -> ApiResponse[list[dict[str, str]]]:
    """
    读取公开媒体在后台内容中的实际引用位置。

    输入：asset_id，媒体资产 UUID；session，数据库会话；_user，具备 media.read 的用户。
    输出：ApiResponse[list[dict[str, str]]]，仅包含中文位置和用途，不返回实体 UUID、私有 RFQ 关系或对象存储凭据。
    """
    from app.core.exceptions.handlers import AppException

    asset = await session.get(MediaAsset, asset_id)
    if asset is None or asset.visibility != "public":
        raise AppException(404, "media_not_found", "公开媒体不存在")

    usage_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_usage(location: str, role: str) -> None:
        """追加去重后的公开引用位置，避免一项关系重复污染后台展示。"""
        base_location = location.split("（", 1)[0]
        key = (base_location, role)
        if key not in seen:
            seen.add(key)
            usage_rows.append({"location": location, "role": role})

    owner_labels = {
        "company_profile": "企业资料",
        "product_category": "产品分类",
        "product": "产品",
        "material": "材料",
        "technology": "技术工艺",
        "application": "应用场景",
        "solution": "解决方案",
        "case_study": "客户案例",
        "knowledge_article": "知识文章",
        "faq": "常见问题",
        "author_expert": "作者与专家",
        "manufacturing_capability": "制造能力",
        "equipment": "设备",
        "certificate": "证书",
        "patent": "专利",
        "exhibition": "展会",
        "download_resource": "下载资料",
    }
    links = list(
        (
            await session.scalars(
                select(ContentMediaLink).where(ContentMediaLink.media_asset_id == asset.id)
            )
        ).all()
    )
    for link in links:
        add_usage(owner_labels.get(link.owner_type, "公开内容"), link.role)

    download_count = len(
        list(
            (
                await session.scalars(
                    select(DownloadResource).where(DownloadResource.media_asset_id == asset.id)
                )
            ).all()
        )
    )
    if download_count:
        add_usage(f"下载资料（{download_count}条）", "download")

    async def add_fk_usage(model: object, field_name: str, location: str, role: str) -> None:
        """按公开实体的媒体外键补充引用位置，不读取实体正文或私有字段。"""
        column = getattr(model, field_name)
        count = len(
            list(
                (
                    await session.scalars(
                        select(model).where(column == asset.id)  # type: ignore[arg-type]
                    )
                ).all()
            )
        )
        if count:
            add_usage(f"{location}（{count}条）", role)

    for model, field_name, location, role in (
        (CompanyProfile, "logo_media_id", "企业 Logo", "primary"),
        (CompanyProfile, "primary_factory_media_id", "企业工厂主图", "primary"),
        (ProductCategory, "cover_media_id", "产品分类", "cover"),
        (Product, "primary_media_id", "产品", "primary"),
        (CaseStudy, "primary_media_id", "客户案例", "primary"),
        (KnowledgeArticle, "primary_media_id", "知识文章", "primary"),
        (AuthorExpert, "profile_media_id", "作者头像", "profile"),
        (ManufacturingCapability, "primary_media_id", "制造能力", "primary"),
        (Equipment, "primary_media_id", "设备", "primary"),
        (Certificate, "public_file_media_id", "证书文件", "download"),
        (Patent, "public_file_media_id", "专利文件", "download"),
        (Honor, "primary_media_id", "荣誉", "primary"),
        (Exhibition, "primary_media_id", "展会", "primary"),
    ):
        await add_fk_usage(model, field_name, location, role)

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
