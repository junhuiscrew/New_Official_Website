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
from app.modules.authority.models import AuthorExpert, CaseStudy
from app.modules.content.models import ContentPublication, ContentRoute
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
    validate_geo_visibility(
        direct_answer=payload.direct_answer,
        key_facts=payload.key_facts_json,
        evidence=payload.evidence_json,
        visible_text=payload.visible_source_text,
    )
    await _reject_case_private_identity(session, owner_type, owner_id, repr(payload.model_dump()))
    if payload.reviewer_id:
        reviewer = await session.get(AuthorExpert, payload.reviewer_id)
        if reviewer is None or not reviewer.is_real_person_verified:
            raise AppException(409, "verified_reviewer_required", "GEO reviewer 必须是已核验的真实专家")
    values = payload.model_dump(exclude={"visible_source_text"})
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
