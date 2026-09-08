"""固定 Privacy 管理端与公开政策交付 API。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.modules.auth.dependencies import get_current_user, require_csrf
from app.modules.privacy.schemas import (
    PrivacyDraftCreate,
    PrivacyDraftUpdate,
    PrivacyPageStatusUpdate,
    PrivacyPublishAction,
    PrivacyReviewAction,
)
from app.modules.privacy.services import (
    create_privacy_draft,
    get_privacy_admin_state,
    get_public_privacy_policy,
    initialize_privacy_page,
    issue_privacy_context,
    list_privacy_history,
    publish_privacy_draft,
    review_privacy_translation,
    set_privacy_page_status,
    update_privacy_draft,
)
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/privacy", tags=["privacy"])
public_router = APIRouter(prefix="/public/privacy", tags=["public-privacy"])
_PRIVACY_ROBOTS_HEADER = "noindex, follow"

_SUPPORTING_PERMISSIONS: dict[str, tuple[frozenset[str], ...]] = {
    "privacy.edit": (frozenset({"content.update", "translation.update"}),),
    "privacy.review": (
        frozenset({"content.review"}),
        frozenset({"translation.review"}),
    ),
    "privacy.publish": (
        frozenset({"content.publish"}),
        frozenset({"translation.publish"}),
    ),
}


def require_privacy_action(permission_code: str) -> Callable[..., User]:
    """
    创建 Privacy 资源权限与既有内容权限组合依赖。

    输入：permission_code，privacy.read/edit/review/publish/history 之一。
    输出：Callable，权限完整时返回当前用户；否则返回 403。
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        """输入当前用户；输出通过 Privacy 组合授权的同一用户。"""
        _roles, permissions = collect_authorization(user)
        permission_set = set(permissions)
        if permission_code not in permission_set:
            raise AppException(403, "permission_denied", "没有执行 Privacy 操作的权限")
        for accepted_group in _SUPPORTING_PERMISSIONS.get(permission_code, ()):
            if not permission_set.intersection(accepted_group):
                raise AppException(403, "permission_denied", "缺少 Privacy 操作所需内容权限")
        return user

    return dependency


