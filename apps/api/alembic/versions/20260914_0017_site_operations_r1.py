"""新增站点品牌、导航页脚与受控重定向草稿字段。"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260914_0017"
down_revision = "20260910_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    追加站点运营配置表及重定向工作流字段。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；只创建结构并等值回填现有重定向，不写业务配置。
    """
    op.create_table(
        "site_brand_settings",
        sa.Column(
            "singleton_key",
            sa.String(32),
            server_default="primary",
            nullable=False,
            comment="唯一品牌设置键，固定为primary",
        ),
        sa.Column(
            "draft_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="品牌完整双语草稿JSON",
        ),
        sa.Column(
            "applied_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="品牌完整双语应用版JSON",
        ),
        sa.Column(
            "draft_header_logo_media_id", sa.Uuid(), nullable=True, comment="草稿桌面Logo媒体ID"
        ),
        sa.Column(
            "draft_mobile_logo_media_id", sa.Uuid(), nullable=True, comment="草稿移动端Logo媒体ID"
        ),
        sa.Column(
            "draft_favicon_media_id", sa.Uuid(), nullable=True, comment="草稿浏览器小图标媒体ID"
        ),
        sa.Column(
            "applied_header_logo_media_id", sa.Uuid(), nullable=True, comment="应用版桌面Logo媒体ID"
        ),
        sa.Column(
            "applied_mobile_logo_media_id",
            sa.Uuid(),
            nullable=True,
            comment="应用版移动端Logo媒体ID",
        ),
        sa.Column(
            "applied_favicon_media_id", sa.Uuid(), nullable=True, comment="应用版浏览器小图标媒体ID"
        ),
        sa.Column(
            "draft_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="品牌草稿乐观锁修订号",
        ),
        sa.Column(
            "applied_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="品牌应用版修订号",
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True, comment="最近保存草稿用户ID"),
        sa.Column("applied_by", sa.Uuid(), nullable=True, comment="最近应用品牌用户ID"),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=True, comment="最近应用品牌时间"
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
            "singleton_key = 'primary'",
            name=op.f("ck_site_brand_settings_site_brand_singleton_key_value"),
        ),
        sa.CheckConstraint(
            "draft_revision >= 0",
            name=op.f("ck_site_brand_settings_site_brand_draft_revision_nonnegative"),
        ),
        sa.CheckConstraint(
            "applied_revision >= 0",
            name=op.f("ck_site_brand_settings_site_brand_applied_revision_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["draft_header_logo_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["draft_mobile_logo_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["draft_favicon_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["applied_header_logo_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["applied_mobile_logo_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["applied_favicon_media_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
        comment="站点品牌草稿与应用配置表",
    )
    op.create_table(
        "site_navigation_settings",
        sa.Column("locale_id", sa.Uuid(), nullable=False, comment="导航语言ID"),
        sa.Column(
            "draft_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="当前语言导航与页脚草稿JSON",
        ),
        sa.Column(
            "applied_config_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="当前语言导航与页脚应用版JSON",
        ),
        sa.Column(
            "draft_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="导航草稿乐观锁修订号",
        ),
        sa.Column(
            "applied_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="导航应用版修订号",
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True, comment="最近保存草稿用户ID"),
        sa.Column("applied_by", sa.Uuid(), nullable=True, comment="最近应用导航用户ID"),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=True, comment="最近应用导航时间"
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
            name=op.f("ck_site_navigation_settings_site_navigation_draft_revision_nonnegative"),
        ),
        sa.CheckConstraint(
            "applied_revision >= 0",
            name=op.f("ck_site_navigation_settings_site_navigation_applied_revision_nonnegative"),
        ),
        sa.ForeignKeyConstraint(["locale_id"], ["locales.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("locale_id"),
        comment="站点导航与页脚草稿及应用配置表",
    )
    with op.batch_alter_table("redirect_rules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "draft_source_host", sa.String(255), nullable=True, comment="后台草稿来源主机名"
            )
        )
        batch_op.add_column(
            sa.Column(
                "draft_source_path", sa.String(1000), nullable=True, comment="后台草稿来源精确路径"
            )
        )
        batch_op.add_column(
            sa.Column(
                "draft_target_url", sa.String(1500), nullable=True, comment="后台草稿目标正式URL"
            )
        )
        batch_op.add_column(
            sa.Column(
                "draft_status_code", sa.Integer(), nullable=True, comment="后台草稿HTTP状态码"
            )
        )
        batch_op.add_column(
            sa.Column("draft_notes", sa.Text(), nullable=True, comment="后台草稿内部备注")
        )
        batch_op.add_column(
            sa.Column(
                "workflow_status",
                sa.String(32),
                server_default="confirmed",
                nullable=False,
                comment="受控流程状态：draft草稿，checked已检查，confirmed已确认",
            )
        )
        batch_op.add_column(
            sa.Column(
                "revision",
                sa.Integer(),
                server_default="0",
                nullable=False,
                comment="重定向草稿乐观锁修订号",
            )
        )
        batch_op.add_column(
            sa.Column(
                "checked_revision", sa.Integer(), nullable=True, comment="最近通过冲突检查的修订号"
            )
        )
        batch_op.add_column(
            sa.Column("updated_by", sa.Uuid(), nullable=True, comment="最近修改草稿用户ID")
        )
        batch_op.add_column(
            sa.Column("confirmed_by", sa.Uuid(), nullable=True, comment="最近确认启用用户ID")
        )
        batch_op.add_column(
            sa.Column(
                "confirmed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最近确认启用时间",
            )
        )
        batch_op.create_check_constraint(
            "redirect_rule_workflow_status_value",
            "workflow_status IN ('draft','checked','confirmed')",
        )
        batch_op.create_check_constraint("redirect_rule_revision_nonnegative", "revision >= 0")
        batch_op.create_foreign_key(
            "fk_redirect_rules_updated_by_users",
            "users",
            ["updated_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_redirect_rules_confirmed_by_users",
            "users",
            ["confirmed_by"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text(
            "UPDATE redirect_rules SET draft_source_host=source_host, draft_source_path=source_path, draft_target_url=target_url, draft_status_code=status_code, draft_notes=notes"
        )
    )


def downgrade() -> None:
    """输入无；输出None，显式降级时移除本轮追加结构。"""
    with op.batch_alter_table("redirect_rules") as batch_op:
        batch_op.drop_constraint("fk_redirect_rules_confirmed_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_redirect_rules_updated_by_users", type_="foreignkey")
        batch_op.drop_constraint(
            op.f("ck_redirect_rules_redirect_rule_revision_nonnegative"), type_="check"
        )
        batch_op.drop_constraint(
            op.f("ck_redirect_rules_redirect_rule_workflow_status_value"), type_="check"
        )
        for column_name in (
            "confirmed_at",
            "confirmed_by",
            "updated_by",
            "checked_revision",
            "revision",
            "workflow_status",
            "draft_notes",
            "draft_status_code",
            "draft_target_url",
            "draft_source_path",
            "draft_source_host",
        ):
            batch_op.drop_column(column_name)
    op.drop_table("site_navigation_settings")
    op.drop_table("site_brand_settings")
