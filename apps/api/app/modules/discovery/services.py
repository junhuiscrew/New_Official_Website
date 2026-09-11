"""统一 SEO/GEO、来源、Redirect 与已发布 URL 事务服务。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import (
    FAQ,
    ArticleFAQ,
    AuthorExpert,
    AuthorExpertTranslation,
    CaseStudy,
    CaseStudyTranslation,
    FAQCase,
    FAQProduct,
    FAQTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
)
from app.modules.authority.services import editorial_identity_is_eligible
from app.modules.catalog.models import Product, ProductSpecValue, ProductTranslation
from app.modules.company.models import (
    CompanyProfile,
    CompanyProfileTranslation,
    Exhibition,
    ExhibitionTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.content.enums import PublicationStatus, TranslationState
from app.modules.content.models import (
    ContentPublication,
    ContentRoute,
    SitePage,
    SitePageTranslation,
    TranslationStatus,
)
from app.modules.content.services.publication import transition_publication
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import validate_content_path
from app.modules.discovery.geo import validate_geo_visibility
from app.modules.discovery.models import GeoDocument, RedirectRule, SeoDocument, SourceCitation
from app.modules.discovery.redirects import OFFICIAL_HOST, RedirectEdge, validate_redirect_rule
from app.modules.discovery.schemas import (
    GeoDocumentUpsert,
    RedirectRuleCreate,
    SeoDocumentUpsert,
    SourceCitationCreate,
)
from app.modules.localization.models import Locale

SITE_PAGE_OWNER_TYPE = "site_page"
PRODUCTS_SITE_PAGE_KEY = "products"
PRODUCTS_SITE_PAGE_LANGUAGES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "display_name": "产品",
        "path": "/zh-cn/products/",
    },
    "en": {
        "display_name": "Products",
        "path": "/en/products/",
    },
}
MANAGED_SITE_PAGE_DEFINITIONS: dict[str, dict[str, Any]] = {
    PRODUCTS_SITE_PAGE_KEY: {
        "languages": PRODUCTS_SITE_PAGE_LANGUAGES,
        "public_metadata": False,
        "robots_index": True,
        "robots_follow": True,
    },
    "contact": {
        "languages": {
            "zh-CN": {
                "display_name": "联系我们",
                "path": "/zh-cn/contact/",
            },
            "en": {
                "display_name": "Contact",
                "path": "/en/contact/",
            },
        },
        "public_metadata": True,
        "robots_index": False,
        "robots_follow": False,
    },
    "request-a-quote": {
        "languages": {
            "zh-CN": {
                "display_name": "获取报价",
                "path": "/zh-cn/request-a-quote/",
            },
            "en": {
                "display_name": "Request a Quote",
                "path": "/en/request-a-quote/",
            },
        },
        "public_metadata": True,
        "robots_index": False,
        "robots_follow": True,
    },
}
OFFICIAL_SITE_ORIGIN = "https://junhuiscrewbarrel.com"


def _visible_values(*values: object) -> list[str]:
    """
    把结构化公开字段递归展开为可用于事实匹配的文本片段。

    输入：values，字符串、数字、列表或字典形式的公开字段。
    输出：list[str]，去空后的可见文本片段。
    """
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            result.extend(_visible_values(*value.values()))
        elif isinstance(value, list | tuple | set):
            result.extend(_visible_values(*value))
        elif isinstance(value, bool):
            result.append("true" if value else "false")
        else:
            text = str(value).strip()
            if text:
                result.append(text)
    return result


async def _visible_faq_text(
    session: AsyncSession,
    relation_model: type,
    owner_column: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> list[str]:
    """
    查询页面中实际可见且已发布的 FAQ 文本。

    输入：数据库会话、关系模型、owner 字段、owner ID 与语言 ID。
    输出：list[str]，按展示顺序排列的问题和答案。
    """
    rows = (
        await session.execute(
            select(FAQTranslation.question, FAQTranslation.answer)
            .join(FAQ, FAQ.id == FAQTranslation.faq_id)
            .join(relation_model, relation_model.faq_id == FAQ.id)
            .join(
                TranslationStatus,
                (TranslationStatus.owner_type == "faq")
                & (TranslationStatus.owner_id == FAQ.id)
                & (TranslationStatus.locale_id == FAQTranslation.locale_id),
            )
            .where(
                getattr(relation_model, owner_column) == owner_id,
                FAQTranslation.locale_id == locale_id,
                FAQ.status == "enabled",
                TranslationStatus.status == "published",
            )
            .order_by(relation_model.sort_order, FAQ.sort_order)
        )
    ).all()
    return [part for row in rows for part in (row.question, row.answer)]


async def build_visible_source_text(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> str:
    """
    从数据库真实公开字段构造 GEO 可见事实文本，拒绝客户端自报正文。

    输入：session 异步会话、owner_type 内容类型、owner_id 实体 ID、locale_id 语言 ID。
    输出：str，受支持公开页面可见文本的稳定聚合。
    """
    visible: list[str] = []
    if owner_type == "product":
        product = await session.get(Product, owner_id)
        translation = await session.scalar(
            select(ProductTranslation).where(
                ProductTranslation.product_id == owner_id,
                ProductTranslation.locale_id == locale_id,
            )
        )
        if product is None or translation is None:
            raise AppException(404, "visible_content_not_found", "未找到对应语言的产品可见正文")
        visible.extend(
            _visible_values(
                translation.name,
                translation.short_description,
                translation.description,
                translation.highlights_jsonb,
            )
        )
        specifications = list(
            (
                await session.scalars(
                    select(ProductSpecValue).where(
                        ProductSpecValue.product_id == owner_id,
                        ProductSpecValue.is_public.is_(True),
                    )
                )
            ).all()
        )
        for specification in specifications:
            visible.extend(
                _visible_values(
                    specification.value_text,
                    specification.value_number,
                    specification.value_min,
                    specification.value_max,
                    specification.value_boolean,
                    specification.enum_value,
                    specification.unit_override,
                )
            )
        visible.extend(
            await _visible_faq_text(
                session, FAQProduct, "product_id", owner_id, locale_id
            )
        )
    elif owner_type == "case_study":
        case = await session.get(CaseStudy, owner_id)
        translation = await session.scalar(
            select(CaseStudyTranslation).where(
                CaseStudyTranslation.case_study_id == owner_id,
                CaseStudyTranslation.locale_id == locale_id,
            )
        )
        if case is None or translation is None:
            raise AppException(404, "visible_content_not_found", "未找到对应语言的案例可见正文")
        # 客户名称、地址和 Logo 只有在明确授权时才属于页面可见事实。
        visible.extend(
            _visible_values(
                translation.title,
                translation.summary,
                translation.client_description,
                translation.problem,
                translation.analysis,
                translation.solution,
                translation.result,
                translation.engineer_comment,
                case.country_code,
                case.industry,
                case.machine_brand,
                case.machine_model,
                case.screw_diameter,
                case.filler_percentage,
                case.client_name if case.client_name_public else None,
                case.client_address if case.client_address_public else None,
                str(case.client_logo_media_id)
                if case.client_logo_public and case.client_logo_media_id
                else None,
            )
        )
        visible.extend(
            await _visible_faq_text(
                session, FAQCase, "case_study_id", owner_id, locale_id
            )
        )
    elif owner_type == "knowledge_article":
        article = await session.get(KnowledgeArticle, owner_id)
        translation = await session.scalar(
            select(KnowledgeArticleTranslation).where(
                KnowledgeArticleTranslation.article_id == owner_id,
                KnowledgeArticleTranslation.locale_id == locale_id,
            )
        )
        if article is None or translation is None:
            raise AppException(404, "visible_content_not_found", "未找到对应语言的知识正文")
        visible.extend(
            _visible_values(
                translation.title,
                translation.summary,
                translation.body_markdown,
            )
        )
        visible.extend(
            await _visible_faq_text(
                session, ArticleFAQ, "article_id", owner_id, locale_id
            )
        )
        sources = list(
            (
                await session.scalars(
                    select(SourceCitation).where(
                        SourceCitation.article_id == owner_id
                    )
                )
            ).all()
        )
        for source in sources:
            visible.extend(
                _visible_values(
                    source.title,
                    source.publisher,
                    source.url,
                    source.publication_date,
                )
            )
    elif owner_type == "author_expert":
        expert = await session.get(AuthorExpert, owner_id)
        translation = await session.scalar(
            select(AuthorExpertTranslation).where(
                AuthorExpertTranslation.author_expert_id == owner_id,
                AuthorExpertTranslation.locale_id == locale_id,
            )
        )
        if expert is None or translation is None:
            raise AppException(404, "visible_content_not_found", "未找到对应语言的专家公开资料")
        visible.extend(
            _visible_values(
                translation.name,
                translation.job_title,
                translation.short_bio,
                translation.expertise_json,
                expert.years_experience,
            )
        )
    elif owner_type == "manufacturing_capability":
        capability = await session.get(ManufacturingCapability, owner_id)
        translation = await session.scalar(select(ManufacturingCapabilityTranslation).where(ManufacturingCapabilityTranslation.capability_id == owner_id, ManufacturingCapabilityTranslation.locale_id == locale_id))
        if capability is None or translation is None or capability.status != "enabled":
            raise AppException(404, "visible_content_not_found", "未找到对应语言的制造能力公开正文")
        visible.extend(_visible_values(translation.name, translation.summary, translation.description, translation.key_facts_json, capability.capability_type))
    elif owner_type == "exhibition":
        exhibition = await session.get(Exhibition, owner_id)
        translation = await session.scalar(select(ExhibitionTranslation).where(ExhibitionTranslation.exhibition_id == owner_id, ExhibitionTranslation.locale_id == locale_id))
        if exhibition is None or translation is None or exhibition.status != "enabled":
            raise AppException(404, "visible_content_not_found", "未找到对应语言的展会公开正文")
        visible.extend(_visible_values(translation.title, translation.summary, translation.description, exhibition.event_name, exhibition.country_code, exhibition.city, exhibition.start_date, exhibition.end_date, exhibition.booth_no))
    elif owner_type == "company_profile":
        profile = await session.get(CompanyProfile, owner_id)
        translation = await session.scalar(
            select(CompanyProfileTranslation).where(
                CompanyProfileTranslation.company_profile_id == owner_id,
                CompanyProfileTranslation.locale_id == locale_id,
            )
        )
        if profile is None or translation is None or profile.status != "enabled":
            raise AppException(404, "visible_content_not_found", "未找到对应语言的公司公开正文")
        visible.extend(
            _visible_values(
                translation.company_name,
                translation.short_intro,
                translation.full_intro,
                translation.mission,
                translation.advantages_json,
                profile.founded_year,
                profile.years_experience,
                profile.employee_count_range,
                profile.factory_area_sqm,
                profile.annual_capacity_text,
                profile.export_markets_json,
                profile.public_address,
            )
        )
    else:
        raise AppException(422, "unsupported_geo_owner", "该内容类型不支持 GEO 文档")
    return "\n".join(visible)


def validate_canonical_override(value: str | None) -> str | None:
    """
    校验 canonical override 只能使用正式主域 HTTPS URL。

    输入：value，可选绝对 canonical URL。
    输出：str | None，规范化前的合法值。
    """
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != OFFICIAL_HOST or parsed.fragment:
        raise AppException(409, "unsafe_canonical_override", "canonical override 必须使用正式主域 HTTPS URL")
    return value


def validate_schema_override(value: dict[str, object] | None) -> dict[str, object] | None:
    """
    拒绝无法由当前事实模型证明的商业与评价 Schema 覆盖字段。

    输入：value，可选 Schema override JSON。
    输出：dict | None，安全的原值；发现禁用键时抛出 AppException。
    """
    if value is None:
        return None
    forbidden = {"offers", "offer", "price", "pricecurrency", "review", "reviews", "rating", "aggregaterating", "ratingvalue"}

    def walk(node: object) -> bool:
        """递归检查 JSON 节点是否包含禁用字段。"""
        if isinstance(node, dict):
            return any(key.casefold() in forbidden or walk(child) for key, child in node.items())
        if isinstance(node, list):
            return any(walk(child) for child in node)
        return False

    if walk(value):
        raise AppException(409, "unsafe_schema_override", "Schema override 不允许虚构 Offer、价格、Review 或 Rating")
    return value


async def _reject_case_private_identity(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    public_document_text: str,
) -> None:
    """
    阻止未获许可的客户身份进入 Case SEO/GEO 文档。

    输入：session、owner 标识与即将公开的文档文本。
    输出：None；命中私密名称、地址或 Logo ID 时抛出 AppException。
    """
    if owner_type != "case_study":
        return
    case = await session.get(CaseStudy, owner_id)
    if case is None:
        raise AppException(404, "case_study_not_found", "客户案例不存在")
    protected_values = [
        case.client_name if not case.client_name_public else None,
        case.client_address if not case.client_address_public else None,
        str(case.client_logo_media_id) if case.client_logo_media_id and not case.client_logo_public else None,
    ]
    normalized_document = public_document_text.casefold()
    if any(value and value.casefold() in normalized_document for value in protected_values):
        raise AppException(409, "case_privacy_violation", "未获公开许可的客户身份不能进入 SEO/GEO")


def _serialize_site_page_entity(entity: object) -> dict[str, object]:
    """
    序列化固定页面相关 ORM 实体的业务列。

    输入：
        entity: object，带 SQLAlchemy 表定义的 ORM 实体。

    输出：
        dict[str, object]，可安全返回给 Admin 的字段字典。
    """
    table = entity.__table__
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in table.columns})


def _require_managed_site_page_definition(system_key: str) -> dict[str, Any]:
    """
    将后台固定页面键解析为服务端白名单配置。

    输入：
        system_key: str，调用方提供的稳定页面键。

    输出：
        dict[str, Any]，固定页面名称、路径和 robots 规则；未登记键抛出 404。
    """
    definition = MANAGED_SITE_PAGE_DEFINITIONS.get(system_key)
    if definition is None:
        raise AppException(404, "site_page_not_found", "固定页面不存在")
    return definition


async def _lock_site_page_initialization(
    session: AsyncSession,
    system_key: str,
) -> None:
    """
    在 PostgreSQL 事务内按固定键串行化页面初始化和组合回读。

    输入：
        session: AsyncSession，调用方控制的数据库事务。
        system_key: str，白名单固定页面键。

    输出：
        None；SQLite 等测试数据库依赖唯一约束，不执行数据库专用锁。
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        # 固定 advisory key 使并发初始化先后读取，避免两个请求同时创建半套关联记录。
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"site_page:{system_key}:initialize"},
        )


