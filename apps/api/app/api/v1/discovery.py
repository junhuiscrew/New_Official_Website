"""统一 SEO/GEO、来源、Redirect 与 URL Change 管理 API。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.content.models import ContentRoute
from app.modules.content.services.indexable import list_indexable_routes
from app.modules.discovery.health_checks import geo_health_checks, seo_health_checks
from app.modules.discovery.models import GeoDocument, RedirectRule, SeoDocument, SourceCitation
from app.modules.discovery.schemas import (
    GeoDocumentUpsert,
    PublishedUrlChange,
    RedirectRuleCreate,
    SeoDocumentUpsert,
    SourceCitationCreate,
)
from app.modules.discovery.services import (
    change_published_url,
    create_redirect_rule,
    create_source_citation,
    upsert_geo_document,
    upsert_seo_document,
)
from app.modules.users.models import User

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
    return success_response(
        {
            "seo": seo_health_checks(
                seo=seo,
                canonical_path=route.path if route else None,
                in_sitemap=bool(route and route.id in indexed_ids),
                internal_link_count=0,
            ),
            "geo": geo_health_checks(
                geo=geo,
                source_count=len(sources),
                has_first_party_evidence=any(
                    item.source_type in {"internal-first-party", "case-evidence"}
                    for item in sources
                ),
            ),
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
    await _commit(session)
    return success_response(_serialize(document))


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
