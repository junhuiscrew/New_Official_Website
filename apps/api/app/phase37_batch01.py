"""Phase 3.7 Batch01 真实资料的受控 dry-run 与 Draft-only 导入工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.phase37_pilot import (
    PilotApiClient,
    PilotImportError,
    build_webp_derivative,
    redact_evidence,
)

_BATCH_ID = "JH-P37-B01-20260906"
_TARGET_ENVIRONMENT = "phase37-local-https"
_PRODUCTS = (
    {
        "key": "P01",
        "slug": "nitrided-screw",
        "category": "screws",
        "media": "IMG-02",
        "code": "B01-P01",
    },
    {
        "key": "P02",
        # 原建议 slug 与已验收试点冲突；保留旧 draft，不覆盖并采用可编辑的新 slug。
        "slug": "junhui-nitrided-barrel",
        "category": "barrels",
        "media": "IMG-03",
        "code": "B01-P02",
    },
    {
        "key": "P03",
        "slug": "electroplated-screw",
        "category": "screws",
        "media": "IMG-04",
        "code": "B01-P03",
    },
)
_CATEGORIES = {
    "screws": {"zh-CN": "螺杆", "en": "Screws", "sort_order": 10},
    "barrels": {"zh-CN": "机筒", "en": "Barrels", "sort_order": 20},
}
_GROUPS = {
    "尺寸与外观": {"code": "dimensions-and-surface", "en": "Dimensions and surface"},
    "表面处理与硬度": {
        "code": "surface-treatment-and-hardness",
        "en": "Surface treatment and hardness",
    },
}
_ASSET_FILES = {
    "IMG-01": "assets/brand/junhui-logo-original.png",
    "IMG-02": "assets/products/junhui-nitrided-screw-original.png",
    "IMG-03": "assets/products/junhui-nitrided-barrel-original.png",
    "IMG-04": "assets/products/junhui-electroplated-screw-original.png",
}


class BatchState(BaseModel):
    """私有状态文件；只保存幂等映射，不保存凭据或签名 URL。"""

    batch_id: Literal["JH-P37-B01-20260906"] = _BATCH_ID
    target_environment: Literal["phase37-local-https"] = _TARGET_ENVIRONMENT
    mappings: dict[str, str] = Field(default_factory=dict)


def _read_json(path: Path) -> Any:
    """
    读取 UTF-8 JSON。

    输入：path，包内 JSON 路径。
    输出：Any，解析后的 JSON 数据。
    """
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(path: Path) -> BatchState:
    """
    读取或初始化私有幂等状态。

    输入：path，忽略目录内状态文件。
    输出：BatchState，经过批次和目标环境校验的状态。
    """
    if not path.exists():
        return BatchState()
    return BatchState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: BatchState) -> None:
    """
    原子保存不含凭据的私有幂等状态。

    输入：path、state。
    输出：None。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def load_batch_package(package_root: Path) -> dict[str, Any]:
    """
    校验 Batch01 规划资料、素材哈希和“零参数值”边界。

    输入：package_root，用户指定的解压目录。
    输出：dict，手工映射前已核验的公司、产品、字段与媒体资料。
    """
    products_payload = _read_json(package_root / "data/products-draft.json")
    definitions_payload = _read_json(
        package_root / "data/specification-definitions-proposal.json"
    )
    assets_payload = _read_json(package_root / "data/assets-manifest.json")
    company_payload = _read_json(package_root / "data/company-draft.json")
    values_payload = _read_json(package_root / "data/product-spec-values.json")
    products = products_payload.get("products", [])
    definitions = definitions_payload.get("definitions", [])
    assets = assets_payload.get("assets", [])
    if products_payload.get("kind") != "planning_manifest_not_api_payload":
        raise PilotImportError("products_manifest_kind_invalid")
    if definitions_payload.get("policy") != "definitions_only_no_values":
        raise PilotImportError("definition_policy_invalid")
    if len(products) != 3 or {item.get("external_key") for item in products} != {
        "P01",
        "P02",
        "P03",
    }:
        raise PilotImportError("product_scope_mismatch")
    if len(definitions) != 7 or any(item.get("default_value") is not None for item in definitions):
        raise PilotImportError("definition_scope_mismatch")
    if definitions_payload.get("product_spec_values") or values_payload:
        raise PilotImportError("product_values_must_be_empty")
    asset_by_id = {str(item["source_id"]): item for item in assets}
    if set(asset_by_id) != {"IMG-01", "IMG-02", "IMG-03", "IMG-04", "IMG-05"}:
        raise PilotImportError("asset_scope_mismatch")
    if asset_by_id["IMG-05"].get("candidate_website_media"):
        raise PilotImportError("internal_reference_must_not_be_public")
    for source_id, relative_path in _ASSET_FILES.items():
        asset = asset_by_id[source_id]
        source_path = package_root / relative_path
        if not source_path.is_file():
            raise PilotImportError(f"asset_missing:{source_id}")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if digest != asset.get("sha256"):
            raise PilotImportError(f"asset_hash_mismatch:{source_id}")
    f05 = next(item for item in definitions if item.get("external_key") == "F05")
    if (
        f05.get("display_name_zh") != "氮化后表面镀硬铬硬度"
        or f05.get("display_name_en_draft") is not None
        or not f05.get("term_confirmation_pending")
    ):
        raise PilotImportError("f05_frozen_label_mismatch")
    return {
        "products": products,
        "definitions": definitions,
        "assets": asset_by_id,
        "company": company_payload,
        "company_source": (
            package_root / "sources/company-introduction-user-original.txt"
        ).read_text(encoding="utf-8"),
    }


