"""用户查询、邮箱归一化与授权集合服务。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.users.models import Role, RolePermission, User, UserRole


def normalize_email(email: str) -> str:
    """
    按认证唯一性规则归一化邮箱。

    输入：
        email: str，外部提交邮箱。

    输出：str，去除首尾空白并转为小写的邮箱。
    """
    return email.strip().lower()


async def find_user_with_permissions(
    session: AsyncSession,
    *,
    email: str | None = None,
    user_id: uuid.UUID | None = None,
) -> User | None:
    """
    按邮箱或ID加载用户及完整角色权限图。

    输入：
        session: AsyncSession，数据库 session。
        email: str | None，待归一化查询邮箱。
        user_id: uuid.UUID | None，用户主键。

    输出：User | None，包含已预加载授权关系的用户。
    """
    statement = select(User).options(
        selectinload(User.role_links)
        .selectinload(UserRole.role)
        .selectinload(Role.permission_links)
        .selectinload(RolePermission.permission)
    )
    if email is not None:
        statement = statement.where(User.email == normalize_email(email))
    elif user_id is not None:
        statement = statement.where(User.id == user_id)
    else:
        raise ValueError("email 和 user_id 必须提供一个")
    return await session.scalar(statement)


def collect_authorization(user: User) -> tuple[list[str], list[str]]:
    """
    从预加载关系中提取稳定排序的角色和权限代码。

    输入：
        user: User，已预加载 role_links 的用户。

    输出：tuple[list[str], list[str]]，角色名与去重权限代码。
    """
    roles = sorted({link.role.name for link in user.role_links})
    permissions = sorted(
        {
            permission_link.permission.code
            for role_link in user.role_links
            for permission_link in role_link.role.permission_links
        }
    )
    return roles, permissions


async def list_users_with_roles(session: AsyncSession) -> list[User]:
    """
    列出全部后台用户并预加载角色权限。

    输入：session，数据库 session。

    输出：list[User]，按邮箱稳定排序的用户集合。
    """
    statement = (
        select(User)
        .options(
            selectinload(User.role_links)
            .selectinload(UserRole.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission)
        )
        .order_by(User.email)
    )
    return list((await session.scalars(statement)).all())
