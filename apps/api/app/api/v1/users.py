"""Users 基础管理 API。"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.core.security.passwords import hash_password
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.users.models import Role, RolePermission, User, UserRole
from app.modules.users.schemas import UserCreate, UserData, UserUpdate
from app.modules.users.service import (
    collect_authorization,
    find_user_with_permissions,
    list_users_with_roles,
    normalize_email,
)

router = APIRouter(prefix="/users", tags=["users"])


def _serialize(user: User) -> UserData:
    """将已预加载角色关系的 User 转换为安全输出。"""
    roles, _permissions = collect_authorization(user)
    return UserData(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=roles,
    )


@router.get("", response_model=ApiResponse[list[UserData]])
async def get_users(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("user.read")),
) -> ApiResponse[list[UserData]]:
    """列出后台用户与角色。"""
    return success_response([_serialize(user) for user in await list_users_with_roles(session)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[UserData])
async def post_user(
    payload: UserCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission("user.create")),
    _role_manager: User = Depends(require_permission("role.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[UserData]:
    """创建用户、校验角色、写入 Argon2id 密码与审计事件。"""
    ip, user_agent = get_client_context(request)
    normalized_email = normalize_email(str(payload.email))
    if await session.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise AppException(409, "user_email_conflict", "用户邮箱已存在")
    roles = list(
        (
            await session.scalars(
                select(Role)
                .where(Role.name.in_(payload.role_names))
                .options(
                    selectinload(Role.permission_links).selectinload(RolePermission.permission)
                )
            )
        ).all()
    )
    if {role.name for role in roles} != set(payload.role_names):
        raise AppException(422, "unknown_role", "包含不存在的角色")
    _actor_roles, actor_permissions = collect_authorization(actor)
    requested_permissions = {
        link.permission.code for role in roles for link in role.permission_links
    }
    if not requested_permissions.issubset(set(actor_permissions)):
        raise AppException(403, "role_permission_ceiling", "不能分配超出当前用户权限范围的角色")

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    for role in roles:
        session.add(UserRole(user_id=user.id, role_id=role.id, assigned_by=actor.id))
        write_audit_log(
            session,
            action="role.assign",
            target_type="user",
            user_id=actor.id,
            target_id=str(user.id),
            ip=ip,
            user_agent=user_agent,
            metadata={"role": role.name},
        )
    write_audit_log(
        session,
        action="user.create",
        target_type="user",
        user_id=actor.id,
        target_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    stored = await find_user_with_permissions(session, user_id=user.id)
    assert stored is not None
    return success_response(_serialize(stored))


@router.patch("/{user_id}", response_model=ApiResponse[UserData])
async def patch_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission("user.update")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[UserData]:
    """更新用户基础信息并记录 user.update。"""
    ip, user_agent = get_client_context(request)
    user = await session.get(User, user_id)
    if user is None:
        raise AppException(404, "user_not_found", "用户不存在")
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    write_audit_log(
        session,
        action="user.update",
        target_type="user",
        user_id=actor.id,
        target_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    stored = await find_user_with_permissions(session, user_id=user.id)
    assert stored is not None
    return success_response(_serialize(stored))


@router.post("/{user_id}/disable", response_model=ApiResponse[UserData])
async def disable_user(
    user_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission("user.disable")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[UserData]:
    """停用用户且禁止用户停用自己。"""
    ip, user_agent = get_client_context(request)
    if actor.id == user_id:
        raise AppException(409, "cannot_disable_self", "不能停用当前登录用户")
    user = await session.get(User, user_id)
    if user is None:
        raise AppException(404, "user_not_found", "用户不存在")
    user.is_active = False
    write_audit_log(
        session,
        action="user.disable",
        target_type="user",
        user_id=actor.id,
        target_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
    await session.commit()
    stored = await find_user_with_permissions(session, user_id=user.id)
    assert stored is not None
    return success_response(_serialize(stored))
