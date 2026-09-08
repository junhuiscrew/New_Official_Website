"""创建 Privacy P1 不可变版本、唯一公开指针与 RFQ 版本证据。"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260908_0012"
down_revision = "20260907_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PRIVACY_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("8e268dc8-8af8-4cbf-9b7c-c23214188e01", "privacy.read", "读取隐私政策工作区"),
    ("8e268dc8-8af8-4cbf-9b7c-c23214188e02", "privacy.edit", "创建和编辑隐私政策草稿"),
    ("8e268dc8-8af8-4cbf-9b7c-c23214188e03", "privacy.review", "人工审核隐私政策翻译"),
    ("8e268dc8-8af8-4cbf-9b7c-c23214188e04", "privacy.publish", "发布隐私政策版本"),
    ("8e268dc8-8af8-4cbf-9b7c-c23214188e05", "privacy.history", "读取隐私政策历史版本"),
)

_PRIVACY_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "super_admin": tuple(item[1] for item in _PRIVACY_PERMISSIONS),
    "content_admin": tuple(item[1] for item in _PRIVACY_PERMISSIONS),
    "editor": ("privacy.read", "privacy.edit"),
    "translator": ("privacy.read", "privacy.edit"),
    "reviewer": ("privacy.read", "privacy.review", "privacy.publish", "privacy.history"),
}


def _install_postgresql_guards() -> None:
    """
    安装 Privacy 已审核/已发布版本及共享生命周期的数据库最终防线。

    输入：无，使用 Alembic 当前 PostgreSQL 连接。
    输出：None，创建触发器函数与触发器。
    """
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_notice_immutable_guard()
        RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM translation_statuses
                WHERE owner_type = 'privacy_notice_version'
                  AND owner_id = OLD.id
                  AND status IN ('human_reviewed', 'published')
            ) OR EXISTS (
                SELECT 1 FROM content_publications
                WHERE owner_type = 'privacy_notice_version'
                  AND owner_id = OLD.id
                  AND status = 'published'
            ) OR EXISTS (
                SELECT 1 FROM privacy_page_states WHERE current_version_id = OLD.id
            ) OR EXISTS (
                SELECT 1 FROM rfqs WHERE privacy_notice_version_id = OLD.id
            ) THEN
                RAISE EXCEPTION 'privacy_notice_immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_notice_version_immutable
        BEFORE UPDATE OR DELETE ON privacy_notice_versions
        FOR EACH ROW EXECUTE FUNCTION privacy_notice_immutable_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_translation_immutable_guard()
        RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM translation_statuses
                WHERE owner_type = 'privacy_notice_version'
                  AND owner_id = OLD.privacy_notice_version_id
                  AND status IN ('human_reviewed', 'published')
            ) OR EXISTS (
                SELECT 1 FROM privacy_page_states
                WHERE current_version_id = OLD.privacy_notice_version_id
            ) OR EXISTS (
                SELECT 1 FROM rfqs
                WHERE privacy_notice_version_id = OLD.privacy_notice_version_id
            ) THEN
                RAISE EXCEPTION 'privacy_notice_translation_immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_translation_immutable
        BEFORE UPDATE OR DELETE ON privacy_notice_version_translations
        FOR EACH ROW EXECUTE FUNCTION privacy_translation_immutable_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_translation_status_guard()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.owner_type = 'privacy_notice_version' THEN
                IF TG_OP = 'DELETE' AND OLD.status IN ('human_reviewed', 'published') THEN
                    RAISE EXCEPTION 'privacy_translation_status_immutable';
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    IF NEW.owner_type <> OLD.owner_type
                       OR NEW.owner_id <> OLD.owner_id
                       OR NEW.locale_id <> OLD.locale_id THEN
                        RAISE EXCEPTION 'privacy_translation_status_owner_immutable';
                    END IF;
                    IF OLD.status = 'published' THEN
                        RAISE EXCEPTION 'privacy_translation_status_immutable';
                    END IF;
                    IF OLD.status = 'human_reviewed'
                       AND NOT (NEW.status = 'published'
                                AND NEW.source_locale_id IS NOT DISTINCT FROM OLD.source_locale_id
                                AND NEW.translated_by IS NOT DISTINCT FROM OLD.translated_by
                                AND NEW.reviewed_by IS NOT DISTINCT FROM OLD.reviewed_by) THEN
                        RAISE EXCEPTION 'privacy_translation_status_immutable';
                    END IF;
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_translation_status_immutable
        BEFORE UPDATE OR DELETE ON translation_statuses
        FOR EACH ROW EXECUTE FUNCTION privacy_translation_status_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_publication_guard()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.owner_type = 'privacy_notice_version' THEN
                IF TG_OP = 'DELETE' AND OLD.status = 'published' THEN
                    RAISE EXCEPTION 'privacy_publication_immutable';
                END IF;
                IF TG_OP = 'UPDATE' THEN
                    IF NEW.owner_type <> OLD.owner_type
                       OR NEW.owner_id <> OLD.owner_id
                       OR NEW.locale_id <> OLD.locale_id THEN
                        RAISE EXCEPTION 'privacy_publication_owner_immutable';
                    END IF;
                    IF OLD.status = 'published' THEN
                        RAISE EXCEPTION 'privacy_publication_immutable';
                    END IF;
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_publication_immutable
        BEFORE UPDATE OR DELETE ON content_publications
        FOR EACH ROW EXECUTE FUNCTION privacy_publication_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_lifecycle_owner_guard()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.owner_type = 'privacy_notice_version'
               AND NOT EXISTS (SELECT 1 FROM privacy_notice_versions WHERE id = NEW.owner_id) THEN
                RAISE EXCEPTION 'privacy_lifecycle_owner_missing';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_translation_owner
        BEFORE INSERT OR UPDATE ON translation_statuses
        FOR EACH ROW EXECUTE FUNCTION privacy_lifecycle_owner_guard();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_publication_owner
        BEFORE INSERT OR UPDATE ON content_publications
        FOR EACH ROW EXECUTE FUNCTION privacy_lifecycle_owner_guard();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_page_pointer_guard()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.current_version_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM privacy_notice_versions
                WHERE id = NEW.current_version_id AND site_page_id = NEW.site_page_id
            ) THEN
                RAISE EXCEPTION 'privacy_current_pointer_owner_mismatch';
            END IF;
            IF NEW.draft_version_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM privacy_notice_versions
                WHERE id = NEW.draft_version_id AND site_page_id = NEW.site_page_id
            ) THEN
                RAISE EXCEPTION 'privacy_draft_pointer_owner_mismatch';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_page_pointer_owner
        BEFORE INSERT OR UPDATE ON privacy_page_states
        FOR EACH ROW EXECUTE FUNCTION privacy_page_pointer_guard();
        """
    )


