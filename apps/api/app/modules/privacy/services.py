"""Privacy P1 版本生命周期、公开政策与 RFQ 上下文服务。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64DecodeError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import jwt
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.content.models import (
    ContentPublication,
    ContentRoute,
    SitePage,
    SitePageTranslation,
    TranslationStatus,
)
from app.modules.content.services.revisions import store_revision
from app.modules.localization.models import Locale
from app.modules.privacy.models import (
    PrivacyNoticeVersion,
    PrivacyNoticeVersionTranslation,
    PrivacyPageState,
)
from app.modules.privacy.schemas import PrivacyDraftUpdate
from app.modules.users.models import Permission, Role, RolePermission

PRIVACY_PAGE_KEY = "privacy"
PRIVACY_VERSION_OWNER_TYPE = "privacy_notice_version"
SITE_PAGE_OWNER_TYPE = "site_page"
PRIVACY_HASH_ALGORITHM = "sha256-nfc-json-v1"
PRIVACY_CONTEXT_AUDIENCE = "junhui-rfq-privacy-consent"
PRIVACY_CONTEXT_TYPE = "privacy_policy_context"
OFFICIAL_ORIGIN = "https://junhuiscrewbarrel.com"

PRIVACY_LANGUAGES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "slug": "zh-cn",
        "display_name": "隐私政策",
        "path": "/zh-cn/privacy/",
    },
    "en": {
        "slug": "en",
        "display_name": "Privacy Policy",
        "path": "/en/privacy/",
    },
}

PRIVACY_PERMISSION_DEFINITIONS: dict[str, str] = {
    "privacy.read": "读取隐私政策工作区",
    "privacy.edit": "创建和编辑隐私政策草稿",
    "privacy.review": "人工审核隐私政策翻译",
    "privacy.publish": "发布隐私政策版本",
    "privacy.history": "读取隐私政策历史版本",
}

PRIVACY_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "super_admin": frozenset(PRIVACY_PERMISSION_DEFINITIONS),
    "content_admin": frozenset(PRIVACY_PERMISSION_DEFINITIONS),
    "editor": frozenset({"privacy.read", "privacy.edit"}),
    "translator": frozenset({"privacy.read", "privacy.edit"}),
    "reviewer": frozenset(
        {"privacy.read", "privacy.review", "privacy.publish", "privacy.history"}
    ),
}

_RAW_HTML_PATTERN = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>", re.DOTALL)
_IMAGE_MARKDOWN_PATTERN = re.compile(r"(?<!\\)!\s*\[", re.IGNORECASE)
_INLINE_LINK_PATTERN = re.compile(
    r"(?<![!\\])\[[^\]\r\n]*\]\(([^)\r\n]*)\)", re.IGNORECASE
)
_INLINE_LINK_START_PATTERN = re.compile(r"(?<![!\\])\[[^\]\r\n]*\]\(")
_REFERENCE_LINK_PATTERN = re.compile(
    r"(?<![!\\])\[[^\]\r\n]+\]\[[^\]\r\n]*\]|^\s*\[[^\]]+\]:",
    re.IGNORECASE | re.MULTILINE,
)
_ALLOWED_LINK_SCHEMES = ("http://", "https://", "mailto:")
_URI_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedPrivacyContext:
    """
    表示服务端已验证且仍指向当前政策的 RFQ 上下文。

    输入：内部版本、公开标签、语言、哈希、规范 URL 与服务器确认时间。
    输出：ValidatedPrivacyContext；内部 UUID 仅供当前事务写入 RFQ，不进入公共响应。
    """

    version_id: uuid.UUID
    version_label: str
    locale: str
    content_hash: str
    canonical_url: str
    confirmed_at: datetime


def _as_utc(value: datetime) -> datetime:
    """
    将数据库或调用方时间统一为 UTC aware datetime。

    输入：value，可能为 SQLite 返回的 naive datetime。
    输出：datetime，UTC 时区时间。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _decoded_link_target(value: str) -> str:
    """
    解码 Markdown 链接目标以识别实体、百分号及控制字符混淆协议。

    输入：value，Markdown 链接目标。
    输出：str，供危险 scheme 比较的紧凑小写值。
    """
    decoded = html.unescape(value)
    for _attempt in range(2):
        decoded = unquote(decoded)
    return re.sub(r"[\x00-\x20]+", "", decoded).lower()


def _validate_markdown_safety(body_markdown: str) -> None:
    """
    拒绝原始 HTML、所有图片及无法可靠验证的链接，避免交付活动内容。

    输入：body_markdown，已完成 Unicode/换行规范化的 Markdown。
    输出：None；仅简单安全链接可通过，其余 HTML/图片/链接抛出 AppException。
    """
    if _RAW_HTML_PATTERN.search(body_markdown):
        raise AppException(422, "privacy_markdown_unsafe", "隐私政策 Markdown 不允许原始 HTML")
    if _IMAGE_MARKDOWN_PATTERN.search(body_markdown):
        raise AppException(422, "privacy_markdown_unsafe", "隐私政策 Markdown 不允许图片")
    if _REFERENCE_LINK_PATTERN.search(body_markdown):
        raise AppException(422, "privacy_markdown_unsafe", "隐私政策不支持引用式 Markdown 链接")

    matches = list(_INLINE_LINK_PATTERN.finditer(body_markdown))
    if len(matches) != len(_INLINE_LINK_START_PATTERN.findall(body_markdown)):
        raise AppException(422, "privacy_markdown_unsafe", "隐私政策包含无法安全解析的链接")
    for match in matches:
        target = match.group(1)
        if (
            not target
            or any(character.isspace() for character in target)
            or any(character in target for character in "<>()\\")
            or (match.end() < len(body_markdown) and body_markdown[match.end()] == ")")
        ):
            raise AppException(422, "privacy_markdown_unsafe", "隐私政策包含复杂 Markdown 链接")
        normalized_target = _decoded_link_target(target)
        if normalized_target.startswith("mailto:"):
            address = normalized_target.removeprefix("mailto:")
            # 只允许单一简单邮箱，拒绝 subject/body/Bcc 等 mailto header 注入。
            if re.fullmatch(r"[^\s@<>?,;#&]+@[^\s@<>?,;#&]+", address) is None:
                raise AppException(422, "privacy_markdown_unsafe", "隐私政策邮件链接格式不安全")
            continue
        if normalized_target.startswith(_ALLOWED_LINK_SCHEMES[:2]):
            continue
        if (
            normalized_target.startswith(("//", "\\"))
            or _URI_SCHEME_PATTERN.match(normalized_target)
        ):
            raise AppException(422, "privacy_markdown_unsafe", "隐私政策链接协议不安全")


