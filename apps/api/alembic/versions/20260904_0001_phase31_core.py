"""创建 Phase 3.1 用户、RBAC 与语言基础表。

Revision ID: 20260904_0001
Revises: None
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    创建 Phase 3.1 六张基础表及其索引和外键。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None；目标数据库升级到本 revision。
    """
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False, comment="用户邮箱"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="密码哈希"),
        sa.Column("display_name", sa.String(length=100), nullable=True, comment="用户显示名称"),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False, comment="是否启用"
        ),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        comment="用户表",
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=64), nullable=False, comment="角色唯一名称"),
        sa.Column("display_name", sa.String(length=100), nullable=False, comment="角色显示名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="角色说明"),
        sa.Column(
            "is_system",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="是否系统内置角色",
        ),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        comment="角色表",
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=100), nullable=False, comment="权限唯一编码"),
        sa.Column("display_name", sa.String(length=100), nullable=False, comment="权限显示名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="权限说明"),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        comment="权限表",
    )
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)

    op.create_table(
        "locales",
        sa.Column("code", sa.String(length=16), nullable=False, comment="标准语言代码"),
        sa.Column("slug", sa.String(length=16), nullable=False, comment="语言URL路径标识"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="语言英文名称"),
        sa.Column("native_name", sa.String(length=100), nullable=False, comment="语言本地名称"),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否默认语言",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="是否启用：true启用，false停用",
        ),
        sa.Column(
            "sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="显示排序值"
        ),
        sa.Column("id", sa.Uuid(), nullable=False, comment="主键ID"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locales")),
        comment="站点语言表",
    )
    op.create_index(op.f("ix_locales_code"), "locales", ["code"], unique=True)
    op.create_index(op.f("ix_locales_slug"), "locales", ["slug"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False, comment="用户ID"),
        sa.Column("role_id", sa.Uuid(), nullable=False, comment="角色ID"),
        sa.Column("assigned_by", sa.Uuid(), nullable=True, comment="分配操作用户ID"),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="角色分配时间",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"], ["users.id"], name=op.f("fk_user_roles_assigned_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
        comment="用户角色关联表",
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False, comment="角色ID"),
        sa.Column("permission_id", sa.Uuid(), nullable=False, comment="权限ID"),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="权限授予时间",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id_roles"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
        comment="角色权限关联表",
    )


def downgrade() -> None:
    """
    按外键依赖逆序删除 Phase 3.1 基础表。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None；目标数据库回退到基础表创建前。
    """
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_locales_slug"), table_name="locales")
    op.drop_index(op.f("ix_locales_code"), table_name="locales")
    op.drop_table("locales")
    op.drop_index(op.f("ix_permissions_code"), table_name="permissions")
    op.drop_table("permissions")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_table("roles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

