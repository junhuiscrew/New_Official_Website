"""Phase 3.2 语言、角色、权限与角色矩阵的幂等系统 Seed。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.authority.models import KnowledgeCategory, KnowledgeCategoryTranslation
from app.modules.localization.models import Locale
from app.modules.users.models import Permission, Role, RolePermission

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

KNOWLEDGE_CATEGORY_SLUGS: tuple[str, ...] = (
    "technical-guides",
    "material-guides",
    "selection-guides",
    "troubleshooting",
    "comparisons",
    "faq",
    "industry-knowledge",
    "company-news",
    "exhibitions",
)

_KNOWLEDGE_CATEGORY_NAMES: dict[str, tuple[str, str]] = {
    "technical-guides": ("技术指南", "Technical Guides"),
    "material-guides": ("材料指南", "Material Guides"),
    "selection-guides": ("选型指南", "Selection Guides"),
    "troubleshooting": ("故障排查", "Troubleshooting"),
    "comparisons": ("对比分析", "Comparisons"),
    "faq": ("常见问题", "FAQ"),
    "industry-knowledge": ("行业知识", "Industry Knowledge"),
    "company-news": ("公司新闻", "Company News"),
    "exhibitions": ("展会信息", "Exhibitions"),
}

PERMISSION_CODES: tuple[str, ...] = (
    "user.read",
    "user.create",
    "user.update",
    "user.disable",
    "role.read",
    "role.manage",
    "locale.read",
    "locale.manage",
    "content.read",
    "content.create",
    "content.update",
    "content.review",
    "content.publish",
    "content.archive",
    "translation.read",
    "translation.create",
    "translation.update",
    "translation.review",
    "translation.publish",
    "seo.read",
    "seo.update",
    "geo.read",
    "geo.update",
    "redirect.read",
    "redirect.manage",
    "media.read",
    "media.upload",
    "media.update",
    "media.delete",
    "rfq.read",
    "rfq.assign",
    "rfq.update",
    "rfq.download_private_file",
    "settings.read",
    "settings.update",
    "audit.read",
    "catalog.read",
    "catalog.create",
    "catalog.update",
    "catalog.archive",
    "specification.read",
    "specification.manage",
    "material.read",
    "material.create",
    "material.update",
    "material.archive",
    "technology.read",
    "technology.create",
    "technology.update",
    "technology.archive",
    "application.read",
    "application.create",
    "application.update",
    "application.archive",
    "solution.read",
    "solution.create",
    "solution.update",
    "solution.archive",
    "case.read",
    "case.create",
    "case.update",
    "case.review",
    "case.publish",
    "case.archive",
    "knowledge.read",
    "knowledge.create",
    "knowledge.update",
    "knowledge.review",
    "knowledge.publish",
    "knowledge.archive",
    "faq.read",
    "faq.create",
    "faq.update",
    "faq.review",
    "faq.publish",
    "faq.archive",
    "expert.read",
    "expert.create",
    "expert.update",
    "expert.review",
    "expert.publish",
    "expert.archive",
    "source.read",
    "source.manage",
    "company.read",
    "company.update",
    "capability.read",
    "capability.create",
    "capability.update",
    "capability.archive",
    "equipment.read",
    "equipment.create",
    "equipment.update",
    "equipment.archive",
    "certificate.read",
    "certificate.create",
    "certificate.update",
    "certificate.archive",
    "patent.read",
    "patent.create",
    "patent.update",
    "patent.archive",
    "honor.read",
    "honor.create",
    "honor.update",
    "honor.archive",
    "exhibition.read",
    "exhibition.create",
    "exhibition.update",
    "exhibition.archive",
    "download.read",
    "download.create",
    "download.update",
    "download.archive",
)

PERMISSIONS: tuple[dict[str, object], ...] = tuple(
    {
        "code": code,
        "display_name": code,
        "description": f"Phase 3.2 系统权限：{code}",
    }
    for code in PERMISSION_CODES
)

CONTENT_PERMISSIONS = frozenset(code for code in PERMISSION_CODES if code.startswith("content."))
TRANSLATION_PERMISSIONS = frozenset(
    code for code in PERMISSION_CODES if code.startswith("translation.")
)
MEDIA_PERMISSIONS = frozenset(code for code in PERMISSION_CODES if code.startswith("media."))
RFQ_PERMISSIONS = frozenset(code for code in PERMISSION_CODES if code.startswith("rfq."))
CATALOG_PERMISSIONS = frozenset(code for code in PERMISSION_CODES if code.startswith("catalog."))
SPECIFICATION_PERMISSIONS = frozenset(
    code for code in PERMISSION_CODES if code.startswith("specification.")
)
STRUCTURED_CONTENT_PERMISSIONS = frozenset(
    code
    for code in PERMISSION_CODES
    if code.startswith(("material.", "technology.", "application.", "solution."))
)
AUTHORITY_PERMISSIONS = frozenset(
    code
    for code in PERMISSION_CODES
    if code.startswith(("case.", "knowledge.", "faq.", "expert.", "source."))
)

# 角色矩阵只声明系统基线；Seed 只补充缺失关系，不删除管理员后续添加的自定义映射。
ROLE_PERMISSION_MATRIX: dict[str, frozenset[str]] = {
    "super_admin": frozenset(PERMISSION_CODES),
    "content_admin": CONTENT_PERMISSIONS
    | TRANSLATION_PERMISSIONS
    | MEDIA_PERMISSIONS
    | CATALOG_PERMISSIONS
    | SPECIFICATION_PERMISSIONS
    | STRUCTURED_CONTENT_PERMISSIONS
    | AUTHORITY_PERMISSIONS
    | frozenset(
        {
            "user.read",
            "role.read",
            "locale.read",
            "locale.manage",
            "seo.read",
            "seo.update",
            "geo.read",
            "geo.update",
            "redirect.read",
            "redirect.manage",
            "settings.read",
            "audit.read",
        }
    ),
    "editor": frozenset(
        {
            "content.read",
            "content.create",
            "content.update",
            "translation.read",
            "media.read",
            "media.upload",
            "catalog.read",
            "catalog.create",
            "catalog.update",
            "specification.read",
            "material.read",
            "technology.read",
            "application.read",
            "solution.read",
            "case.read",
            "case.create",
            "case.update",
            "knowledge.read",
            "knowledge.create",
            "knowledge.update",
            "faq.read",
            "faq.create",
            "faq.update",
            "expert.read",
        }
    ),
    "translator": frozenset(
        {
            "content.read",
            "locale.read",
            "translation.read",
            "translation.create",
            "translation.update",
            "case.read",
            "knowledge.read",
            "faq.read",
            "expert.read",
        }
    ),
    "reviewer": frozenset(
        {
            "content.read",
            "content.review",
            "content.publish",
            "translation.read",
            "translation.review",
            "translation.publish",
            "audit.read",
            "catalog.read",
            "specification.read",
            "material.read",
            "technology.read",
            "application.read",
            "solution.read",
            "case.read",
            "case.review",
            "case.publish",
            "knowledge.read",
            "knowledge.review",
            "knowledge.publish",
            "faq.read",
            "faq.review",
            "faq.publish",
            "expert.read",
            "expert.review",
            "expert.publish",
        }
    ),
    "seo_manager": frozenset(
        {
            "content.read",
            "translation.read",
            "locale.read",
            "catalog.read",
            "specification.read",
            "material.read",
            "technology.read",
            "application.read",
            "solution.read",
            "seo.read",
            "seo.update",
            "geo.read",
            "geo.update",
            "redirect.read",
            "redirect.manage",
            "audit.read",
            "case.read",
            "knowledge.read",
            "faq.read",
            "expert.read",
            "source.read",
            "source.manage",
        }
    ),
    "sales": RFQ_PERMISSIONS,
    "media_manager": MEDIA_PERMISSIONS,
}

# Trust/Download 权限集合在定义矩阵后补充，保持旧角色声明清晰且 Seed 幂等。
TRUST_PERMISSIONS = frozenset(code for code in PERMISSION_CODES if code.startswith(("company.", "capability.", "equipment.", "certificate.", "patent.", "honor.", "exhibition.", "download.")))
ROLE_PERMISSION_MATRIX["content_admin"] = ROLE_PERMISSION_MATRIX["content_admin"] | TRUST_PERMISSIONS
ROLE_PERMISSION_MATRIX["editor"] = ROLE_PERMISSION_MATRIX["editor"] | frozenset({"company.read", "capability.read", "equipment.read", "certificate.read", "patent.read", "honor.read", "exhibition.read", "download.read"})
# Reviewer 需要读取审核目标，但不会因此获得任何 Company/Trust update 权限。
ROLE_PERMISSION_MATRIX["reviewer"] = ROLE_PERMISSION_MATRIX["reviewer"] | frozenset({"company.read", "capability.read", "equipment.read", "certificate.read", "patent.read", "honor.read", "exhibition.read"})
ROLE_PERMISSION_MATRIX["sales"] = RFQ_PERMISSIONS
ROLE_PERMISSION_MATRIX["media_manager"] = MEDIA_PERMISSIONS | frozenset({"download.read", "download.create", "download.update", "download.archive"})


async def _seed_by_unique_field(
    session: AsyncSession,
    model: type[Locale] | type[Role] | type[Permission],
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
    写入语言、基础角色、权限和系统角色权限映射。

    输入：
        session_factory: async_sessionmaker[AsyncSession]，目标数据库 session factory。

    输出：None；事务成功提交或异常时自动回滚。
    """
    async with session_factory() as session, session.begin():
        await _seed_by_unique_field(session, Locale, LOCALES, "code")
        await _seed_by_unique_field(session, Role, ROLES, "name")
        await _seed_by_unique_field(session, Permission, PERMISSIONS, "code")
        await session.flush()

        roles = {role.name: role for role in (await session.scalars(select(Role))).all()}
        permissions = {
            permission.code: permission
            for permission in (await session.scalars(select(Permission))).all()
        }
        existing_pairs = set(
            (
                await session.execute(select(RolePermission.role_id, RolePermission.permission_id))
            ).all()
        )
        for role_name, permission_codes in ROLE_PERMISSION_MATRIX.items():
            role = roles[role_name]
            for permission_code in permission_codes:
                permission = permissions[permission_code]
                pair = (role.id, permission.id)
                if pair not in existing_pairs:
                    session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                    existing_pairs.add(pair)
        await _seed_knowledge_categories(session)


