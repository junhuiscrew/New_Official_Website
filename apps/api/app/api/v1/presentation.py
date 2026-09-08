"""首页模块编辑、作者预览与全站模块总览 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.presentation.schemas import (
    HomepageDraftUpdate,
    HomepageExpectedRevision,
)
from app.modules.presentation.services import (
    apply_homepage_layout,
    get_homepage_detail,
    get_homepage_language_detail,
    get_homepage_preview,
    get_site_overview,
    initialize_homepage,
    restore_homepage_draft,
    save_homepage_draft,
)
from app.modules.users.models import User

router = APIRouter(prefix="/presentation", tags=["presentation"])


@router.post(
    "/homepage/initialize",
    response_model=ApiResponse[dict[str, Any]],
)
async def initialize_homepage_endpoint(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入认证会话；输出幂等初始化后的双语首页配置。"""
    detail = await initialize_homepage(session, actor_id=user.id)
    await session.commit()
    return success_response(detail)


@router.get(
    "/homepage",
    response_model=ApiResponse[dict[str, Any]],
)
async def homepage_detail_endpoint(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入认证会话；输出双语首页布局详情。"""
    return success_response(await get_homepage_detail(session))


@router.get(
    "/homepage/{locale_code}",
    response_model=ApiResponse[dict[str, Any]],
)
async def homepage_language_detail_endpoint(
    locale_code: str,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入语言代码和认证会话；输出单语言首页布局详情。"""
    return success_response(
        await get_homepage_language_detail(session, locale_code)
    )


@router.patch(
    "/homepage/{locale_code}/draft",
    response_model=ApiResponse[dict[str, Any]],
)
async def save_homepage_draft_endpoint(
    locale_code: str,
    payload: HomepageDraftUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入完整白名单草稿；输出保存并回读后的单语言详情。"""
    detail = await save_homepage_draft(
        session,
        locale_code=locale_code,
        payload=payload,
        actor_id=user.id,
    )
    await session.commit()
    return success_response(detail)


@router.post(
    "/homepage/{locale_code}/apply",
    response_model=ApiResponse[dict[str, Any]],
)
async def apply_homepage_layout_endpoint(
    locale_code: str,
    payload: HomepageExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.publish")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入草稿修订号；输出应用并回读后的单语言详情。"""
    detail = await apply_homepage_layout(
        session,
        locale_code=locale_code,
        expected_revision=payload.expected_revision,
        actor_id=user.id,
    )
    await session.commit()
    return success_response(detail)


@router.post(
    "/homepage/{locale_code}/restore",
    response_model=ApiResponse[dict[str, Any]],
)
async def restore_homepage_draft_endpoint(
    locale_code: str,
    payload: HomepageExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入草稿修订号；输出从应用版恢复后的新草稿。"""
    detail = await restore_homepage_draft(
        session,
        locale_code=locale_code,
        expected_revision=payload.expected_revision,
        actor_id=user.id,
    )
    await session.commit()
    return success_response(detail)


@router.get(
    "/homepage/{locale_code}/preview",
    response_model=ApiResponse[dict[str, Any]],
)
async def homepage_preview_endpoint(
    locale_code: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """
    返回仅服务端认证可读的完整布局预览。

    输入：语言、响应对象、数据库会话和具备 content.read 的用户。
    输出：ApiResponse，始终禁止共享缓存和索引。
    """
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return success_response(await get_homepage_preview(session, locale_code))


@router.get(
    "/site-overview/{locale_code}",
    response_model=ApiResponse[dict[str, Any]],
)
async def site_overview_endpoint(
    locale_code: str,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入语言和认证会话；输出全站前后台及内容状态总览。"""
    return success_response(await get_site_overview(session, locale_code))

