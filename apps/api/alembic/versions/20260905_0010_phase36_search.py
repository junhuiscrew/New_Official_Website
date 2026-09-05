"""为 Phase 3.6 六类公开搜索内容启用 trigram 并建立名称索引。"""

from collections.abc import Sequence

from alembic import op

revision = "20260905_0010"
down_revision = "20260904_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 索引名、翻译表及公开搜索标题字段保持显式对应，便于安全降级与运维核查。
_TRIGRAM_INDEXES = (
    (
        "ix_product_translations_name_trgm",
        "product_translations",
        "name",
    ),
    (
        "ix_material_translations_name_trgm",
        "material_translations",
        "name",
    ),
    (
        "ix_application_translations_name_trgm",
        "application_translations",
        "name",
    ),
    (
        "ix_solution_translations_name_trgm",
        "solution_translations",
        "name",
    ),
    (
        "ix_knowledge_article_translations_title_trgm",
        "knowledge_article_translations",
        "title",
    ),
    (
        "ix_case_study_translations_title_trgm",
        "case_study_translations",
        "title",
    ),
)


def upgrade() -> None:
    """
    安装共享 pg_trgm 扩展，并为实际公开搜索 UNION 的标题列建立 GIN 索引。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None，数据库获得六个可命名管理的 trigram 索引。
    """
    # SQLite 仅用于单元迁移回归，不支持 PostgreSQL 扩展和操作符类。
    if op.get_bind().dialect.name != "postgresql":
        return
    # IF NOT EXISTS 允许复用数据库中由其他消费者预先安装的共享扩展。
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in _TRIGRAM_INDEXES:
        op.create_index(
            index_name,
            table_name,
            [column_name],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={column_name: "gin_trgm_ops"},
        )


def downgrade() -> None:
    """
    仅删除本迁移创建的命名索引，保留可能被其他模块复用的 pg_trgm 扩展。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None，按逆序移除六个搜索索引。
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    for index_name, table_name, _column_name in reversed(_TRIGRAM_INDEXES):
        op.drop_index(index_name, table_name=table_name)
