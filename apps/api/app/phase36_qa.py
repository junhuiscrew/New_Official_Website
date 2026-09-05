"""Phase 3.6 Remediation 的本地有内容浏览器 QA 数据准备器。"""

from __future__ import annotations

import base64
import os
import re
import uuid
from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.schemas import (
    AuthorExpertCreate,
    AuthorityRelationUpdate,
    AuthorityTranslationInput,
    KnowledgeArticleCreate,
    KnowledgeCategoryCreate,
)
from app.modules.authority.services import (
    create_author_expert,
    create_knowledge_article,
    create_knowledge_category,
    replace_authority_relations,
)
from app.modules.catalog.models import Product
from app.modules.catalog.schemas import (
    CategoryCreate,
    ProductCreate,
    RelationUpdate,
    TranslationInput,
)
from app.modules.catalog.services import create_category, create_product, replace_product_relations
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation
from app.modules.media.services import validate_upload_bytes
from app.modules.media.storage import MinioStorageAdapter

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")
_QA_CONFIRMATION = "LOCAL_QA_ONLY"
# 公开样本图片只用于本地 E2E；字节经过正常签名/SHA256校验并真实写入 MinIO。
_QA_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlI6wAAAABJRU5ErkJggg=="
)


class Phase36QaManifest(BaseModel):
    """可提交的脱敏 QA 清单；不包含凭据、RFQ token 或私有签名 URL。"""

    run_id: str
    product_slug: str
    product_category_slug: str
    knowledge_slug: str
    knowledge_category_slug: str
    missing_translation_slug: str
    public_media_path: str
    product_count: int


def _assert_qa_allowed(run_id: str) -> str:
    """
    验证隔离 QA 命令的环境和显式确认。

    输入：run_id: str，调用方指定的短期运行标识。
    输出：str，校验后的运行标识；不安全时抛出 AppException。
    """
    if get_settings().app_env == "production":
        raise AppException(409, "qa_forbidden_in_production", "QA 数据命令禁止在生产环境运行")
    if os.getenv("PHASE36_QA_CONFIRM") != _QA_CONFIRMATION:
        raise AppException(409, "qa_confirmation_required", "必须显式确认本地 QA 数据准备")
    normalized = run_id.strip().lower()
    if not _RUN_ID.fullmatch(normalized):
        raise AppException(
            422, "qa_run_id_invalid", "QA run-id 必须是 3~40 位小写字母、数字或连字符"
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
        width=1,
        height=1,
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
            return Phase36QaManifest(
                run_id=run_id,
                product_slug=product_slug,
                product_category_slug=category_slug,
                knowledge_slug=knowledge_slug,
                knowledge_category_slug=knowledge_category_slug,
                missing_translation_slug=missing_translation_slug,
                public_media_path=f"qa/phase36/{run_id}/product.png",
                product_count=26,
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
                        "QA Extrusion Screw" if index == 0 else f"QA Product {index:02d}",
                        "QA 挤出机螺杆" if index == 0 else f"QA 产品 {index:02d}",
                    ),
                ),
            )
            if index == 0:
                product.primary_media_id = media.id
            await _publish_many(session, "product", product.id, locales)
            products.append(product)

        # 产品关系由正式服务维护；本地 QA 不创建任何虚构公开材料事实。
        await replace_product_relations(session, products[0].id, RelationUpdate())

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

        return Phase36QaManifest(
            run_id=run_id,
            product_slug=product_slug,
            product_category_slug=category_slug,
            knowledge_slug=knowledge_slug,
            knowledge_category_slug=knowledge_category_slug,
            missing_translation_slug=missing_translation_slug,
            public_media_path=f"qa/phase36/{run_id}/product.png",
            product_count=len(products),
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