async def _site_page_locales(
    session: AsyncSession,
    language_definitions: dict[str, dict[str, str]],
) -> dict[str, Locale]:
    """
    读取固定页面要求的全部启用语言。

    输入：
        session: AsyncSession，数据库会话。
        language_definitions: dict，按语言代码登记的固定页面配置。

    输出：
        dict[str, Locale]，按 zh-CN/en 代码索引的语言；缺失或停用时抛出 409。
    """
    locales = {
        locale.code: locale
        for locale in (
            await session.scalars(
                select(Locale).where(Locale.code.in_(language_definitions))
            )
        ).all()
    }
    if set(locales) != set(language_definitions) or any(
        not locale.is_enabled for locale in locales.values()
    ):
        raise AppException(
            409,
            "site_page_conflict",
            "固定页面要求启用的 zh-CN 与 en 语言",
        )
    return locales


async def _site_page_language_records(
    session: AsyncSession,
    *,
    page: SitePage,
    locale: Locale,
    lock: bool = False,
) -> tuple[SitePageTranslation, TranslationStatus, ContentPublication, ContentRoute]:
    """
    读取同一固定页面语言的翻译与完整生命周期记录。

    输入：
        session: AsyncSession，数据库会话。
        page: SitePage，固定页面实体。
        locale: Locale，目标语言。
        lock: bool，写事务校验时是否锁定关联记录。

    输出：
        tuple，依次为页面翻译、翻译状态、发布状态和 canonical Route。
    """
    translation_query = select(SitePageTranslation).where(
            SitePageTranslation.site_page_id == page.id,
            SitePageTranslation.locale_id == locale.id,
        )
    translation_status_query = select(TranslationStatus).where(
            TranslationStatus.owner_type == SITE_PAGE_OWNER_TYPE,
            TranslationStatus.owner_id == page.id,
            TranslationStatus.locale_id == locale.id,
        )
    publication_query = select(ContentPublication).where(
            ContentPublication.owner_type == SITE_PAGE_OWNER_TYPE,
            ContentPublication.owner_id == page.id,
            ContentPublication.locale_id == locale.id,
        )
    route_query = select(ContentRoute).where(
            ContentRoute.owner_type == SITE_PAGE_OWNER_TYPE,
            ContentRoute.owner_id == page.id,
            ContentRoute.locale_id == locale.id,
            ContentRoute.is_canonical.is_(True),
        )
    if lock:
        translation_query = translation_query.with_for_update()
        translation_status_query = translation_status_query.with_for_update()
        publication_query = publication_query.with_for_update()
        route_query = route_query.with_for_update()
    translation = await session.scalar(translation_query)
    translation_status = await session.scalar(translation_status_query)
    publication = await session.scalar(publication_query)
    route = await session.scalar(route_query)
    if any(
        item is None for item in (translation, translation_status, publication, route)
    ):
        raise AppException(
            409,
            "site_page_conflict",
            "固定页面的双语生命周期记录不完整",
        )
    return translation, translation_status, publication, route