def normalize_privacy_content(title: str, body_markdown: str) -> tuple[str, str]:
    """
    规范化政策标题和 Markdown，并执行活动内容安全边界。

    输入：title 原始标题；body_markdown 原始 Markdown 正文。
    输出：tuple[str, str]，NFC、LF、去尾随空白和首尾空行后的标题与正文。
    """
    normalized_title = unicodedata.normalize("NFC", title).strip()
    normalized_body = unicodedata.normalize("NFC", body_markdown).replace("\r\n", "\n")
    normalized_body = normalized_body.replace("\r", "\n")
    normalized_body = "\n".join(line.rstrip(" \t") for line in normalized_body.split("\n")).strip()
    if not normalized_title or not normalized_body:
        raise AppException(422, "privacy_translation_incomplete", "隐私政策标题和正文不能为空")
    _validate_markdown_safety(normalized_body)
    return normalized_title, normalized_body


def compute_privacy_content_hash(title: str, body_markdown: str) -> str:
    """
    按 sha256-nfc-json-v1 算法计算确定性政策内容哈希。

    输入：title 与 body_markdown；函数会再次执行同一规范化和安全校验。
    输出：str，规范 JSON UTF-8 字节的 SHA-256 十六进制摘要。
    """
    normalized_title, normalized_body = normalize_privacy_content(title, body_markdown)
    canonical = json.dumps(
        {"body_markdown": normalized_body, "title": normalized_title},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def sync_privacy_permissions(session: AsyncSession) -> None:
    """
    幂等补充 Privacy 原子权限及最小角色映射，不覆盖任何既有角色配置。

    输入：session，调用方事务中的数据库会话。
    输出：None；只创建缺失权限和缺失关联，sales/seo_manager 永不获授权。
    """
    permissions: dict[str, Permission] = {}
    for code, description in PRIVACY_PERMISSION_DEFINITIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, display_name=code, description=description)
            session.add(permission)
            await session.flush()
        permissions[code] = permission

    for role_name, permission_codes in PRIVACY_ROLE_PERMISSIONS.items():
        role = await session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            continue
        for code in permission_codes:
            exists = await session.scalar(
                select(RolePermission.role_id).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permissions[code].id,
                )
            )
            if exists is None:
                session.add(
                    RolePermission(role_id=role.id, permission_id=permissions[code].id)
                )
    await session.flush()


async def _lock_privacy_namespace(session: AsyncSession) -> None:
    """
    在 PostgreSQL 对 Privacy 稳定命名空间获取事务级咨询锁。

    输入：session，数据库会话。
    输出：None；SQLite 测试中为空操作。
    """
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended('privacy:site-page', 0))")
        )


async def _privacy_locales(session: AsyncSession) -> dict[str, Locale]:
    """
    加载 Privacy 固定支持的两种站点语言。

    输入：session，数据库会话。
    输出：dict[str, Locale]，以标准语言代码索引；缺失时抛出 409。
    """
    locales = {
        locale.code: locale
        for locale in (
            await session.scalars(select(Locale).where(Locale.code.in_(PRIVACY_LANGUAGES)))
        ).all()
    }
    if set(locales) != set(PRIVACY_LANGUAGES):
        raise AppException(409, "privacy_locale_missing", "隐私政策所需语言尚未配置")
    return locales


