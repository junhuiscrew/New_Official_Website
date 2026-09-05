"""统一 SEO/GEO、来源、Redirect 与已发布 URL 事务服务。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.modules.catalog.models import Product, ProductSpecValue, ProductTranslation
from app.modules.company.models import (
    CompanyProfile,
    CompanyProfileTranslation,
    Exhibition,
    ExhibitionTranslation,
    ManufacturingCapability,
    ManufacturingCapabilityTranslation,
)
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
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


async def upsert_seo_document(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    payload: SeoDocumentUpsert,
    actor_id: uuid.UUID | None,
) -> SeoDocument:
    """
    新增或更新统一 SEO 文档并写入审计。

    输入：session、owner 标识、locale、payload 与 actor_id。
    输出：SeoDocument，当前事务中的文档。
    """
    values = payload.model_dump()
    values["canonical_override"] = validate_canonical_override(payload.canonical_override)
    values["schema_override_jsonb"] = validate_schema_override(payload.schema_override_jsonb)
    await _reject_case_private_identity(session, owner_type, owner_id, repr(values))
    document = await session.scalar(
        select(SeoDocument).where(
            SeoDocument.owner_type == owner_type,
            SeoDocument.owner_id == owner_id,
            SeoDocument.locale_id == locale_id,
        )
    )
    if document is None:
        document = SeoDocument(owner_type=owner_type, owner_id=owner_id, locale_id=locale_id, **values)
        session.add(document)
    else:
        for key, value in values.items():
            setattr(document, key, value)
    write_audit_log(session, action="seo.upsert", target_type=owner_type, target_id=str(owner_id), user_id=actor_id, metadata={"locale_id": str(locale_id), "robots_index": payload.robots_index})
    await session.flush()
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
        if reviewer is None or not reviewer.is_real_person_verified:
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
