"""安全创建首个 Super Admin 的独立服务。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security.passwords import hash_password
from app.modules.audit.service import write_audit_log
from app.modules.users.models import Role, User, UserRole
from app.modules.users.service import normalize_email


async def create_super_admin(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """
    创建唯一邮箱用户并绑定已有 super_admin 系统角色。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，数据库工厂。
        email: str，管理员邮箱。
        password: str，满足强度规则的明文密码。
        display_name: str，管理员显示名称。

    输出：User，新创建且密码已哈希的管理员用户。
    """
    normalized_email = normalize_email(email)
    password_hash = hash_password(password)
    async with session_factory() as session, session.begin():
        existing = await session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            raise ValueError("该管理员邮箱已存在，未执行覆盖")
        role = await session.scalar(select(Role).where(Role.name == "super_admin"))
        if role is None:
            raise ValueError("super_admin 角色不存在，请先执行 seed")

        user = User(
            email=normalized_email,
            password_hash=password_hash,
            display_name=display_name.strip(),
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id, assigned_by=None))
        write_audit_log(
            session,
            action="user.create",
            target_type="user",
            user_id=user.id,
            target_id=str(user.id),
            metadata={"source": "bootstrap"},
        )
        write_audit_log(
            session,
            action="role.assign",
            target_type="user",
            user_id=user.id,
            target_id=str(user.id),
            metadata={"role": "super_admin", "source": "bootstrap"},
        )
    return user
