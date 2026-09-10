"""Case、Knowledge、FAQ 与真实 Expert 的最小 Admin CRUD API。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions.handlers import AppException
from app.core.pagination import PaginationParams
from app.core.responses import ApiResponse, success_response
from app.modules.audit.service import write_audit_log
from app.modules.auth.dependencies import get_current_user, require_csrf
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
    CaseStudyCreate,
    CaseStudyUpdate,
    FAQCreate,
    FAQUpdate,
    KnowledgeArticleCreate,
    KnowledgeArticleUpdate,
    KnowledgeCategoryCreate,
    KnowledgeCategoryUpdate,
)
from app.modules.authority.services import (
    create_author_expert,
    create_case_study,
    create_faq,
    create_knowledge_article,
    create_knowledge_category,
    replace_authority_relations,
    update_author_expert,
    update_case_study,
    update_faq,
    update_knowledge_article,
    update_knowledge_category,
)
from app.modules.content.enums import PublicationStatus
from app.modules.content.models import ContentPublication, ContentRoute, TranslationStatus
from app.modules.content.services.publication import transition_publication
from app.modules.discovery.models import GeoDocument, SeoDocument, SourceCitation
from app.modules.localization.models import Locale
from app.modules.users.models import User
from app.modules.users.service import collect_authorization

router = APIRouter(prefix="/authority", tags=["authority"])

_PUBLICATION_PERMISSION_ACTIONS: dict[PublicationStatus, str] = {
    PublicationStatus.REVIEW: "review",
    PublicationStatus.SCHEDULED: "publish",
    PublicationStatus.PUBLISHED: "publish",
    PublicationStatus.ARCHIVED: "archive",
    PublicationStatus.DRAFT: "update",
}

_ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "cases": {"permission": "case", "model": CaseStudy, "translation": CaseStudyTranslation, "owner_field": "case_study_id", "create_schema": CaseStudyCreate, "update_schema": CaseStudyUpdate, "create": create_case_study, "update": update_case_study, "owner_type": "case_study", "relations": True},
    "knowledge": {"permission": "knowledge", "model": KnowledgeArticle, "translation": KnowledgeArticleTranslation, "owner_field": "article_id", "create_schema": KnowledgeArticleCreate, "update_schema": KnowledgeArticleUpdate, "create": create_knowledge_article, "update": update_knowledge_article, "owner_type": "knowledge_article", "relations": True},
    "knowledge-categories": {"permission": "knowledge", "model": KnowledgeCategory, "translation": KnowledgeCategoryTranslation, "owner_field": "category_id", "create_schema": KnowledgeCategoryCreate, "update_schema": KnowledgeCategoryUpdate, "create": create_knowledge_category, "update": update_knowledge_category, "owner_type": "knowledge_category", "relations": False},
    "faqs": {"permission": "faq", "model": FAQ, "translation": FAQTranslation, "owner_field": "faq_id", "create_schema": FAQCreate, "update_schema": FAQUpdate, "create": create_faq, "update": update_faq, "owner_type": "faq", "relations": True},
    "experts": {"permission": "expert", "model": AuthorExpert, "translation": AuthorExpertTranslation, "owner_field": "author_expert_id", "create_schema": AuthorExpertCreate, "update_schema": AuthorExpertUpdate, "create": create_author_expert, "update": update_author_expert, "owner_type": "author_expert", "relations": False},
}

_RELATION_READ_CONFIG: dict[str, tuple[str, tuple[tuple[str, type, str], ...]]] = {
    "case_study": (
        "case_study_id",
        (
            ("product_ids", CaseProduct, "product_id"),
            ("material_ids", CaseMaterial, "material_id"),
            ("technology_ids", CaseTechnology, "technology_id"),
            ("application_ids", CaseApplication, "application_id"),
            ("solution_ids", CaseSolution, "solution_id"),
        ),
    ),
    "knowledge_article": (
        "article_id",
        (
            ("product_ids", ArticleProduct, "product_id"),
            ("material_ids", ArticleMaterial, "material_id"),
            ("technology_ids", ArticleTechnology, "technology_id"),
            ("application_ids", ArticleApplication, "application_id"),
            ("solution_ids", ArticleSolution, "solution_id"),
            ("case_ids", ArticleCase, "case_study_id"),
            ("faq_ids", ArticleFAQ, "faq_id"),
        ),
    ),
    "faq": (
        "faq_id",
        (
            ("product_ids", FAQProduct, "product_id"),
            ("material_ids", FAQMaterial, "material_id"),
            ("solution_ids", FAQSolution, "solution_id"),
            ("article_ids", FAQArticle, "article_id"),
            ("case_ids", FAQCase, "case_study_id"),
        ),
    ),
}


def _config(entity_type: str) -> dict[str, Any]:
    """
    解析白名单 Authority 类型配置。

    输入：entity_type，路由中的稳定复数名称。
    输出：dict，模型与服务配置；未知类型返回 404。
    """
    config = _ENTITY_CONFIG.get(entity_type)
    if config is None:
        raise AppException(404, "authority_type_not_found", "未知 Authority Content 类型")
    return config


def _require(user: User, permission_code: str) -> None:
    """
    在动态 Authority 路由中执行服务端原子权限检查。

    输入：当前 user 与 permission_code。
    输出：None；缺少权限时抛出 403。
    """
    _roles, permissions = collect_authorization(user)
    if permission_code not in permissions:
        raise AppException(403, "permission_denied", "没有执行此操作的权限")


def _serialize(entity: Any) -> dict[str, Any]:
    """
    将 Admin 已授权 ORM 实体转换为 JSON 字典。

    输入：entity，SQLAlchemy 实体。
    输出：dict，所有数据库列的 JSON 结果。
    """
    return jsonable_encoder({column.name: getattr(entity, column.name) for column in entity.__table__.columns})


async def _commit(session: AsyncSession) -> None:
    """
    提交 Admin 写事务并统一转换完整性冲突。

    输入：session，请求数据库会话。
    输出：None；IntegrityError 转为 409。
    """
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(409, "authority_conflict", "内容唯一键或关系约束冲突") from exc


async def _detail(session: AsyncSession, config: dict[str, Any], entity: Any) -> dict[str, Any]:
    """
    聚合 Admin 编辑页需要的翻译、生命周期、SEO/GEO 与来源状态。

    输入：session、类型 config 与实体。
    输出：dict，完整编辑 DTO；公开接口不会复用此含私密字段结构。
    """
    owner_type = config["owner_type"]
    owner_id = entity.id
    translations = list((await session.scalars(select(config["translation"]).where(getattr(config["translation"], config["owner_field"]) == owner_id).order_by(config["translation"].locale_id))).all())
    statuses = list((await session.scalars(select(TranslationStatus).where(TranslationStatus.owner_type == owner_type, TranslationStatus.owner_id == owner_id))).all())
    publications = list((await session.scalars(select(ContentPublication).where(ContentPublication.owner_type == owner_type, ContentPublication.owner_id == owner_id))).all())
    routes = list((await session.scalars(select(ContentRoute).where(ContentRoute.owner_type == owner_type, ContentRoute.owner_id == owner_id))).all())
    seo = list((await session.scalars(select(SeoDocument).where(SeoDocument.owner_type == owner_type, SeoDocument.owner_id == owner_id))).all())
    geo = list((await session.scalars(select(GeoDocument).where(GeoDocument.owner_type == owner_type, GeoDocument.owner_id == owner_id))).all())
    geo_ids = [item.id for item in geo]
    sources = list((await session.scalars(select(SourceCitation).where(SourceCitation.geo_document_id.in_(geo_ids)))).all()) if geo_ids else []
    result = _serialize(entity)
    relations: dict[str, list[str]] = {}
    relation_config = _RELATION_READ_CONFIG.get(owner_type)
    if relation_config:
        owner_column, relation_items = relation_config
        for field_name, relation_model, target_column in relation_items:
            values = await session.scalars(
                select(getattr(relation_model, target_column))
                .where(getattr(relation_model, owner_column) == owner_id)
                .order_by(relation_model.sort_order)
            )
            relations[field_name] = [str(value) for value in values.all()]
    result.update(
        translations=[_serialize(item) for item in translations],
        translation_statuses=[_serialize(item) for item in statuses],
        publications=[_serialize(item) for item in publications],
        routes=[_serialize(item) for item in routes],
        seo_documents=[_serialize(item) for item in seo],
        geo_documents=[_serialize(item) for item in geo],
        sources=[_serialize(item) for item in sources],
        relations=relations,
    )
    return result


async def _list_items_with_title_projection(
    session: AsyncSession,
    config: dict[str, Any],
    entities: list[Any],
) -> list[dict[str, Any]]:
    """
    为 Admin 列表补充中英文可读标题，不返回正文或私密客户字段之外的新数据。

    输入：
        session: AsyncSession，当前数据库会话。
        config: dict[str, Any]，Authority 实体白名单配置。
        entities: list[Any]，当前分页已经读取的主实体。

    输出：
        list[dict[str, Any]]，主实体列加中文标题、英文标题和翻译数量。
    """
    if not entities:
        return []

    translation_model = config["translation"]
    owner_column = getattr(translation_model, config["owner_field"])
    title_column_name = next(
        name for name in ("title", "question", "name") if hasattr(translation_model, name)
    )
    title_column = getattr(translation_model, title_column_name)
    translation_rows = (
        await session.execute(
            select(owner_column, Locale.code, title_column)
            .join(Locale, Locale.id == translation_model.locale_id)
            .where(owner_column.in_([entity.id for entity in entities]))
        )
    ).all()

    titles_by_owner: dict[uuid.UUID, dict[str, str]] = {}
    for owner_id, locale_code, title in translation_rows:
        if title:
            titles_by_owner.setdefault(owner_id, {})[locale_code] = str(title)

    items: list[dict[str, Any]] = []
    for entity in entities:
        titles = titles_by_owner.get(entity.id, {})
        fallback = next(iter(titles.values()), getattr(entity, "slug", "") or "未命名内容")
        item = _serialize(entity)
        item.update(
            display_title=titles.get("zh-CN") or titles.get("en") or fallback,
            display_title_en=titles.get("en") or titles.get("zh-CN") or fallback,
            translation_count=len(titles),
        )
        items.append(item)
    return items


@router.get("/{entity_type}", response_model=ApiResponse[dict[str, Any]])
async def list_authority_entities(
    entity_type: str,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """分页列出一种 Authority 实体，并使用对应 granular read 权限。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.read")
    model = config["model"]
    total = await session.scalar(select(func.count()).select_from(model))
    order = getattr(model, "sort_order", model.id)
    rows = list((await session.scalars(select(model).order_by(order, model.id).offset(pagination.offset).limit(pagination.page_size))).all())
    items = await _list_items_with_title_projection(session, config, rows)
    return success_response({"items": items, "page": pagination.page, "page_size": pagination.page_size, "total": total or 0})


