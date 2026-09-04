"""Product、Case 与 Knowledge 的只读公开 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.discovery.public_delivery import (
    get_public_case,
    get_public_knowledge,
    get_public_product,
)
from app.modules.discovery.services import resolve_redirect

router = APIRouter(prefix="/public", tags=["public"])


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
