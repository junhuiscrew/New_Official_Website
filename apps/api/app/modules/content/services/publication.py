"""内容、翻译与路由一致发布事务服务。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.content.enums import PublicationStatus, TranslationState
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.localization.models import Locale

_TRANSITION_PERMISSIONS: dict[tuple[str, str], str] = {
    ("draft", "review"): "content.update",
    ("review", "scheduled"): "content.publish",
    ("review", "published"): "content.publish",
    ("scheduled", "published"): "content.publish",
    ("published", "archived"): "content.archive",
    ("archived", "draft"): "content.update",
}


async def invalidate_publication_after_translation_edit(
    session: AsyncSession,
    *,
    publication: ContentPublication,
    translation: TranslationStatus,
    route: ContentRoute,
    actor_id: uuid.UUID | None,
) -> None:
    """
    在正文修改后统一撤销审核、发布和公开索引状态。

    输入：session、同一 owner/locale 的 publication、translation、route 和 actor_id。
    输出：None；Translation 回到 draft，已发布内容回到 review，Route inactive/noindex。
    """
    owner_key = (publication.owner_type, publication.owner_id, publication.locale_id)
    if owner_key != (translation.owner_type, translation.owner_id, translation.locale_id) or (
        owner_key != (route.owner_type, route.owner_id, route.locale_id)
    ):
        raise AppException(409, "publication_owner_mismatch", "发布、翻译和路由必须属于同一内容语言")
    previous_publication_status = publication.status
    translation.status = TranslationState.DRAFT.value
    translation.reviewed_by = None
    translation.published_at = None
    if publication.status in {
        PublicationStatus.PUBLISHED.value,
        PublicationStatus.SCHEDULED.value,
    }:
        publication.status = PublicationStatus.REVIEW.value
    publication.published_at = None
    publication.scheduled_at = None
    route.active = False
    route.indexable = False
    write_audit_log(
        session,
        action="publication.invalidated_by_translation",
        target_type=publication.owner_type,
        target_id=str(publication.owner_id),
        user_id=actor_id,
        metadata={
            "from": previous_publication_status,
            "to": publication.status,
            "locale_id": str(publication.locale_id),
        },
    )
    await session.flush()


async def transition_publication(
    session: AsyncSession,
    *,
    publication: ContentPublication,
    translation: TranslationStatus,
    route: ContentRoute,
    target_status: PublicationStatus,
    actor_permissions: set[str],
    actor_id: uuid.UUID | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    在调用方事务内同步更新内容、翻译、路由和审计状态。

    输入：
        session: AsyncSession，调用方控制的数据库事务。
        publication: ContentPublication，内容发布状态记录。
        translation: TranslationStatus，同一 owner/locale 的翻译状态。
        route: ContentRoute，同一 owner/locale 的规范路由。
        target_status: PublicationStatus，目标发布状态。
        actor_permissions: set[str]，服务端解析出的当前权限。
        actor_id: uuid.UUID | None，操作用户ID。
        ip: str | None，可信请求上下文解析出的客户端 IP。
        user_agent: str | None，请求 User-Agent。

    输出：None；非法转换或权限不足时抛出 AppException。
    """
    # 先锁 Locale，再按固定顺序刷新三类记录；并发停用/发布和双发布只能串行决策。
    locale = await session.scalar(
        select(Locale).where(Locale.id == publication.locale_id).with_for_update()
    )
    locked_records = []
    for model, record in (
        (ContentPublication, publication),
        (TranslationStatus, translation),
        (ContentRoute, route),
    ):
        locked = await session.scalar(
            select(model)
            .where(model.id == record.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked is None:
            raise AppException(409, "publication_record_missing", "发布关联记录不存在")
        locked_records.append(locked)
    publication, translation, route = locked_records

    publication_key = (publication.owner_type, publication.owner_id, publication.locale_id)
    if publication_key != (translation.owner_type, translation.owner_id, translation.locale_id) or (
        publication_key != (route.owner_type, route.owner_id, route.locale_id)
    ):
        raise AppException(
            409, "publication_owner_mismatch", "发布、翻译和路由必须属于同一内容语言"
        )
    if not route.is_canonical:
        raise AppException(409, "canonical_route_required", "只有规范路由可以进入发布流程")
    transition = (publication.status, target_status.value)
    required_permission = _TRANSITION_PERMISSIONS.get(transition)
    if required_permission is None:
        raise AppException(409, "invalid_publication_transition", "不允许的发布状态转换")
    if required_permission not in actor_permissions:
        raise AppException(403, "permission_denied", "没有执行发布状态转换的权限")
    if target_status is PublicationStatus.PUBLISHED and translation.status not in {
        TranslationState.HUMAN_REVIEWED.value,
        TranslationState.PUBLISHED.value,
    }:
        raise AppException(409, "translation_not_reviewed", "翻译完成人工审核后才能发布")
    if target_status in {PublicationStatus.SCHEDULED, PublicationStatus.PUBLISHED}:
        if locale is None or not locale.is_enabled:
            raise AppException(409, "locale_disabled", "禁用或不存在的语言不能进入公开发布流程")

    previous_status = publication.status
    now = datetime.now(UTC)
    publication.status = target_status.value
    if target_status is PublicationStatus.PUBLISHED:
        publication.published_at = now
        translation.status = TranslationState.PUBLISHED.value
        translation.published_at = now
        route.active = True
        route.indexable = True
    else:
        # SEO/GEO 边界：非 published 内容不能通过公开路由被索引。
        route.active = False
        route.indexable = False

    write_audit_log(
        session,
        action="publication.status_change",
        target_type=publication.owner_type,
        target_id=str(publication.owner_id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"from": previous_status, "to": target_status.value},
    )
    write_audit_log(
        session,
        action="route.change",
        target_type=route.owner_type,
        target_id=str(route.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"active": route.active, "indexable": route.indexable},
    )
    await session.flush()
