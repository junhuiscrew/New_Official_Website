"""Case Study、Knowledge、FAQ 与真实 Author/Expert 的结构化 ORM 模型。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UuidPrimaryKeyMixin

_JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")
_LIFECYCLE_CHECK = "status IN ('enabled','disabled','retired')"


class CaseStudy(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """客户案例主实体；客户识别信息默认只允许内部访问。"""

    __tablename__ = "case_studies"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="case_study_status_value"),
        {"comment": "客户案例主实体表"},
    )

    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, comment="稳定案例Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, comment="案例国家二字代码")
    industry: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="客户所属行业")
    machine_brand: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="设备品牌")
    machine_model: Mapped[str | None] = mapped_column(String(160), nullable=True, comment="设备型号")
    screw_diameter: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="螺杆直径描述")
    processed_material_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加工材料内部描述")
    filler_percentage: Mapped[str | None] = mapped_column(String(80), nullable=True, comment="填充比例描述")
    client_name: Mapped[str | None] = mapped_column(String(240), nullable=True, comment="客户真实名称，仅内部使用")
    client_address: Mapped[str | None] = mapped_column(Text, nullable=True, comment="客户真实地址，仅内部使用")
    client_logo_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="客户Logo媒体ID，仅内部使用")
    client_name_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否获得客户名称公开许可")
    client_logo_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否获得客户Logo公开许可")
    client_address_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否获得客户地址公开许可")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐案例")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="案例排序")
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="案例主媒体ID")


class CaseStudyTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """客户案例多语言可见正文。"""

    __tablename__ = "case_study_translations"
    __table_args__ = (
        UniqueConstraint("case_study_id", "locale_id", name="uq_case_study_translation_locale"),
        {"comment": "客户案例翻译表"},
    )

    case_study_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("case_studies.id", ondelete="CASCADE"), nullable=False, comment="客户案例ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    title: Mapped[str] = mapped_column(String(240), nullable=False, comment="案例标题")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="案例摘要")
    client_description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="经许可的客户公开描述")
    problem: Mapped[str | None] = mapped_column(Text, nullable=True, comment="客户问题")
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="技术分析")
    solution: Mapped[str | None] = mapped_column(Text, nullable=True, comment="实施方案")
    result: Mapped[str | None] = mapped_column(Text, nullable=True, comment="实施结果")
    engineer_comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="工程师点评")


class KnowledgeCategory(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """Knowledge Center 稳定分类。"""

    __tablename__ = "knowledge_categories"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="knowledge_category_status_value"),
        {"comment": "知识分类表"},
    )

    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, comment="稳定知识分类Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="分类排序")


class KnowledgeCategoryTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """知识分类翻译。"""

    __tablename__ = "knowledge_category_translations"
    __table_args__ = (
        UniqueConstraint("category_id", "locale_id", name="uq_knowledge_category_translation_locale"),
        {"comment": "知识分类翻译表"},
    )

    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_categories.id", ondelete="CASCADE"), nullable=False, comment="知识分类ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    name: Mapped[str] = mapped_column(String(160), nullable=False, comment="分类名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="分类说明")


class AuthorExpert(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """真实作者或专家公开资料；不得用于虚构人物。"""

    __tablename__ = "author_experts"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="author_expert_status_value"),
        CheckConstraint("role_type IN ('author','expert','author_expert')", name="author_expert_role_type_value"),
        {"comment": "真实作者专家表"},
    )

    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, comment="稳定作者专家Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    role_type: Mapped[str] = mapped_column(String(24), nullable=False, comment="人物类型：author作者，expert专家，author_expert兼任")
    is_real_person_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否已核验为真实人物")
    public_profile_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否允许发布独立公开资料页")
    profile_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="公开头像媒体ID")
    public_email: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="经本人许可的公开邮箱")
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="公开从业年限")
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="公开LinkedIn链接")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="人物排序")


class AuthorExpertTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """真实作者或专家的多语言公开资料。"""

    __tablename__ = "author_expert_translations"
    __table_args__ = (
        UniqueConstraint("author_expert_id", "locale_id", name="uq_author_expert_translation_locale"),
        {"comment": "作者专家翻译表"},
    )

    author_expert_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("author_experts.id", ondelete="CASCADE"), nullable=False, comment="作者专家ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    name: Mapped[str] = mapped_column(String(160), nullable=False, comment="人物姓名")
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="公开职位")
    short_bio: Mapped[str | None] = mapped_column(Text, nullable=True, comment="公开短简介")
    expertise_json: Mapped[list[str]] = mapped_column(_JSON_DOCUMENT_TYPE, nullable=False, default=list, comment="专业领域JSON数组")


class KnowledgeArticle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """Knowledge Center 文章主实体。"""

    __tablename__ = "knowledge_articles"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="knowledge_article_status_value"),
        {"comment": "知识文章主实体表"},
    )

    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_categories.id", ondelete="RESTRICT"), nullable=False, comment="知识分类ID")
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, comment="稳定文章Slug")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("author_experts.id", ondelete="RESTRICT"), nullable=False, comment="真实作者ID")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("author_experts.id", ondelete="SET NULL"), nullable=True, comment="真实审核专家ID")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", comment="是否推荐文章")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="文章排序")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近专业复核时间")
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, comment="文章主媒体ID")


class KnowledgeArticleTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """知识文章安全 Markdown 正文翻译。"""

    __tablename__ = "knowledge_article_translations"
    __table_args__ = (
        UniqueConstraint("article_id", "locale_id", name="uq_knowledge_article_translation_locale"),
        {"comment": "知识文章翻译表"},
    )

    article_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False, comment="知识文章ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    title: Mapped[str] = mapped_column(String(260), nullable=False, comment="文章标题")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="文章摘要")
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, comment="安全Markdown正文")


class FAQ(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """FAQ 主实体；默认只随关联页面展示。"""

    __tablename__ = "faqs"
    __table_args__ = (
        CheckConstraint(_LIFECYCLE_CHECK, name="faq_status_value"),
        {"comment": "常见问题主实体表"},
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="enabled", server_default="enabled", comment="业务状态：enabled启用，disabled停用，retired退役")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="常见问题排序")


class FAQTranslation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """FAQ 多语言问题与答案。"""

    __tablename__ = "faq_translations"
    __table_args__ = (
        UniqueConstraint("faq_id", "locale_id", name="uq_faq_translation_locale"),
        {"comment": "常见问题翻译表"},
    )

    faq_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("faqs.id", ondelete="CASCADE"), nullable=False, comment="常见问题ID")
    locale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("locales.id", ondelete="RESTRICT"), nullable=False, comment="语言ID")
    question: Mapped[str] = mapped_column(String(500), nullable=False, comment="公开问题")
    answer: Mapped[str] = mapped_column(Text, nullable=False, comment="公开答案")


def _relation_model(
    class_name: str,
    table_name: str,
    left_column: str,
    left_table: str,
    right_column: str,
    right_table: str,
) -> type[Base]:
    """
    构造 Authority Content 显式关系模型。

    输入：类名、表名、左右字段与目标表名。
    输出：type[Base]，带联合主键和排序字段的 SQLAlchemy 模型。
    """
    return type(
        class_name,
        (Base,),
        {
            "__tablename__": table_name,
            "__table_args__": {"comment": f"{table_name} 显式关系表"},
            left_column: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{left_table}.id", ondelete="CASCADE"), primary_key=True, comment="左侧实体ID"),
            right_column: mapped_column(Uuid(as_uuid=True), ForeignKey(f"{right_table}.id", ondelete="CASCADE"), primary_key=True, comment="右侧实体ID"),
            "sort_order": mapped_column(Integer, nullable=False, default=0, server_default="0", comment="关系排序"),
        },
    )


CaseProduct = _relation_model("CaseProduct", "case_products", "case_study_id", "case_studies", "product_id", "products")
CaseMaterial = _relation_model("CaseMaterial", "case_materials", "case_study_id", "case_studies", "material_id", "materials")
CaseTechnology = _relation_model("CaseTechnology", "case_technologies", "case_study_id", "case_studies", "technology_id", "technologies")
CaseApplication = _relation_model("CaseApplication", "case_applications", "case_study_id", "case_studies", "application_id", "applications")
CaseSolution = _relation_model("CaseSolution", "case_solutions", "case_study_id", "case_studies", "solution_id", "solutions")
ArticleProduct = _relation_model("ArticleProduct", "article_products", "article_id", "knowledge_articles", "product_id", "products")
ArticleMaterial = _relation_model("ArticleMaterial", "article_materials", "article_id", "knowledge_articles", "material_id", "materials")
ArticleTechnology = _relation_model("ArticleTechnology", "article_technologies", "article_id", "knowledge_articles", "technology_id", "technologies")
ArticleApplication = _relation_model("ArticleApplication", "article_applications", "article_id", "knowledge_articles", "application_id", "applications")
ArticleSolution = _relation_model("ArticleSolution", "article_solutions", "article_id", "knowledge_articles", "solution_id", "solutions")
ArticleCase = _relation_model("ArticleCase", "article_cases", "article_id", "knowledge_articles", "case_study_id", "case_studies")
ArticleFAQ = _relation_model("ArticleFAQ", "article_faqs", "article_id", "knowledge_articles", "faq_id", "faqs")
FAQProduct = _relation_model("FAQProduct", "faq_products", "faq_id", "faqs", "product_id", "products")
FAQMaterial = _relation_model("FAQMaterial", "faq_materials", "faq_id", "faqs", "material_id", "materials")
FAQSolution = _relation_model("FAQSolution", "faq_solutions", "faq_id", "faqs", "solution_id", "solutions")
FAQArticle = _relation_model("FAQArticle", "faq_articles", "faq_id", "faqs", "article_id", "knowledge_articles")
FAQCase = _relation_model("FAQCase", "faq_cases", "faq_id", "faqs", "case_study_id", "case_studies")


AUTHORITY_ENTITY_MODELS = (CaseStudy, KnowledgeCategory, KnowledgeArticle, FAQ, AuthorExpert)
AUTHORITY_TRANSLATION_MODELS = (
    CaseStudyTranslation,
    KnowledgeCategoryTranslation,
    KnowledgeArticleTranslation,
    FAQTranslation,
    AuthorExpertTranslation,
)
AUTHORITY_RELATION_MODELS = (
    CaseProduct,
    CaseMaterial,
    CaseTechnology,
    CaseApplication,
    CaseSolution,
    ArticleProduct,
    ArticleMaterial,
    ArticleTechnology,
    ArticleApplication,
    ArticleSolution,
    ArticleCase,
    ArticleFAQ,
    FAQProduct,
    FAQMaterial,
    FAQSolution,
    FAQArticle,
    FAQCase,
)