def _mapped_action(
    items: list[dict[str, Any]],
    *,
    field: str,
    value: str,
    mapped_id: str | None,
) -> Literal["create", "no-op", "conflict"]:
    """按自然键和私有映射保守分类远端资源。"""
    matches = [item for item in items if str(item.get(field)) == value]
    if not matches:
        return "conflict" if mapped_id else "create"
    if len(matches) != 1:
        return "conflict"
    return "no-op" if mapped_id == str(matches[0].get("id")) else "conflict"


def _derivatives(
    package: dict[str, Any], package_root: Path, output_dir: Path
) -> dict[str, Any]:
    """为获批的 Logo 和三张产品图生成去 EXIF 的等比例 WebP 派生件。"""
    results: dict[str, Any] = {}
    for source_id, relative_path in _ASSET_FILES.items():
        results[source_id] = build_webp_derivative(
            package_root / relative_path,
            output_dir / f"{source_id.lower()}-approved-draft.webp",
        )
    return results


def _remote_state(client: PilotApiClient) -> dict[str, Any]:
    """读取 Batch01 dry-run 所需的真实 CMS 列表和 Company 状态。"""
    locales = client.list_items("locales")
    locale_by_code = {str(item["code"]): item for item in locales}
    if not {"zh-CN", "en"}.issubset(locale_by_code):
        raise PilotImportError("required_locales_missing")
    company = client.get("trust/company-profile")
    return {
        "locales": locale_by_code,
        "categories": client.list_items("catalog/categories?page_size=100"),
        "products": client.list_items("catalog/products?page_size=100"),
        "groups": client.list_items("catalog/specifications/groups?page_size=100"),
        "definitions": client.list_items(
            "catalog/specifications/definitions?page_size=100"
        ),
        "media": client.list_items("media"),
        "company": company,
    }


