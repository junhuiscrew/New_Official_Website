"""Phase 3.4 Authority Content 权限矩阵与知识分类 Seed 测试。"""

import pytest
from sqlalchemy import func, select

from app.core.database import Base, create_database_engine, create_session_factory
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.authority.models import KnowledgeCategory, KnowledgeCategoryTranslation
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.localization.models import Locale
from app.modules.users.models import Permission, Role, RolePermission
from app.seed import KNOWLEDGE_CATEGORY_SLUGS, ROLE_PERMISSION_MATRIX, seed_database


def test_phase34_role_permission_matrix_is_least_privilege() -> None:
    """
    验证 Phase 3.4 新权限按职责分配且销售/媒体角色不越权。

    输入：静态角色权限矩阵。
    输出：None；权限缺失或越权时失败。
    """
    editor = ROLE_PERMISSION_MATRIX["editor"]
    assert {
        "case.read", "case.create", "case.update",
        "knowledge.read", "knowledge.create", "knowledge.update",
        "faq.read", "faq.create", "faq.update",
        "expert.read",
    }.issubset(editor)
    assert not {"case.publish", "knowledge.publish", "expert.create", "source.manage"}.intersection(editor)

    reviewer = ROLE_PERMISSION_MATRIX["reviewer"]
    assert {"case.review", "case.publish", "knowledge.review", "knowledge.publish", "faq.review", "faq.publish"}.issubset(reviewer)
    translator = ROLE_PERMISSION_MATRIX["translator"]
    assert not {"case.publish", "knowledge.publish", "faq.publish"}.intersection(translator)

    seo_manager = ROLE_PERMISSION_MATRIX["seo_manager"]
    assert {"seo.update", "geo.update", "source.read", "source.manage", "redirect.manage"}.issubset(seo_manager)
    assert {"case.read", "knowledge.read", "faq.read", "expert.read"}.issubset(seo_manager)

    authority_prefixes = ("case.", "knowledge.", "faq.", "expert.", "source.")
    for role_name in ("sales", "media_manager"):
        assert not any(code.startswith(authority_prefixes) for code in ROLE_PERMISSION_MATRIX[role_name])


@pytest.mark.asyncio
async def test_phase34_seed_is_idempotent_and_creates_knowledge_categories(
    sqlite_database_url: str,
) -> None:
    """
    验证 Seed 幂等写入九个 Knowledge 分类及中英文翻译。

    输入：sqlite_database_url，隔离数据库。
    输出：None；重复、缺少分类或翻译时失败。
    """
    engine = create_database_engine(sqlite_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    await seed_database(factory)
    await seed_database(factory)
    async with factory() as session:
        slugs = set((await session.scalars(select(KnowledgeCategory.slug))).all())
        translation_count = await session.scalar(select(func.count()).select_from(KnowledgeCategoryTranslation))
        permission_codes = set((await session.scalars(select(Permission.code))).all())
        assert slugs == set(KNOWLEDGE_CATEGORY_SLUGS)
        assert translation_count == len(KNOWLEDGE_CATEGORY_SLUGS) * 2
        assert {"case.read", "knowledge.update", "faq.create", "expert.read", "source.manage"}.issubset(permission_codes)
        assert await session.scalar(select(func.count()).select_from(Locale)) == 2
        assert await session.scalar(select(func.count()).select_from(Role)) == 8
        assert await session.scalar(select(func.count()).select_from(RolePermission)) > 0
    await engine.dispose()
