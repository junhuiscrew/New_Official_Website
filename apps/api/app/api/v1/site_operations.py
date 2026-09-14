"""站点品牌、导航页脚与受控重定向的中文后台 API。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.site_operations.schemas import (
    BrandDraftUpdate,
    ExpectedRevision,
    ManagedRedirectInput,
    ManagedRedirectUpdate,
    NavigationDraftUpdate,
)
from app.modules.site_operations.services import (
    apply_brand,
    apply_navigation,
    check_managed_redirect,
    confirm_managed_redirect,
    create_managed_redirect,
    disable_managed_redirect,
    get_brand_detail,
    get_navigation_detail,
    get_redirect_history,
    get_site_operations_detail,
    initialize_site_operations,
    list_managed_redirects,
    managed_redirect_hosts,
    restore_brand_draft,
    restore_navigation_draft,
    save_brand_draft,
    save_navigation_draft,
    update_managed_redirect,
)
from app.modules.users.models import User

router = APIRouter(prefix="/site-operations", tags=["site-operations"])


@router.post("/initialize", response_model=ApiResponse[dict[str, Any]])
async def initialize_endpoint(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入认证写请求；输出幂等初始化后的等值站点运营配置。"""
    detail = await initialize_site_operations(session, actor_id=user.id)
    await session.commit()
    return success_response(detail)


@router.get("", response_model=ApiResponse[dict[str, Any]])
async def detail_endpoint(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入认证会话；输出品牌和双语导航总览。"""
    return success_response(await get_site_operations_detail(session))


@router.get("/brand", response_model=ApiResponse[dict[str, Any]])
async def brand_detail_endpoint(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入认证会话；输出品牌草稿和应用版。"""
    return success_response(await get_brand_detail(session))


@router.patch("/brand/draft", response_model=ApiResponse[dict[str, Any]])
async def brand_draft_endpoint(
    payload: BrandDraftUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入完整中英文品牌草稿；输出提交并重新读取后的详情。"""
    detail = await save_brand_draft(session, payload=payload, actor_id=user.id)
    await session.commit()
    return success_response(detail)


@router.post("/brand/apply", response_model=ApiResponse[dict[str, Any]])
async def brand_apply_endpoint(
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.publish")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入草稿修订号和确认请求；输出已应用品牌详情。"""
    detail = await apply_brand(
        session, expected_revision=payload.expected_revision, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.post("/brand/restore", response_model=ApiResponse[dict[str, Any]])
async def brand_restore_endpoint(
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入草稿修订号；输出从应用版生成的新草稿。"""
    detail = await restore_brand_draft(
        session, expected_revision=payload.expected_revision, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.get("/brand/preview", response_model=ApiResponse[dict[str, Any]])
async def brand_preview_endpoint(
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入认证请求；输出私有无缓存品牌草稿预览数据。"""
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    detail = await get_brand_detail(session)
    return success_response({"brand": detail["draft"], "revision": detail["draft_revision"]})


@router.get("/navigation/{locale_code}", response_model=ApiResponse[dict[str, Any]])
async def navigation_detail_endpoint(
    locale_code: str,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入语言和认证会话；输出导航页脚草稿、应用版和目标选项。"""
    return success_response(await get_navigation_detail(session, locale_code))


@router.patch("/navigation/{locale_code}/draft", response_model=ApiResponse[dict[str, Any]])
async def navigation_draft_endpoint(
    locale_code: str,
    payload: NavigationDraftUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入完整单语言菜单草稿；输出保存并重新读取后的详情。"""
    detail = await save_navigation_draft(
        session, locale_code=locale_code, payload=payload, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.post("/navigation/{locale_code}/apply", response_model=ApiResponse[dict[str, Any]])
async def navigation_apply_endpoint(
    locale_code: str,
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.publish")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入语言和草稿修订号；输出确认应用后的导航详情。"""
    detail = await apply_navigation(
        session,
        locale_code=locale_code,
        expected_revision=payload.expected_revision,
        actor_id=user.id,
    )
    await session.commit()
    return success_response(detail)


@router.post("/navigation/{locale_code}/restore", response_model=ApiResponse[dict[str, Any]])
async def navigation_restore_endpoint(
    locale_code: str,
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("content.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入语言和修订号；输出从应用版恢复的新草稿。"""
    detail = await restore_navigation_draft(
        session,
        locale_code=locale_code,
        expected_revision=payload.expected_revision,
        actor_id=user.id,
    )
    await session.commit()
    return success_response(detail)


@router.get("/navigation/{locale_code}/preview", response_model=ApiResponse[dict[str, Any]])
async def navigation_preview_endpoint(
    locale_code: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("content.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入认证请求；输出私有无缓存导航草稿预览数据。"""
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    detail = await get_navigation_detail(session, locale_code)
    return success_response(
        {
            "locale": detail["locale"],
            "navigation": detail["draft"],
            "revision": detail["draft_revision"],
        }
    )


@router.get("/redirects", response_model=ApiResponse[dict[str, Any]])
async def redirects_endpoint(
    query: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("redirect.read")),
) -> ApiResponse[dict[str, Any]]:
    """输入可选搜索词；输出重定向列表和主机白名单。"""
    return success_response(
        {
            "items": await list_managed_redirects(session, query),
            "source_hosts": managed_redirect_hosts(),
            "official_target_origin": "https://junhuiscrewbarrel.com",
        }
    )


@router.post("/redirects", response_model=ApiResponse[dict[str, Any]])
async def create_redirect_endpoint(
    payload: ManagedRedirectInput,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入受控表单；输出默认停用的新重定向草稿。"""
    detail = await create_managed_redirect(session, payload=payload, actor_id=user.id)
    await session.commit()
    return success_response(detail)


@router.patch("/redirects/{rule_id}", response_model=ApiResponse[dict[str, Any]])
async def update_redirect_endpoint(
    rule_id: uuid.UUID,
    payload: ManagedRedirectUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入规则ID、修订号与表单；输出重新待检查的草稿。"""
    detail = await update_managed_redirect(
        session, rule_id=rule_id, payload=payload, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.post("/redirects/{rule_id}/check", response_model=ApiResponse[dict[str, Any]])
async def check_redirect_endpoint(
    rule_id: uuid.UUID,
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入当前修订号；输出不访问外网的冲突检查结果。"""
    detail = await check_managed_redirect(
        session, rule_id=rule_id, expected_revision=payload.expected_revision, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.post("/redirects/{rule_id}/confirm", response_model=ApiResponse[dict[str, Any]])
async def confirm_redirect_endpoint(
    rule_id: uuid.UUID,
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入已检查修订号和明确确认；输出启用后的真实规则。"""
    detail = await confirm_managed_redirect(
        session, rule_id=rule_id, expected_revision=payload.expected_revision, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.post("/redirects/{rule_id}/disable", response_model=ApiResponse[dict[str, Any]])
async def disable_redirect_endpoint(
    rule_id: uuid.UUID,
    payload: ExpectedRevision,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("redirect.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """输入规则ID和修订号；输出停用但保留审计历史的规则。"""
    detail = await disable_managed_redirect(
        session, rule_id=rule_id, expected_revision=payload.expected_revision, actor_id=user.id
    )
    await session.commit()
    return success_response(detail)


@router.get("/redirects/{rule_id}/history", response_model=ApiResponse[list[dict[str, Any]]])
async def redirect_history_endpoint(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("redirect.read")),
) -> ApiResponse[list[dict[str, Any]]]:
    """输入规则ID；输出脱敏变更历史。"""
    return success_response(await get_redirect_history(session, rule_id))