async def _validate_managed_site_page(
    session: AsyncSession,
    page: SitePage,
    locales: dict[str, Locale],
    *,
    system_key: str,
    language_definitions: dict[str, dict[str, str]],
    lock: bool = False,
) -> dict[
    str,
    tuple[SitePageTranslation, TranslationStatus, ContentPublication, ContentRoute],
]:
    """
    验证已有固定页面身份、翻译、路由和生命周期保持一致。

    输入：
        session: AsyncSession，数据库会话。
        page: SitePage，待核验页面。
        locales: dict[str, Locale]，要求的双语语言映射。
        system_key: str，服务端登记的页面键。
        language_definitions: dict，服务端登记的双语名称和路径。
        lock: bool，写事务校验时是否锁定双语关联记录。

    输出：
        dict，按语言代码返回已验证记录；发现不一致时抛出 409，绝不覆盖。
    """
    if page.system_key != system_key or page.status != "enabled":
        raise AppException(409, "site_page_conflict", "固定页面身份或状态不一致")
    records: dict[
        str,
        tuple[SitePageTranslation, TranslationStatus, ContentPublication, ContentRoute],
    ] = {}
    for locale_code, config in language_definitions.items():
        language_records = await _site_page_language_records(
            session,
            page=page,
            locale=locales[locale_code],
            lock=lock,
        )
        translation, translation_status, publication, route = language_records
        if translation.display_name != config["display_name"]:
            raise AppException(409, "site_page_conflict", "固定页面语言名称不一致")
        if route.path != config["path"] or not route.is_canonical:
            raise AppException(409, "site_page_conflict", "固定页面 canonical Route 不一致")
        expected_lifecycle = {
            PublicationStatus.DRAFT.value: (TranslationState.DRAFT.value, False, False),
            PublicationStatus.REVIEW.value: (
                TranslationState.HUMAN_REVIEWED.value,
                False,
                False,
            ),
            PublicationStatus.PUBLISHED.value: (
                TranslationState.PUBLISHED.value,
                True,
                True,
            ),
        }.get(publication.status)
        actual_lifecycle = (translation_status.status, route.active, route.indexable)
        if expected_lifecycle is None or actual_lifecycle != expected_lifecycle:
            raise AppException(409, "site_page_conflict", "固定页面生命周期状态不一致")
        records[locale_code] = language_records
    return records


