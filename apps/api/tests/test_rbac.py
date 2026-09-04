"""服务端 RBAC dependency 行为测试。"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.core.exceptions.handlers import AppException
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.auth.dependencies import require_permission
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users.models import Role, User, UserRole
from app.modules.users.service import find_user_with_permissions
from app.seed import seed_database


@pytest.fixture
async def rbac_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建已 Seed 的 RBAC 隔离数据库并在测试后释放。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    yield factory
    await engine.dispose()


async def _user_for_role(session_factory: async_sessionmaker[AsyncSession], role_name: str) -> User:
    """
    创建一个绑定指定系统角色的测试用户并加载授权图。

    输入：session_factory 与 role_name。

    输出：User，已预加载角色权限。
    """
    async with session_factory() as session, session.begin():
        role = await session.scalar(select(Role).where(Role.name == role_name))
        user = User(
            email=f"{role_name}@example.com",
            password_hash="not-used-in-rbac-test",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
    async with session_factory() as session:
        loaded_user = await find_user_with_permissions(session, user_id=user.id)
    assert loaded_user is not None
    return loaded_user


async def test_super_admin_passes_any_seeded_permission(
    rbac_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证 super_admin 通过高权限 SEO 检查。"""
    user = await _user_for_role(rbac_session_factory, "super_admin")
    dependency = require_permission("seo.update")
    assert await dependency(user) is user


@pytest.mark.parametrize(
    ("role_name", "permission_code"),
    [
        ("sales", "seo.update"),
        ("media_manager", "rfq.download_private_file"),
    ],
)
async def test_restricted_roles_receive_403(
    rbac_session_factory: async_sessionmaker[AsyncSession],
    role_name: str,
    permission_code: str,
) -> None:
    """验证销售和媒体角色不能越过各自业务边界。"""
    user = await _user_for_role(rbac_session_factory, role_name)
    dependency = require_permission(permission_code)
    with pytest.raises(AppException) as raised:
        await dependency(user)
    assert raised.value.status_code == 403