def _build_plan(
    package: dict[str, Any],
    state: BatchState,
    remote: dict[str, Any],
    derivatives: dict[str, Any],
) -> dict[str, Any]:
    """构造 create/no-op/conflict/blocked 分类，不写远端。"""
    category_actions = {
        slug: _mapped_action(
            remote["categories"],
            field="slug",
            value=slug,
            mapped_id=state.mappings.get(f"category:{slug}"),
        )
        for slug in _CATEGORIES
    }
    product_actions = {
        item["key"]: _mapped_action(
            remote["products"],
            field="slug",
            value=item["slug"],
            mapped_id=state.mappings.get(f"product:{item['key']}"),
        )
        for item in _PRODUCTS
    }
    group_actions = {
        group["code"]: _mapped_action(
            remote["groups"],
            field="code",
            value=group["code"],
            mapped_id=state.mappings.get(f"group:{group['code']}"),
        )
        for group in _GROUPS.values()
    }
    definition_actions = {
        item["external_key"]: _mapped_action(
            remote["definitions"],
            field="code",
            value=item["proposed_code"],
            mapped_id=state.mappings.get(f"definition:{item['external_key']}"),
        )
        for item in package["definitions"]
    }
    media_ids = {str(item.get("id")) for item in remote["media"]}
    media_actions = {
        source_id: (
            "no-op"
            if state.mappings.get(f"media:{source_id}") in media_ids
            else "conflict"
            if state.mappings.get(f"media:{source_id}")
            else "create"
        )
        for source_id in _ASSET_FILES
    }
    company_profile = remote["company"].get("profile")
    company_mapping = state.mappings.get("company:profile")
    company_action = (
        "create"
        if company_profile is None and not company_mapping
        else "no-op"
        if company_profile and company_mapping == str(company_profile.get("id"))
        else "conflict"
    )
    effective_actions = [
        *category_actions.values(),
        *product_actions.values(),
        *group_actions.values(),
        *definition_actions.values(),
        *media_actions.values(),
        company_action,
    ]
    return {
        "batch_id": _BATCH_ID,
        "target_environment": _TARGET_ENVIRONMENT,
        "status": "conflict" if "conflict" in effective_actions else "ready",
        "locales": {"zh-CN": "no-op", "en": "no-op"},
        "company": company_action,
        "categories": category_actions,
        "products": product_actions,
        "proposed_slug_conflict": {
            "P02": {
                "proposed": "nitrided-barrel",
                "existing": any(
                    item.get("slug") == "nitrided-barrel" for item in remote["products"]
                ),
                "effective_draft_slug": "junhui-nitrided-barrel",
                "resolution": "preserve_existing_and_create_distinct_draft",
            }
        },
        "specification_groups": group_actions,
        "specification_definitions": definition_actions,
        "product_spec_values": "VALUES_INTENTIONALLY_EMPTY",
        "relations": "blocked",
        "media": media_actions,
        "internal_reference_img05": "blocked_publication",
        "derivatives": {
            source_id: {
                "sha256": result.sha256,
                "width": result.width,
                "height": result.height,
                "size_bytes": result.size_bytes,
            }
            for source_id, result in derivatives.items()
        },
    }


def dry_run_batch(
    package_root: Path, state_path: Path, output_dir: Path, api_base: str
) -> dict[str, Any]:
    """
    校验包并读取隔离 CMS，生成不写数据库/MinIO 的 dry-run。

    输入：package_root、state_path、output_dir、api_base。
    输出：dict，脱敏后的批次计划。
    """
    package = load_batch_package(package_root)
    state = load_state(state_path)
    derivatives = _derivatives(package, package_root, output_dir)
    client = PilotApiClient(api_base)
    try:
        client.login()
        remote = _remote_state(client)
    finally:
        client.close()
    return redact_evidence(_build_plan(package, state, remote, derivatives))


def _translation_inputs(
    locale_by_code: dict[str, Any], zh_name: str, en_name: str, zh_short: str, en_short: str
) -> list[dict[str, Any]]:
    """构造只含来源可支持事实的双语 Product/Category 草稿。"""
    return [
        {
            "locale_id": locale_by_code["zh-CN"]["id"],
            "name": zh_name,
            "fields": {"short_description": zh_short, "description": zh_short},
        },
        {
            "locale_id": locale_by_code["en"]["id"],
            "name": en_name,
            "fields": {"short_description": en_short, "description": en_short},
        },
    ]