async def initialize_products_site_page(
    session: AsyncSession,
    *,
    system_key: str,
    actor_id: uuid.UUID | None,
) -> SitePage:
    """
    幂等初始化服务端白名单内的 SitePage 及其双语生命周期记录。

    输入：
        session: AsyncSession，调用方控制提交的数据库事务。
        system_key: str，必须为 products、contact 或 request-a-quote。
        actor_id: uuid.UUID | None，执行初始化的认证用户 ID。

    输出：
        SitePage，新建或已存在且一致的固定页面；冲突时不覆盖并抛出 409。
    """
    definition = _require_managed_site_page_definition(system_key)
    language_definitions: dict[str, dict[str, str]] = definition["languages"]
    await _lock_site_page_initialization(session, system_key)
    locales = await _site_page_locales(session, language_definitions)
    page = await session.scalar(
        select(SitePage).where(SitePage.system_key == system_key).with_for_update()
    )
    occupied_routes = list(
        (
            await session.scalars(
                select(ContentRoute)
                .where(
                    ContentRoute.path.in_(
                        config["path"] for config in language_definitions.values()
                    )
                )
                .with_for_update()
            )
        ).all()
    )
    if page is None:
        if occupied_routes:
            raise AppException(
                409,
                "site_page_conflict",
                "固定页面路径已被其他内容占用",
            )
        page = SitePage(system_key=system_key, status="enabled")
        session.add(page)
        await session.flush()
        for locale_code, config in language_definitions.items():
            locale = locales[locale_code]
            session.add_all(
                [
                    SitePageTranslation(
                        site_page_id=page.id,
                        locale_id=locale.id,
                        display_name=config["display_name"],
                    ),
                    TranslationStatus(
                        owner_type=SITE_PAGE_OWNER_TYPE,
                        owner_id=page.id,
                        locale_id=locale.id,
                        status=TranslationState.DRAFT.value,
                        translated_by=actor_id,
                    ),
                    ContentPublication(
                        owner_type=SITE_PAGE_OWNER_TYPE,
                        owner_id=page.id,
                        locale_id=locale.id,
                        status=PublicationStatus.DRAFT.value,
                    ),
                    ContentRoute(
                        owner_type=SITE_PAGE_OWNER_TYPE,
                        owner_id=page.id,
                        locale_id=locale.id,
                        path=config["path"],
                        is_canonical=True,
                        active=False,
                        indexable=False,
                    ),
                ]
            )
        write_audit_log(
            session,
            action="site_page.initialize",
            target_type=SITE_PAGE_OWNER_TYPE,
            target_id=str(page.id),
            user_id=actor_id,
            metadata={"system_key": system_key},
        )
        await session.flush()
        return page

    # 已存在时只接受完整且归属一致的记录；任何人工差异都报告冲突，不做修补。
    if any(
        route.owner_type != SITE_PAGE_OWNER_TYPE or route.owner_id != page.id
        for route in occupied_routes
    ):
        raise AppException(409, "site_page_conflict", "固定页面路径归属不一致")
    await _validate_managed_site_page(
        session,
        page,
        locales,
        system_key=system_key,
        language_definitions=language_definitions,
    )
    return page


