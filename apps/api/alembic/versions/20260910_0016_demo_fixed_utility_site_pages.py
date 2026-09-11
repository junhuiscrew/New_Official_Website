"""扩展 Contact 与 RFQ 固定页面身份白名单。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260910_0016"
down_revision = "20260909_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    在现有 SitePage 体系中登记 Contact 与 RFQ 固定页面键。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；只扩展数据库约束和字段注释，不写任何业务记录。
    """
    with op.batch_alter_table("site_pages") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_site_pages_site_page_system_key_value"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "site_page_system_key_value",
            "system_key IN ('products','privacy','home','contact','request-a-quote')",
        )
        batch_op.alter_column(
            "system_key",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            comment="系统稳定页面键：仅允许products、privacy、home、contact或request-a-quote",
        )


def downgrade() -> None:
    """
    清理本迁移登记的固定页面后恢复上一版白名单。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；仅在显式降级时移除 Contact/RFQ 的关联数据与页面身份。
    """
    owner_ids = (
        "SELECT id FROM site_pages "
        "WHERE system_key IN ('contact','request-a-quote')"
    )
    seo_ids = (
        "SELECT id FROM seo_documents WHERE owner_type = 'site_page' "
        f"AND owner_id IN ({owner_ids})"
    )
    op.execute(
        sa.text(
            "DELETE FROM content_revisions WHERE owner_type = 'seo_document' "
            f"AND owner_id IN ({seo_ids})"
        )
    )
    for table_name in (
        "seo_documents",
        "content_routes",
        "content_publications",
        "translation_statuses",
    ):
        op.execute(
            sa.text(
                f"DELETE FROM {table_name} WHERE owner_type = 'site_page' "
                f"AND owner_id IN ({owner_ids})"
            )
        )
    op.execute(
        sa.text(
            "DELETE FROM site_page_translations "
            f"WHERE site_page_id IN ({owner_ids})"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM site_pages "
            "WHERE system_key IN ('contact','request-a-quote')"
        )
    )
    with op.batch_alter_table("site_pages") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_site_pages_site_page_system_key_value"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "site_page_system_key_value",
            "system_key IN ('products','privacy','home')",
        )
        batch_op.alter_column(
            "system_key",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            comment="系统稳定页面键：仅允许products、privacy或home",
        )
