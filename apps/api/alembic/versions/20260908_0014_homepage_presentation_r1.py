"""创建固定首页模块化草稿与应用配置。"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260908_0014"
down_revision = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    扩展固定页面白名单并创建首页布局表。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；不插入正文、产品、媒体或首页配置业务记录。
    """
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

    op.create_table(
        "homepage_layouts",
        sa.Column("site_page_id", sa.Uuid(), nullable=False, comment="固定首页页面ID"),
        sa.Column("locale_id", sa.Uuid(), nullable=False, comment="首页布局语言ID"),
        sa.Column(
            "draft_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="后台当前草稿模块配置JSON",
        ),
        sa.Column(
            "applied_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="普通首页当前应用模块配置JSON",
        ),
        sa.Column(
            "draft_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="草稿乐观锁修订号",
        ),
        sa.Column(
            "applied_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="已应用布局修订号",
        ),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            nullable=True,
            comment="最近保存草稿的用户ID",
        ),
        sa.Column(
            "applied_by",
            sa.Uuid(),
            nullable=True,
            comment="最近应用布局的用户ID",
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="最近应用布局时间",
        ),
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
        sa.CheckConstraint(
            "draft_revision >= 0",
            name="homepage_layout_draft_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "applied_revision >= 0",
            name="homepage_layout_applied_revision_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["applied_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["site_page_id"],
            ["site_pages.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_page_id",
            "locale_id",
            name="uq_homepage_layout_site_page_locale",
        ),
        comment="首页模块化布局配置表",
    )


def downgrade() -> None:
    """
    移除首页布局表并恢复此前固定页面白名单。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；要求 home 页面身份已随布局清理。
    """
    op.drop_table("homepage_layouts")
    op.execute(sa.text("DELETE FROM site_page_translations WHERE site_page_id IN "
                       "(SELECT id FROM site_pages WHERE system_key = 'home')"))
    op.execute(sa.text("DELETE FROM site_pages WHERE system_key = 'home'"))
    with op.batch_alter_table("site_pages") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_site_pages_site_page_system_key_value"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "site_page_system_key_value",
            "system_key IN ('products','privacy')",
        )
        batch_op.alter_column(
            "system_key",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            comment="系统稳定页面键：仅允许products或privacy",
        )