async def get_site_page_detail(
    session: AsyncSession,
    *,
    system_key: str,
    include_seo: bool = True,
) -> dict[str, object]:
    """
    按固定 key 返回 Admin 所需的页面、双语 SEO 与生命周期详情。

    输入：
        session: AsyncSession，数据库会话。
        system_key: str，后台可管理的白名单固定页面键。
        include_seo: bool，调用者具备 seo.read 时才返回 SEO 文档。

    输出：
        dict[str, object]，仅包含页面、语言、SEO 和生命周期业务字段。
    """
    definition = _require_managed_site_page_definition(system_key)
    language_definitions: dict[str, dict[str, str]] = definition["languages"]
    # Admin 回读与写入共用事务锁，避免 READ COMMITTED 下拼接出跨事务的双语混合状态。
    await _lock_site_page_initialization(session, system_key)
    page = await session.scalar(
        select(SitePage)
        .where(SitePage.system_key == system_key)
        .with_for_update()
    )
    if page is None:
        raise AppException(404, "site_page_not_initialized", "固定页面尚未初始化")
    locales = await _site_page_locales(session, language_definitions)
    records = await _validate_managed_site_page(
        session,
        page,
        locales,
        system_key=system_key,
        language_definitions=language_definitions,
        lock=True,
    )
    languages: list[dict[str, object]] = []
    for locale_code in language_definitions:
        locale = locales[locale_code]
        translation, translation_status, publication, route = records[locale_code]
        language_detail: dict[str, object] = {
            "locale": _serialize_site_page_entity(locale),
            "translation": _serialize_site_page_entity(translation),
            "translation_status": _serialize_site_page_entity(translation_status),
            "publication": _serialize_site_page_entity(publication),
            "route": _serialize_site_page_entity(route),
        }
        if include_seo:
            seo = await session.scalar(
                select(SeoDocument).where(
                    SeoDocument.owner_type == SITE_PAGE_OWNER_TYPE,
                    SeoDocument.owner_id == page.id,
                    SeoDocument.locale_id == locale.id,
                )
            )
            language_detail["seo"] = (
                _serialize_site_page_entity(seo) if seo is not None else None
            )
        languages.append(language_detail)
    return {
        "page": _serialize_site_page_entity(page),
        "languages": languages,
        "seo_defaults": {
            "robots_index": definition["robots_index"],
            "robots_follow": definition["robots_follow"],
        },
    }


async def get_public_fixed_site_page_metadata(
    session: AsyncSession,
    *,
    system_key: str,
    locale_slug: str,
) -> dict[str, object]:
    """
    返回 Contact/RFQ 固定页面的已发布服务端 SEO 元数据。

    输入：
        session: AsyncSession，数据库会话。
        system_key: str，仅允许配置为公开元数据页的固定键。
        locale_slug: str，请求页面的语言 slug。

    输出：
        dict[str, object]，包含 title、description、canonical、robots 与双语 hreflang；
        页面未完整发布、SEO 不完整或策略不一致时抛出公开 404。
    """
    definition = _require_managed_site_page_definition(system_key)
    if not definition["public_metadata"]:
        raise AppException(404, "public_site_page_not_found", "公开固定页面不存在")
    language_definitions: dict[str, dict[str, str]] = definition["languages"]
    locale = await session.scalar(
        select(Locale).where(
            Locale.slug == locale_slug,
            Locale.is_enabled.is_(True),
        )
    )
    page = await session.scalar(
        select(SitePage).where(
            SitePage.system_key == system_key,
            SitePage.status == "enabled",
        )
    )
    if locale is None or page is None or locale.code not in language_definitions:
        raise AppException(404, "public_site_page_not_found", "公开固定页面不存在")

    locales = await _site_page_locales(session, language_definitions)
    try:
        records = await _validate_managed_site_page(
            session,
            page,
            locales,
            system_key=system_key,
            language_definitions=language_definitions,
        )
    except AppException as exc:
        raise AppException(
            404,
            "public_site_page_not_found",
            "公开固定页面尚未完整发布",
        ) from exc

    seo_by_locale: dict[str, SeoDocument] = {}
    for locale_code, (_translation, translation_status, publication, route) in records.items():
        seo = await session.scalar(
            select(SeoDocument).where(
                SeoDocument.owner_type == SITE_PAGE_OWNER_TYPE,
                SeoDocument.owner_id == page.id,
                SeoDocument.locale_id == locales[locale_code].id,
            )
        )
        expected_canonical = OFFICIAL_SITE_ORIGIN + route.path
        is_publishable_metadata = (
            translation_status.status == TranslationState.PUBLISHED.value
            and publication.status == PublicationStatus.PUBLISHED.value
            and route.active
            and seo is not None
            and bool(seo.seo_title)
            and bool(seo.meta_description)
            and seo.robots_index is definition["robots_index"]
            and seo.robots_follow is definition["robots_follow"]
            and seo.canonical_override in {None, expected_canonical}
        )
        if not is_publishable_metadata or seo is None:
            raise AppException(
                404,
                "public_site_page_not_found",
                "公开固定页面尚未完整发布",
            )
        seo_by_locale[locale_code] = seo

    current_records = records[locale.code]
    _translation, _translation_status, _publication, current_route = current_records
    current_seo = seo_by_locale[locale.code]
    canonical = current_seo.canonical_override or OFFICIAL_SITE_ORIGIN + current_route.path
    hreflang = {
        locale_code: OFFICIAL_SITE_ORIGIN + records[locale_code][3].path
        for locale_code in language_definitions
    }
    default_locale = next(
        (item for item in locales.values() if item.is_default),
        None,
    )
    if default_locale is not None:
        hreflang["x-default"] = (
            OFFICIAL_SITE_ORIGIN + records[default_locale.code][3].path
        )
    return {
        "seo": {
            "title": current_seo.seo_title,
            "description": current_seo.meta_description,
            "canonical": canonical,
            "robots": (
                f"{'index' if current_seo.robots_index else 'noindex'}, "
                f"{'follow' if current_seo.robots_follow else 'nofollow'}"
            ),
            "og_title": current_seo.og_title,
            "og_description": current_seo.og_description,
            "hreflang": hreflang,
        },
        "breadcrumb": [],
        "schema": [],
    }


