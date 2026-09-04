"""Phase 3.2 冻结的共享内容状态枚举。"""

from enum import StrEnum


class PublicationStatus(StrEnum):
    """统一发布状态：草稿、审核、定时、已发布、已归档。"""

    DRAFT = "draft"
    REVIEW = "review"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TranslationState(StrEnum):
    """统一翻译状态：缺失、草稿、机翻、人工审核、已发布。"""

    MISSING = "missing"
    DRAFT = "draft"
    MACHINE_TRANSLATED = "machine_translated"
    HUMAN_REVIEWED = "human_reviewed"
    PUBLISHED = "published"
