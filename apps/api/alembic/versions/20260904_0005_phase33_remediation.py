"""Phase 3.3 remediation：停用内部实体遗留公开生命周期。

Revision ID: 20260904_0005
Revises: 20260904_0004
Create Date: 2026-09-04
"""

from alembic import op

revision = "20260904_0005"
down_revision = "20260904_0004"
branch_labels = None
depends_on = None

_INTERNAL_OWNER_TYPES = (
    "product_model",
    "specification_group",
    "specification_definition",
)


def upgrade() -> None:
    """
    精确归档内部实体的遗留 Publication，并停用其 Route。

    输入：无。
    输出：None；不会影响 Product、Material 等公开主实体。
    """
    owner_types = ", ".join(f"'{owner_type}'" for owner_type in _INTERNAL_OWNER_TYPES)
    op.execute(
        f"UPDATE content_publications SET status = 'archived', scheduled_at = NULL "
        f"WHERE owner_type IN ({owner_types})"
    )
    op.execute(
        f"UPDATE content_routes SET active = false, indexable = false "
        f"WHERE owner_type IN ({owner_types})"
    )


def downgrade() -> None:
    """
    保留安全的不可逆清理结果。

    输入：无。
    输出：None；历史记录的原公开状态不可可靠推断，因此不自动恢复。
    """

