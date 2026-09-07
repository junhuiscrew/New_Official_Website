"""统一 SEO/GEO、来源、Redirect 与 URL Change 管理 API。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import get_current_user, require_csrf, require_permission
from app.modules.authority.models import AuthorExpert
from app.modules.content.models import ContentRoute
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.discovery.geo import validate_geo_visibility
from app.modules.discovery.health_checks import geo_health_checks, seo_health_checks
from app.modules.discovery.models import GeoDocument, RedirectRule, SeoDocument, SourceCitation
from app.modules.discovery.public_delivery import (
    PUBLIC_HANDLER_OWNER_TYPES,
    get_relation_health,
)
from app.modules.discovery.schemas import (
    GeoDocumentUpsert,
    PublishedUrlChange,
    RedirectRuleCreate,
    SeoDocumentUpsert,
    SitePageSeoUpdate,
    SourceCitationCreate,
)
from app.modules.discovery.services import (
    build_visible_source_text,
    change_published_url,
    create_redirect_rule,
    create_source_citation,
    get_site_page_detail,
    initialize_products_site_page,
    publish_products_site_page,
    resolve_products_site_page_owner_locale,
    review_products_site_page,
    upsert_geo_document,
    upsert_seo_document,
    validate_site_page_seo_owner_locale,
)
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _serialize(entity: Any) -> dict[str, Any]:
    """
    将发现层 ORM 实体转换为 JSON。

    输入：entity，SQLAlchemy 实体。
    输出：dict，全部业务列。
    """
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _commit(session: AsyncSession) -> None:
    """输入请求 session 并提交；输出 None。"""
    await session.commit()


def _require_permissions(user: User, required_permissions: set[str]) -> set[str]:
    """
    校验当前用户同时具备 SitePage 生命周期所需全部权限。

    输入：
        user: User，已加载角色权限的认证用户。
        required_permissions: set[str]，必须同时具备的原子权限。

    输出：
        set[str]，当前用户完整权限集合；缺少任一权限时抛出 403。
    """
    _roles, permissions = collect_authorization(user)
    permission_set = set(permissions)
    if not required_permissions.issubset(permission_set):
        raise AppException(403, "permission_denied", "没有执行此操作的权限")
    return permission_set


@router.post(
    "/site-pages/{system_key}/initialize",
    response_model=ApiResponse[dict[str, Any]],
)
async def initialize_site_page(
    system_key: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """
    初始化唯一 Products SitePage；重复请求只回读，不覆盖现有内容。

    输入：固定页面 key、数据库 session、具备 content.update 的用户与 CSRF。
    输出：ApiResponse，包含页面和两语言完整管理状态。
    """
    await initialize_products_site_page(
        session,
        system_key=system_key,
        actor_id=user.id,
    )
    detail = await get_site_page_detail(
        session,
        system_key=system_key,
        include_seo=False,
    )
    await _commit(session)
    return success_response(detail)


@router.get(
    "/site-pages/{system_key}",
    response_model=ApiResponse[dict[str, Any]],
)
async def get_site_page(
    system_key: str,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("seo.read")),
) -> ApiResponse[dict[str, Any]]:
    """
    按固定 key 返回 SitePage 的双语 SEO 与生命周期详情。

    输入：固定页面 key、数据库 session 与具备 seo.read 的用户。
    输出：ApiResponse，Admin 无需提供任何 UUID。
    """
    return success_response(await get_site_page_detail(session, system_key=system_key))


@router.put(
    "/site-pages/{system_key}/seo/{locale_code}",
    response_model=ApiResponse[dict[str, Any]],
)
@router.patch(
    "/site-pages/{system_key}/seo/{locale_code}",
    response_model=ApiResponse[dict[str, Any]],
)
async def put_site_page_seo(
    system_key: str,
    locale_code: str,
    payload: SitePageSeoUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("seo.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """
    按固定页面 key 与语言代码局部保存统一 SeoDocument。

    输入：页面 key、语言代码、局部 SEO payload、数据库 session、用户与 CSRF。
    输出：ApiResponse，保存后重新回读的完整 SitePage 管理状态。
    """
    page, locale = await resolve_products_site_page_owner_locale(
        session,
        system_key=system_key,
        locale_code=locale_code,
    )
    await upsert_seo_document(
        session,
        "site_page",
        page.id,
        locale.id,
        payload,
        user.id,
        partial=True,
        skip_noop=True,
        allow_site_page=True,
    )
    detail = await get_site_page_detail(session, system_key=system_key)
    await _commit(session)
    return success_response(detail)


@router.post(
    "/site-pages/{system_key}/translations/{locale_code}/review",
    response_model=ApiResponse[dict[str, Any]],
)
async def review_site_page_translation(
    system_key: str,
    locale_code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """
    以 translation.review 与 content.review 双权限审核固定页面语言。

    输入：页面 key、语言代码、数据库 session、认证用户与 CSRF。
    输出：ApiResponse，审核后的完整 SitePage 管理状态。
    """
    permissions = _require_permissions(
        user,
        {"translation.review", "content.review"},
    )
    await review_products_site_page(
        session,
        system_key=system_key,
        locale_code=locale_code,
        actor_permissions=permissions,
        actor_id=user.id,
    )
    detail = await get_site_page_detail(
        session,
        system_key=system_key,
        include_seo=False,
    )
    await _commit(session)
    return success_response(detail)


@router.post(
    "/site-pages/{system_key}/publications/{locale_code}/publish",
    response_model=ApiResponse[dict[str, Any]],
)
async def publish_site_page_publication(
    system_key: str,
    locale_code: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """
    以 translation.publish 与 content.publish 双权限发布固定页面语言。

    输入：页面 key、语言代码、数据库 session、认证用户与 CSRF。
    输出：ApiResponse，发布后的完整 SitePage 管理状态。
    """
    permissions = _require_permissions(
        user,
        {"translation.publish", "content.publish"},
    )
    await publish_products_site_page(
        session,
        system_key=system_key,
        locale_code=locale_code,
        actor_permissions=permissions,
        actor_id=user.id,
    )
    detail = await get_site_page_detail(
        session,
        system_key=system_key,
        include_seo=False,
    )
    await _commit(session)
    return success_response(detail)


@router.get("/health/{owner_type}/{owner_id}/{locale_id}", response_model=ApiResponse[dict[str, Any]])
async def get_discovery_health(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("seo.read")),
) -> ApiResponse[dict[str, Any]]:
    """
    返回可解释的 SEO/GEO 健康问题清单。

    输入：内容 owner、语言与数据库 session。
    输出：ApiResponse，不使用不可解释的排名分数。
    """
    owner_filter = (
        (SeoDocument.owner_type == owner_type)
        & (SeoDocument.owner_id == owner_id)
        & (SeoDocument.locale_id == locale_id)
    )
    seo = await session.scalar(select(SeoDocument).where(owner_filter))
    geo = await session.scalar(
        select(GeoDocument).where(
            GeoDocument.owner_type == owner_type,
            GeoDocument.owner_id == owner_id,
            GeoDocument.locale_id == locale_id,
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
    indexed_ids = {item.id for item in await list_indexable_routes(session)}
    sources = []
    if geo is not None:
        sources = list(
            (
                await session.scalars(
                    select(SourceCitation).where(SourceCitation.geo_document_id == geo.id)
                )
            ).all()
        )
    claims_match = True
    if geo is not None:
        try:
            visible_text = await build_visible_source_text(
                session, owner_type, owner_id, locale_id
            )
            validate_geo_visibility(
                direct_answer=geo.direct_answer,
                key_facts=geo.key_facts_json,
                evidence=geo.evidence_json,
                visible_text=visible_text,
            )
        except AppException:
            claims_match = False
    reviewer_verified = False
    if geo is not None and geo.reviewer_id is not None:
        reviewer = await session.get(AuthorExpert, geo.reviewer_id)
        reviewer_verified = bool(reviewer and reviewer.is_real_person_verified)
    internal_link_count, has_broken_relation_target = await get_relation_health(
        session, owner_type, owner_id, locale_id
    )
    return success_response(
        {
            "seo": seo_health_checks(
                seo=seo,
                canonical_path=route.path if route else None,
                in_sitemap=bool(route and route.id in indexed_ids),
                internal_link_count=internal_link_count,
                has_public_handler=owner_type in PUBLIC_HANDLER_OWNER_TYPES,
                has_broken_relation_target=has_broken_relation_target,
            ),
            "geo": geo_health_checks(
                geo=geo,
                source_count=len(sources),
                has_first_party_evidence=any(
                    item.source_type in {"internal-first-party", "case-evidence"}
                    for item in sources
                ),
                claims_match_server_visible_content=claims_match,
                reviewer_verified=reviewer_verified,
            ),
        }
    )


@router.get(
    "/geo-visible-source/{owner_type}/{owner_id}/{locale_id}",
    response_model=ApiResponse[dict[str, str]],
)
async def get_geo_visible_source(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("geo.read")),
) -> ApiResponse[dict[str, str]]:
    """
    返回由服务端真实内容构造的 GEO 可见事实只读预览。

    输入：内容类型、实体 ID、语言 ID 与数据库 session。
    输出：ApiResponse，包含不可由客户端修改的 visible_source_text。
    """
    return success_response(
        {
            "visible_source_text": await build_visible_source_text(
                session, owner_type, owner_id, locale_id
            )
        }
    )


@router.get("/seo/{owner_type}/{owner_id}/{locale_id}", response_model=ApiResponse[dict[str, Any] | None])
async def get_seo_document(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("seo.read")),
) -> ApiResponse[dict[str, Any] | None]:
    """读取指定内容语言的统一 SEO 文档。"""
    if owner_type == "site_page":
        await validate_site_page_seo_owner_locale(
            session,
            owner_id=owner_id,
            locale_id=locale_id,
        )
    document = await session.scalar(select(SeoDocument).where(SeoDocument.owner_type == owner_type, SeoDocument.owner_id == owner_id, SeoDocument.locale_id == locale_id))
    return success_response(_serialize(document) if document else None)


@router.put("/seo/{owner_type}/{owner_id}/{locale_id}", response_model=ApiResponse[dict[str, Any]])
async def put_seo_document(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    payload: SeoDocumentUpsert,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("seo.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """新增或更新指定内容语言的 SEO 文档。"""
    document = await upsert_seo_document(session, owner_type, owner_id, locale_id, payload, user.id)
    serialized = _serialize(document)
    await _commit(session)
    return success_response(serialized)


@router.get("/geo/{owner_type}/{owner_id}/{locale_id}", response_model=ApiResponse[dict[str, Any] | None])
async def get_geo_document(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("geo.read")),
) -> ApiResponse[dict[str, Any] | None]:
    """读取指定内容语言的统一 GEO 文档。"""
    document = await session.scalar(select(GeoDocument).where(GeoDocument.owner_type == owner_type, GeoDocument.owner_id == owner_id, GeoDocument.locale_id == locale_id))
    return success_response(_serialize(document) if document else None)


@router.put("/geo/{owner_type}/{owner_id}/{locale_id}", response_model=ApiResponse[dict[str, Any]])
async def put_geo_document(
    owner_type: str,
    owner_id: uuid.UUID,
    locale_id: uuid.UUID,
    payload: GeoDocumentUpsert,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("geo.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """新增或更新经过可见事实校验的 GEO 文档。"""
    document = await upsert_geo_document(session, owner_type, owner_id, locale_id, payload, user.id)
    await _commit(session)
    return success_response(_serialize(document))


@router.get("/sources", response_model=ApiResponse[list[dict[str, Any]]])
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("source.read")),
) -> ApiResponse[list[dict[str, Any]]]:
    """按稳定排序读取可核验来源。"""
    rows = list((await session.scalars(select(SourceCitation).order_by(SourceCitation.sort_order, SourceCitation.id))).all())
    return success_response([_serialize(item) for item in rows])


@router.post("/sources", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_source(
    payload: SourceCitationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("source.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """创建可核验来源引用。"""
    source = await create_source_citation(session, payload, user.id)
    await _commit(session)
    return success_response(_serialize(source))


@router.get("/redirects", response_model=ApiResponse[list[dict[str, Any]]])
async def list_redirects(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("redirect.read")),
) -> ApiResponse[list[dict[str, Any]]]:
    """读取 Redirect Manager 规则。"""
    rows = list((await session.scalars(select(RedirectRule).order_by(RedirectRule.source_host, RedirectRule.source_path))).all())
    return success_response([_serialize(item) for item in rows])


@router.post("/redirects", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_redirect(
    payload: RedirectRuleCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """创建通过 self/loop/chain/duplicate/unsafe 校验的 Redirect。"""
    rule = await create_redirect_rule(session, payload, user.id)
    await _commit(session)
    return success_response(_serialize(rule))


@router.post("/url-change", response_model=ApiResponse[dict[str, Any]])
async def post_url_change(
    payload: PublishedUrlChange,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """执行已发布 URL 的单事务迁移。"""
    route = await change_published_url(session, **payload.model_dump(), actor_id=user.id)
    await _commit(session)
    return success_response(_serialize(route))
