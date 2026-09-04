"""创建 Phase 3.2 认证、翻译、发布、路由、修订与审计基础。

Revision ID: 20260904_0002
Revises: 20260904_0001
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260904_0002"
down_revision: str | None = "20260904_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_column(name: str, comment: str, nullable: bool = False) -> sa.Column:
    """
    创建带中文注释的 UUID migration 字段。

    输入：
        name: str，英文字段名。
        comment: str，中文字段说明。
        nullable: bool，是否允许空值。

    输出：sa.Column，可直接传入 op.create_table。
    """
    return sa.Column(name, sa.Uuid(), nullable=nullable, comment=comment)


def _timestamp_columns() -> tuple[sa.Column, sa.Column]:
    """
    创建统一的 created_at 与 updated_at 字段。

    输入：无。

    输出：tuple[sa.Column, sa.Column]，带服务器默认值的时间字段。
    """
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="更新时间",
        ),
    )


def upgrade() -> None:
    """
    升级到 Phase 3.2 数据库基础结构。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None；完成类型修正、约束和新表创建。
    """
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS citext")
        op.drop_index(op.f("ix_users_email"), table_name="users")
        op.alter_column(
            "users",
            "email",
            existing_type=sa.String(length=320),
            type_=postgresql.CITEXT(),
            existing_nullable=False,
            postgresql_using="email::citext",
        )
        op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_index(
        "ux_locales_single_default",
        "locales",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "auth_sessions",
        _uuid_column("user_id", "用户ID"),
        sa.Column("token_hash", sa.String(length=64), nullable=False, comment="刷新凭据HMAC摘要"),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False, comment="刷新会话过期时间"
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="撤销时间"),
        _uuid_column("rotated_from_id", "轮换来源会话ID", nullable=True),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最近使用时间"
        ),
        sa.Column("ip", sa.String(length=45), nullable=True, comment="客户端IP地址"),
        sa.Column("user_agent", sa.Text(), nullable=True, comment="客户端User-Agent"),
        _uuid_column("id", "主键ID"),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_auth_sessions_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_id"],
            ["auth_sessions.id"],
            ondelete="SET NULL",
            name=op.f("fk_auth_sessions_rotated_from_id_auth_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        comment="认证刷新会话表",
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_auth_sessions_token_hash"), "auth_sessions", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"], unique=False
    )

    op.create_table(
        "translation_statuses",
        sa.Column("owner_type", sa.String(length=100), nullable=False, comment="主实体类型"),
        _uuid_column("owner_id", "主实体ID"),
        _uuid_column("locale_id", "目标语言ID"),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'missing'"),
            nullable=False,
            comment="翻译状态：missing缺失，draft草稿，machine_translated机翻，human_reviewed人工审核，published已发布",
        ),
        _uuid_column("source_locale_id", "源语言ID", nullable=True),
        _uuid_column("translated_by", "翻译用户ID", nullable=True),
        _uuid_column("reviewed_by", "审核用户ID", nullable=True),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True, comment="翻译发布时间"
        ),
        _uuid_column("id", "主键ID"),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('missing','draft','machine_translated','human_reviewed','published')",
            name=op.f("ck_translation_statuses_translation_status_value"),
        ),
        sa.ForeignKeyConstraint(
            ["locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
            name=op.f("fk_translation_statuses_locale_id_locales"),
        ),
        sa.ForeignKeyConstraint(
            ["source_locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
            name=op.f("fk_translation_statuses_source_locale_id_locales"),
        ),
        sa.ForeignKeyConstraint(
            ["translated_by"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_translation_statuses_translated_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_translation_statuses_reviewed_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_statuses")),
        sa.UniqueConstraint(
            "owner_type", "owner_id", "locale_id", name="uq_translation_owner_locale"
        ),
        comment="内容翻译状态表",
    )

    op.create_table(
        "content_publications",
        sa.Column("owner_type", sa.String(length=100), nullable=False, comment="主实体类型"),
        _uuid_column("owner_id", "主实体ID"),
        _uuid_column("locale_id", "发布语言ID"),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'draft'"),
            nullable=False,
            comment="发布状态：draft草稿，review审核，scheduled定时，published已发布，archived已归档",
        ),
        sa.Column(
            "scheduled_at", sa.DateTime(timezone=True), nullable=True, comment="计划发布时间"
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True, comment="实际发布时间"
        ),
        _uuid_column("id", "主键ID"),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('draft','review','scheduled','published','archived')",
            name=op.f("ck_content_publications_publication_status_value"),
        ),
        sa.ForeignKeyConstraint(
            ["locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
            name=op.f("fk_content_publications_locale_id_locales"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_publications")),
        sa.UniqueConstraint(
            "owner_type", "owner_id", "locale_id", name="uq_publication_owner_locale"
        ),
        comment="内容发布状态表",
    )

    op.create_table(
        "content_routes",
        sa.Column("owner_type", sa.String(length=100), nullable=False, comment="主实体类型"),
        _uuid_column("owner_id", "主实体ID"),
        _uuid_column("locale_id", "路由语言ID"),
        sa.Column("path", sa.String(length=500), nullable=False, comment="站内绝对路径"),
        sa.Column(
            "is_canonical",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="是否规范路由",
        ),
        sa.Column(
            "indexable",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否允许索引",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否对外生效",
        ),
        _uuid_column("id", "主键ID"),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
            name=op.f("fk_content_routes_locale_id_locales"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_routes")),
        sa.UniqueConstraint("path", name="uq_content_routes_path"),
        comment="内容路由注册表",
    )
    op.create_index(
        "ix_content_route_owner_locale",
        "content_routes",
        ["owner_type", "owner_id", "locale_id"],
        unique=False,
    )

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "content_revisions",
        sa.Column("owner_type", sa.String(length=100), nullable=False, comment="主实体类型"),
        _uuid_column("owner_id", "主实体ID"),
        _uuid_column("locale_id", "修订语言ID"),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="同一内容语言下的修订序号"),
        sa.Column("snapshot_jsonb", json_type, nullable=False, comment="内容快照JSON"),
        _uuid_column("changed_by", "变更用户ID", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="修订创建时间",
        ),
        _uuid_column("id", "主键ID"),
        sa.ForeignKeyConstraint(
            ["locale_id"],
            ["locales.id"],
            ondelete="RESTRICT",
            name=op.f("fk_content_revisions_locale_id_locales"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_content_revisions_changed_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_revisions")),
        sa.UniqueConstraint(
            "owner_type", "owner_id", "locale_id", "revision_no", name="uq_content_revision_number"
        ),
        comment="内容修订快照表",
    )

    op.create_table(
        "audit_logs",
        _uuid_column("user_id", "操作用户ID，匿名或用户被删除时为空", nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False, comment="审计动作"),
        sa.Column("target_type", sa.String(length=100), nullable=False, comment="目标实体类型"),
        sa.Column("target_id", sa.String(length=100), nullable=True, comment="目标实体ID"),
        sa.Column("ip", sa.String(length=45), nullable=True, comment="客户端IP地址"),
        sa.Column("user_agent", sa.Text(), nullable=True, comment="客户端User-Agent"),
        sa.Column("metadata_json", json_type, nullable=False, comment="审计结构化元数据"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="审计事件创建时间",
        ),
        _uuid_column("id", "主键ID"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL", name=op.f("fk_audit_logs_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        comment="操作审计日志表",
    )
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    """
    回退 Phase 3.2 基础结构并恢复邮箱 VARCHAR 类型。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None；按依赖逆序移除本 revision 对象。
    """
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("content_revisions")
    op.drop_index("ix_content_route_owner_locale", table_name="content_routes")
    op.drop_table("content_routes")
    op.drop_table("content_publications")
    op.drop_table("translation_statuses")
    op.drop_index(op.f("ix_auth_sessions_expires_at"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_token_hash"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ux_locales_single_default", table_name="locales")

    if op.get_bind().dialect.name == "postgresql":
        op.drop_index(op.f("ix_users_email"), table_name="users")
        op.alter_column(
            "users",
            "email",
            existing_type=postgresql.CITEXT(),
            type_=sa.String(length=320),
            existing_nullable=False,
            postgresql_using="email::text",
        )
        op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
