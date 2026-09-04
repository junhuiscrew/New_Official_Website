"""Roles 与 Permissions 查看和显式维护 API。"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.request_context import get_client_context
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import require_csrf, require_permission
from app.modules.users.models import Permission, Role, RolePermission, User
from app.modules.users.schemas import RoleData, RolePermissionUpdate
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/rbac", tags=["rbac"])


def _serialize_role(role: Role) -> RoleData:
    """将预加载权限关系的 Role 转换为矩阵输出。"""
    return RoleData(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=sorted(link.permission.code for link in role.permission_links),
    )


async def _load_role(session: AsyncSession, role_id: uuid.UUID) -> Role | None:
    """按主键加载角色和权限关系。"""
    return await session.scalar(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.permission_links).selectinload(RolePermission.permission))
        .execution_options(populate_existing=True)
    )


@router.get("/roles", response_model=ApiResponse[list[RoleData]])
async def get_roles(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_permission("role.read")),
) -> ApiResponse[list[RoleData]]:
    """返回 8 个系统角色及当前权限映射。"""
    roles = (
        await session.scalars(
            select(Role)
            .options(selectinload(Role.permission_links).selectinload(RolePermission.permission))
            .order_by(Role.name)
        )
    ).all()
    return success_response([_serialize_role(role) for role in roles])


@router.put("/roles/{role_id}/permissions", response_model=ApiResponse[RoleData])
async def put_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_permission("role.manage")),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[RoleData]:
    """按明确管理员请求替换角色权限并记录 permission.change。"""
    ip, user_agent = get_client_context(request)
    role = await session.get(Role, role_id)
    if role is None:
        raise AppException(404, "role_not_found", "角色不存在")
    permissions = list(
        (
            await session.scalars(
                select(Permission).where(Permission.code.in_(payload.permission_codes))
            )
        ).all()
    )
    if {permission.code for permission in permissions} != set(payload.permission_codes):
        raise AppException(422, "unknown_permission", "包含不存在的权限")
    _actor_roles, actor_permissions = collect_authorization(actor)
    if not set(payload.permission_codes).issubset(set(actor_permissions)):
        raise AppException(403, "permission_grant_ceiling", "不能授予超出当前用户权限范围的权限")
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    session.add_all(
        [RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions]
    )
    write_audit_log(
        session,
        action="permission.change",
        target_type="role",
        user_id=actor.id,
        target_id=str(role.id),
        ip=ip,
        user_agent=user_agent,
        metadata={"permission_codes": sorted(payload.permission_codes)},
    )
    await session.commit()
    stored = await _load_role(session, role.id)
    assert stored is not None
    return success_response(_serialize_role(stored))
