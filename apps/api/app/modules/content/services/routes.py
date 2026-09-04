"""稳定多语言 Content Route 注册服务。"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.content.models import ContentRoute
from app.modules.localization.models import Locale

_KEBAB_SEGMENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_content_path(path: str, locale_slug: str) -> None:
    """
    验证路由具有语言前缀、尾斜杠与小写 kebab-case 分段。

    输入：
        path: str，站内绝对路径。
        locale_slug: str，Locale URL slug。

    输出：None；格式不稳定时抛出 ValueError。
    """
    if not path.startswith("/") or not path.endswith("/") or path.lower() != path:
        raise ValueError("内容路径必须是小写、首尾带斜杠的绝对路径")
    segments = path.strip("/").split("/")
    if (
        not segments
        or segments[0] != locale_slug
        or any(not _KEBAB_SEGMENT.fullmatch(segment) for segment in segments)
    ):
        raise ValueError("内容路径必须使用语言前缀和 kebab-case 分段")


async def create_content_route(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    locale: Locale,
    path: str,
) -> ContentRoute:
    """
    注册默认非公开、不可索引的唯一内容路由。

    输入：session、owner_type、owner_id、locale 与 path。

    输出：ContentRoute，已加入当前事务的新路由。
    """
    locked_locale = await session.scalar(
        select(Locale).where(Locale.id == locale.id).with_for_update()
    )
    if locked_locale is None or not locked_locale.is_enabled:
        raise AppException(409, "locale_disabled", "禁用或不存在的语言不能注册内容路由")
    locale = locked_locale
    validate_content_path(path, locale.slug)
    if await session.scalar(select(ContentRoute).where(ContentRoute.path == path)) is not None:
        raise AppException(409, "route_conflict", "内容路径已被占用")
    existing_canonical = await session.scalar(
        select(ContentRoute).where(
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == owner_id,
            ContentRoute.locale_id == locale.id,
            ContentRoute.is_canonical.is_(True),
        )
    )
    if existing_canonical is not None:
        raise AppException(409, "canonical_route_conflict", "同一内容语言只能有一个规范路由")
    route = ContentRoute(
        owner_type=owner_type,
        owner_id=owner_id,
        locale_id=locale.id,
        path=path,
        is_canonical=True,
        active=False,
        indexable=False,
    )
    session.add(route)
    await session.flush()
    return route
