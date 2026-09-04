"""Authority Content 统一翻译、发布、路由、修订、审计与关系服务。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.handlers import AppException
from app.modules.audit.service import write_audit_log
from app.modules.authority.models import (
    FAQ,
    ArticleApplication,
    ArticleCase,
    ArticleFAQ,
    ArticleMaterial,
    ArticleProduct,
    ArticleSolution,
    ArticleTechnology,
    AuthorExpert,
    AuthorExpertTranslation,
    CaseApplication,
    CaseMaterial,
    CaseProduct,
    CaseSolution,
    CaseStudy,
    CaseStudyTranslation,
    CaseTechnology,
    FAQArticle,
    FAQCase,
    FAQMaterial,
    FAQProduct,
    FAQSolution,
    FAQTranslation,
    KnowledgeArticle,
    KnowledgeArticleTranslation,
    KnowledgeCategory,
    KnowledgeCategoryTranslation,
)
from app.modules.authority.schemas import (
    AuthorExpertCreate,
    AuthorExpertUpdate,
    AuthorityRelationUpdate,
    AuthorityTranslationInput,
    CaseStudyCreate,
    CaseStudyUpdate,
    FAQCreate,
    FAQUpdate,
    KnowledgeArticleCreate,
    KnowledgeArticleUpdate,
    KnowledgeCategoryCreate,
    KnowledgeCategoryUpdate,
)
from app.modules.catalog.models import Application, Material, Product, Solution, Technology
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import invalidate_publication_after_translation_edit
from app.modules.content.services.revisions import store_revision
from app.modules.content.services.routes import create_content_route
from app.modules.localization.models import Locale

_CONFIG: dict[str, tuple[type, type, str, set[str]]] = {
    "case_study": (CaseStudy, CaseStudyTranslation, "case_study_id", {"title"}),
    "knowledge_category": (KnowledgeCategory, KnowledgeCategoryTranslation, "category_id", {"name"}),
    "knowledge_article": (KnowledgeArticle, KnowledgeArticleTranslation, "article_id", {"title", "body_markdown"}),
    "faq": (FAQ, FAQTranslation, "faq_id", {"question", "answer"}),
    "author_expert": (AuthorExpert, AuthorExpertTranslation, "author_expert_id", {"name"}),
}
PUBLIC_OWNER_TYPES = frozenset({"case_study", "knowledge_article", "author_expert"})


async def _default_locale(session: AsyncSession) -> Locale:
    """
    读取显式默认语言。

    输入：session，数据库会话。
    输出：Locale；缺失时抛出 AppException。
    """
    locale = await session.scalar(select(Locale).where(Locale.is_default.is_(True)))
    if locale is None:
        raise AppException(409, "default_locale_required", "必须配置一个默认语言")
    return locale


def _snapshot(entity: Any) -> dict[str, Any]:
    """
    生成不含自动时间字段的 ORM 快照。

    输入：entity，SQLAlchemy 实体。
    输出：dict，可 JSON 编码的列字典。
    """
    return {
        column.name: getattr(entity, column.name)
        for column in entity.__table__.columns
        if column.name not in {"created_at", "updated_at"}
    }


async def _route_path(session: AsyncSession, owner_type: str, entity: Any, locale: Locale) -> str:
    """
    构造 Authority Content 稳定 canonical 路径。

    输入：session、owner_type、entity 与 locale。
    输出：str，带语言前缀和尾斜杠的路径。
    """
    if owner_type == "case_study":
        return f"/{locale.slug}/case-studies/{entity.slug}/"
    if owner_type == "author_expert":
        return f"/{locale.slug}/experts/{entity.slug}/"
    if owner_type == "knowledge_article":
        category = await session.get(KnowledgeCategory, entity.category_id)
        if category is None or category.status != "enabled":
            raise AppException(409, "knowledge_category_required", "文章必须使用启用的知识分类")
        return f"/{locale.slug}/knowledge/{category.slug}/{entity.slug}/"
    raise AppException(409, "public_lifecycle_not_supported", "该实体不拥有独立公开页面")


def _public_profile_allowed(owner_type: str, entity: Any) -> bool:
    """
    判断实体是否允许建立独立公开生命周期。

    输入：owner_type 与实体。
    输出：bool，作者专家需同时核验真人并开启公开资料。
    """
    if owner_type == "author_expert":
        return bool(entity.is_real_person_verified and entity.public_profile_enabled)
    return owner_type in PUBLIC_OWNER_TYPES


async def _ensure_lifecycle(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    locale: Locale,
) -> tuple[ContentPublication, ContentRoute]:
    """
    幂等创建统一 Publication 与 canonical ContentRoute。

    输入：session、owner 标识、实体和语言。
    输出：(ContentPublication, ContentRoute)，均保持 draft/inactive/noindex。
    """
    if not _public_profile_allowed(owner_type, entity):
        raise AppException(409, "public_profile_not_allowed", "该实体当前不能建立公开资料页")
    publication = await session.scalar(
        select(ContentPublication).where(
            ContentPublication.owner_type == owner_type,
            ContentPublication.owner_id == entity.id,
            ContentPublication.locale_id == locale.id,
        )
    )
    if publication is None:
        publication = ContentPublication(owner_type=owner_type, owner_id=entity.id, locale_id=locale.id, status="draft")
        session.add(publication)
    route = await session.scalar(
        select(ContentRoute).where(
            ContentRoute.owner_type == owner_type,
            ContentRoute.owner_id == entity.id,
            ContentRoute.locale_id == locale.id,
            ContentRoute.is_canonical.is_(True),
        )
    )
    if route is None:
        route = await create_content_route(
            session,
            owner_type,
            entity.id,
            locale,
            await _route_path(session, owner_type, entity, locale),
        )
    route.active = False
    route.indexable = False
    await session.flush()
    return publication, route


async def _create_translations(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    translations: list[AuthorityTranslationInput],
) -> None:
    """
    创建全部 Locale 的 TranslationStatus，并写入请求中的结构化翻译。

    输入：session、owner_type、entity 与翻译列表。
    输出：None；重复语言、禁用语言或缺少必填正文时拒绝。
    """
    translation_model, owner_field, required_fields = _CONFIG[owner_type][1:]
    translation_map = {item.locale_id: item for item in translations}
    if len(translation_map) != len(translations):
        raise AppException(409, "duplicate_translation", "同一请求不能重复提交语言")
    locales = list((await session.scalars(select(Locale).order_by(Locale.sort_order))).all())
    default_locale = await _default_locale(session)
    for locale in locales:
        item = translation_map.get(locale.id)
        session.add(
            TranslationStatus(
                owner_type=owner_type,
                owner_id=entity.id,
                locale_id=locale.id,
                source_locale_id=default_locale.id,
                status="draft" if item else "missing",
            )
        )
        if item is None:
            continue
        if not locale.is_enabled:
            raise AppException(409, "locale_disabled", "不能向停用语言写入内容")
        missing = [name for name in required_fields if not item.fields.get(name)]
        if missing:
            raise AppException(422, "translation_fields_required", "翻译缺少必填结构化字段", {"fields": missing})
        allowed = set(translation_model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at"}
        values = {key: value for key, value in item.fields.items() if key in allowed}
        session.add(translation_model(**{owner_field: entity.id, "locale_id": locale.id, **values}))
        if _public_profile_allowed(owner_type, entity):
            await _ensure_lifecycle(session, owner_type, entity, locale)
    await session.flush()


async def _create_entity(
    session: AsyncSession,
    owner_type: str,
    payload: BaseModel,
    actor_id: uuid.UUID | None,
) -> Any:
    """
    统一创建 Authority 主实体、翻译、生命周期、Revision 与 Audit。

    输入：session、owner_type、创建 payload 和 actor_id。
    输出：Any，新建 ORM 实体。
    """
    model = _CONFIG[owner_type][0]
    values = payload.model_dump(exclude={"translations"})
    entity = model(**values)
    session.add(entity)
    await session.flush()
    await _create_translations(session, owner_type, entity, payload.translations)
    default_locale = await _default_locale(session)
    await store_revision(
        session,
        owner_type,
        entity.id,
        default_locale.id,
        jsonable_encoder({"master": _snapshot(entity), "translations": [item.model_dump(mode="json") for item in payload.translations]}),
        actor_id,
    )
    write_audit_log(session, action=f"{owner_type}.create", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    await session.flush()
    return entity


async def create_case_study(session: AsyncSession, payload: CaseStudyCreate, actor_id: uuid.UUID | None = None) -> CaseStudy:
    """创建客户案例及统一生命周期；输入 session/payload/actor_id，输出 CaseStudy。"""
    return await _create_entity(session, "case_study", payload, actor_id)


async def create_knowledge_category(session: AsyncSession, payload: KnowledgeCategoryCreate, actor_id: uuid.UUID | None = None) -> KnowledgeCategory:
    """创建知识分类；输入 session/payload/actor_id，输出 KnowledgeCategory。"""
    return await _create_entity(session, "knowledge_category", payload, actor_id)


async def create_author_expert(session: AsyncSession, payload: AuthorExpertCreate, actor_id: uuid.UUID | None = None) -> AuthorExpert:
    """创建真实人物；输入 session/payload/actor_id，输出 AuthorExpert。"""
    if payload.public_profile_enabled and not payload.is_real_person_verified:
        raise AppException(409, "verified_person_required", "公开 Expert 页面必须对应已核验的真实人物")
    return await _create_entity(session, "author_expert", payload, actor_id)


async def create_knowledge_article(session: AsyncSession, payload: KnowledgeArticleCreate, actor_id: uuid.UUID | None = None) -> KnowledgeArticle:
    """创建知识文章；输入 session/payload/actor_id，输出 KnowledgeArticle。"""
    author = await session.get(AuthorExpert, payload.author_id)
    if author is None or not author.is_real_person_verified:
        raise AppException(409, "verified_author_required", "知识文章必须使用已核验的真实作者")
    if payload.reviewer_id:
        reviewer = await session.get(AuthorExpert, payload.reviewer_id)
        if reviewer is None or not reviewer.is_real_person_verified:
            raise AppException(409, "verified_reviewer_required", "审核人必须是已核验的真实专家")
    return await _create_entity(session, "knowledge_article", payload, actor_id)


async def create_faq(session: AsyncSession, payload: FAQCreate, actor_id: uuid.UUID | None = None) -> FAQ:
    """创建无独立 Route 的 FAQ；输入 session/payload/actor_id，输出 FAQ。"""
    return await _create_entity(session, "faq", payload, actor_id)


async def _has_published_locale(session: AsyncSession, owner_type: str, owner_id: uuid.UUID) -> bool:
    """输入 owner 标识，输出是否存在已发布语言。"""
    return (
        await session.scalar(
            select(ContentPublication.id).where(
                ContentPublication.owner_type == owner_type,
                ContentPublication.owner_id == owner_id,
                ContentPublication.status == "published",
            )
        )
        is not None
    )


async def _upsert_translation(
    session: AsyncSession,
    owner_type: str,
    entity: Any,
    item: AuthorityTranslationInput,
    actor_id: uuid.UUID | None,
) -> None:
    """
    新建或更新单语言正文，并同步撤销已发布内容。

    输入：session、owner_type、entity、翻译 item 与 actor_id。
    输出：None；正文与生命周期保持事务一致。
    """
    translation_model, owner_field, required_fields = _CONFIG[owner_type][1:]
    locale = await session.get(Locale, item.locale_id)
    if locale is None or not locale.is_enabled:
        raise AppException(409, "locale_disabled", "不能向停用或不存在的语言写入内容")
    missing = [name for name in required_fields if not item.fields.get(name)]
    if missing:
        raise AppException(422, "translation_fields_required", "翻译缺少必填结构化字段", {"fields": missing})
    translation = await session.scalar(
        select(translation_model).where(
            getattr(translation_model, owner_field) == entity.id,
            translation_model.locale_id == item.locale_id,
        )
    )
    allowed = set(translation_model.__table__.columns.keys()) - {"id", owner_field, "locale_id", "created_at", "updated_at"}
    values = {key: value for key, value in item.fields.items() if key in allowed}
    if translation is None:
        translation = translation_model(**{owner_field: entity.id, "locale_id": item.locale_id, **values})
        session.add(translation)
    else:
        for key, value in values.items():
            setattr(translation, key, value)
    status = await session.scalar(
        select(TranslationStatus).where(
            TranslationStatus.owner_type == owner_type,
            TranslationStatus.owner_id == entity.id,
            TranslationStatus.locale_id == item.locale_id,
        )
    )
    if status is None:
        status = TranslationStatus(owner_type=owner_type, owner_id=entity.id, locale_id=item.locale_id, source_locale_id=(await _default_locale(session)).id, status="draft")
        session.add(status)
    status.status = "draft"
    status.reviewed_by = None
    status.published_at = None
    if _public_profile_allowed(owner_type, entity):
        publication, route = await _ensure_lifecycle(session, owner_type, entity, locale)
        await invalidate_publication_after_translation_edit(
            session,
            publication=publication,
            translation=status,
            route=route,
            actor_id=actor_id,
        )
    await session.flush()
    await store_revision(
        session,
        owner_type,
        entity.id,
        item.locale_id,
        jsonable_encoder({"master": _snapshot(entity), "translation": _snapshot(translation)}),
        actor_id,
    )


async def _withdraw_disabled_entity(session: AsyncSession, owner_type: str, entity: Any) -> None:
    """
    将 disabled/retired 实体的全部发布和路由退出公开索引。

    输入：session、owner_type 与实体。
    输出：None；全部 Publication archived、Route inactive/noindex。
    """
    if entity.status == "enabled":
        return
    publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == entity.id))).all())
    routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == entity.id))).all())
    for publication in publications:
        publication.status = "archived"
        publication.published_at = None
        publication.scheduled_at = None
    for route in routes:
        route.active = False
        route.indexable = False


async def _update_entity(
    session: AsyncSession,
    owner_type: str,
    entity_id: uuid.UUID,
    payload: BaseModel,
    actor_id: uuid.UUID | None,
) -> Any:
    """
    统一更新 Authority 主实体和翻译。

    输入：session、owner_type、entity_id、更新 payload、actor_id。
    输出：Any，更新后的实体。
    """
    model = _CONFIG[owner_type][0]
    entity = await session.get(model, entity_id)
    if entity is None:
        raise AppException(404, f"{owner_type}_not_found", "内容实体不存在")
    values = payload.model_dump(exclude={"translations"}, exclude_unset=True)
    if any(key in values for key in ("slug", "category_id")) and await _has_published_locale(session, owner_type, entity.id):
        changed = any(getattr(entity, key) != value for key, value in values.items() if key in {"slug", "category_id"})
        if changed:
            raise AppException(409, "published_url_change_required", "已发布 URL 必须通过专用事务修改")
    for key, value in values.items():
        setattr(entity, key, value)
    if owner_type == "author_expert" and entity.public_profile_enabled and not entity.is_real_person_verified:
        raise AppException(409, "verified_person_required", "公开 Expert 页面必须对应已核验的真实人物")
    translations = payload.translations
    if translations is not None:
        if len({item.locale_id for item in translations}) != len(translations):
            raise AppException(409, "duplicate_translation", "同一请求不能重复提交语言")
        for item in translations:
            await _upsert_translation(session, owner_type, entity, item, actor_id)
    else:
        default_locale = await _default_locale(session)
        await store_revision(session, owner_type, entity.id, default_locale.id, jsonable_encoder({"master": _snapshot(entity)}), actor_id)
    await _withdraw_disabled_entity(session, owner_type, entity)
    write_audit_log(session, action=f"{owner_type}.update", target_type=owner_type, target_id=str(entity.id), user_id=actor_id)
    await session.flush()
    return entity


async def update_case_study(session: AsyncSession, entity_id: uuid.UUID, payload: CaseStudyUpdate, actor_id: uuid.UUID | None = None) -> CaseStudy:
    """更新客户案例；输入 session/id/payload/actor，输出 CaseStudy。"""
    return await _update_entity(session, "case_study", entity_id, payload, actor_id)


async def update_knowledge_category(session: AsyncSession, entity_id: uuid.UUID, payload: KnowledgeCategoryUpdate, actor_id: uuid.UUID | None = None) -> KnowledgeCategory:
    """更新知识分类；输入 session/id/payload/actor，输出 KnowledgeCategory。"""
    return await _update_entity(session, "knowledge_category", entity_id, payload, actor_id)


async def update_author_expert(session: AsyncSession, entity_id: uuid.UUID, payload: AuthorExpertUpdate, actor_id: uuid.UUID | None = None) -> AuthorExpert:
    """更新真实作者专家；输入 session/id/payload/actor，输出 AuthorExpert。"""
    return await _update_entity(session, "author_expert", entity_id, payload, actor_id)


async def update_knowledge_article(session: AsyncSession, entity_id: uuid.UUID, payload: KnowledgeArticleUpdate, actor_id: uuid.UUID | None = None) -> KnowledgeArticle:
    """更新知识文章；输入 session/id/payload/actor，输出 KnowledgeArticle。"""
    if payload.author_id:
        author = await session.get(AuthorExpert, payload.author_id)
        if author is None or not author.is_real_person_verified:
            raise AppException(409, "verified_author_required", "知识文章必须使用已核验的真实作者")
    return await _update_entity(session, "knowledge_article", entity_id, payload, actor_id)


async def update_faq(session: AsyncSession, entity_id: uuid.UUID, payload: FAQUpdate, actor_id: uuid.UUID | None = None) -> FAQ:
    """更新 FAQ；输入 session/id/payload/actor，输出 FAQ。"""
    return await _update_entity(session, "faq", entity_id, payload, actor_id)


_RELATION_CONFIG: dict[str, dict[str, tuple[type, str, type]]] = {
    "case_study": {
        "product_ids": (CaseProduct, "product_id", Product),
        "material_ids": (CaseMaterial, "material_id", Material),
        "technology_ids": (CaseTechnology, "technology_id", Technology),
        "application_ids": (CaseApplication, "application_id", Application),
        "solution_ids": (CaseSolution, "solution_id", Solution),
    },
    "knowledge_article": {
        "product_ids": (ArticleProduct, "product_id", Product),
        "material_ids": (ArticleMaterial, "material_id", Material),
        "technology_ids": (ArticleTechnology, "technology_id", Technology),
        "application_ids": (ArticleApplication, "application_id", Application),
        "solution_ids": (ArticleSolution, "solution_id", Solution),
        "case_ids": (ArticleCase, "case_study_id", CaseStudy),
        "faq_ids": (ArticleFAQ, "faq_id", FAQ),
    },
    "faq": {
        "product_ids": (FAQProduct, "product_id", Product),
        "material_ids": (FAQMaterial, "material_id", Material),
        "solution_ids": (FAQSolution, "solution_id", Solution),
        "article_ids": (FAQArticle, "article_id", KnowledgeArticle),
        "case_ids": (FAQCase, "case_study_id", CaseStudy),
    },
}


async def replace_authority_relations(
    session: AsyncSession,
    owner_type: str,
    owner_id: uuid.UUID,
    payload: AuthorityRelationUpdate,
    actor_id: uuid.UUID | None = None,
) -> None:
    """
    整体替换 Case/Article/FAQ 的显式关系并保存 Revision。

    输入：session、owner_type、owner_id、关系列表与 actor_id。
    输出：None；目标缺失或停用时拒绝。
    """
    config = _RELATION_CONFIG.get(owner_type)
    if config is None:
        raise AppException(409, "relation_owner_not_supported", "该实体不支持关系编辑")
    owner_model = _CONFIG[owner_type][0]
    if await session.get(owner_model, owner_id) is None:
        raise AppException(404, f"{owner_type}_not_found", "关系主实体不存在")
    owner_column = {"case_study": "case_study_id", "knowledge_article": "article_id", "faq": "faq_id"}[owner_type]
    relation_snapshot: dict[str, list[str]] = {}
    for field_name, (relation_model, target_column, target_model) in config.items():
        target_ids = getattr(payload, field_name)
        if target_ids:
            found = set((await session.scalars(select(target_model.id).where(target_model.id.in_(target_ids)))).all())
            if found != set(target_ids):
                raise AppException(409, "relation_target_missing", f"{field_name} 包含不存在的目标")
        await session.execute(delete(relation_model).where(getattr(relation_model, owner_column) == owner_id))
        for order, target_id in enumerate(target_ids):
            session.add(relation_model(**{owner_column: owner_id, target_column: target_id, "sort_order": order}))
        relation_snapshot[field_name] = [str(value) for value in target_ids]
    locale = await _default_locale(session)
    await store_revision(session, owner_type, owner_id, locale.id, {"relations": relation_snapshot}, actor_id)
    write_audit_log(session, action=f"{owner_type}.relations.replace", target_type=owner_type, target_id=str(owner_id), user_id=actor_id, metadata=relation_snapshot)
    await session.flush()