def _drop_postgresql_guards() -> None:
    """
    按依赖逆序移除 Privacy PostgreSQL 触发器与函数。

    输入：无，使用 Alembic 当前 PostgreSQL 连接。
    输出：None。
    """
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_page_pointer_owner ON privacy_page_states")
    op.execute("DROP FUNCTION IF EXISTS privacy_page_pointer_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_publication_owner ON content_publications")
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_translation_owner ON translation_statuses")
    op.execute("DROP FUNCTION IF EXISTS privacy_lifecycle_owner_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_publication_immutable ON content_publications")
    op.execute("DROP FUNCTION IF EXISTS privacy_publication_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_translation_status_immutable ON translation_statuses")
    op.execute("DROP FUNCTION IF EXISTS privacy_translation_status_guard()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_privacy_translation_immutable "
        "ON privacy_notice_version_translations"
    )
    op.execute("DROP FUNCTION IF EXISTS privacy_translation_immutable_guard()")
    op.execute("DROP TRIGGER IF EXISTS trg_privacy_notice_version_immutable ON privacy_notice_versions")
    op.execute("DROP FUNCTION IF EXISTS privacy_notice_immutable_guard()")


def _insert_privacy_permissions() -> None:
    """
    最小化写入 Privacy 权限及允许角色的缺失关联。

    输入：无，读取既有 roles 并写 permissions/role_permissions。
    输出：None；不修改 sales、seo_manager 或任何既有关联。
    """
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permission_table,
        [
            {
                "id": uuid.UUID(permission_id),
                "code": code,
                "display_name": code,
                "description": description,
            }
            for permission_id, code, description in _PRIVACY_PERMISSIONS
        ],
    )
    connection = op.get_bind()
    for role_name, permission_codes in _PRIVACY_ROLE_PERMISSIONS.items():
        for permission_code in permission_codes:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id, granted_at)
                    SELECT roles.id, permissions.id, CURRENT_TIMESTAMP
                    FROM roles, permissions
                    WHERE roles.name = :role_name
                      AND permissions.code = :permission_code
                      AND NOT EXISTS (
                          SELECT 1 FROM role_permissions existing
                          WHERE existing.role_id = roles.id
                            AND existing.permission_id = permissions.id
                      )
                    """
                ),
                {"role_name": role_name, "permission_code": permission_code},
            )


def upgrade() -> None:
    """
    创建 Privacy P1 数据结构、保护触发器和 nullable RFQ 证据字段。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；不插入政策正文、日期、审核者或发布版本。
    """
    with op.batch_alter_table("site_pages") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_site_pages_site_page_system_key_value"), type_="check"
        )
        batch_op.create_check_constraint(
            "site_page_system_key_value", "system_key IN ('products','privacy')"
        )
        batch_op.alter_column(
            "system_key",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            comment="系统稳定页面键：仅允许products或privacy",
        )

    op.create_table(
        "privacy_notice_versions",
        sa.Column("site_page_id", sa.Uuid(), nullable=False, comment="稳定隐私页面ID"),
        sa.Column("version_no", sa.Integer(), nullable=False, comment="服务端版本序号"),
        sa.Column(
            "version_label", sa.String(length=40), nullable=False, comment="服务端生成的公开版本标签"
        ),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True, comment="政策生效时间"),
        sa.Column(
            "row_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="草稿乐观并发版本号",
        ),
        sa.Column("cloned_from_id", sa.Uuid(), nullable=True, comment="克隆来源隐私版本ID"),
        sa.Column("created_by", sa.Uuid(), nullable=True, comment="创建用户ID"),
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
        sa.CheckConstraint("version_no > 0", name="privacy_notice_version_number_positive"),
        sa.CheckConstraint("row_version > 0", name="privacy_notice_row_version_positive"),
        sa.ForeignKeyConstraint(["site_page_id"], ["site_pages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["cloned_from_id"], ["privacy_notice_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_label", name="uq_privacy_notice_versions_version_label"),
        sa.UniqueConstraint(
            "site_page_id", "version_no", name="uq_privacy_notice_version_number"
        ),
        comment="隐私政策不可变版本表",
    )
    op.create_table(
        "privacy_notice_version_translations",
        sa.Column("privacy_notice_version_id", sa.Uuid(), nullable=False, comment="隐私政策版本ID"),
        sa.Column("locale_id", sa.Uuid(), nullable=False, comment="政策语言ID"),
        sa.Column("title", sa.String(length=300), nullable=True, comment="规范化政策标题"),
        sa.Column(
            "body_markdown", sa.Text(), nullable=True, comment="规范化且不含活动内容的Markdown正文"
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
            comment="规范化标题与正文的SHA-256十六进制哈希",
        ),
        sa.Column(
            "hash_algorithm",
            sa.String(length=40),
            server_default="sha256-nfc-json-v1",
            nullable=False,
            comment="内容哈希算法及规范化版本",
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
            "((title IS NULL AND body_markdown IS NULL AND content_hash IS NULL) OR "
            "(title IS NOT NULL AND body_markdown IS NOT NULL AND content_hash IS NOT NULL))",
            name="privacy_translation_content_complete",
        ),
        sa.ForeignKeyConstraint(
            ["privacy_notice_version_id"], ["privacy_notice_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["locale_id"], ["locales.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "privacy_notice_version_id",
            "locale_id",
            name="uq_privacy_notice_version_translation_locale",
        ),
        comment="隐私政策版本多语言正文表",
    )
    op.create_table(
        "privacy_page_states",
        sa.Column("site_page_id", sa.Uuid(), nullable=False, comment="稳定隐私页面ID"),
        sa.Column("current_version_id", sa.Uuid(), nullable=True, comment="当前唯一公开隐私版本ID"),
        sa.Column("draft_version_id", sa.Uuid(), nullable=True, comment="当前后台工作草稿版本ID"),
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
            "current_version_id IS NULL OR draft_version_id IS NULL OR "
            "current_version_id <> draft_version_id",
            name="privacy_page_distinct_pointers",
        ),
        sa.ForeignKeyConstraint(["site_page_id"], ["site_pages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["current_version_id"], ["privacy_notice_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["draft_version_id"], ["privacy_notice_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_page_id", name="uq_privacy_page_state_site_page"),
        comment="隐私页面当前版本状态表",
    )

    with op.batch_alter_table("rfqs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "privacy_notice_version_id",
                sa.Uuid(),
                nullable=True,
                comment="确认时不可变隐私政策版本ID；历史询盘为空",
            )
        )
        batch_op.add_column(
            sa.Column(
                "privacy_version_label",
                sa.String(length=40),
                nullable=True,
                comment="确认时公开隐私政策版本标签；历史询盘为空",
            )
        )
        batch_op.add_column(
            sa.Column(
                "privacy_policy_locale",
                sa.String(length=16),
                nullable=True,
                comment="确认时隐私政策语言；历史询盘为空",
            )
        )
        batch_op.add_column(
            sa.Column(
                "privacy_content_hash",
                sa.String(length=64),
                nullable=True,
                comment="确认时隐私政策内容哈希；历史询盘为空",
            )
        )
        batch_op.add_column(
            sa.Column(
                "privacy_canonical_url",
                sa.String(length=1000),
                nullable=True,
                comment="确认时隐私政策规范URL；历史询盘为空",
            )
        )
        batch_op.add_column(
            sa.Column(
                "privacy_confirmed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="服务端确认隐私政策上下文时间；历史询盘为空",
            )
        )
        batch_op.create_foreign_key(
            "fk_rfqs_privacy_notice_version_id_privacy_notice_versions",
            "privacy_notice_versions",
            ["privacy_notice_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "rfq_privacy_metadata_all_or_none",
            "((privacy_notice_version_id IS NULL AND privacy_version_label IS NULL "
            "AND privacy_policy_locale IS NULL AND privacy_content_hash IS NULL "
            "AND privacy_canonical_url IS NULL AND privacy_confirmed_at IS NULL) OR "
            "(privacy_notice_version_id IS NOT NULL AND privacy_version_label IS NOT NULL "
            "AND privacy_policy_locale IS NOT NULL AND privacy_content_hash IS NOT NULL "
            "AND privacy_canonical_url IS NOT NULL AND privacy_confirmed_at IS NOT NULL))",
        )

    _insert_privacy_permissions()
    if op.get_bind().dialect.name == "postgresql":
        _install_postgresql_guards()


def downgrade() -> None:
    """
    按依赖逆序移除 Privacy P1 结构和最小权限定义。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；不会修改旧 RFQ 的其他字段。
    """
    if op.get_bind().dialect.name == "postgresql":
        _drop_postgresql_guards()

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code IN "
            "('privacy.read','privacy.edit','privacy.review','privacy.publish','privacy.history'))"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE code IN "
            "('privacy.read','privacy.edit','privacy.review','privacy.publish','privacy.history')"
        )
    )
    with op.batch_alter_table("rfqs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_rfqs_rfq_privacy_metadata_all_or_none"), type_="check"
        )
        batch_op.drop_constraint(
            "fk_rfqs_privacy_notice_version_id_privacy_notice_versions", type_="foreignkey"
        )
        batch_op.drop_column("privacy_confirmed_at")
        batch_op.drop_column("privacy_canonical_url")
        batch_op.drop_column("privacy_content_hash")
        batch_op.drop_column("privacy_policy_locale")
        batch_op.drop_column("privacy_version_label")
        batch_op.drop_column("privacy_notice_version_id")

    # Privacy 版本使用多态 owner 关联共享状态表；回退前必须显式清理，避免留下悬空记录。
    connection.execute(
        sa.text("DELETE FROM content_revisions WHERE owner_type = 'privacy_notice_version'")
    )
    connection.execute(
        sa.text("DELETE FROM translation_statuses WHERE owner_type = 'privacy_notice_version'")
    )
    connection.execute(
        sa.text("DELETE FROM content_publications WHERE owner_type = 'privacy_notice_version'")
    )
    connection.execute(sa.text("DELETE FROM audit_logs WHERE action LIKE 'privacy.%'"))

    # 稳定 Privacy 页面同样复用 SitePage 的多态生命周期；只删除 system_key=privacy 的依赖。
    privacy_page_ids = "(SELECT id FROM site_pages WHERE system_key = 'privacy')"
    for table_name in (
        "content_revisions",
        "translation_statuses",
        "content_publications",
        "content_routes",
    ):
        connection.execute(
            sa.text(
                f"DELETE FROM {table_name} WHERE owner_type = 'site_page' "
                f"AND owner_id IN {privacy_page_ids}"
            )
        )
    connection.execute(
        sa.text(
            "DELETE FROM site_page_translations WHERE site_page_id IN "
            "(SELECT id FROM site_pages WHERE system_key = 'privacy')"
        )
    )

    op.drop_table("privacy_page_states")
    op.drop_table("privacy_notice_version_translations")
    op.drop_table("privacy_notice_versions")
    connection.execute(sa.text("DELETE FROM site_pages WHERE system_key = 'privacy'"))
    with op.batch_alter_table("site_pages") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_site_pages_site_page_system_key_value"), type_="check"
        )
        batch_op.create_check_constraint(
            "site_page_system_key_value", "system_key IN ('products')"
        )
        batch_op.alter_column(
            "system_key",
            existing_type=sa.String(length=64),
            existing_nullable=False,
            comment="系统稳定页面键：仅允许products",
        )