def _upload_media(
    client: PilotApiClient,
    package: dict[str, Any],
    state: BatchState,
    derivatives: dict[str, Any],
    locale_by_code: dict[str, Any],
    source_ids: set[str],
    state_path: Path,
) -> int:
    """上传指定获批派生图并建立双语 alt；IMG-05 永不进入调用集合。"""
    created = 0
    for source_id in sorted(source_ids):
        mapping_key = f"media:{source_id}"
        mapped_media_id = state.mappings.get(mapping_key)
        if mapped_media_id:
            # 幂等复用也通过受权限和 CSRF 保护的 API 核验真实对象尺寸，端点同值时 no-op。
            client.post(f"media/{mapped_media_id}/refresh-image-metadata")
            continue
        derivative = derivatives[source_id]
        asset = package["assets"][source_id]
        with derivative.path.open("rb") as handle:
            media = client.post(
                "media/assets",
                files={"file": (derivative.path.name, handle, "image/webp")},
                data={"visibility": "public"},
            )
        media_id = str(media["id"])
        state.mappings[mapping_key] = media_id
        save_state(state_path, state)
        for locale_code, alt_text in (
            ("zh-CN", asset["alt_zh_draft"]),
            ("en", asset["alt_en_draft"]),
        ):
            client.patch(
                f"media/{media_id}/translations/{locale_by_code[locale_code]['id']}",
                data={"alt_text": alt_text, "title": alt_text, "caption": None},
            )
        created += 1
    return created


def _apply_company(
    client: PilotApiClient,
    package: dict[str, Any],
    state: BatchState,
    locale_by_code: dict[str, Any],
    state_path: Path,
) -> str:
    """通过既有 Trust API 保存 Company Profile 双语草稿。"""
    if state.mappings.get("company:profile"):
        return "no-op"
    company = package["company"]
    response = client.put(
        "trust/company-profile",
        json={
            "status": "enabled",
            "logo_media_id": state.mappings["media:IMG-01"],
            "translations": [
                {
                    "locale_id": locale_by_code["zh-CN"]["id"],
                    "fields": {
                        "company_name": company["display_name_zh_user_supplied"],
                        "short_intro": company["optional_short_intro_zh_draft"],
                        "full_intro": package["company_source"],
                    },
                },
                {
                    "locale_id": locale_by_code["en"]["id"],
                    "fields": {
                        "company_name": company["candidate_name_en_unreviewed"],
                        "short_intro": company["optional_short_intro_en_draft"],
                        "full_intro": company["optional_short_intro_en_draft"],
                    },
                },
            ],
        },
    )
    state.mappings["company:profile"] = str(response["id"])
    save_state(state_path, state)
    return "create"


def _apply_specification_dictionary(
    client: PilotApiClient,
    package: dict[str, Any],
    state: BatchState,
    locale_by_code: dict[str, Any],
    state_path: Path,
) -> dict[str, int]:
    """仅创建两个分组与七个字段定义，明确不创建 ProductSpecValue。"""
    created_groups = 0
    created_definitions = 0
    for zh_name, group in _GROUPS.items():
        mapping_key = f"group:{group['code']}"
        if not state.mappings.get(mapping_key):
            result = client.post(
                "catalog/specifications/groups",
                json={
                    "code": group["code"],
                    "sort_order": len(state.mappings),
                    "translations": [
                        {"locale_id": locale_by_code["zh-CN"]["id"], "name": zh_name},
                        {"locale_id": locale_by_code["en"]["id"], "name": group["en"]},
                    ],
                },
            )
            state.mappings[mapping_key] = str(result["id"])
            save_state(state_path, state)
            created_groups += 1
    for index, definition in enumerate(package["definitions"], start=1):
        mapping_key = f"definition:{definition['external_key']}"
        if state.mappings.get(mapping_key):
            continue
        group_code = _GROUPS[definition["proposed_group"]]["code"]
        translations = [
            {
                "locale_id": locale_by_code["zh-CN"]["id"],
                "name": definition["display_name_zh"],
                "fields": {"help_text": definition["notes"]},
            }
        ]
        if definition["display_name_en_draft"]:
            translations.append(
                {
                    "locale_id": locale_by_code["en"]["id"],
                    "name": definition["display_name_en_draft"],
                    "fields": {"help_text": "Draft term; requires user review."},
                }
            )
        result = client.post(
            "catalog/specifications/definitions",
            json={
                "group_id": state.mappings[f"group:{group_code}"],
                "code": definition["proposed_code"],
                "value_type": definition["proposed_value_type"],
                "default_unit": definition["proposed_unit"],
                "is_filterable": False,
                "sort_order": index,
                "translations": translations,
            },
        )
        state.mappings[mapping_key] = str(result["id"])
        save_state(state_path, state)
        created_definitions += 1
    return {"groups": created_groups, "definitions": created_definitions, "values": 0}


