"""Content Revision 存储与回滚读取契约测试。"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401
from app.modules.content.models import ContentRevision
from app.modules.content.services.revisions import get_rollback_snapshot, store_revision
from app.modules.localization.models import Locale
from app.modules.users import models as user_models  # noqa: F401


@pytest.fixture
async def revision_session_factory(
    sqlite_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """创建修订服务隔离数据库。"""
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        session.add(
            Locale(
                code="en",
                slug="en",
                name="English",
                native_name="English",
                is_default=True,
                is_enabled=True,
            )
        )
    yield factory
    await engine.dispose()


async def test_revision_numbers_increment_and_rollback_returns_immutable_snapshot(
    revision_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """验证修订序号递增，回滚契约返回目标快照的独立副本。"""
    owner_id = uuid.uuid4()
    async with revision_session_factory() as session, session.begin():
        locale = await session.scalar(select(Locale))
        first = await store_revision(session, "page", owner_id, locale.id, {"title": "First"}, None)
        second = await store_revision(
            session, "page", owner_id, locale.id, {"title": "Second"}, None
        )
        rollback = await get_rollback_snapshot(session, "page", owner_id, locale.id, 1)
        rollback["title"] = "Mutated outside storage"

    async with revision_session_factory() as session:
        stored_first = await session.scalar(
            select(ContentRevision).where(ContentRevision.revision_no == 1)
        )
    assert (first.revision_no, second.revision_no) == (1, 2)
    assert stored_first.snapshot_jsonb == {"title": "First"}