@router.get("/{entity_type}/{entity_id}", response_model=ApiResponse[dict[str, Any]])
async def get_authority_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    """返回 Authority 实体的真实 Admin 编辑聚合 DTO。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.read")
    entity = await session.get(config["model"], entity_id)
    if entity is None:
        raise AppException(404, "authority_not_found", "内容实体不存在")
    return success_response(await _detail(session, config, entity))


@router.post("/{entity_type}", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[dict[str, Any]])
async def post_authority_entity(
    entity_type: str,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """按类型校验并创建 Authority 实体。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.create")
    validated = config["create_schema"].model_validate(payload)
    entity = await config["create"](session, validated, user.id)
    await _commit(session)
    return success_response(_serialize(entity))


@router.patch("/{entity_type}/{entity_id}", response_model=ApiResponse[dict[str, Any]])
async def patch_authority_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """按类型校验并更新 Authority 实体。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.update")
    validated = config["update_schema"].model_validate(payload)
    entity = await config["update"](session, entity_id, validated, user.id)
    await _commit(session)
    return success_response(_serialize(entity))


@router.post("/{entity_type}/{entity_id}/archive", response_model=ApiResponse[dict[str, Any]])
async def archive_authority_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """将 Authority 实体标记 retired 并退出公开索引。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.archive")
    validated = config["update_schema"].model_validate({"status": "retired"})
    entity = await config["update"](session, entity_id, validated, user.id)
    await _commit(session)
    return success_response(_serialize(entity))


