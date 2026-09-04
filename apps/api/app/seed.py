"""Phase 3.1 的幂等基础数据 Seed。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.localization.models import Locale
from app.modules.users.models import Role

LOCALES: tuple[dict[str, object], ...] = (
    {
        "code": "zh-CN",
        "slug": "zh-cn",
        "name": "Simplified Chinese",
        "native_name": "简体中文",
        "is_default": True,
        "is_enabled": True,
        "sort_order": 10,
    },
    {
        "code": "en",
        "slug": "en",
        "name": "English",
        "native_name": "English",
        "is_default": False,
        "is_enabled": True,
        "sort_order": 20,
    },
)

ROLES: tuple[dict[str, object], ...] = (
    {"name": "super_admin", "display_name": "超级管理员", "description": "拥有全部系统权限"},
    {
        "name": "content_admin",
        "display_name": "内容管理员",
        "description": "管理站点内容与发布流程",
    },
    {"name": "editor", "display_name": "编辑", "description": "创建和编辑内容"},
    {"name": "translator", "display_name": "翻译", "description": "维护多语言翻译"},
    {"name": "reviewer", "display_name": "审核员", "description": "审核内容与翻译"},
    {"name": "seo_manager", "display_name": "SEO 管理员", "description": "维护 SEO 与 GEO 信息"},
    {"name": "sales", "display_name": "销售", "description": "处理询盘与客户沟通"},
    {"name": "media_manager", "display_name": "媒体管理员", "description": "管理公开媒体资产"},
)


async def _seed_by_unique_field(
    session: AsyncSession,
    model: type[Locale] | type[Role],
    rows: Sequence[dict[str, object]],
    unique_field: str,
) -> None:
    """
    按唯一字段补充缺失的基础记录，保证重复执行安全。

    输入：
        session: AsyncSession，当前数据库事务 session。
        model: type[Locale] | type[Role]，目标 ORM 模型。
        rows: Sequence[dict[str, object]]，待写入的确定性记录。
        unique_field: str，用于识别重复记录的字段名。

    输出：None；缺失记录被加入当前 session。
    """
    existing_values = set((await session.scalars(select(getattr(model, unique_field)))).all())
    for row in rows:
        if row[unique_field] not in existing_values:
            session.add(model(**row))


async def seed_database(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """
    写入 Phase 3.1 的语言与基础角色。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，目标数据库 session factory。

    输出：None；事务成功提交或异常时自动回滚。
    """
    async with session_factory() as session, session.begin():
        await _seed_by_unique_field(session, Locale, LOCALES, "code")
        await _seed_by_unique_field(session, Role, ROLES, "name")
