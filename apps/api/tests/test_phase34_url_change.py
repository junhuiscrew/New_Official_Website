"""Phase 3.4 已发布 URL Change 事务回归测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.audit.models import AuditLog
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.authority.models import CaseStudy, CaseStudyTranslation
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.content.models import (
    ContentPublication,
    ContentRevision,
    ContentRoute,
    TranslationStatus,
)
from app.modules.discovery.models import RedirectRule
from app.modules.localization.models import Locale
from app.modules.users import models as _user_models  # noqa: F401


@pytest.mark.asyncio
async def test_published_url_change_is_one_atomic_delivery_transaction(
    sqlite_database_url: str,
) -> None:
    """
    验证 URL 变更同步完成旧路由失活、新 canonical、永久 Redirect、Revision 与 Audit。

    输入：sqlite_database_url，隔离数据库。
    输出：None；任一事务成员缺失时失败。
    """
    from app.modules.discovery.services import change_published_url

    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        locale = Locale(code="en", slug="en", name="English", native_name="English", is_default=True, is_enabled=True)
        case = CaseStudy(slug="new-case-slug", status="enabled")
        session.add_all([locale, case])
        await session.flush()
        old_route = ContentRoute(
            owner_type="case_study",
            owner_id=case.id,
            locale_id=locale.id,
            path="/en/case-studies/old-case-slug/",
            is_canonical=True,
            active=True,
            indexable=True,
        )
        session.add_all(
            [
                CaseStudyTranslation(case_study_id=case.id, locale_id=locale.id, title="Published case"),
                TranslationStatus(owner_type="case_study", owner_id=case.id, locale_id=locale.id, status="published"),
                ContentPublication(owner_type="case_study", owner_id=case.id, locale_id=locale.id, status="published"),
                old_route,
            ]
        )
        await session.flush()
        new_route = await change_published_url(
            session,
            owner_type="case_study",
            owner_id=case.id,
            locale_id=locale.id,
            new_path="/en/case-studies/new-case-slug/",
            actor_id=None,
        )
        redirect = await session.scalar(select(RedirectRule))
        assert old_route.is_canonical is False
        assert old_route.active is False and old_route.indexable is False
        assert new_route.is_canonical is True and new_route.active is True and new_route.indexable is True
        assert redirect is not None and redirect.status_code == 301
        assert redirect.source_host == "junhuiscrewbarrel.com"
        assert redirect.target_url == "https://junhuiscrewbarrel.com/en/case-studies/new-case-slug/"
        assert await session.scalar(select(func.count()).select_from(ContentRevision).where(ContentRevision.owner_id == case.id)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.target_id == str(case.id))) == 1
    await engine.dispose()