async def validate_site_page_seo_owner_locale(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
) -> SitePage:
    """
    校验 site_page SEO owner 存在且语言真实属于该页面。

    输入：
        session: AsyncSession，数据库会话。
        owner_id: uuid.UUID，SitePage 主键。
        locale_id: uuid.UUID，SEO 文档语言主键。

    输出：
        SitePage，已验证的页面；不匹配时抛出 409。
    """
    page = await session.get(SitePage, owner_id)
    if page is None:
        raise AppException(
            409,
            "site_page_owner_locale_mismatch",
            "SEO owner 不是有效的固定页面",
        )
    translation_id = await session.scalar(
        select(SitePageTranslation.id).where(
            SitePageTranslation.site_page_id == owner_id,
            SitePageTranslation.locale_id == locale_id,
        )
    )
    if translation_id is None:
        raise AppException(
            409,
            "site_page_owner_locale_mismatch",
            "SEO 语言不属于该固定页面",
        )
    return page


async def _managed_site_page_lifecycle_records(
    session: AsyncSession,
    *,
    system_key: str,
    locale_code: str,
) -> tuple[SitePage, TranslationStatus, ContentPublication, ContentRoute]:
    """
    按固定 key 与语言代码读取 SitePage 生命周期三元组。

    输入：
        session: AsyncSession，数据库会话。
        system_key: str，后台可管理的白名单固定页面键。
        locale_code: str，必须为 zh-CN 或 en。

    输出：
        tuple，页面、翻译状态、发布状态及 canonical Route。
    """
    definition = _require_managed_site_page_definition(system_key)
    language_definitions: dict[str, dict[str, str]] = definition["languages"]
    if locale_code not in language_definitions:
        raise AppException(404, "site_page_locale_not_found", "固定页面语言不存在")
    # 与初始化共用事务锁；先锁定并完整校验双语记录，再允许任何 SEO/生命周期写入。
    await _lock_site_page_initialization(session, system_key)
    locales = await _site_page_locales(session, language_definitions)
    page = await session.scalar(
        select(SitePage)
        .where(SitePage.system_key == system_key)
        .with_for_update()
    )
    locale = locales.get(locale_code)
    if page is None or locale is None:
        raise AppException(404, "site_page_not_initialized", "固定页面尚未初始化")
    records = await _validate_managed_site_page(
        session,
        page,
        locales,
        system_key=system_key,
        language_definitions=language_definitions,
        lock=True,
    )
    _translation, translation_status, publication, route = records[locale_code]
    return page, translation_status, publication, route


async def resolve_products_site_page_owner_locale(
    session: AsyncSession,
    *,
    system_key: str,
    locale_code: str,
) -> tuple[SitePage, Locale]:
    """
    将 Admin 使用的固定 key/语言代码解析为真实页面和 Locale。

    输入：
        session: AsyncSession，数据库会话。
        system_key: str，后台可管理的白名单固定页面键。
        locale_code: str，必须为 zh-CN 或 en。

    输出：
        tuple[SitePage, Locale]，供 SEO 保存使用的真实 UUID owner 与语言。
    """
    page, _translation, _publication, _route = await _managed_site_page_lifecycle_records(
        session,
        system_key=system_key,
        locale_code=locale_code,
    )
    locale = await session.scalar(select(Locale).where(Locale.code == locale_code))
    if locale is None:
        raise AppException(404, "site_page_locale_not_found", "固定页面语言不存在")
    return page, locale


def _require_site_page_permissions(
    actor_permissions: set[str],
    required_permissions: set[str],
) -> None:
    """
    校验 SitePage 生命周期操作要求的全部原子权限。

    输入：
        actor_permissions: set[str]，当前用户完整权限。
        required_permissions: set[str]，本次操作必须同时具备的权限。

    输出：
        None；缺少任一权限时抛出 403。
    """
    if not required_permissions.issubset(actor_permissions):
        raise AppException(403, "permission_denied", "没有执行此操作的权限")


async def review_products_site_page(
    session: AsyncSession,
    *,
    system_key: str,
    locale_code: str,
    actor_permissions: set[str],
    actor_id: uuid.UUID | None,
) -> None:
    """
    审核白名单固定页面翻译并复用统一服务把 Publication 转为 review。

    输入：session、固定页面 key、语言代码、完整权限集合与操作用户 ID。
    输出：None；状态或双重审核权限不满足时抛出 AppException。
    """
    _require_site_page_permissions(
        actor_permissions,
        {"translation.review", "content.review"},
    )
    page, translation, publication, route = await _managed_site_page_lifecycle_records(
        session,
        system_key=system_key,
        locale_code=locale_code,
    )
    if (
        publication.status == PublicationStatus.REVIEW.value
        and translation.status == TranslationState.HUMAN_REVIEWED.value
    ):
        return
    if publication.status != PublicationStatus.DRAFT.value or translation.status not in {
        TranslationState.DRAFT.value,
        TranslationState.MACHINE_TRANSLATED.value,
    }:
        raise AppException(409, "site_page_not_reviewable", "当前固定页面状态不能审核")
    translation.status = TranslationState.HUMAN_REVIEWED.value
    translation.reviewed_by = actor_id
    write_audit_log(
        session,
        action="translation.review",
        target_type=SITE_PAGE_OWNER_TYPE,
        target_id=str(page.id),
        user_id=actor_id,
        metadata={"locale_code": locale_code},
    )
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=PublicationStatus.REVIEW,
        actor_permissions=actor_permissions,
        actor_id=actor_id,
    )


async def publish_products_site_page(
    session: AsyncSession,
    *,
    system_key: str,
    locale_code: str,
    actor_permissions: set[str],
    actor_id: uuid.UUID | None,
) -> None:
    """
    复用统一生命周期服务发布已审核的白名单固定页面语言。

    输入：session、固定页面 key、语言代码、完整权限集合与操作用户 ID。
    输出：None；状态或双重发布权限不满足时抛出 AppException。
    """
    _require_site_page_permissions(
        actor_permissions,
        {"translation.publish", "content.publish"},
    )
    _page, translation, publication, route = await _managed_site_page_lifecycle_records(
        session,
        system_key=system_key,
        locale_code=locale_code,
    )
    if (
        publication.status == PublicationStatus.PUBLISHED.value
        and translation.status == TranslationState.PUBLISHED.value
        and route.active
        and route.indexable
    ):
        return
    if (
        publication.status != PublicationStatus.REVIEW.value
        or translation.status != TranslationState.HUMAN_REVIEWED.value
    ):
        raise AppException(409, "site_page_not_publishable", "固定页面须先完成人工审核")
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=PublicationStatus.PUBLISHED,
        actor_permissions=actor_permissions,
        actor_id=actor_id,
    )