def _apply_products(
    client: PilotApiClient,
    package: dict[str, Any],
    state: BatchState,
    locale_by_code: dict[str, Any],
    state_path: Path,
    limit: int,
) -> int:
    """按批准顺序创建最多 limit 款产品草稿，不自动建立规格或关系。"""
    product_source = {item["external_key"]: item for item in package["products"]}
    selected = _PRODUCTS[:limit]
    for product in selected:
        category_slug = product["category"]
        category_key = f"category:{category_slug}"
        if not state.mappings.get(category_key):
            category = _CATEGORIES[category_slug]
            created = client.post(
                "catalog/categories",
                json={
                    "slug": category_slug,
                    "sort_order": category["sort_order"],
                    "translations": _translation_inputs(
                        locale_by_code,
                        category["zh-CN"],
                        category["en"],
                        f"{category['zh-CN']}产品分类。",
                        f"{category['en']} product category.",
                    ),
                },
            )
            state.mappings[category_key] = str(created["id"])
            save_state(state_path, state)
        product_key = f"product:{product['key']}"
        if state.mappings.get(product_key):
            continue
        source = product_source[product["key"]]
        created = client.post(
            "catalog/products",
            json={
                "category_id": state.mappings[category_key],
                "code": product["code"],
                "slug": product["slug"],
                "status": "enabled",
                "featured": False,
                "sort_order": list(_PRODUCTS).index(product) + 1,
                "primary_media_id": state.mappings[f"media:{product['media']}"],
                "translations": _translation_inputs(
                    locale_by_code,
                    source["name_zh_user_supplied"],
                    source["name_en_draft"],
                    source["short_description_zh_draft"],
                    source["short_description_en_draft"],
                ),
            },
        )
        state.mappings[product_key] = str(created["id"])
        save_state(state_path, state)
    return sum(bool(state.mappings.get(f"product:{item['key']}")) for item in selected)


def verify_batch(client: PilotApiClient, state: BatchState, limit: int) -> dict[str, Any]:
    """验证已写入对象仍为双语 draft、关闭 Route，且参数值和关系为空。"""
    product_checks: dict[str, Any] = {}
    for product in _PRODUCTS[:limit]:
        product_id = state.mappings.get(f"product:{product['key']}")
        if not product_id:
            raise PilotImportError(f"product_mapping_missing:{product['key']}")
        detail = client.get(f"catalog/products/{product_id}")
        values = client.list_items(
            f"catalog/specifications/values?product_id={product_id}&page_size=100"
        )
        checks = {
            "two_translations": len(detail.get("translations", [])) == 2,
            "translations_draft": len(detail.get("translation_statuses", [])) == 2
            and all(item.get("status") == "draft" for item in detail["translation_statuses"]),
            "publications_draft": len(detail.get("publications", [])) == 2
            and all(item.get("status") == "draft" for item in detail["publications"]),
            "routes_closed": len(detail.get("routes", [])) == 2
            and all(not item.get("active") and not item.get("indexable") for item in detail["routes"]),
            "values_intentionally_empty": not values and not detail.get("specifications"),
            "relations_empty": all(
                not relation_values for relation_values in detail.get("relations", {}).values()
            ),
            "primary_media_set": bool(detail.get("primary_media_id")),
        }
        if not all(checks.values()):
            raise PilotImportError(f"product_draft_verification_failed:{product['key']}")
        product_checks[product["key"]] = checks
    company = client.get("trust/company-profile")
    company_checks = {
        "profile_present": company.get("profile") is not None,
        "two_translations": len(company.get("translations", [])) == 2,
        "translations_draft": len(company.get("translation_statuses", [])) == 2
        and all(item.get("status") == "draft" for item in company["translation_statuses"]),
        "publications_draft": len(company.get("publications", [])) == 2
        and all(item.get("status") == "draft" for item in company["publications"]),
        "routes_closed": len(company.get("routes", [])) == 2
        and all(not item.get("active") and not item.get("indexable") for item in company["routes"]),
    }
    if not all(company_checks.values()):
        raise PilotImportError("company_draft_verification_failed")
    return {"products": product_checks, "company": company_checks}


