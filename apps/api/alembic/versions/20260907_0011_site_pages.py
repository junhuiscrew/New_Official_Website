"""创建 Products 固定站点页面身份与翻译表。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260907_0011"
down_revision = "20260905_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    创建固定页面身份与真实语言名称结构，不插入任何业务内容。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None，数据库新增 site_pages 与 site_page_translations 表。
    """
    op.create_table(
        "site_pages",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
            comment="主键ID",
        ),
        sa.Column(
            "system_key",
            sa.String(length=64),
            nullable=False,
            comment="系统稳定页面键：仅允许products",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="enabled",
            nullable=False,
            comment="页面状态：enabled启用，disabled禁用，retired退役",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新时间",
        ),
        sa.CheckConstraint("system_key IN ('products')", name="site_page_system_key_value"),
        sa.CheckConstraint(
            "status IN ('enabled','disabled','retired')", name="site_page_status_value"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_key", name="uq_site_pages_system_key"),
        comment="固定站点页面表",
    )
    op.create_table(
        "site_page_translations",
        sa.Column("site_page_id", sa.Uuid(), nullable=False, comment="固定页面ID"),
        sa.Column("locale_id", sa.Uuid(), nullable=False, comment="语言ID"),
        sa.Column("display_name", sa.String(length=120), nullable=False, comment="页面显示名称"),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["locale_id"], ["locales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_page_id"], ["site_pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_page_id", "locale_id", name="uq_site_page_translation_locale"),
        comment="固定站点页面翻译表",
    )


def downgrade() -> None:
    """
    按外键依赖逆序移除固定页面结构。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None，数据库恢复至 20260905_0010 结构。
    """
    op.drop_table("site_page_translations")
    op.drop_table("site_pages")
