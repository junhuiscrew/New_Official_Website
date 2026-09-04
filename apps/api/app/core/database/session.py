"""异步数据库引擎、session factory 与 FastAPI 依赖。"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_database_engine(database_url: str) -> AsyncEngine:
    """
    根据数据库 URL 创建 SQLAlchemy 异步引擎。

    输入：
        database_url: str，SQLAlchemy 异步数据库连接 URL。

    输出：
        AsyncEngine，启用连接存活检查的数据库引擎。
    """
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine_instance: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    为指定引擎创建类型化异步 session factory。

    输入：
        engine_instance: AsyncEngine，目标数据库引擎。

    输出：
        async_sessionmaker[AsyncSession]，不在提交后过期对象的 session factory。
    """
    return async_sessionmaker(engine_instance, expire_on_commit=False, class_=AsyncSession)


engine = create_database_engine(get_settings().database_url)
async_session_factory = create_session_factory(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    为一次 FastAPI 请求提供数据库 session，并在结束后关闭。

    输入：无。

    输出：
        AsyncIterator[AsyncSession]，请求作用域的异步数据库 session。
    """
    async with async_session_factory() as session:
        yield session
