"""确定性基础数据 Seed 测试。"""

from sqlalchemy import select

from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.localization.models import Locale
from app.modules.users.models import Role
from app.seed import seed_database


async def test_seed_creates_locales_and_roles_idempotently(
    sqlite_database_url: str,
) -> None:
    """
    验证 locale 与角色 Seed 内容完整，并且重复执行不会产生重复数据。

    输入：
        sqlite_database_url: str，测试专用数据库 URL。

    输出：None；断言失败时由 pytest 报告。
    """
    engine = create_database_engine(sqlite_database_url)
    session_factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    await seed_database(session_factory)
    await seed_database(session_factory)

    async with session_factory() as session:
        locale_codes = set((await session.scalars(select(Locale.code))).all())
        role_names = set((await session.scalars(select(Role.name))).all())

    await engine.dispose()
    assert locale_codes == {"zh-CN", "en"}
    assert role_names == {
        "super_admin",
        "content_admin",
        "editor",
        "translator",
        "reviewer",
        "seo_manager",
        "sales",
        "media_manager",
    }
