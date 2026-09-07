"""SEO/GEO、来源、Redirect 与 URL Change 请求模型。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SeoDocumentUpsert(BaseModel):
    """统一 SEO 文档新增或更新输入。"""

    seo_title: str | None = Field(default=None, max_length=320)
    meta_description: str | None = None
    canonical_override: str | None = Field(default=None, max_length=500)
    robots_index: bool = True
    robots_follow: bool = True
    og_title: str | None = Field(default=None, max_length=320)
    og_description: str | None = None
    og_media_id: uuid.UUID | None = None
    schema_override_jsonb: dict[str, Any] | None = None


class SitePageSeoUpdate(SeoDocumentUpsert):
    """固定 SitePage SEO 局部更新输入；拒绝后台误传其他业务字段。"""

    model_config = ConfigDict(extra="forbid")


class GeoDocumentUpsert(BaseModel):
    """统一 GEO 文档新增或更新输入；可见事实由服务端数据库构造。"""

    model_config = ConfigDict(extra="forbid")

    direct_answer: str | None = None
    target_questions_json: list[str] = Field(default_factory=list)
    key_facts_json: list[str] = Field(default_factory=list)
    evidence_json: list[str] = Field(default_factory=list)
    related_questions_json: list[str] = Field(default_factory=list)
    reviewer_id: uuid.UUID | None = None
    last_reviewed_at: datetime | None = None


class SourceCitationCreate(BaseModel):
    """可核验来源引用创建输入。"""

    geo_document_id: uuid.UUID | None = None
    article_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=1000)
    publisher: str | None = Field(default=None, max_length=240)
    publication_date: date | None = None
    access_date: date | None = None
    source_type: Literal[
        "official",
        "standard",
        "technical-paper",
        "manufacturer",
        "internal-first-party",
        "case-evidence",
        "other",
    ]
    sort_order: int = 0


class RedirectRuleCreate(BaseModel):
    """精确 Redirect 规则创建输入。"""

    source_host: str = Field(min_length=1, max_length=255)
    source_path: str = Field(min_length=1, max_length=1000)
    target_url: str = Field(min_length=8, max_length=1500)
    status_code: Literal[301, 302, 307, 308] = 301
    enabled: bool = True
    notes: str | None = None


class PublishedUrlChange(BaseModel):
    """已发布 canonical URL 事务变更输入。"""

    owner_type: Literal["product", "case_study", "knowledge_article", "author_expert"]
    owner_id: uuid.UUID
    locale_id: uuid.UUID
    new_path: str = Field(min_length=3, max_length=500)