async def upsert_seo_document(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    payload: SeoDocumentUpsert,
    actor_id: uuid.UUID | None,
    *,
    partial: bool = False,
    skip_noop: bool = False,
    allow_site_page: bool = False,
) -> SeoDocument:
    """
    新增或更新统一 SEO 文档并写入审计。

    输入：session、owner 标识、locale、payload、actor_id、更新/no-op 模式及 SitePage 专用授权。
    输出：SeoDocument，当前事务中的文档。
    """
    if owner_type == SITE_PAGE_OWNER_TYPE:
        if not allow_site_page:
            raise AppException(
                409,
                "site_page_fixed_key_required",
                "固定页面 SEO 必须通过按 system key 的专用接口保存",
            )
        await validate_site_page_seo_owner_locale(
            session,
            owner_id=owner_id,
            locale_id=locale_id,
        )
    # 通用 PUT 保持既有完整替换语义；只有固定页面入口显式启用局部更新。
    update_values = payload.model_dump(exclude_unset=partial)
    if "canonical_override" in update_values:
        update_values["canonical_override"] = validate_canonical_override(
            update_values["canonical_override"]
        )
    if "schema_override_jsonb" in update_values:
        update_values["schema_override_jsonb"] = validate_schema_override(
            update_values["schema_override_jsonb"]
        )
    await _reject_case_private_identity(session, owner_type, owner_id, repr(update_values))
    document = await session.scalar(
        select(SeoDocument).where(
            SeoDocument.owner_type == owner_type,
            SeoDocument.owner_id == owner_id,
            SeoDocument.locale_id == locale_id,
        )
    )
    if document is None:
        create_values = payload.model_dump()
        create_values.update(update_values)
        create_values["canonical_override"] = validate_canonical_override(
            create_values["canonical_override"]
        )
        create_values["schema_override_jsonb"] = validate_schema_override(
            create_values["schema_override_jsonb"]
        )
        document = SeoDocument(
            owner_type=owner_type,
            owner_id=owner_id,
            locale_id=locale_id,
            **create_values,
        )
        session.add(document)
    else:
        if skip_noop and all(
            getattr(document, key) == value for key, value in update_values.items()
        ):
            return document
        for key, value in update_values.items():
            setattr(document, key, value)
    # 先取得真实 SEO 文档 ID，再把完整元数据写入独立修订流，避免混入正文 owner 的修订序号。
    await session.flush()
    snapshot = jsonable_encoder(
        {
            "document_id": document.id,
            "owner_type": document.owner_type,
            "owner_id": document.owner_id,
            "locale_id": document.locale_id,
            "seo_title": document.seo_title,
            "meta_description": document.meta_description,
            "canonical_override": document.canonical_override,
            "robots_index": document.robots_index,
            "robots_follow": document.robots_follow,
            "og_title": document.og_title,
            "og_description": document.og_description,
            "og_media_id": document.og_media_id,
            "schema_override_jsonb": document.schema_override_jsonb,
        }
    )
    await store_revision(
        session,
        "seo_document",
        document.id,
        locale_id,
        snapshot,
        actor_id,
    )
    write_audit_log(
        session,
        action="seo.upsert",
        target_type=owner_type,
        target_id=str(owner_id),
        user_id=actor_id,
        metadata={"locale_id": str(locale_id), "robots_index": document.robots_index},
    )
    await session.flush()
    # 部分方言会在同事务内的关联刷新后过期实例；显式刷新保证 API 序列化不触发隐式异步 IO。
    await session.refresh(document)
    return document


async def upsert_geo_document(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    payload: GeoDocumentUpsert,
    actor_id: uuid.UUID | None,
) -> GeoDocument:
    """
    新增或更新与可见正文一致的 GEO 文档。

    输入：session、owner 标识、locale、payload 与 actor_id。
    输出：GeoDocument；隐藏声明或虚构 reviewer 时拒绝。
    """
    await _reject_case_private_identity(
        session, owner_type, owner_id, repr(payload.model_dump())
    )
    visible_source_text = await build_visible_source_text(
        session, owner_type, owner_id, locale_id
    )
    validate_geo_visibility(
        direct_answer=payload.direct_answer,
        key_facts=payload.key_facts_json,
        evidence=payload.evidence_json,
        visible_text=visible_source_text,
    )
    if payload.reviewer_id:
        reviewer = await session.get(AuthorExpert, payload.reviewer_id)
        # 生产仍只接受已核验真人；显式隔离 Demo 可使用不冒充真人的演示编辑组织。
        if reviewer is None or not editorial_identity_is_eligible(
            reviewer, demo_mode=get_settings().demo_mode
        ):
            raise AppException(409, "verified_reviewer_required", "GEO reviewer 必须是已核验的真实专家")
    values = payload.model_dump()
    document = await session.scalar(
        select(GeoDocument).where(
            GeoDocument.owner_type == owner_type,
            GeoDocument.owner_id == owner_id,
            GeoDocument.locale_id == locale_id,
        )
    )
    if document is None:
        document = GeoDocument(owner_type=owner_type, owner_id=owner_id, locale_id=locale_id, **values)
        session.add(document)
    else:
        for key, value in values.items():
            setattr(document, key, value)
    write_audit_log(session, action="geo.upsert", target_type=owner_type, target_id=str(owner_id), user_id=actor_id, metadata={"locale_id": str(locale_id)})
    await session.flush()
    # 复核人查询或同事务关联写入可能使字段过期；显式刷新后再交给 API 序列化。
    await session.refresh(document)
    return document