@router.post("/initialize", response_model=ApiResponse[dict[str, object]])
async def initialize_privacy(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.edit")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """
    幂等初始化稳定 Privacy 技术身份与私有生命周期骨架。

    输入：认证请求、数据库会话、具备组合权限的用户与 CSRF。
    输出：ApiResponse，fresh GET-compatible Privacy 管理状态。
    """
    ip, user_agent = get_client_context(request)
    await initialize_privacy_page(
        session,
        actor_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@router.get("", response_model=ApiResponse[dict[str, object]])
async def get_privacy_state(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_privacy_action("privacy.read")),
) -> ApiResponse[dict[str, object]]:
    """输入认证会话；输出 current/draft 完整 Privacy 管理状态。"""
    return success_response(await get_privacy_admin_state(session))


@router.get("/current", response_model=ApiResponse[dict[str, object]])
async def get_privacy_current(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_privacy_action("privacy.read")),
) -> ApiResponse[dict[str, object]]:
    """输入认证会话；输出当前公开版本管理 DTO，不存在时返回 404。"""
    state = await get_privacy_admin_state(session)
    if state["current"] is None:
        raise AppException(404, "privacy_current_not_found", "当前没有隐私政策版本")
    return success_response(state["current"])


@router.get("/draft", response_model=ApiResponse[dict[str, object]])
@router.get("/draft/preview", response_model=ApiResponse[dict[str, object]])
async def get_privacy_draft(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_privacy_action("privacy.read")),
) -> ApiResponse[dict[str, object]]:
    """输入认证会话；输出可重开/预览的当前草稿 DTO，不存在时返回 404。"""
    state = await get_privacy_admin_state(session)
    if state["draft"] is None:
        raise AppException(404, "privacy_draft_not_found", "隐私政策草稿不存在")
    return success_response(state["draft"])


@router.get("/history", response_model=ApiResponse[dict[str, object]])
async def get_privacy_history(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_privacy_action("privacy.history")),
) -> ApiResponse[dict[str, object]]:
    """输入具备 history 权限的会话；输出不含内部 UUID 的不可删除版本历史。"""
    items = await list_privacy_history(session)
    return success_response({"items": items, "total": len(items)})


@router.post("/drafts", response_model=ApiResponse[dict[str, object]])
async def post_privacy_draft(
    payload: PrivacyDraftCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.edit")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """输入固定克隆选项；输出创建草稿后的 fresh Privacy 管理状态。"""
    ip, user_agent = get_client_context(request)
    await create_privacy_draft(
        session,
        actor_id=user.id,
        clone_current=payload.clone_current,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@router.put("/draft", response_model=ApiResponse[dict[str, object]])
async def put_privacy_draft(
    payload: PrivacyDraftUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.edit")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """输入双语正文/生效时间及乐观版本；输出保存后的 fresh 管理状态。"""
    ip, user_agent = get_client_context(request)
    await update_privacy_draft(
        session,
        payload,
        actor_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@router.post("/draft/review/{locale}", response_model=ApiResponse[dict[str, object]])
async def post_privacy_review(
    locale: str,
    payload: PrivacyReviewAction,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.review")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """输入固定语言与真实审核用户；输出审核后的 fresh Privacy 管理状态。"""
    ip, user_agent = get_client_context(request)
    await review_privacy_translation(
        session,
        locale=locale,
        actor_id=user.id,
        expected_version_label=payload.expected_version_label,
        expected_revision=payload.expected_revision,
        expected_content_hash=payload.expected_content_hash,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@router.post("/draft/publish", response_model=ApiResponse[dict[str, object]])
async def post_privacy_publish(
    payload: PrivacyPublishAction,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.publish")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """输入具备三项发布权限的真实用户；输出原子切换后的 fresh 管理状态。"""
    ip, user_agent = get_client_context(request)
    await publish_privacy_draft(
        session,
        actor_id=user.id,
        expected_version_label=payload.expected_version_label,
        expected_revision=payload.expected_revision,
        expected_content_hashes=payload.expected_content_hashes,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@router.patch("/status", response_model=ApiResponse[dict[str, object]])
async def patch_privacy_status(
    payload: PrivacyPageStatusUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_privacy_action("privacy.publish")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, object]]:
    """输入 enabled/disabled；输出启停后的 fresh Privacy 管理状态。"""
    ip, user_agent = get_client_context(request)
    await set_privacy_page_status(
        session,
        status=payload.status,
        actor_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    return success_response(await get_privacy_admin_state(session))


@public_router.get("/{locale_slug}", response_model=ApiResponse[dict[str, object]])
async def public_privacy_policy(
    locale_slug: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, object]]:
    """输入固定语言 slug；输出唯一 current 双语合格政策，并始终标记 noindex。"""
    try:
        policy = await get_public_privacy_policy(session, locale_slug)
    except AppException as exc:
        # 禁用/切换期间的错误响应同样强制重验证，避免缓存旧的可用性结论。
        exc.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        exc.headers["X-Robots-Tag"] = _PRIVACY_ROBOTS_HEADER
        raise
    response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    response.headers["X-Robots-Tag"] = _PRIVACY_ROBOTS_HEADER
    return success_response(policy)


@public_router.get(
    "/{locale_slug}/context/{version_label}",
    response_model=ApiResponse[dict[str, str]],
)
async def public_privacy_context(
    locale_slug: str,
    version_label: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, str]]:
    """输入语言与已展示公开标签；输出 no-store 的短期 RFQ 政策上下文。"""
    try:
        context = await issue_privacy_context(
            session,
            locale=locale_slug,
            version_label=version_label,
        )
    except AppException as exc:
        # consent context 的成功和失败都不得落入浏览器或中间缓存。
        exc.headers["Cache-Control"] = "no-store"
        exc.headers["Pragma"] = "no-cache"
        exc.headers["X-Robots-Tag"] = _PRIVACY_ROBOTS_HEADER
        raise
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Robots-Tag"] = _PRIVACY_ROBOTS_HEADER
    return success_response(context)