async def lock_privacy_page_state(
    session: AsyncSession,
) -> tuple[SitePage, PrivacyPageState]:
    """
    按统一顺序锁定稳定页面后锁定 Privacy 状态，供发布与 RFQ 创建复用。

    输入：session，当前事务数据库会话。
    输出：tuple[SitePage, PrivacyPageState]；未初始化时抛出 404。
    """
    await _lock_privacy_namespace(session)
    page = await session.scalar(
        select(SitePage)
        .where(SitePage.system_key == PRIVACY_PAGE_KEY)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if page is None:
        raise AppException(404, "privacy_not_initialized", "隐私页面尚未初始化")
    state = await session.scalar(
        select(PrivacyPageState)
        .where(PrivacyPageState.site_page_id == page.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state is None:
        raise AppException(409, "privacy_state_missing", "隐私页面状态记录缺失")
    return page, state


async def initialize_privacy_page(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> SitePage:
    """
    幂等创建稳定 Privacy 技术身份、双语私有路由与空状态，不创建政策正文。

    输入：session、操作用户 actor_id 与可信请求上下文。
    输出：SitePage，新建或已验证一致的稳定 privacy 页面。
    """
    await _lock_privacy_namespace(session)
    locales = await _privacy_locales(session)
    page = await session.scalar(
        select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY).with_for_update()
    )
    if page is not None:
        state = await session.scalar(
            select(PrivacyPageState).where(PrivacyPageState.site_page_id == page.id)
        )
        translations = list(
            (
                await session.scalars(
                    select(SitePageTranslation).where(SitePageTranslation.site_page_id == page.id)
                )
            ).all()
        )
        routes = list(
            (
                await session.scalars(
                    select(ContentRoute).where(
                        ContentRoute.owner_type == SITE_PAGE_OWNER_TYPE,
                        ContentRoute.owner_id == page.id,
                    )
                )
            ).all()
        )
        translation_map = {item.locale_id: item for item in translations}
        route_map = {item.locale_id: item for item in routes}
        coherent = state is not None and page.status in {"enabled", "disabled"}
        for code, config in PRIVACY_LANGUAGES.items():
            locale = locales[code]
            translation = translation_map.get(locale.id)
            route = route_map.get(locale.id)
            coherent = coherent and bool(
                translation
                and translation.display_name == config["display_name"]
                and route
                and route.path == config["path"]
                and route.is_canonical
                and not route.indexable
            )
        if not coherent or len(translations) != 2 or len(routes) != 2:
            raise AppException(409, "privacy_page_conflict", "既有隐私页面技术状态不一致")
        return page

    occupied = list(
        (
            await session.scalars(
                select(ContentRoute)
                .where(ContentRoute.path.in_(item["path"] for item in PRIVACY_LANGUAGES.values()))
                .with_for_update()
            )
        ).all()
    )
    if occupied:
        raise AppException(409, "privacy_page_conflict", "隐私页面规范路径已被占用")

    page = SitePage(system_key=PRIVACY_PAGE_KEY, status="enabled")
    session.add(page)
    await session.flush()
    state = PrivacyPageState(site_page_id=page.id)
    session.add(state)
    for code, config in PRIVACY_LANGUAGES.items():
        locale = locales[code]
        session.add_all(
            [
                SitePageTranslation(
                    site_page_id=page.id,
                    locale_id=locale.id,
                    display_name=config["display_name"],
                ),
                ContentRoute(
                    owner_type=SITE_PAGE_OWNER_TYPE,
                    owner_id=page.id,
                    locale_id=locale.id,
                    path=config["path"],
                    is_canonical=True,
                    active=False,
                    indexable=False,
                ),
            ]
        )
    await session.flush()
    # 初始化也写入技术快照，但快照不包含任何政策正文或虚构日期。
    for code, config in PRIVACY_LANGUAGES.items():
        await store_revision(
            session,
            SITE_PAGE_OWNER_TYPE,
            page.id,
            locales[code].id,
            {
                "system_key": PRIVACY_PAGE_KEY,
                "status": page.status,
                "path": config["path"],
                "active": False,
                "indexable": False,
            },
            actor_id,
        )
    write_audit_log(
        session,
        action="privacy.initialize",
        target_type=SITE_PAGE_OWNER_TYPE,
        target_id=str(page.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"system_key": PRIVACY_PAGE_KEY},
    )
    await session.flush()
    return page


async def _load_version_rows(
    session: AsyncSession,
    page: SitePage,
    version: PrivacyNoticeVersion,
    *,
    lock: bool,
) -> dict[str, tuple[Locale, PrivacyNoticeVersionTranslation, TranslationStatus, ContentPublication, ContentRoute]]:
    """
    按固定语言顺序加载某版本的正文、生命周期和稳定路由。

    输入：session、稳定页面、版本以及是否加行锁。
    输出：dict，按语言代码索引的完整五元组；缺失时抛出 409。
    """
    locales = await _privacy_locales(session)
    rows: dict[
        str,
        tuple[
            Locale,
            PrivacyNoticeVersionTranslation,
            TranslationStatus,
            ContentPublication,
            ContentRoute,
        ],
    ] = {}
    for code in PRIVACY_LANGUAGES:
        locale = locales[code]
        statements = (
            select(PrivacyNoticeVersionTranslation).where(
                PrivacyNoticeVersionTranslation.privacy_notice_version_id == version.id,
                PrivacyNoticeVersionTranslation.locale_id == locale.id,
            ),
            select(TranslationStatus).where(
                TranslationStatus.owner_type == PRIVACY_VERSION_OWNER_TYPE,
                TranslationStatus.owner_id == version.id,
                TranslationStatus.locale_id == locale.id,
            ),
            select(ContentPublication).where(
                ContentPublication.owner_type == PRIVACY_VERSION_OWNER_TYPE,
                ContentPublication.owner_id == version.id,
                ContentPublication.locale_id == locale.id,
            ),
            select(ContentRoute).where(
                ContentRoute.owner_type == SITE_PAGE_OWNER_TYPE,
                ContentRoute.owner_id == page.id,
                ContentRoute.locale_id == locale.id,
            ),
        )
        loaded: list[object | None] = []
        for statement in statements:
            if lock:
                statement = statement.with_for_update().execution_options(populate_existing=True)
            loaded.append(await session.scalar(statement))
        if any(item is None for item in loaded):
            raise AppException(409, "privacy_lifecycle_incomplete", "隐私政策生命周期记录不完整")
        translation, translation_status, publication, route = loaded
        rows[code] = (locale, translation, translation_status, publication, route)  # type: ignore[arg-type]
    return rows


async def _version_is_immutable(session: AsyncSession, version_id: uuid.UUID) -> bool:
    """
    判断版本是否已进入人工审核或发布状态。

    输入：session 与 version_id。
    输出：bool，任一语言已人工审核/发布或版本为当前公开指针时为 true。
    """
    reviewed = await session.scalar(
        select(TranslationStatus.id).where(
            TranslationStatus.owner_type == PRIVACY_VERSION_OWNER_TYPE,
            TranslationStatus.owner_id == version_id,
            TranslationStatus.status.in_(("human_reviewed", "published")),
        )
    )
    published = await session.scalar(
        select(ContentPublication.id).where(
            ContentPublication.owner_type == PRIVACY_VERSION_OWNER_TYPE,
            ContentPublication.owner_id == version_id,
            ContentPublication.status == "published",
        )
    )
    current = await session.scalar(
        select(PrivacyPageState.id).where(PrivacyPageState.current_version_id == version_id)
    )
    return reviewed is not None or published is not None or current is not None


async def get_privacy_draft_record(
    session: AsyncSession,
) -> PrivacyNoticeVersion | None:
    """
    读取当前后台草稿版本 ORM 记录。

    输入：session，数据库会话。
    输出：PrivacyNoticeVersion | None，未初始化或无草稿时返回 None。
    """
    page = await session.scalar(select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY))
    if page is None:
        return None
    state = await session.scalar(
        select(PrivacyPageState).where(PrivacyPageState.site_page_id == page.id)
    )
    if state is None or state.draft_version_id is None:
        return None
    return await session.get(PrivacyNoticeVersion, state.draft_version_id)


async def _store_version_revision(
    session: AsyncSession,
    version: PrivacyNoticeVersion,
    locale: Locale,
    translation: PrivacyNoticeVersionTranslation,
    translation_status: TranslationStatus,
    publication: ContentPublication,
    actor_id: uuid.UUID | None,
    action: str,
) -> None:
    """
    把某语言当前 Privacy 状态追加到共享 ContentRevision。

    输入：版本、语言、正文、生命周期、操作用户和动作。
    输出：None；快照由共享修订服务持久化。
    """
    await store_revision(
        session,
        PRIVACY_VERSION_OWNER_TYPE,
        version.id,
        locale.id,
        {
            "action": action,
            "version_label": version.version_label,
            "revision": version.row_version,
            "effective_at": (
                _as_utc(version.effective_at).isoformat() if version.effective_at else None
            ),
            "locale": locale.code,
            "title": translation.title,
            "body_markdown": translation.body_markdown,
            "content_hash": translation.content_hash,
            "hash_algorithm": translation.hash_algorithm,
            "translation_status": translation_status.status,
            "publication_status": publication.status,
        },
        actor_id,
    )


async def create_privacy_draft(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    clone_current: bool = True,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PrivacyNoticeVersion:
    """
    创建服务端编号的新草稿，并可从当前或已锁定草稿克隆正文。

    输入：session、actor_id、clone_current 与请求上下文。
    输出：PrivacyNoticeVersion，新建的可编辑草稿；已有可编辑草稿时抛出 409。
    """
    page, state = await lock_privacy_page_state(session)
    source: PrivacyNoticeVersion | None = None
    existing_draft: PrivacyNoticeVersion | None = None
    if state.draft_version_id is not None:
        existing_draft = await session.scalar(
            select(PrivacyNoticeVersion)
            .where(PrivacyNoticeVersion.id == state.draft_version_id)
            .with_for_update()
        )
        if existing_draft is None:
            raise AppException(409, "privacy_draft_missing", "隐私政策草稿指针无效")
        if not await _version_is_immutable(session, existing_draft.id):
            raise AppException(409, "privacy_draft_exists", "已有可编辑隐私政策草稿")
    if clone_current and existing_draft is not None:
        source = existing_draft
    elif clone_current and state.current_version_id is not None:
        source = await session.get(PrivacyNoticeVersion, state.current_version_id)

    latest_number = await session.scalar(
        select(func.max(PrivacyNoticeVersion.version_no)).where(
            PrivacyNoticeVersion.site_page_id == page.id
        )
    )
    version_no = (latest_number or 0) + 1
    version = PrivacyNoticeVersion(
        site_page_id=page.id,
        version_no=version_no,
        version_label=f"PRIVACY-{version_no:06d}",
        # 每个版本必须由操作者明确设置自身生效时间，克隆只复用正文证据。
        effective_at=None,
        row_version=1,
        cloned_from_id=source.id if source else None,
        created_by=actor_id,
    )
    session.add(version)
    await session.flush()
    locales = await _privacy_locales(session)
    source_rows = await _load_version_rows(session, page, source, lock=True) if source else {}
    for code in PRIVACY_LANGUAGES:
        locale = locales[code]
        source_translation = source_rows[code][1] if source else None
        translation = PrivacyNoticeVersionTranslation(
            privacy_notice_version_id=version.id,
            locale_id=locale.id,
            title=source_translation.title if source_translation else None,
            body_markdown=source_translation.body_markdown if source_translation else None,
            content_hash=source_translation.content_hash if source_translation else None,
            hash_algorithm=PRIVACY_HASH_ALGORITHM,
        )
        translation_status = TranslationStatus(
            owner_type=PRIVACY_VERSION_OWNER_TYPE,
            owner_id=version.id,
            locale_id=locale.id,
            status="draft",
            translated_by=actor_id,
        )
        publication = ContentPublication(
            owner_type=PRIVACY_VERSION_OWNER_TYPE,
            owner_id=version.id,
            locale_id=locale.id,
            status="draft",
        )
        session.add_all([translation, translation_status, publication])
        await session.flush()
        await _store_version_revision(
            session,
            version,
            locale,
            translation,
            translation_status,
            publication,
            actor_id,
            "create",
        )
    state.draft_version_id = version.id
    write_audit_log(
        session,
        action="privacy.draft_create",
        target_type=PRIVACY_VERSION_OWNER_TYPE,
        target_id=str(version.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={
            "version_label": version.version_label,
            "cloned_from_label": source.version_label if source else None,
        },
    )
    await session.flush()
    return version


async def update_privacy_draft(
    session: AsyncSession,
    payload: PrivacyDraftUpdate,
    *,
    actor_id: uuid.UUID | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PrivacyNoticeVersion:
    """
    以乐观锁完整替换指定语言正文并重算服务端哈希。

    输入：session、PrivacyDraftUpdate、操作用户及请求上下文。
    输出：PrivacyNoticeVersion，更新后的草稿；冲突或不可变版本抛出 409。
    """
    page, state = await lock_privacy_page_state(session)
    if state.draft_version_id is None:
        raise AppException(404, "privacy_draft_not_found", "隐私政策草稿不存在")
    version = await session.scalar(
        select(PrivacyNoticeVersion)
        .where(PrivacyNoticeVersion.id == state.draft_version_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if version is None:
        raise AppException(409, "privacy_draft_missing", "隐私政策草稿指针无效")
    if version.row_version != payload.expected_revision:
        raise AppException(409, "privacy_draft_conflict", "隐私政策草稿已被其他请求修改")
    if await _version_is_immutable(session, version.id):
        raise AppException(409, "privacy_version_immutable", "已审核或已发布版本不可编辑")
    rows = await _load_version_rows(session, page, version, lock=True)
    effective_at_changed = "effective_at" in payload.model_fields_set
    previous_effective_at = version.effective_at
    if effective_at_changed:
        version.effective_at = payload.effective_at
    version.row_version += 1
    revised_locales: set[str] = set()
    for item in payload.translations:
        locale, translation, translation_status, publication, _route = rows[item.locale]
        title, body = normalize_privacy_content(item.title, item.body_markdown)
        translation.title = title
        translation.body_markdown = body
        translation.content_hash = compute_privacy_content_hash(title, body)
        translation.hash_algorithm = PRIVACY_HASH_ALGORITHM
        translation_status.status = "draft"
        translation_status.translated_by = actor_id
        translation_status.reviewed_by = None
        translation_status.published_at = None
        publication.status = "draft"
        publication.published_at = None
        await _store_version_revision(
            session,
            version,
            locale,
            translation,
            translation_status,
            publication,
            actor_id,
            "update",
        )
        revised_locales.add(item.locale)
    if effective_at_changed:
        # 生效时间属于整个版本；即使未改正文，也为未覆盖语言各追加一份可追溯快照。
        for code, (locale, translation, translation_status, publication, _route) in rows.items():
            if code in revised_locales:
                continue
            await _store_version_revision(
                session,
                version,
                locale,
                translation,
                translation_status,
                publication,
                actor_id,
                "effective_at_update",
            )
    effective_at_from = (
        _as_utc(previous_effective_at).isoformat() if previous_effective_at else None
    )
    effective_at_to = _as_utc(version.effective_at).isoformat() if version.effective_at else None
    write_audit_log(
        session,
        action="privacy.draft_update",
        target_type=PRIVACY_VERSION_OWNER_TYPE,
        target_id=str(version.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={
            "version_label": version.version_label,
            "revision": version.row_version,
            "locales": [item.locale for item in payload.translations],
            "effective_at_changed": effective_at_changed,
            "effective_at_from": effective_at_from if effective_at_changed else None,
            "effective_at_to": effective_at_to if effective_at_changed else None,
        },
    )
    await session.flush()
    return version


def _assert_translation_hash(translation: PrivacyNoticeVersionTranslation) -> None:
    """
    验证某语言正文完整、安全且哈希由当前内容重算后完全一致。

    输入：translation，政策版本语言记录。
    输出：None；正文缺失或哈希失配时抛出 AppException。
    """
    if not translation.title or not translation.body_markdown or not translation.content_hash:
        raise AppException(409, "privacy_translation_incomplete", "隐私政策双语正文不完整")
    if translation.hash_algorithm != PRIVACY_HASH_ALGORITHM:
        raise AppException(409, "privacy_hash_invalid", "隐私政策哈希算法不受支持")
    expected_hash = compute_privacy_content_hash(translation.title, translation.body_markdown)
    if expected_hash != translation.content_hash:
        raise AppException(409, "privacy_hash_mismatch", "隐私政策内容哈希校验失败")


def _assert_observed_draft(
    version: PrivacyNoticeVersion,
    rows: dict[
        str,
        tuple[
            Locale,
            PrivacyNoticeVersionTranslation,
            TranslationStatus,
            ContentPublication,
            ContentRoute,
        ],
    ],
    *,
    expected_version_label: str,
    expected_revision: int,
    expected_content_hashes: dict[str, str],
) -> None:
    """
    在数据库锁内核对管理员实际观察到的生命周期目标。

    输入：version、锁定的双语 rows，以及客户端观察的标签、Revision 和语言哈希。
    输出：None；任一观察值已陈旧或被伪造时抛出 409，禁止生命周期变更。
    """
    if (
        version.version_label != expected_version_label
        or version.row_version != expected_revision
        or any(
            locale not in rows or rows[locale][1].content_hash != expected_hash
            for locale, expected_hash in expected_content_hashes.items()
        )
    ):
        raise AppException(
            409,
            "privacy_draft_observation_conflict",
            "隐私政策草稿已变化，请刷新并重新确认",
        )


async def review_privacy_translation(
    session: AsyncSession,
    *,
    locale: str,
    actor_id: uuid.UUID | None,
    expected_version_label: str,
    expected_revision: int,
    expected_content_hash: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PrivacyNoticeVersion:
    """
    使用真实用户身份把当前草稿指定语言标记为人工审核。

    输入：session、固定 locale、actor_id、管理员观察值与请求上下文。
    输出：PrivacyNoticeVersion；缺失用户、正文或草稿时抛出业务异常。
    """
    if actor_id is None:
        raise AppException(409, "privacy_reviewer_required", "人工审核必须记录真实用户")
    if locale not in PRIVACY_LANGUAGES:
        raise AppException(404, "privacy_locale_not_found", "隐私政策语言不存在")
    page, state = await lock_privacy_page_state(session)
    if state.draft_version_id is None:
        raise AppException(404, "privacy_draft_not_found", "隐私政策草稿不存在")
    version = await session.scalar(
        select(PrivacyNoticeVersion)
        .where(PrivacyNoticeVersion.id == state.draft_version_id)
        .with_for_update()
    )
    if version is None:
        raise AppException(409, "privacy_draft_missing", "隐私政策草稿指针无效")
    rows = await _load_version_rows(session, page, version, lock=True)
    _assert_observed_draft(
        version,
        rows,
        expected_version_label=expected_version_label,
        expected_revision=expected_revision,
        expected_content_hashes={locale: expected_content_hash},
    )
    locale_record, translation, translation_status, publication, _route = rows[locale]
    _assert_translation_hash(translation)
    if translation_status.status == "published" or publication.status == "published":
        raise AppException(409, "privacy_version_immutable", "已发布版本不可重新审核")
    if translation_status.status == "human_reviewed":
        return version
    translation_status.status = "human_reviewed"
    translation_status.reviewed_by = actor_id
    publication.status = "review"
    await _store_version_revision(
        session,
        version,
        locale_record,
        translation,
        translation_status,
        publication,
        actor_id,
        "review",
    )
    write_audit_log(
        session,
        action="privacy.translation_review",
        target_type=PRIVACY_VERSION_OWNER_TYPE,
        target_id=str(version.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"version_label": version.version_label, "locale": locale},
    )
    await session.flush()
    return version


async def publish_privacy_draft(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    expected_version_label: str,
    expected_revision: int,
    expected_content_hashes: dict[str, str],
    now: datetime | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> PrivacyNoticeVersion:
    """
    原子校验双语审核、哈希、生效时间并切换唯一公开版本指针。

    输入：session、操作用户、管理员观察值、可注入测试时钟和请求上下文。
    输出：PrivacyNoticeVersion，成功成为 current 的版本；任一门禁失败则不部分发布。
    """
    if actor_id is None:
        raise AppException(409, "privacy_publisher_required", "发布必须记录真实用户")
    page, state = await lock_privacy_page_state(session)
    if page.status != "enabled":
        raise AppException(409, "privacy_page_disabled", "禁用的隐私页面不能发布")
    if state.draft_version_id is None:
        raise AppException(404, "privacy_draft_not_found", "隐私政策草稿不存在")
    version = await session.scalar(
        select(PrivacyNoticeVersion)
        .where(PrivacyNoticeVersion.id == state.draft_version_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if version is None:
        raise AppException(409, "privacy_draft_missing", "隐私政策草稿指针无效")
    trusted_now = _as_utc(now or datetime.now(UTC))
    if version.effective_at is None:
        raise AppException(409, "privacy_effective_missing", "隐私政策生效时间不能为空")
    if _as_utc(version.effective_at) > trusted_now:
        raise AppException(409, "privacy_effective_in_future", "隐私政策尚未到生效时间")

    rows = await _load_version_rows(session, page, version, lock=True)
    if set(expected_content_hashes) != set(PRIVACY_LANGUAGES):
        raise AppException(
            409,
            "privacy_draft_observation_conflict",
            "隐私政策双语观察值不完整，请刷新并重新确认",
        )
    _assert_observed_draft(
        version,
        rows,
        expected_version_label=expected_version_label,
        expected_revision=expected_revision,
        expected_content_hashes=expected_content_hashes,
    )
    # 先完整检查两种语言和服务端哈希，再检查审核状态，返回稳定且最有信息量的错误。
    for code, (locale, translation, _translation_status, publication, route) in rows.items():
        if not locale.is_enabled:
            raise AppException(409, "privacy_locale_disabled", "禁用语言不能发布隐私政策")
        _assert_translation_hash(translation)
        expected_route = PRIVACY_LANGUAGES[code]["path"]
        if not route.is_canonical or route.path != expected_route:
            raise AppException(409, "privacy_route_invalid", "隐私政策规范路由不一致")
        if publication.status not in {"draft", "review"}:
            raise AppException(409, "privacy_publication_invalid", "隐私政策发布状态不允许切换")
    for code, (_locale, _translation, translation_status, _publication, _route) in rows.items():
        if translation_status.status != "human_reviewed":
            raise AppException(
                409,
                "privacy_translation_not_reviewed",
                f"{code} 隐私政策尚未完成人工审核",
            )

    for _code, (locale, translation, translation_status, publication, route) in rows.items():
        translation_status.status = "published"
        translation_status.published_at = trusted_now
        publication.status = "published"
        publication.published_at = trusted_now
        route.active = True
        # Privacy 是业务 noindex 页面；发布也绝不把稳定路由加入索引集合。
        route.indexable = False
        await _store_version_revision(
            session,
            version,
            locale,
            translation,
            translation_status,
            publication,
            actor_id,
            "publish",
        )
    previous_current = state.current_version_id
    state.current_version_id = version.id
    state.draft_version_id = None
    write_audit_log(
        session,
        action="privacy.publish_switch",
        target_type=PRIVACY_VERSION_OWNER_TYPE,
        target_id=str(version.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={
            "version_label": version.version_label,
            "previous_current_present": previous_current is not None,
        },
    )
    await session.flush()
    return version


def _normalize_locale_identifier(value: str) -> str | None:
    """
    把公开 locale slug 或标准代码收敛到标准代码。

    输入：value，外部语言标识。
    输出：str | None，仅 zh-CN/en 返回标准代码。
    """
    lowered = value.strip().lower()
    for code, config in PRIVACY_LANGUAGES.items():
        if lowered in {code.lower(), config["slug"]}:
            return code
    return None


async def _build_public_policy(
    session: AsyncSession,
    page: SitePage,
    state: PrivacyPageState,
    locale_code: str,
    *,
    now: datetime,
    lock: bool,
) -> dict[str, object]:
    """
    从唯一 current 指针构造严格双语公开政策 DTO。

    输入：session、页面、状态、标准语言、可信时间及锁选项。
    输出：dict，不含内部 UUID/可信 HTML；任何公开门禁失败统一返回 404。
    """
    unavailable = AppException(404, "privacy_policy_unavailable", "当前没有可用隐私政策")
    if page.status != "enabled" or state.current_version_id is None:
        raise unavailable
    statement = select(PrivacyNoticeVersion).where(
        PrivacyNoticeVersion.id == state.current_version_id,
        PrivacyNoticeVersion.site_page_id == page.id,
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    version = await session.scalar(statement)
    if version is None or version.effective_at is None or _as_utc(version.effective_at) > now:
        raise unavailable
    try:
        rows = await _load_version_rows(session, page, version, lock=lock)
        alternates: dict[str, str] = {}
        for code, (locale, translation, translation_status, publication, route) in rows.items():
            _assert_translation_hash(translation)
            if (
                not locale.is_enabled
                or translation_status.status != "published"
                or publication.status != "published"
                or not route.is_canonical
                or not route.active
                or route.indexable
                or route.path != PRIVACY_LANGUAGES[code]["path"]
            ):
                raise unavailable
            alternates[code] = route.path
    except AppException as exc:
        if exc.code == "privacy_policy_unavailable":
            raise
        raise unavailable from exc
    _locale, translation, _status, _publication, route = rows[locale_code]
    return {
        "locale": locale_code,
        "title": translation.title,
        "body_markdown": translation.body_markdown,
        "content_format": "markdown",
        "rendering_trust": "untrusted",
        "version_label": version.version_label,
        "content_hash": translation.content_hash,
        "hash_algorithm": translation.hash_algorithm,
        "effective_at": _as_utc(version.effective_at).isoformat(),
        "canonical_path": route.path,
        "canonical_url": OFFICIAL_ORIGIN + route.path,
        "alternates": alternates,
        "robots": {"index": False, "follow": True},
    }


async def get_public_privacy_policy(
    session: AsyncSession,
    locale: str,
    *,
    now: datetime | None = None,
    lock: bool = False,
) -> dict[str, object]:
    """
    返回固定语言的当前合格双语隐私政策。

    输入：session、locale slug/代码、可注入测试时钟与是否加事务锁。
    输出：dict，公开 Markdown、标签、哈希、规范路径、双语 alternate 与强制 noindex。
    """
    locale_code = _normalize_locale_identifier(locale)
    if locale_code is None:
        raise AppException(404, "privacy_policy_unavailable", "当前没有可用隐私政策")
    if lock:
        page, state = await lock_privacy_page_state(session)
    else:
        page = await session.scalar(
            select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY)
        )
        if page is None:
            raise AppException(404, "privacy_policy_unavailable", "当前没有可用隐私政策")
        state = await session.scalar(
            select(PrivacyPageState).where(PrivacyPageState.site_page_id == page.id)
        )
        if state is None:
            raise AppException(404, "privacy_policy_unavailable", "当前没有可用隐私政策")
    return await _build_public_policy(
        session,
        page,
        state,
        locale_code,
        now=_as_utc(now or datetime.now(UTC)),
        lock=lock,
    )


def create_privacy_context_token(
    policy: dict[str, object],
    *,
    now: datetime | None = None,
    ttl: timedelta | None = None,
) -> str:
    """
    为当前公开政策签发短期、专用 audience 的 RFQ 确认上下文。

    输入：服务端 policy DTO、可注入签发时间和 TTL。
    输出：str，绑定公开版本标签、语言、哈希、规范 URL 与签发/过期时间的 JWT。
    """
    settings = get_settings()
    issued_at = _as_utc(now or datetime.now(UTC))
    lifetime = ttl or timedelta(minutes=settings.privacy_context_token_ttl_minutes)
    return jwt.encode(
        {
            "aud": PRIVACY_CONTEXT_AUDIENCE,
            "type": PRIVACY_CONTEXT_TYPE,
            "ver": policy["version_label"],
            "loc": policy["locale"],
            "hash": policy["content_hash"],
            "url": policy["canonical_url"],
            "iat": issued_at,
            "exp": issued_at + lifetime,
        },
        settings.jwt_signing_secret,
        algorithm="HS256",
    )


def _has_canonical_jwt_encoding(token: str) -> bool:
    """
    检查 JWT 三段是否使用唯一、规范的无填充 Base64URL 表示。

    输入：token，待验证的紧凑 JWT 字符串。
    输出：bool；三段均可解码且重新编码完全一致时为 True，防止等价签名字节的文本变体。
    """
    segments = token.split(".")
    if len(segments) != 3 or any(not segment for segment in segments):
        return False
    try:
        for segment in segments:
            padding = "=" * (-len(segment) % 4)
            decoded = urlsafe_b64decode((segment + padding).encode("ascii"))
            canonical = urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
            if canonical != segment:
                return False
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, Base64DecodeError):
        return False
    return True


async def issue_privacy_context(
    session: AsyncSession,
    *,
    locale: str,
    version_label: str,
) -> dict[str, str]:
    """
    仅为请求标签仍精确等于当前政策的语言签发上下文。

    输入：session、固定 locale 和客户端从政策响应取得的公开 version_label。
    输出：dict，短期 token 与过期时间；不接收 UUID、哈希或客户端时间。
    """
    now = datetime.now(UTC)
    policy = await get_public_privacy_policy(session, locale, now=now)
    if policy["version_label"] != version_label:
        raise AppException(409, "privacy_context_stale", "隐私政策版本已更新，请重新确认")
    ttl = timedelta(minutes=get_settings().privacy_context_token_ttl_minutes)
    return {
        "token": create_privacy_context_token(policy, now=now, ttl=ttl),
        "expires_at": (now + ttl).isoformat(),
        "version_label": str(policy["version_label"]),
        "locale": str(policy["locale"]),
    }


async def validate_privacy_context(
    session: AsyncSession,
    token: str | None,
    *,
    expected_locale: str | None,
    now: datetime | None = None,
) -> ValidatedPrivacyContext:
    """
    校验 RFQ 上下文签名、期限、语言及当前版本/哈希/URL，并持有一致锁。

    输入：session、可选 token、RFQ 语言与可注入服务器时间。
    输出：ValidatedPrivacyContext，仅在 token 仍精确匹配 current 政策时返回。
    """
    if not token:
        raise AppException(422, "privacy_context_required", "提交询盘需要隐私政策上下文")
    if not _has_canonical_jwt_encoding(token):
        raise AppException(422, "privacy_context_invalid", "隐私政策上下文无效")
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_signing_secret,
            algorithms=["HS256"],
            audience=PRIVACY_CONTEXT_AUDIENCE,
            options={"require": ["aud", "type", "ver", "loc", "hash", "url", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppException(422, "privacy_context_expired", "隐私政策上下文已过期") from exc
    except jwt.PyJWTError as exc:
        raise AppException(422, "privacy_context_invalid", "隐私政策上下文无效") from exc
    if claims.get("type") != PRIVACY_CONTEXT_TYPE:
        raise AppException(422, "privacy_context_invalid", "隐私政策上下文无效")
    token_locale = _normalize_locale_identifier(str(claims.get("loc", "")))
    submitted_locale = _normalize_locale_identifier(expected_locale) if expected_locale else None
    if token_locale is None or (submitted_locale is not None and submitted_locale != token_locale):
        raise AppException(422, "privacy_context_locale_mismatch", "询盘语言与隐私政策不一致")
    trusted_now = _as_utc(now or datetime.now(UTC))
    try:
        policy = await get_public_privacy_policy(session, token_locale, now=trusted_now, lock=True)
    except AppException as exc:
        raise AppException(409, "privacy_context_stale", "隐私政策已更新或不可用") from exc
    if any(
        claims.get(claim) != policy[field]
        for claim, field in (
            ("ver", "version_label"),
            ("loc", "locale"),
            ("hash", "content_hash"),
            ("url", "canonical_url"),
        )
    ):
        raise AppException(409, "privacy_context_stale", "隐私政策版本已更新，请重新确认")
    page = await session.scalar(select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY))
    state = await session.scalar(
        select(PrivacyPageState).where(PrivacyPageState.site_page_id == page.id)
    )
    if state is None or state.current_version_id is None:
        raise AppException(409, "privacy_context_stale", "隐私政策已更新或不可用")
    return ValidatedPrivacyContext(
        version_id=state.current_version_id,
        version_label=str(policy["version_label"]),
        locale=token_locale,
        content_hash=str(policy["content_hash"]),
        canonical_url=str(policy["canonical_url"]),
        confirmed_at=trusted_now,
    )


async def _serialize_privacy_version(
    session: AsyncSession,
    page: SitePage,
    version: PrivacyNoticeVersion,
) -> dict[str, object]:
    """
    构造不含内部 UUID 的后台版本 DTO。

    输入：session、稳定页面和政策版本。
    输出：dict，包含公开标签、乐观版本、生效时间及双语工作状态。
    """
    rows = await _load_version_rows(session, page, version, lock=False)
    translations: dict[str, dict[str, object]] = {}
    for code, (_locale, translation, translation_status, publication, route) in rows.items():
        translations[code] = {
            "locale": code,
            "title": translation.title,
            "body_markdown": translation.body_markdown,
            "content_format": "markdown",
            "rendering_trust": "untrusted",
            "content_hash": translation.content_hash,
            "hash_algorithm": translation.hash_algorithm,
            "translation_status": translation_status.status,
            "publication_status": publication.status,
            "canonical_path": route.path,
            "route_active": route.active,
            # 后台必须暴露实际数据库状态，不能用常量掩盖错误漂移。
            "route_indexable": route.indexable,
        }
    source_label: str | None = None
    if version.cloned_from_id is not None:
        source_label = await session.scalar(
            select(PrivacyNoticeVersion.version_label).where(
                PrivacyNoticeVersion.id == version.cloned_from_id
            )
        )
    return {
        "version_label": version.version_label,
        "revision": version.row_version,
        "effective_at": _as_utc(version.effective_at).isoformat() if version.effective_at else None,
        "cloned_from_version_label": source_label,
        "created_at": _as_utc(version.created_at).isoformat(),
        "translations": translations,
    }


async def get_privacy_admin_state(session: AsyncSession) -> dict[str, object]:
    """
    返回 Privacy 管理端可回读的稳定页面、current 与 draft 状态。

    输入：session，数据库会话。
    输出：dict，不含页面、版本、语言或路由内部 UUID。
    """
    page = await session.scalar(select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY))
    if page is None:
        raise AppException(404, "privacy_not_initialized", "隐私页面尚未初始化")
    state = await session.scalar(
        select(PrivacyPageState).where(PrivacyPageState.site_page_id == page.id)
    )
    if state is None:
        raise AppException(409, "privacy_state_missing", "隐私页面状态记录缺失")
    current = await session.get(PrivacyNoticeVersion, state.current_version_id) if state.current_version_id else None
    draft = await session.get(PrivacyNoticeVersion, state.draft_version_id) if state.draft_version_id else None
    return {
        "page": {"system_key": PRIVACY_PAGE_KEY, "status": page.status},
        "current": await _serialize_privacy_version(session, page, current) if current else None,
        "draft": await _serialize_privacy_version(session, page, draft) if draft else None,
    }


async def list_privacy_history(session: AsyncSession) -> list[dict[str, object]]:
    """
    按服务端版本号倒序返回授权历史，不暴露内部 UUID。

    输入：session，数据库会话。
    输出：list[dict]，所有不可删除版本的管理 DTO。
    """
    page = await session.scalar(select(SitePage).where(SitePage.system_key == PRIVACY_PAGE_KEY))
    if page is None:
        raise AppException(404, "privacy_not_initialized", "隐私页面尚未初始化")
    versions = list(
        (
            await session.scalars(
                select(PrivacyNoticeVersion)
                .where(PrivacyNoticeVersion.site_page_id == page.id)
                .order_by(PrivacyNoticeVersion.version_no.desc())
            )
        ).all()
    )
    return [await _serialize_privacy_version(session, page, version) for version in versions]


async def set_privacy_page_status(
    session: AsyncSession,
    *,
    status: str,
    actor_id: uuid.UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> SitePage:
    """
    启用或禁用 Privacy 页面而不改动当前版本快照。

    输入：session、enabled/disabled、真实用户及请求上下文。
    输出：SitePage，更新后的稳定页面。
    """
    page, _state = await lock_privacy_page_state(session)
    previous = page.status
    page.status = status
    locales = await _privacy_locales(session)
    for code, config in PRIVACY_LANGUAGES.items():
        await store_revision(
            session,
            SITE_PAGE_OWNER_TYPE,
            page.id,
            locales[code].id,
            {"system_key": PRIVACY_PAGE_KEY, "status": status, "path": config["path"]},
            actor_id,
        )
    write_audit_log(
        session,
        action="privacy.status_change",
        target_type=SITE_PAGE_OWNER_TYPE,
        target_id=str(page.id),
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"from": previous, "to": status},
    )
    await session.flush()
    return page