async def create_source_citation(
    session: AsyncSession,
    payload: SourceCitationCreate,
    actor_id: uuid.UUID | None,
) -> SourceCitation:
    """
    创建可核验来源引用并拒绝占位/伪造 URL。

    输入：session、来源 payload 与 actor_id。
    输出：SourceCitation，新建来源。
    """
    if payload.geo_document_id is None and payload.article_id is None:
        raise AppException(422, "source_owner_required", "来源必须关联 GEO 文档或知识文章")
    parsed = urlparse(payload.url)
    placeholder_hosts = {"example.com", "example.org", "test.invalid", "localhost"}
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.hostname.lower() in placeholder_hosts:
        raise AppException(409, "unverifiable_source", "来源必须使用可核验的真实 URL")
    citation = SourceCitation(**payload.model_dump())
    session.add(citation)
    write_audit_log(session, action="source.create", target_type="source_citation", user_id=actor_id, metadata={"source_type": payload.source_type, "url": payload.url})
    await session.flush()
    return citation


async def create_redirect_rule(
    session: AsyncSession,
    payload: RedirectRuleCreate,
    actor_id: uuid.UUID | None,
) -> RedirectRule:
    """
    创建通过图安全校验的精确 Redirect 规则。

    输入：session、规则 payload 与 actor_id。
    输出：RedirectRule，新建规则。
    """
    existing = list((await session.scalars(select(RedirectRule).where(RedirectRule.enabled.is_(True)))).all())
    normalized_target = validate_redirect_rule(
        payload.source_host,
        payload.source_path,
        payload.target_url,
        [RedirectEdge(item.source_host, item.source_path, item.target_url) for item in existing],
    )
    rule = RedirectRule(
        **payload.model_dump(exclude={"target_url"}),
        target_url=normalized_target,
        created_by=actor_id,
    )
    session.add(rule)
    write_audit_log(session, action="redirect.create", target_type="redirect_rule", user_id=actor_id, metadata={"source_host": payload.source_host, "source_path": payload.source_path, "target_url": normalized_target})
    await session.flush()
    return rule


async def resolve_redirect(
    session: AsyncSession,
    source_host: str,
    source_path: str,
) -> RedirectRule | None:
    """
    解析一条启用的精确重定向并记录命中。

    输入：session、请求来源主机和精确路径。
    输出：RedirectRule | None；没有规则时返回 None，不做模糊匹配。
    """
    normalized_host = source_host.strip().lower().rstrip(".")
    rule = await session.scalar(
        select(RedirectRule).where(
            RedirectRule.source_host == normalized_host,
            RedirectRule.source_path == source_path,
            RedirectRule.enabled.is_(True),
        )
    )
    if rule is not None:
        rule.hit_count += 1
        rule.last_hit_at = datetime.now(UTC)
        await session.flush()
    return rule


async def change_published_url(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    new_path: str,
    actor_id: uuid.UUID | None,
) -> ContentRoute:
    """
    在调用方事务内原子完成已发布 canonical URL 迁移。

    输入：session、owner 标识、locale、new_path 与 actor_id。
    输出：ContentRoute，新 canonical；同时创建永久 Redirect、Revision 与 Audit。
    """
    locale = await session.get(Locale, locale_id)
    if locale is None or not locale.is_enabled:
        raise AppException(409, "locale_disabled", "URL 变更需要启用语言")
    validate_content_path(new_path, locale.slug)
    publication = await session.scalar(
        select(ContentPublication).where(
            ContentPublication.owner_type == owner_type,
            ContentPublication.owner_id == owner_id,
            ContentPublication.locale_id == locale_id,
        ).with_for_update()
    )
    old_route = await session.scalar(
        select(ContentRoute).where(
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == owner_id,
            ContentRoute.locale_id == locale_id,
            ContentRoute.is_canonical.is_(True),
        ).with_for_update()
    )
    if publication is None or publication.status != "published" or old_route is None:
        raise AppException(409, "published_route_required", "只有已发布 canonical 内容可执行 URL Change")
    if await session.scalar(select(ContentRoute.id).where(ContentRoute.path == new_path)) is not None:
        raise AppException(409, "route_conflict", "新 URL 已被占用")
    redirect_payload = RedirectRuleCreate(
        source_host=OFFICIAL_HOST,
        source_path=old_route.path,
        target_url=f"https://{OFFICIAL_HOST}{new_path}",
        status_code=301,
    )
    existing_rules = list((await session.scalars(select(RedirectRule).where(RedirectRule.enabled.is_(True)))).all())
    normalized_target = validate_redirect_rule(
        redirect_payload.source_host,
        redirect_payload.source_path,
        redirect_payload.target_url,
        [RedirectEdge(item.source_host, item.source_path, item.target_url) for item in existing_rules],
    )
    previous_indexable = old_route.indexable
    old_route.is_canonical = False
    old_route.active = False
    old_route.indexable = False
    await session.flush()
    new_route = ContentRoute(
        owner_type=owner_type,
        owner_id=owner_id,
        locale_id=locale_id,
        path=new_path,
        is_canonical=True,
        active=True,
        indexable=previous_indexable,
    )
    session.add(new_route)
    session.add(
        RedirectRule(
            source_host=OFFICIAL_HOST,
            source_path=old_route.path,
            target_url=normalized_target,
            status_code=301,
            enabled=True,
            created_by=actor_id,
            notes="已发布 canonical URL 变更自动创建",
        )
    )
    await session.flush()
    await store_revision(
        session,
        owner_type,
        owner_id,
        locale_id,
        jsonable_encoder({"url_change": {"from": old_route.path, "to": new_path, "status_code": 301}}),
        actor_id,
    )
    write_audit_log(
        session,
        action="content.published_url_change",
        target_type=owner_type,
        target_id=str(owner_id),
        user_id=actor_id,
        metadata={"from": old_route.path, "to": new_path},
    )
    await session.flush()
    return new_route
