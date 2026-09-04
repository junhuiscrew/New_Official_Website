"""数据库连接与基础 metadata 测试。"""

from sqlalchemy import text

from app.core.database import create_database_engine, create_session_factory


async def test_database_session_executes_query(sqlite_database_url: str) -> None:
    """
    验证异步数据库 session 可以建立连接并执行 SQL。

    输入：
        sqlite_database_url: str，测试专用数据库 URL。

    输出：None；断言失败时由 pytest 报告。
    """
    engine = create_database_engine(sqlite_database_url)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        result = await session.execute(text("SELECT 1"))

    await engine.dispose()
    assert result.scalar_one() == 1


def test_core_metadata_contains_required_tables() -> None:
    """
    验证 Phase 3.1 六张基础表均已注册到 SQLAlchemy metadata。

    输入：无。

    输出：None；断言失败时由 pytest 报告。
    """
    from app.core.database import Base
    from app.modules.localization import models as localization_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401

    assert {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "locales",
    }.issubset(Base.metadata.tables)