def apply_batch(
    package_root: Path,
    state_path: Path,
    output_dir: Path,
    api_base: str,
    limit: int,
) -> dict[str, Any]:
    """
    经显式环境门禁，通过既有 API 导入公司、字段及最多三款 Product draft。

    输入：package_root、state_path、output_dir、api_base、limit。
    输出：dict，脱敏后的写入和生命周期校验结果。
    """
    if os.getenv("PHASE37_BATCH01_DRAFT_AUTHORIZED") != "1":
        raise PilotImportError("batch01_draft_authorization_required")
    if limit not in {1, 3}:
        raise PilotImportError("batch01_limit_must_be_1_or_3")
    package = load_batch_package(package_root)
    state = load_state(state_path)
    derivatives = _derivatives(package, package_root, output_dir)
    client = PilotApiClient(api_base)
    try:
        client.login()
        remote = _remote_state(client)
        plan = _build_plan(package, state, remote, derivatives)
        if plan["status"] == "conflict":
            raise PilotImportError("batch01_remote_conflict")
        selected_media = {"IMG-01", *(item["media"] for item in _PRODUCTS[:limit])}
        created_media = _upload_media(
            client,
            package,
            state,
            derivatives,
            remote["locales"],
            selected_media,
            state_path,
        )
        company_action = _apply_company(
            client, package, state, remote["locales"], state_path
        )
        dictionary = _apply_specification_dictionary(
            client, package, state, remote["locales"], state_path
        )
        product_count = _apply_products(
            client, package, state, remote["locales"], state_path, limit
        )
        verification = verify_batch(client, state, limit)
    finally:
        client.close()
    return redact_evidence(
        {
            "batch_id": _BATCH_ID,
            "status": "applied",
            "limit": limit,
            "created_media": created_media,
            "company": company_action,
            "dictionary": dictionary,
            "mapped_products": product_count,
            "product_spec_values": "VALUES_INTENTIONALLY_EMPTY",
            "verification": verification,
        }
    )


def main() -> int:
    """解析 Batch01 dry-run/apply 命令并打印脱敏 JSON。"""
    parser = argparse.ArgumentParser(description="Phase 3.7 Batch01 Draft Import")
    parser.add_argument("command", choices=("dry-run", "apply", "verify"))
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    state = load_state(Path(args.state))
    client: PilotApiClient | None = None
    if args.command == "dry-run":
        result = dry_run_batch(
            Path(args.package_root), Path(args.state), Path(args.output_dir), args.api_base
        )
    elif args.command == "apply":
        result = apply_batch(
            Path(args.package_root),
            Path(args.state),
            Path(args.output_dir),
            args.api_base,
            args.limit,
        )
    else:
        client = PilotApiClient(args.api_base)
        try:
            client.login()
            result = verify_batch(client, state, args.limit)
        finally:
            client.close()
    print(json.dumps(redact_evidence(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
