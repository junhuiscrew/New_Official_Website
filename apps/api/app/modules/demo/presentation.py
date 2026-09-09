"""Demo R2 首页媒体槽位服务，仅在显式独立演示环境中可用。"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.company.models import CompanyProfile
from app.modules.demo.models import ContentMediaLink
from app.modules.localization.models import Locale
from app.modules.media.models import MediaAsset, MediaAssetTranslation

_SLOT_RULES: dict[str, tuple[str, str | None, int | None]] = {
    "hero": ("image", None, None),
    "video_1": ("video", "video", 0),
    "poster_1": ("image", "video_poster", 0),
    "video_2": ("video", "video", 1),
    "poster_2": ("image", "video_poster", 1),
}


class DemoPresentationMediaUpdate(BaseModel):
    """
    演示首页媒体更新请求。

    输入：expected_token 为读取时的并发令牌；assignments 为固定槽位与媒体ID。
    输出：经过严格字段校验的更新对象，不接受任意扩展槽位。
    """

    model_config = ConfigDict(extra="forbid")

    expected_token: str = Field(min_length=64, max_length=64)
    assignments: dict[str, uuid.UUID | None]


def presentation_media_selection_token(assignments: dict[str, str | None]) -> str:
    """
    计算首页媒体选择的稳定并发令牌。

    输入：assignments，固定槽位到媒体ID字符串或None的映射。
    输出：str，排序序列化后的SHA256十六进制摘要。
    """
    normalized = {key: assignments.get(key) for key in sorted(_SLOT_RULES)}
    payload = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_demo_mode() -> None:
    """
    拒绝在主实例或生产环境读取、修改演示专用媒体槽位。

    输入：无，读取当前应用配置。
    输出：None；非显式Demo环境抛出404，避免暴露该管理能力。
    """
    settings = get_settings()
    if not settings.demo_mode or settings.app_env == "production":
        raise AppException(404, "demo_feature_not_found", "演示功能不可用")


async def _company(session: AsyncSession) -> CompanyProfile:
    """输入数据库会话；输出当前Demo唯一公司资料，缺失时抛出409。"""
    company = await session.scalar(select(CompanyProfile).order_by(CompanyProfile.created_at))
    if company is None:
        raise AppException(409, "demo_company_missing", "请先初始化Demo内容")
    return company


async def _selection(
    session: AsyncSession,
    company: CompanyProfile,
) -> tuple[dict[str, str | None], dict[tuple[str, int], ContentMediaLink]]:
    """输入会话和公司；输出固定槽位当前选择及可原地更新的媒体关联。"""
    links = list(
        (
            await session.scalars(
                select(ContentMediaLink).where(
                    ContentMediaLink.owner_type == "company_profile",
                    ContentMediaLink.owner_id == company.id,
                    ContentMediaLink.role.in_(["video", "video_poster"]),
                )
            )
        ).all()
    )
    by_key = {(link.role, link.sort_order): link for link in links}
    assignments: dict[str, str | None] = {
        "hero": str(company.primary_factory_media_id) if company.primary_factory_media_id else None,
    }
    for slot, (_media_type, role, order) in _SLOT_RULES.items():
        if slot == "hero" or role is None or order is None:
            continue
        link = by_key.get((role, order))
        assignments[slot] = str(link.media_asset_id) if link else None
    return assignments, by_key


async def get_demo_presentation_media(session: AsyncSession) -> dict[str, Any]:
    """
    返回后台媒体槽位、当前选择和可读媒体选项。

    输入：session，数据库会话。
    输出：dict，包含稳定令牌、固定槽位和带文件名/双语Alt的媒体选项。
    """
    require_demo_mode()
    company = await _company(session)
    assignments, _links = await _selection(session, company)
    locales = {
        locale.id: locale.code
        for locale in (await session.scalars(select(Locale))).all()
    }
    translation_rows = (
        await session.execute(
            select(MediaAssetTranslation).where(
                MediaAssetTranslation.media_asset_id.in_(
                    select(MediaAsset.id).where(MediaAsset.visibility == "public")
                )
            )
        )
    ).scalars()
    alt_by_asset: dict[uuid.UUID, dict[str, str]] = {}
    for translation in translation_rows:
        if translation.alt_text:
            alt_by_asset.setdefault(translation.media_asset_id, {})[
                locales.get(translation.locale_id, str(translation.locale_id))
            ] = translation.alt_text
    assets = list(
        (
            await session.scalars(
                select(MediaAsset)
                .where(
                    MediaAsset.visibility == "public",
                    MediaAsset.upload_status == "ready",
                    MediaAsset.media_type.in_(["image", "video"]),
                )
                .order_by(MediaAsset.media_type, MediaAsset.original_filename)
            )
        ).all()
    )
    return {
        "token": presentation_media_selection_token(assignments),
        "assignments": assignments,
        "slots": {
            key: {"media_type": media_type, "required": key in {"hero", "video_1", "video_2"}}
            for key, (media_type, _role, _order) in _SLOT_RULES.items()
        },
        "assets": [
            {
                "id": str(asset.id),
                "media_type": asset.media_type,
                "filename": asset.original_filename,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
                "duration_seconds": asset.duration_seconds,
                "preview_url": f"/api/v1/public/media/{asset.id}",
                "alt": alt_by_asset.get(asset.id, {}),
            }
            for asset in assets
        ],
    }


async def update_demo_presentation_media(
    session: AsyncSession,
    *,
    payload: DemoPresentationMediaUpdate,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """
    以并发令牌更新固定Demo首页媒体槽位并写入Audit。

    输入：session、已校验payload和真实登录操作人ID。
    输出：dict，保存后的完整媒体槽位回读。
    """
    require_demo_mode()
    unknown = sorted(set(payload.assignments) - set(_SLOT_RULES))
    if unknown:
        raise AppException(422, "demo_media_slot_invalid", "包含未允许的演示媒体槽位", unknown)
    company = await _company(session)
    before, links = await _selection(session, company)
    if presentation_media_selection_token(before) != payload.expected_token:
        raise AppException(409, "revision_conflict", "首页媒体已被其他编辑更新，请刷新后重试")

    merged = {**before, **{key: str(value) if value else None for key, value in payload.assignments.items()}}
    asset_ids = {uuid.UUID(value) for value in merged.values() if value}
    assets = {
        asset.id: asset
        for asset in (
            await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
        ).all()
    }
    for slot, value in merged.items():
        expected_type, _role, _order = _SLOT_RULES[slot]
        if slot in {"hero", "video_1", "video_2"} and value is None:
            raise AppException(422, "demo_media_required", f"{slot} 不能为空")
        if value is None:
            continue
        asset = assets.get(uuid.UUID(value))
        if (
            asset is None
            or asset.visibility != "public"
            or asset.upload_status != "ready"
            or asset.media_type != expected_type
        ):
            raise AppException(422, "demo_media_type_invalid", f"{slot} 的媒体类型或状态不正确")

    company.primary_factory_media_id = uuid.UUID(merged["hero"]) if merged["hero"] else None
    for slot, (_media_type, role, order) in _SLOT_RULES.items():
        if role is None or order is None:
            continue
        value = merged[slot]
        link = links.get((role, order))
        if value is None:
            if link is not None:
                await session.delete(link)
            continue
        media_id = uuid.UUID(value)
        if link is None:
            session.add(
                ContentMediaLink(
                    owner_type="company_profile",
                    owner_id=company.id,
                    media_asset_id=media_id,
                    role=role,
                    sort_order=order,
                )
            )
        else:
            link.media_asset_id = media_id

    write_audit_log(
        session,
        action="demo.presentation_media_update",
        target_type="company_profile",
        target_id=str(company.id),
        user_id=actor_id,
        metadata={"before_token": payload.expected_token, "changed_slots": sorted(payload.assignments)},
    )
    await session.commit()
    return await get_demo_presentation_media(session)
