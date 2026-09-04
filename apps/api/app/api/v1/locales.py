"""Locale 管理 API；所有写操作由服务端权限依赖保护。"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.localization.schemas import LocaleCreate, LocaleData, LocaleUpdate
from app.modules.localization.service import (
    create_locale,
    list_locales,
    set_default_locale,
    update_locale,
)
from app.modules.users.models import User

router = APIRouter(prefix="/locales", tags=["locales"])


def _serialize(locale) -> LocaleData:
    """将 Locale ORM 实体转换为字符串 UUID 的 API 输出。"""
    return LocaleData(
        id=str(locale.id),
        code=locale.code,
        slug=locale.slug,
        name=locale.name,
        native_name=locale.native_name,
        is_default=locale.is_default,
        is_enabled=locale.is_enabled,
        sort_order=locale.sort_order,
    )


@router.get("", response_model=ApiResponse[list[LocaleData]])
async def get_locales(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("locale.read")),
) -> ApiResponse[list[LocaleData]]:
    """返回 Admin 可见的全部语言配置。"""
    return success_response([_serialize(locale) for locale in await list_locales(session)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[LocaleData])
async def post_locale(
    payload: LocaleCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("locale.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[LocaleData]:
    """创建语言配置并记录 locale.change。"""
    ip, user_agent = get_client_context(request)
    locale = await create_locale(session, payload)
    write_audit_log(
        session,
        action="locale.change",
        target_type="locale",
        user_id=user.id,
        target_id=str(locale.id),
        ip=ip,
        user_agent=user_agent,
        metadata={"operation": "create"},
    )
    await session.commit()
    return success_response(_serialize(locale))


@router.patch("/{locale_id}", response_model=ApiResponse[LocaleData])
async def patch_locale(
    locale_id: uuid.UUID,
    payload: LocaleUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("locale.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[LocaleData]:
    """更新、启停或排序语言配置并写入审计。"""
    ip, user_agent = get_client_context(request)
    locale = await update_locale(session, locale_id, payload)
    write_audit_log(
        session,
        action="locale.change",
        target_type="locale",
        user_id=user.id,
        target_id=str(locale.id),
        ip=ip,
        user_agent=user_agent,
        metadata={"operation": "update", "fields": sorted(payload.model_fields_set)},
    )
    await session.commit()
    return success_response(_serialize(locale))


@router.post("/{locale_id}/set-default", response_model=ApiResponse[LocaleData])
async def post_default_locale(
    locale_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("locale.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[LocaleData]:
    """事务化切换全站默认语言并写入审计。"""
    ip, user_agent = get_client_context(request)
    locale = await set_default_locale(session, locale_id)
    write_audit_log(
        session,
        action="locale.change",
        target_type="locale",
        user_id=user.id,
        target_id=str(locale.id),
        ip=ip,
        user_agent=user_agent,
        metadata={"operation": "set_default"},
    )
    await session.commit()
    return success_response(_serialize(locale))