async def _seed_knowledge_categories(session: AsyncSession) -> None:
    """
    幂等写入 Knowledge Center 冻结分类与中英文名称。

    输入：
        session: AsyncSession，当前 Seed 事务会话。

    输出：None；只补充缺失分类和翻译，不覆盖管理员已有内容。
    """
    locales = {locale.code: locale for locale in (await session.scalars(select(Locale))).all()}
    existing = {
        category.slug: category
        for category in (await session.scalars(select(KnowledgeCategory))).all()
    }
    for sort_order, slug in enumerate(KNOWLEDGE_CATEGORY_SLUGS, start=1):
        category = existing.get(slug)
        if category is None:
            category = KnowledgeCategory(slug=slug, status="enabled", sort_order=sort_order * 10)
            session.add(category)
            await session.flush()
            existing[slug] = category
        names = _KNOWLEDGE_CATEGORY_NAMES[slug]
        for locale_code, name in (("zh-CN", names[0]), ("en", names[1])):
            locale = locales[locale_code]
            translation = await session.scalar(
                select(KnowledgeCategoryTranslation).where(
                    KnowledgeCategoryTranslation.category_id == category.id,
                    KnowledgeCategoryTranslation.locale_id == locale.id,
                )
            )
            if translation is None:
                session.add(
                    KnowledgeCategoryTranslation(
                        category_id=category.id,
                        locale_id=locale.id,
                        name=name,
                    )
                )
