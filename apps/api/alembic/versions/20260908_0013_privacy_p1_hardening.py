"""加固 Privacy 审核状态迁移与真实审核者数据库约束。"""

from collections.abc import Sequence

from alembic import op

revision = "20260908_0013"
down_revision = "20260908_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_hardened_translation_status_guard() -> None:
    """
    替换 Privacy 翻译状态触发器，约束合法生命周期和审核者证据。

    输入：无，使用 Alembic 当前 PostgreSQL 连接。
    输出：None；仅影响 owner_type=privacy_notice_version 的记录。
    """
    op.execute(
        "DROP TRIGGER IF EXISTS trg_privacy_translation_status_immutable "
        "ON translation_statuses"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION privacy_translation_status_guard()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.owner_type = 'privacy_notice_version'
                   AND (NEW.status <> 'draft'
                        OR NEW.reviewed_by IS NOT NULL
                        OR NEW.published_at IS NOT NULL) THEN
                    RAISE EXCEPTION 'privacy_translation_status_transition_invalid';
                END IF;
                RETURN NEW;
            END IF;

            IF OLD.owner_type = 'privacy_notice_version' THEN
                IF TG_OP = 'DELETE' THEN
                    IF OLD.status IN ('human_reviewed', 'published') THEN
                        RAISE EXCEPTION 'privacy_translation_status_immutable';
                    END IF;
                    RETURN OLD;
                END IF;

                IF NEW.owner_type <> OLD.owner_type
                   OR NEW.owner_id <> OLD.owner_id
                   OR NEW.locale_id <> OLD.locale_id THEN
                    RAISE EXCEPTION 'privacy_translation_status_owner_immutable';
                END IF;

                IF OLD.status = 'draft' AND NEW.status = 'draft' THEN
                    IF NEW.reviewed_by IS NOT NULL OR NEW.published_at IS NOT NULL THEN
                        RAISE EXCEPTION 'privacy_translation_status_transition_invalid';
                    END IF;
                    RETURN NEW;
                END IF;

                IF OLD.status = 'draft' AND NEW.status = 'human_reviewed' THEN
                    IF NEW.reviewed_by IS NULL OR NEW.published_at IS NOT NULL THEN
                        RAISE EXCEPTION 'privacy_translation_reviewer_required';
                    END IF;
                    RETURN NEW;
                END IF;

                IF OLD.status = 'human_reviewed' AND NEW.status = 'published' THEN
                    IF NEW.reviewed_by IS NULL
                       OR NEW.published_at IS NULL
                       OR NEW.source_locale_id IS DISTINCT FROM OLD.source_locale_id
                       OR NEW.translated_by IS DISTINCT FROM OLD.translated_by
                       OR NEW.reviewed_by IS DISTINCT FROM OLD.reviewed_by THEN
                        RAISE EXCEPTION 'privacy_translation_status_transition_invalid';
                    END IF;
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'privacy_translation_status_transition_invalid';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_privacy_translation_status_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON translation_statuses
        FOR EACH ROW EXECUTE FUNCTION privacy_translation_status_guard();
        """
    )


def _restore_p1_translation_status_guard() -> None:
    """
    恢复 0012 的原始已审核/已发布不可变保护。

    输入：无，使用 Alembic 当前 PostgreSQL 连接。
    输出：None。
    """
    op.execute(
        "DROP TRIGGER IF EXISTS trg_privacy_translation_status_immutable "
        "ON translation_statuses"
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


def upgrade() -> None:
    """
    安装 Privacy 翻译状态数据库加固。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None；不写政策正文、不改变现有生命周期状态。
    """
    if op.get_bind().dialect.name == "postgresql":
        _install_hardened_translation_status_guard()


def downgrade() -> None:
    """
    回退到 0012 的 Privacy 翻译状态保护。

    输入：无，由 Alembic 提供当前迁移连接。
    输出：None。
    """
    if op.get_bind().dialect.name == "postgresql":
        _restore_p1_translation_status_guard()
