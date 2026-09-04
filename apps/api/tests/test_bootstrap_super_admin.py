"""安全 Bootstrap Super Admin 流程测试。"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.security.passwords import verify_password
from app.modules.audit.models import AuditLog
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users.bootstrap import create_super_admin
from app.modules.users.models import Role, User, UserRole
from app.seed import seed_database


@pytest.fixture
async def bootstrap_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建已 Seed 的 bootstrap 测试数据库。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    yield factory
    await engine.dispose()


async def test_create_super_admin_normalizes_email_hashes_password_and_audits(
    bootstrap_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证 bootstrap 会归一化邮箱、哈希密码、绑定角色并留下审计记录。

    输入：bootstrap_session_factory，测试数据库工厂。

    输出：None；断言持久化用户、角色与审计动作。
    """
    user = await create_super_admin(
        bootstrap_session_factory,
        email="  OWNER@EXAMPLE.COM ",
        password="StrongPassword!2026",
        display_name="Website Owner",
    )

    async with bootstrap_session_factory() as session:
        stored = await session.scalar(select(User).where(User.id == user.id))
        role = await session.scalar(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        actions = (await session.scalars(select(AuditLog.action).order_by(AuditLog.action))).all()

    assert stored.email == "owner@example.com"
    assert stored.password_hash.startswith("$argon2id$")
    assert verify_password("StrongPassword!2026", stored.password_hash)
    assert role.name == "super_admin"
    assert actions == ["role.assign", "user.create"]


async def test_create_super_admin_rejects_weak_password(
    bootstrap_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 bootstrap 不接受弱密码。"""
    with pytest.raises(ValueError, match="密码至少12位"):
        await create_super_admin(
            bootstrap_session_factory,
            email="owner@example.com",
            password="weak",
            display_name="Owner",
        )


async def test_create_super_admin_exits_safely_when_email_exists(
    bootstrap_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证重复 bootstrap 不会覆盖既有管理员密码。"""
    await create_super_admin(
        bootstrap_session_factory,
        email="owner@example.com",
        password="StrongPassword!2026",
        display_name="Owner",
    )
    with pytest.raises(ValueError, match="已存在"):
        await create_super_admin(
            bootstrap_session_factory,
            email="OWNER@example.com",
            password="DifferentPassword!2026",
            display_name="Replacement",
        )
