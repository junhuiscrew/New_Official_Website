"""新增 Demo R2 来源追踪和内容媒体关系。"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260909_0015"
down_revision = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    创建演示批次来源和内容媒体关系表。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；只创建结构和约束，不插入任何演示业务记录。
    """
    with op.batch_alter_table("author_experts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "identity_kind",
                sa.String(length=24),
                server_default="person",
                nullable=False,
                comment="身份类型：person真实人物，organization演示编辑组织",
            )
        )
        batch_op.create_check_constraint(
            "author_expert_identity_kind_value",
            "identity_kind IN ('person','organization')",
        )
    op.create_table(
        "demo_content_records",
        sa.Column("batch_id", sa.String(length=80), nullable=False, comment="演示批次ID"),
        sa.Column("alias", sa.String(length=160), nullable=False, comment="包内稳定演示别名"),
        sa.Column("entity_type", sa.String(length=100), nullable=False, comment="业务实体类型"),
        sa.Column("entity_id", sa.Uuid(), nullable=False, comment="独立演示库实体ID"),
        sa.Column("content_origin", sa.String(length=32), nullable=False, comment="内容来源类型"),
        sa.Column("initial_fingerprint", sa.String(length=64), nullable=False, comment="首次受控导入内容SHA256"),
        sa.Column(
            "replacement_status",
            sa.String(length=24),
            server_default="demo_active",
            nullable=False,
            comment="替换状态：demo_active演示中，replaced已替换，conflict人工修改冲突，retired停用",
        ),
        sa.Column(
            "source_metadata_jsonb",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            comment="生成来源、许可、原始样例和替换说明JSON",
        ),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="更新时间"),
        sa.CheckConstraint(
            "content_origin IN ('synthetic_demo','approved_public_copy','generated_demo','licensed_demo')",
            name="demo_content_origin",
        ),
        sa.CheckConstraint(
            "replacement_status IN ('demo_active','replaced','conflict','retired')",
            name="demo_content_replacement_status",
        ),
        sa.CheckConstraint("length(initial_fingerprint) = 64", name="demo_content_fingerprint_length"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "alias", name="uq_demo_content_batch_alias"),
        sa.UniqueConstraint("batch_id", "entity_type", "entity_id", name="uq_demo_content_batch_entity"),
        comment="演示内容批次来源与替换状态表",
    )
    op.create_table(
        "content_media_links",
        sa.Column("owner_type", sa.String(length=100), nullable=False, comment="内容主实体类型"),
        sa.Column("owner_id", sa.Uuid(), nullable=False, comment="内容主实体ID"),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False, comment="媒体资产ID"),
        sa.Column("role", sa.String(length=24), nullable=False, comment="媒体用途：主图、图库、视频、视频封面、下载、封面或首页Hero"),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False, comment="同一用途下的媒体排序"),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="更新时间"),
        sa.CheckConstraint(
            "role IN ('primary','gallery','video','video_poster','download','cover','hero')",
            name="content_media_role",
        ),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_type", "owner_id", "role", "sort_order", name="uq_content_media_owner_role_order"),
        comment="跨内容类型媒体引用关系表",
    )
    op.create_index("ix_demo_content_entity", "demo_content_records", ["entity_type", "entity_id"])
    op.create_index("ix_content_media_owner", "content_media_links", ["owner_type", "owner_id"])


def downgrade() -> None:
    """
    移除 Demo R2 新增结构。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；不触碰既有正式内容表。
    """
    op.drop_index("ix_content_media_owner", table_name="content_media_links")
    op.drop_index("ix_demo_content_entity", table_name="demo_content_records")
    op.drop_table("content_media_links")
    op.drop_table("demo_content_records")
    with op.batch_alter_table("author_experts") as batch_op:
        batch_op.drop_constraint(
            "author_expert_identity_kind_value",
            type_="check",
        )
        batch_op.drop_column("identity_kind")
