"""加强规范路由唯一性。

Revision ID: 20260904_0003
Revises: 20260904_0002
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0003"
down_revision: str | None = "20260904_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    为每个内容语言增加至多一个规范路由的数据库约束。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None；创建跨 PostgreSQL/SQLite 的部分唯一索引。
    """
    op.create_index(
        "ux_content_routes_one_canonical",
        "content_routes",
        ["owner_type", "owner_id", "locale_id"],
        unique=True,
        postgresql_where=sa.text("is_canonical"),
        sqlite_where=sa.text("is_canonical = 1"),
    )


def downgrade() -> None:
    """
    移除规范路由唯一索引。

    输入：由 Alembic migration context 提供数据库连接。

    输出：None。
    """
    op.drop_index("ux_content_routes_one_canonical", table_name="content_routes")
