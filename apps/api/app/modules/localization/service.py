"""Locale 唯一性、启停与默认语言事务服务。"""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.localization.models import Locale
from app.modules.localization.schemas import LocaleCreate, LocaleUpdate

_FROZEN_LOCALE_IDENTIFIERS = {"zh-CN": "zh-cn", "en": "en"}


async def list_locales(session: AsyncSession) -> list[Locale]:
    """
    按显示顺序列出全部语言配置。

    输入：session，数据库 session。

    输出：list[Locale]，按 sort_order 与 code 稳定排序。
    """
    return list(
        (await session.scalars(select(Locale).order_by(Locale.sort_order, Locale.code))).all()
    )


async def _get_locale_or_404(session: AsyncSession, locale_id: uuid.UUID) -> Locale:
    """按主键加行锁获取 Locale，不存在时抛出 404 业务异常。"""
    locale = await session.scalar(select(Locale).where(Locale.id == locale_id).with_for_update())
    if locale is None:
        raise AppException(404, "locale_not_found", "语言配置不存在")
    return locale


async def _ensure_unique(
    session: AsyncSession,
    *,
    code: str,
    slug: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """验证 code 与 slug 不与另一条 Locale 冲突。"""
    statement = select(Locale).where(or_(Locale.code == code, Locale.slug == slug))
    if exclude_id is not None:
        statement = statement.where(Locale.id != exclude_id)
    if await session.scalar(statement) is not None:
        raise AppException(409, "locale_conflict", "Locale code 或 slug 已存在")


async def create_locale(session: AsyncSession, payload: LocaleCreate) -> Locale:
    """
    创建非默认语言配置并保证 code/slug 唯一。

    输入：session 与 LocaleCreate。

    输出：Locale，已加入当前事务的新语言。
    """
    await _ensure_unique(session, code=payload.code, slug=payload.slug)
    locale = Locale(**payload.model_dump(), is_default=False)
    session.add(locale)
    await session.flush()
    return locale


async def update_locale(
    session: AsyncSession, locale_id: uuid.UUID, payload: LocaleUpdate
) -> Locale:
    """
    更新语言字段，并阻止直接禁用默认语言。

    输入：session、locale_id 和部分更新数据。

    输出：Locale，更新后的语言实体。
    """
    locale = await _get_locale_or_404(session, locale_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_enabled") is False and locale.is_default:
        raise AppException(409, "default_locale_required", "请先切换默认语言再禁用")
    identifier_changed = ("code" in changes and changes["code"] != locale.code) or (
        "slug" in changes and changes["slug"] != locale.slug
    )
    if identifier_changed and locale.code in _FROZEN_LOCALE_IDENTIFIERS:
        raise AppException(409, "frozen_locale_identifier", "基础语言的 code 与 slug 已冻结")
    if identifier_changed:
        referenced = False
        for model in (ContentRoute, ContentPublication, TranslationStatus):
            if (
                await session.scalar(select(model.id).where(model.locale_id == locale.id).limit(1))
                is not None
            ):
                referenced = True
                break
        if referenced:
            raise AppException(
                409, "locale_identifier_in_use", "已被内容引用的语言不能修改 code 或 slug"
            )
    if changes.get("is_enabled") is False:
        public_route = await session.scalar(
            select(ContentRoute.id)
            .where(
                ContentRoute.locale_id == locale.id,
                or_(ContentRoute.active.is_(True), ContentRoute.indexable.is_(True)),
            )
            .limit(1)
        )
        public_content = await session.scalar(
            select(ContentPublication.id)
            .where(
                ContentPublication.locale_id == locale.id,
                ContentPublication.status.in_(("scheduled", "published")),
            )
            .limit(1)
        )
        if public_route is not None or public_content is not None:
            raise AppException(
                409, "locale_has_public_content", "存在公开或计划发布内容的语言不能停用"
            )
    await _ensure_unique(
        session,
        code=str(changes.get("code", locale.code)),
        slug=str(changes.get("slug", locale.slug)),
        exclude_id=locale.id,
    )
    for field_name, value in changes.items():
        if value is not None:
            setattr(locale, field_name, value)
    await session.flush()
    return locale


async def set_default_locale(session: AsyncSession, locale_id: uuid.UUID) -> Locale:
    """
    在单一事务内清除旧默认值并设置新的已启用默认语言。

    输入：session 与目标 locale_id。

    输出：Locale，新默认语言。
    """
    # 所有默认语言切换都按主键顺序锁定完整 Locale 集合，避免不同目标请求互相等待。
    locked_locales = list(
        (await session.scalars(select(Locale).order_by(Locale.id).with_for_update())).all()
    )
    locale = next((item for item in locked_locales if item.id == locale_id), None)
    if locale is None:
        raise AppException(404, "locale_not_found", "语言配置不存在")
    if not locale.is_enabled:
        raise AppException(409, "locale_disabled", "禁用语言不能设为默认语言")
    await session.execute(update(Locale).values(is_default=False))
    await session.flush()
    locale.is_default = True
    await session.flush()
    return locale
