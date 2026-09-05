"""结构化核心内容与 Authority Content 的只读公开 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.company.services import (
    get_public_company_profile,
    get_public_trust,
    list_public_trust,
)
from app.modules.discovery.public_collections import (
    get_public_home,
    get_public_navigation,
)
from app.modules.discovery.public_delivery import (
    get_public_case,
    get_public_catalog_entity,
    get_public_expert,
    get_public_knowledge,
    get_public_product,
)
from app.modules.discovery.services import resolve_redirect
from app.modules.media.services import list_public_downloads
from app.modules.media.storage import MinioStorageAdapter, get_storage_adapter

router = APIRouter(prefix="/public", tags=["public"])

PUBLIC_COLLECTION_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"


@router.get("/navigation/{locale_slug}", response_model=ApiResponse[dict[str, Any]])
async def public_navigation(
    locale_slug: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回全局导航和 Footer 所需的严格发布内容。

    输入：语言 slug、HTTP 响应与数据库 session。
    输出：ApiResponse，包含 canonical Link DTO 和真实公司联系方式。
    """
    response.headers["Cache-Control"] = PUBLIC_COLLECTION_CACHE_CONTROL
    return success_response(await get_public_navigation(session, locale_slug))


@router.get("/home/{locale_slug}", response_model=ApiResponse[dict[str, Any]])
async def public_home(
    locale_slug: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回首页单次 SSR 请求所需的严格发布聚合数据。

    输入：语言 slug、HTTP 响应与数据库 session。
    输出：ApiResponse，缺失内容族保持空数组或 None。
    """
    response.headers["Cache-Control"] = PUBLIC_COLLECTION_CACHE_CONTROL
    return success_response(await get_public_home(session, locale_slug))


@router.get("/downloads/{locale_slug}", response_model=ApiResponse[list[dict[str, Any]]])
async def public_downloads(
    locale_slug: str,
    session: AsyncSession = Depends(get_session),
    storage: MinioStorageAdapter = Depends(get_storage_adapter),
) -> ApiResponse[list[dict[str, Any]]]:
    """返回 public-media 中已就绪的公开下载资源，不暴露私有 RFQ 文件。"""
    return success_response(
        await list_public_downloads(session, locale_slug, storage=storage)
    )


@router.get("/company-profile/{locale_slug}", response_model=ApiResponse[dict[str, Any]])
async def public_company_profile(locale_slug: str, session: AsyncSession = Depends(get_session)) -> ApiResponse[dict[str, Any]]:
    """返回由真实 Company Profile 驱动的 About/Organization 数据。"""
    return success_response(await get_public_company_profile(session, locale_slug))


@router.get("/redirects/resolve", response_class=RedirectResponse, include_in_schema=False)
async def public_redirect(
    host: str = Query(min_length=1, max_length=255),
    path: str = Query(min_length=1, max_length=1000),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """
    按精确 host/path 执行 Redirect Manager 规则。

    输入：host、path 与数据库 session。
    输出：RedirectResponse；不存在规则时以公开 404 结束。
    """
    from app.core.exceptions.handlers import AppException

    rule = await resolve_redirect(session, host, path)
    if rule is None:
        raise AppException(404, "redirect_not_found", "重定向规则不存在")
    await session.commit()
    return RedirectResponse(rule.target_url, status_code=rule.status_code)


@router.get("/products/{locale_slug}/{category_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_product(
    locale_slug: str,
    category_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回严格已发布 Product DTO。

    输入：语言、分类、产品 slug 与数据库 session。
    输出：ApiResponse，供 Nuxt SSR 使用的结构化产品数据。
    """
    return success_response(await get_public_product(session, locale_slug, category_slug, slug))


@router.get("/case-studies/{locale_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_case_study(
    locale_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回隐私白名单保护的严格已发布 Case DTO。

    输入：语言、案例 slug 与数据库 session。
    输出：ApiResponse，供 Nuxt SSR 使用的客户案例数据。
    """
    return success_response(await get_public_case(session, locale_slug, slug))


@router.get("/knowledge/{locale_slug}/{category_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_knowledge_article(
    locale_slug: str,
    category_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回带真实作者与来源的严格已发布 Knowledge DTO。

    输入：语言、分类、文章 slug 与数据库 session。
    输出：ApiResponse，供 Nuxt SSR 使用的知识文章数据。
    """
    return success_response(await get_public_knowledge(session, locale_slug, category_slug, slug))


@router.get("/experts/{locale_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_expert(
    locale_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回已核验真实人物的严格公开 Expert DTO。

    输入：语言、人物 slug 与数据库 session。
    输出：ApiResponse，供 Nuxt Expert SSR 使用的人物与 Person Schema 数据。
    """
    return success_response(await get_public_expert(session, locale_slug, slug))


@router.get("/trust/{resource}/{locale_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_trust(resource: str, locale_slug: str, slug: str, session: AsyncSession = Depends(get_session)) -> ApiResponse[dict[str, Any]]:
    """返回公开 Company Trust DTO；设备不提供独立页面。"""
    owner_types = {"capabilities": "manufacturing_capability", "certificates": "certificate", "patents": "patent", "honors": "honor", "exhibitions": "exhibition"}
    owner_type = owner_types.get(resource)
    if owner_type is None:
        from app.core.exceptions.handlers import AppException
        raise AppException(404, "public_content_not_found", "公开 Trust 内容不存在")
    return success_response(await get_public_trust(session, owner_type, locale_slug, slug))


@router.get("/trust/{resource}/{locale_slug}", response_model=ApiResponse[list[dict[str, Any]]])
async def public_trust_index(resource: str, locale_slug: str, session: AsyncSession = Depends(get_session)) -> ApiResponse[list[dict[str, Any]]]:
    """输入 Trust 资源与语言；输出真实、已发布且符合索引门槛的列表。"""
    return success_response(await list_public_trust(session, resource, locale_slug))


@router.get(
    "/product-categories/{locale_slug}/{slug}",
    response_model=ApiResponse[dict[str, Any]],
)
async def public_product_category(
    locale_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """输入语言和分类 slug，输出 Sitemap 可解析的公开产品分类 DTO。"""
    return success_response(
        await get_public_catalog_entity(
            session, "product_category", locale_slug, slug
        )
    )


@router.get("/{resource}/{locale_slug}/{slug}", response_model=ApiResponse[dict[str, Any]])
async def public_catalog_entity(
    resource: str,
    locale_slug: str,
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    """
    返回 Material、Technology、Application 或 Solution 最小公开 DTO。

    输入：资源复数名、语言、实体 slug 与数据库 session。
    输出：ApiResponse；不支持的资源按公开 404 处理。
    """
    owner_types = {
        "materials": "material",
        "technologies": "technology",
        "applications": "application",
        "solutions": "solution",
    }
    owner_type = owner_types.get(resource)
    if owner_type is None:
        from app.core.exceptions.handlers import AppException

        raise AppException(404, "public_content_not_found", "公开内容不存在")
    return success_response(
        await get_public_catalog_entity(session, owner_type, locale_slug, slug)
    )
