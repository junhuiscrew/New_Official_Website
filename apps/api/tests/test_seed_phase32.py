"""Permission 与 8 角色映射 Seed 测试。"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.localization import models as localization_models  # noqa: F401
from app.modules.users.models import Permission, Role, RolePermission
from app.seed import PERMISSIONS, ROLE_PERMISSION_MATRIX, seed_database


@pytest.fixture
async def seed_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """
    创建可重复执行 Seed 的隔离数据库。

    输入：sqlite_database_url，测试数据库 URL。

    输出：AsyncIterator[async_sessionmaker[AsyncSession]]，测试 session factory。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


async def test_permission_and_role_matrix_seed_is_idempotent(
    seed_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证结构化内容权限与 8 个角色映射重复 Seed 不产生重复记录。

    输入：seed_session_factory，测试数据库工厂。

    输出：None；断言权限、映射数量与关键隔离边界。
    """
    await seed_database(seed_session_factory)
    await seed_database(seed_session_factory)

    async with seed_session_factory() as session:
        permission_count = await session.scalar(select(func.count()).select_from(Permission))
        roles = (await session.scalars(select(Role))).all()
        role_by_name = {role.name: role for role in roles}
        permission_by_code = {
            permission.code: permission
            for permission in (await session.scalars(select(Permission))).all()
        }
        pairs = set(
            (
                await session.execute(select(RolePermission.role_id, RolePermission.permission_id))
            ).all()
        )

    assert permission_count == len(PERMISSIONS)
    assert set(role_by_name) == set(ROLE_PERMISSION_MATRIX)
    assert len(pairs) == sum(len(codes) for codes in ROLE_PERMISSION_MATRIX.values())
    assert (role_by_name["sales"].id, permission_by_code["seo.update"].id) not in pairs
    assert (
        role_by_name["media_manager"].id,
        permission_by_code["rfq.download_private_file"].id,
    ) not in pairs
    assert all(
        (role_by_name["super_admin"].id, permission.id) in pairs
        for permission in permission_by_code.values()
    )


async def test_seed_preserves_custom_permission_mapping(
    seed_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    验证系统 Seed 只补充映射，不删除管理员自定义权限关系。

    输入：seed_session_factory，测试数据库工厂。

    输出：None；断言自定义映射重复 Seed 后仍存在。
    """
    await seed_database(seed_session_factory)
    async with seed_session_factory() as session, session.begin():
        sales = await session.scalar(select(Role).where(Role.name == "sales"))
        custom = Permission(code="custom.export", display_name="自定义导出", description=None)
        session.add(custom)
        await session.flush()
        session.add(RolePermission(role_id=sales.id, permission_id=custom.id))

    await seed_database(seed_session_factory)
    async with seed_session_factory() as session:
        custom_pair = await session.scalar(
            select(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Permission.code == "custom.export")
        )
    assert custom_pair is not None
