"""Demo R2 用户内容包的严格读取、稳定标识和指纹工具。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

DEMO_BATCH_ID = "JH-DEMO-R2-V1"
DEMO_PACKAGE_KIND = "ORIGINAL_DEMO_CONTENT_STARTER_NOT_DIRECT_API_PAYLOAD"
DEMO_PACKAGE_VERSION = "DEMO-CONTENT-R2-V1"
DEMO_RECORD_COUNT = 90
DEMO_RELATION_COUNT = 72
DEMO_HOMEPAGE_MODULE_COUNT = 14

_SLUG_FRAGMENT = re.compile(r"[^a-z0-9]+")


class DemoPackageError(ValueError):
    """表示用户内容包不满足已授权 Demo R2 范围。"""


class DemoRecord(BaseModel):
    """一条用户提供的演示内容记录；额外字段保留给领域映射器处理。"""

    model_config = ConfigDict(extra="allow")

    kind: str = Field(min_length=1, max_length=80)
    alias: str = Field(min_length=1, max_length=160)
    content_origin: str
    demo_batch_id: str
    replaces_real_data: bool
    locale_content: dict[str, dict[str, Any]]

    @field_validator("locale_content")
    @classmethod
    def validate_bilingual_content(
        cls, locale_content: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        校验一条演示记录恰好提供中文和英文内容。

        输入：locale_content，按语言代码组织的内容字典。
        输出：dict，校验通过的原内容。
        """
        if set(locale_content) != {"zh-CN", "en"}:
            raise ValueError("demo_record_bilingual_content_required")
        if any(not isinstance(content, dict) or not content for content in locale_content.values()):
            raise ValueError("demo_record_locale_content_empty")
        return locale_content


class DemoRelation(BaseModel):
    """包内一条稳定别名关系。"""

    model_config = ConfigDict(extra="forbid")

    relation: str = Field(min_length=1, max_length=100)
    from_alias: str = Field(alias="from", min_length=1, max_length=160)
    to_alias: str = Field(alias="to", min_length=1, max_length=160)
    semantics: str | None = None


class DemoHomepageModule(BaseModel):
    """首页固定十四模块的一条范围声明。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    label_zh: str = Field(min_length=1, max_length=160)
    label_en: str = Field(min_length=1, max_length=160)
    required_demo_content: bool


class DemoPackage(BaseModel):
    """通过范围校验后可供领域初始化器读取的 Demo R2 内容包。"""

    model_config = ConfigDict(extra="allow")

    schema_version: int
    kind: str
    version: str
    state: str
    record_count: int
    demo_batch_id: str
    homepage: list[DemoHomepageModule]
    records: list[DemoRecord]
    relations: list[DemoRelation]
    demo_page_copy: dict[str, Any]


def canonical_demo_slug(alias: str, explicit_slug: str | None) -> str:
    """
    为缺少slug的演示记录生成稳定、可读且不会冒充正式内容的路径。

    输入：alias，包内稳定别名；explicit_slug，可选显式slug。
    输出：str，合法的小写kebab-case Demo slug。
    """
    if explicit_slug:
        normalized = _SLUG_FRAGMENT.sub("-", explicit_slug.strip().lower()).strip("-")
    else:
        normalized = _SLUG_FRAGMENT.sub("-", alias.strip().lower()).strip("-")
        if not normalized.startswith("demo-"):
            normalized = f"demo-{normalized}"
    if not normalized or len(normalized) > 180:
        raise DemoPackageError("demo_slug_invalid")
    return normalized


def record_fingerprint(record: DemoRecord | dict[str, Any]) -> str:
    """
    计算与JSON键顺序无关的内容指纹。

    输入：record，Pydantic演示记录或原始字典。
    输出：str，64位小写SHA256。
    """
    payload = record.model_dump(mode="json", by_alias=True) if isinstance(record, DemoRecord) else record
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_demo_package(path: Path) -> DemoPackage:
    """
    读取并验证用户交付的90条双语内容与72条关系。

    输入：path，私有内容包JSON路径。
    输出：DemoPackage，仅在批次、版本、数量和引用完整时返回。
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoPackageError("demo_package_unreadable") from exc

    raw_records = payload.get("records") if isinstance(payload, dict) else None
    record_batches = {
        str(item.get("demo_batch_id"))
        for item in raw_records or []
        if isinstance(item, dict)
    }
    declared_batch = payload.get("demo_batch_id") if isinstance(payload, dict) else None
    if record_batches != {DEMO_BATCH_ID} or (
        declared_batch is not None and declared_batch != DEMO_BATCH_ID
    ):
        raise DemoPackageError("demo_batch_id_invalid")

    enriched = dict(payload)
    enriched["demo_batch_id"] = DEMO_BATCH_ID
    try:
        package = DemoPackage.model_validate(enriched)
    except ValidationError as exc:
        raise DemoPackageError("demo_package_schema_invalid") from exc

    if package.kind != DEMO_PACKAGE_KIND or package.version != DEMO_PACKAGE_VERSION:
        raise DemoPackageError("demo_package_identity_invalid")
    if package.record_count != DEMO_RECORD_COUNT or len(package.records) != DEMO_RECORD_COUNT:
        raise DemoPackageError("demo_record_count_invalid")
    if len(package.relations) != DEMO_RELATION_COUNT:
        raise DemoPackageError("demo_relation_count_invalid")
    if len(package.homepage) != DEMO_HOMEPAGE_MODULE_COUNT:
        raise DemoPackageError("demo_homepage_module_count_invalid")

    aliases = [record.alias for record in package.records]
    if len(set(aliases)) != len(aliases):
        raise DemoPackageError("demo_record_alias_duplicate")
    alias_set = set(aliases)
    if any(
        relation.from_alias not in alias_set or relation.to_alias not in alias_set
        for relation in package.relations
    ):
        raise DemoPackageError("demo_relation_target_missing")
    return package