@router.put("/{entity_type}/{entity_id}/relations", response_model=ApiResponse[dict[str, Any]])
async def put_authority_relations(
    entity_type: str,
    entity_id: uuid.UUID,
    payload: AuthorityRelationUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, Any]]:
    """整体替换 Authority 实体关系并写 Revision/Audit。"""
    config = _config(entity_type)
    _require(user, f"{config['permission']}.update")
    if not config["relations"]:
        raise AppException(409, "relations_not_supported", "该实体不支持关系编辑")
    await replace_authority_relations(session, config["owner_type"], entity_id, payload, user.id)
    await _commit(session)
    return success_response(payload.model_dump(mode="json"))


@router.post("/{entity_type}/{entity_id}/translations/{locale_id}/review", response_model=ApiResponse[dict[str, str]])
async def review_authority_translation(
    entity_type: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    将指定翻译标记为人工审核完成。

    输入：实体类型/ID、语言ID、session 与当前用户。
    输出：ApiResponse，新的 translation status。
    """
    config = _config(entity_type)
    _require(user, f"{config['permission']}.review")
    status_row = await session.scalar(
        select(TranslationStatus).where(
            TranslationStatus.owner_type == config["owner_type"],
            TranslationStatus.owner_id == entity_id,
            TranslationStatus.locale_id == locale_id,
        )
    )
    if status_row is None or status_row.status in {"missing", "published"}:
        raise AppException(409, "translation_not_reviewable", "只有已有草稿翻译可以人工审核")
    status_row.status = "human_reviewed"
    status_row.reviewed_by = user.id
    write_audit_log(session, action="translation.review", target_type=config["owner_type"], target_id=str(entity_id), user_id=user.id, metadata={"locale_id": str(locale_id)})
    await _commit(session)
    return success_response({"status": status_row.status})


@router.post("/{entity_type}/{entity_id}/translations/{locale_id}/publish", response_model=ApiResponse[dict[str, str]])
async def publish_faq_translation(
    entity_type: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    发布无独立 Route/Publication 的 FAQ 翻译。

    输入：仅允许 faqs 类型、实体/语言ID、session 与当前用户。
    输出：ApiResponse，新的 translation status。
    """
    config = _config(entity_type)
    if config["owner_type"] != "faq":
        raise AppException(409, "publication_required", "独立页面必须通过统一 Publication 发布")
    _require(user, "faq.publish")
    status_row = await session.scalar(
        select(TranslationStatus).where(
            TranslationStatus.owner_type == "faq",
            TranslationStatus.owner_id == entity_id,
            TranslationStatus.locale_id == locale_id,
        )
    )
    if status_row is None or status_row.status != "human_reviewed":
        raise AppException(409, "translation_not_reviewed", "FAQ 翻译完成人工审核后才能发布")
    status_row.status = "published"
    status_row.published_at = datetime.now(UTC)
    write_audit_log(session, action="translation.publish", target_type="faq", target_id=str(entity_id), user_id=user.id, metadata={"locale_id": str(locale_id)})
    await _commit(session)
    return success_response({"status": status_row.status})


@router.post("/{entity_type}/{entity_id}/publications/{locale_id}/{target_status}", response_model=ApiResponse[dict[str, str]])
async def transition_authority_publication(
    entity_type: str,
    entity_id: uuid.UUID,
    locale_id: uuid.UUID,
    target_status: PublicationStatus,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> ApiResponse[dict[str, str]]:
    """
    通过既有统一服务转换 Case/Knowledge/Expert 的 Publication。

    输入：实体类型/ID、语言、目标状态、session 与当前用户。
    输出：ApiResponse，新的 publication status。
    """
    config = _config(entity_type)
    if config["owner_type"] not in {"case_study", "knowledge_article", "author_expert"}:
        raise AppException(409, "publication_not_supported", "该实体没有独立 Publication")
    # Authority 外层校验实体职责；统一 transition_publication() 继续校验全局内容职责。
    permission_action = _PUBLICATION_PERMISSION_ACTIONS[target_status]
    _require(user, f"{config['permission']}.{permission_action}")
    publication = await session.scalar(select(ContentPublication).where(ContentPublication.owner_type == config["owner_type"], ContentPublication.owner_id == entity_id, ContentPublication.locale_id == locale_id))
    translation = await session.scalar(select(TranslationStatus).where(TranslationStatus.owner_type == config["owner_type"], TranslationStatus.owner_id == entity_id, TranslationStatus.locale_id == locale_id))
    route = await session.scalar(select(ContentRoute).where(ContentRoute.owner_type == config["owner_type"], ContentRoute.owner_id == entity_id, ContentRoute.locale_id == locale_id, ContentRoute.is_canonical.is_(True)))
    if publication is None or translation is None or route is None:
        raise AppException(409, "publication_records_required", "发布、翻译与 canonical Route 必须完整")
    _roles, permissions = collect_authorization(user)
    await transition_publication(
        session,
        publication=publication,
        translation=translation,
        route=route,
        target_status=target_status,
        actor_permissions=permissions,
        actor_id=user.id,
    )
    await _commit(session)
    return success_response({"status": publication.status})
