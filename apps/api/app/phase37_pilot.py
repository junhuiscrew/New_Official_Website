"""Phase 3.7 首批产品的受控 Draft Import 工具。"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, HttpUrl, model_validator

_CATEGORY_KEY = "junhui:product-category:injection-molding-machine-barrels"
_PRODUCT_KEY = "junhui:product:nitrided-barrel"
_TARGET_ENVIRONMENT = "phase37-local-https"
_APPROVED_SOURCE_NAMES = (
    "01-骏辉螺杆 氮化机筒 (1).jpg",
    "02-骏辉螺杆 氮化机筒 (3).jpg",
    "03-骏辉螺杆 氮化机筒 (4).jpg",
    "04-骏辉螺杆 氮化机筒 (5).jpg",
)
_REDACTED_KEYS = {
    "access_token",
    "cookie",
    "csrf_token",
    "password",
    "refresh_token",
    "signed_url",
    "storage_key",
}


class PilotImportError(RuntimeError):
    """首批导入门禁、来源或远端状态不符合批准范围。"""


class PilotContent(BaseModel):
    """分类或产品的稳定外部键、slug 与双语草稿名称。"""

    external_key: str
    slug: str
    name_zh_cn: str = Field(min_length=1)
    name_en: str = Field(min_length=1)


class PilotSource(BaseModel):
    """单张获批源图片的哈希、顺序与双语媒体文本。"""

    external_key: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    order: int = Field(ge=1)
    alt_zh_cn: str = Field(min_length=1)
    alt_en: str = Field(min_length=1)


class PilotManifest(BaseModel):
    """首批导入的私有批准清单与幂等映射。"""

    schema_version: Literal[1]
    batch_id: str = Field(pattern=r"^[a-z0-9-]+$")
    target_environment: Literal["phase37-local-https"]
    draft_import_authorized: bool
    protected_preview_publish_authorized: bool
    reviewer_zh_cn: Literal["user"]
    reviewer_en: Literal["user"]
    content_source_policy: Literal["unambiguous_source_facts_only"]
    out_of_scope_sources: list[str]
    source_url: HttpUrl
    category: PilotContent
    product: PilotContent
    sources: list[PilotSource]
    mappings: dict[str, str] = Field(default_factory=dict)
    blocked_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_frozen_scope(self) -> PilotManifest:
        """
        校验用户批准的单产品、四图片和 Draft-only 范围。

        输入：self，已完成字段级校验的 manifest。
        输出：PilotManifest，范围完全匹配时返回自身。
        """
        if self.category.external_key != _CATEGORY_KEY:
            raise ValueError("category_scope_mismatch")
        if self.product.external_key != _PRODUCT_KEY:
            raise ValueError("product_scope_mismatch")
        if len(self.sources) != 4:
            raise ValueError("exactly_four_sources")
        if sorted(source.order for source in self.sources) != [1, 2, 3, 4]:
            raise ValueError("source_order_mismatch")
        if len({source.external_key for source in self.sources}) != 4:
            raise ValueError("duplicate_source_external_key")
        ordered_sources = sorted(self.sources, key=lambda source: source.order)
        if tuple(source.filename for source in ordered_sources) != _APPROVED_SOURCE_NAMES:
            raise ValueError("source_filename_scope_mismatch")
        expected_keys = {
            f"junhui:media:nitrided-barrel:{order:02d}" for order in range(1, 5)
        }
        if {source.external_key for source in self.sources} != expected_keys:
            raise ValueError("source_external_key_scope_mismatch")
        if self.out_of_scope_sources != ["05-骏辉螺杆 氮化机筒日精.jpg"]:
            raise ValueError("out_of_scope_source_mismatch")
        if not self.draft_import_authorized or self.protected_preview_publish_authorized:
            raise ValueError("draft_only_authorization_required")
        return self


class DerivativeResult(BaseModel):
    """单张 WebP 派生副本的路径、哈希和像素尺寸。"""

    path: Path
    sha256: str
    width: int
    height: int
    size_bytes: int


def load_manifest(path: Path) -> PilotManifest:
    """
    从私有 JSON 文件读取并校验首批 manifest。

    输入：path，manifest 文件路径。
    输出：PilotManifest，已通过全部批次门禁。
    """
    return PilotManifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: PilotManifest) -> None:
    """
    原子保存更新后的私有幂等映射。

    输入：path 目标文件；manifest 待保存批次。
    输出：None；使用同目录临时文件替换原清单。
    """
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def validate_source_files(manifest: PilotManifest, source_root: Path) -> list[Path]:
    """
    校验四张源图的文件名边界和 SHA-256。

    输入：manifest 批次清单；source_root 私有源图目录。
    输出：list[Path]，按批准顺序排列的源文件路径。
    """
    validated: list[Path] = []
    for source in sorted(manifest.sources, key=lambda item: item.order):
        if Path(source.filename).name != source.filename:
            raise PilotImportError("source_path_not_flat")
        source_path = source_root / source.filename
        if not source_path.is_file():
            raise PilotImportError(f"source_missing:{source.external_key}")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if digest != source.sha256:
            raise PilotImportError(f"source_hash_mismatch:{source.external_key}")
        validated.append(source_path)
    return validated


def build_webp_derivative(source: Path, output: Path) -> DerivativeResult:
    """
    生成去 EXIF、固定质量且不改变真实像素内容的 WebP 副本。

    输入：source 源 JPEG；output 派生 WebP 路径。
    输出：DerivativeResult，包含文件哈希、尺寸与字节数。
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        normalized = ImageOps.exif_transpose(original).convert("RGB")
        width, height = normalized.size
        normalized.save(output, "WEBP", quality=82, method=6, exif=b"")
    content = output.read_bytes()
    return DerivativeResult(
        path=output,
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
        size_bytes=len(content),
    )


def classify_resource(
    items: list[dict[str, Any]],
    slug: str,
    mapped_id: str | None,
) -> Literal["create", "no-op", "conflict"]:
    """
    保守判断远端资源应创建、保持不变还是停止冲突。

    输入：items 远端列表；slug 目标 slug；mapped_id 私有 manifest 映射。
    输出：create、no-op 或 conflict。
    """
    matches = [item for item in items if item.get("slug") == slug]
    if not matches:
        return "conflict" if mapped_id else "create"
    if len(matches) != 1:
        return "conflict"
    return "no-op" if mapped_id == str(matches[0].get("id")) else "conflict"


def redact_evidence(value: Any, key: str | None = None) -> Any:
    """
    递归移除证据中的凭据、内部ID和对象存储定位。

    输入：value 任意 JSON 兼容值；key 当前字段名。
    输出：脱敏后的 JSON 兼容值。
    """
    if key and (key in _REDACTED_KEYS or (key.endswith("_id") and key != "batch_id")):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {item_key: redact_evidence(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact_evidence(item) for item in value]
    return value


def _response_data(response: httpx.Response) -> Any:
    """
    解包统一 API envelope，并把错误转换成导入异常。

    输入：response，API HTTP 响应。
    输出：Any，envelope 的 data 字段。
    """
    try:
        body = response.json()
    except ValueError as exc:
        raise PilotImportError(f"api_non_json:{response.status_code}") from exc
    if response.is_error or not body.get("success"):
        error = body.get("error") or {}
        raise PilotImportError(f"api_error:{response.status_code}:{error.get('code', 'unknown')}")
    return body.get("data")


class PilotApiClient:
    """携带 App Cookie、CSRF 和可选 Basic Auth 的首批导入客户端。"""

    def __init__(self, api_base: str) -> None:
        """
        根据环境变量创建安全 HTTP 客户端。

        输入：api_base，目标 `/api/v1` 根地址。
        输出：None；客户端保存在实例中。
        """
        basic_user = os.getenv("PHASE37_BASIC_USER")
        basic_password = os.getenv("PHASE37_BASIC_PASSWORD")
        basic_auth = (
            httpx.BasicAuth(basic_user, basic_password)
            if basic_user and basic_password
            else None
        )
        ca_cert = os.getenv("PHASE37_CA_CERT")
        self.client = httpx.Client(
            base_url=api_base.rstrip("/") + "/",
            auth=basic_auth,
            verify=ca_cert or True,
            timeout=30,
            follow_redirects=False,
            trust_env=False,
        )

    def close(self) -> None:
        """关闭底层 HTTP 连接池。"""
        self.client.close()

    def login(self) -> None:
        """使用环境变量登录，并安装双提交 CSRF Header。"""
        email = os.getenv("PHASE37_ADMIN_EMAIL")
        password = os.getenv("PHASE37_ADMIN_PASSWORD")
        if not email or not password:
            raise PilotImportError("admin_credentials_required")
        _response_data(
            self.client.post("auth/login", json={"email": email, "password": password})
        )
        csrf_token = self.client.cookies.get("junhui_csrf")
        if not csrf_token:
            raise PilotImportError("csrf_cookie_missing")
        self.client.headers["X-CSRF-Token"] = csrf_token

    def get(self, path: str) -> Any:
        """输入 API 相对路径，输出解包后的 GET data。"""
        return _response_data(self.client.get(path.lstrip("/")))

    def post(self, path: str, **kwargs: Any) -> Any:
        """输入 API 相对路径和 httpx 参数，输出 POST data。"""
        return _response_data(self.client.post(path.lstrip("/"), **kwargs))

    def patch(self, path: str, **kwargs: Any) -> Any:
        """输入 API 相对路径和 httpx 参数，输出 PATCH data。"""
        return _response_data(self.client.patch(path.lstrip("/"), **kwargs))

    def list_items(self, path: str) -> list[dict[str, Any]]:
        """输入列表端点，输出分页或数组响应中的条目。"""
        data = self.get(path)
        return list(data.get("items", [])) if isinstance(data, dict) else list(data)


def _derivatives(
    manifest: PilotManifest,
    source_root: Path,
    output_dir: Path,
) -> dict[str, DerivativeResult]:
    """校验源图并按 external key 生成四张确定性 WebP。"""
    source_paths = validate_source_files(manifest, source_root)
    results: dict[str, DerivativeResult] = {}
    for source, source_path in zip(
        sorted(manifest.sources, key=lambda item: item.order),
        source_paths,
        strict=True,
    ):
        results[source.external_key] = build_webp_derivative(
            source_path,
            output_dir / f"nitrided-barrel-{source.order:02d}.webp",
        )
    return results


def _remote_state(client: PilotApiClient, manifest: PilotManifest) -> dict[str, Any]:
    """读取远端 Locale、Catalog 和 Media 状态用于 dry-run。"""
    locales = client.list_items("locales")
    categories = client.list_items("catalog/categories?page_size=100")
    products = client.list_items("catalog/products?page_size=100")
    media = client.list_items("media")
    locale_by_code = {str(item["code"]): item for item in locales}
    if not {"zh-CN", "en"}.issubset(locale_by_code):
        raise PilotImportError("required_locales_missing")
    return {
        "locales": locale_by_code,
        "categories": categories,
        "products": products,
        "media": media,
        "category_action": classify_resource(
            categories,
            manifest.category.slug,
            manifest.mappings.get(manifest.category.external_key),
        ),
        "product_action": classify_resource(
            products,
            manifest.product.slug,
            manifest.mappings.get(manifest.product.external_key),
        ),
    }


def dry_run_pilot(
    manifest: PilotManifest,
    source_root: Path,
    output_dir: Path,
    api_base: str,
) -> dict[str, Any]:
    """
    生成派生图并只读分类目标环境，不写数据库或 MinIO。

    输入：manifest、源图目录、派生目录和 API 根地址。
    输出：dict，脱敏的 create/no-op/conflict/blocked 计划。
    """
    derivatives = _derivatives(manifest, source_root, output_dir)
    client = PilotApiClient(api_base)
    try:
        client.login()
        state = _remote_state(client, manifest)
    finally:
        client.close()
    media_ids = {str(item.get("id")) for item in state["media"]}
    media_actions = {
        source.external_key: (
            "no-op"
            if manifest.mappings.get(source.external_key) in media_ids
            else "conflict"
            if manifest.mappings.get(source.external_key)
            else "create"
        )
        for source in manifest.sources
    }
    result = {
        "batch_id": manifest.batch_id,
        "target_environment": _TARGET_ENVIRONMENT,
        "locales": {"zh-CN": "no-op", "en": "no-op"},
        "category": state["category_action"],
        "product": state["product_action"],
        "media": media_actions,
        "derivatives": {
            key: {
                "sha256": item.sha256,
                "width": item.width,
                "height": item.height,
                "size_bytes": item.size_bytes,
            }
            for key, item in derivatives.items()
        },
        "specifications": "blocked",
        "relations": "blocked",
        "blocked_fields": manifest.blocked_fields,
    }
    if "conflict" in {state["category_action"], state["product_action"]} or any(
        action == "conflict" for action in media_actions.values()
    ):
        result["status"] = "conflict"
    else:
        result["status"] = "ready"
    return redact_evidence(result)


def _translation_inputs(
    manifest: PilotManifest,
    locale_by_code: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造分类和产品的双语 Draft payload。"""
    category_translations = [
        {
            "locale_id": locale_by_code["zh-CN"]["id"],
            "name": manifest.category.name_zh_cn,
            "fields": {"short_description": "注塑机料筒产品分类"},
        },
        {
            "locale_id": locale_by_code["en"]["id"],
            "name": manifest.category.name_en,
            "fields": {"short_description": "Barrels for injection molding machines."},
        },
    ]
    product_translations = [
        {
            "locale_id": locale_by_code["zh-CN"]["id"],
            "name": manifest.product.name_zh_cn,
            "fields": {
                "short_description": "用于注塑机的氮化料筒。",
                "description": "本页面为待审核产品草稿；冲突或适用范围不明确的旧站参数尚未录入。",
                "highlights_jsonb": [],
            },
        },
        {
            "locale_id": locale_by_code["en"]["id"],
            "name": manifest.product.name_en,
            "fields": {
                "short_description": "A nitrided barrel for injection molding machines.",
                "description": "This page is a review-pending draft. Conflicting legacy specifications are not included.",
                "highlights_jsonb": [],
            },
        },
    ]
    return category_translations, product_translations


def apply_pilot(
    manifest_path: Path,
    source_root: Path,
    output_dir: Path,
    api_base: str,
) -> dict[str, Any]:
    """
    通过既有 API 幂等导入批准的四张媒体、分类和产品 Draft。

    输入：manifest_path、源图目录、派生目录和 API 根地址。
    输出：dict，脱敏后的 apply 与生命周期摘要。
    """
    manifest = load_manifest(manifest_path)
    derivatives = _derivatives(manifest, source_root, output_dir)
    client = PilotApiClient(api_base)
    try:
        client.login()
        state = _remote_state(client, manifest)
        if "conflict" in {state["category_action"], state["product_action"]}:
            raise PilotImportError("catalog_conflict")
        locale_by_code = state["locales"]
        media_ids = {str(item.get("id")) for item in state["media"]}
        created_media = 0
        for source in sorted(manifest.sources, key=lambda item: item.order):
            mapped = manifest.mappings.get(source.external_key)
            if mapped:
                if mapped not in media_ids:
                    raise PilotImportError(f"mapped_media_missing:{source.external_key}")
                continue
            derivative = derivatives[source.external_key]
            with derivative.path.open("rb") as handle:
                media = client.post(
                    "media/assets",
                    files={"file": (derivative.path.name, handle, "image/webp")},
                    data={"visibility": "public"},
                )
            media_id = str(media["id"])
            manifest.mappings[source.external_key] = media_id
            save_manifest(manifest_path, manifest)
            for locale_code, alt_text in (
                ("zh-CN", source.alt_zh_cn),
                ("en", source.alt_en),
            ):
                client.patch(
                    f"media/{media_id}/translations/{locale_by_code[locale_code]['id']}",
                    data={"alt_text": alt_text, "title": alt_text, "caption": alt_text},
                )
            created_media += 1

        category_translations, product_translations = _translation_inputs(
            manifest,
            locale_by_code,
        )
        if state["category_action"] == "create":
            category = client.post(
                "catalog/categories",
                json={
                    "slug": manifest.category.slug,
                    "status": "enabled",
                    "translations": category_translations,
                },
            )
            manifest.mappings[manifest.category.external_key] = str(category["id"])
            save_manifest(manifest_path, manifest)
        category_id = manifest.mappings[manifest.category.external_key]

        if state["product_action"] == "create":
            primary_media_id = manifest.mappings[
                min(manifest.sources, key=lambda item: item.order).external_key
            ]
            product = client.post(
                "catalog/products",
                json={
                    "category_id": category_id,
                    "slug": manifest.product.slug,
                    "status": "enabled",
                    "featured": False,
                    "primary_media_id": primary_media_id,
                    "translations": product_translations,
                },
            )
            manifest.mappings[manifest.product.external_key] = str(product["id"])
            save_manifest(manifest_path, manifest)

        verification = _verify_remote(client, manifest)
    finally:
        client.close()
    return redact_evidence(
        {
            "batch_id": manifest.batch_id,
            "status": "applied" if created_media else "no-op",
            "created_media": created_media,
            "category": state["category_action"],
            "product": state["product_action"],
            "verification": verification,
        }
    )


def _verify_remote(client: PilotApiClient, manifest: PilotManifest) -> dict[str, Any]:
    """读取 Product Detail 并验证 Draft 生命周期门禁。"""
    product_id = manifest.mappings.get(manifest.product.external_key)
    if not product_id:
        raise PilotImportError("product_mapping_missing")
    detail = client.get(f"catalog/products/{product_id}")
    translation_statuses = detail.get("translation_statuses", [])
    publications = detail.get("publications", [])
    routes = detail.get("routes", [])
    checks = {
        "two_translations": len(detail.get("translations", [])) == 2,
        "translation_status_draft": len(translation_statuses) == 2
        and all(item.get("status") == "draft" for item in translation_statuses),
        "publication_draft": len(publications) == 2
        and all(item.get("status") == "draft" for item in publications),
        "routes_closed": len(routes) == 2
        and all(not item.get("active") and not item.get("indexable") for item in routes),
        "primary_media_set": bool(detail.get("primary_media_id")),
        "no_models": not detail.get("models"),
        "no_specifications": not detail.get("specifications"),
        "no_relations": all(not values for values in detail.get("relations", {}).values()),
    }
    if not all(checks.values()):
        raise PilotImportError("draft_lifecycle_verification_failed")
    return checks


def verify_pilot(manifest: PilotManifest, api_base: str) -> dict[str, Any]:
    """
    只读验证已导入试点的 Draft 生命周期。

    输入：manifest 批次清单；api_base API 根地址。
    输出：dict，脱敏布尔断言。
    """
    client = PilotApiClient(api_base)
    try:
        client.login()
        result = _verify_remote(client, manifest)
    finally:
        client.close()
    return redact_evidence({"batch_id": manifest.batch_id, "checks": result})


def run_pilot_command(
    command: str,
    manifest_path: Path,
    source_root: Path,
    output_dir: Path,
    api_base: str,
) -> dict[str, Any]:
    """
    分派 dry-run、apply 或 verify 命令。

    输入：命令、manifest、源图目录、输出目录与 API 根地址。
    输出：dict，可安全打印的脱敏执行结果。
    """
    manifest = load_manifest(manifest_path)
    if command == "phase37-pilot-dry-run":
        return dry_run_pilot(manifest, source_root, output_dir, api_base)
    if command == "phase37-pilot-apply":
        return apply_pilot(manifest_path, source_root, output_dir, api_base)
    if command == "phase37-pilot-verify":
        return verify_pilot(manifest, api_base)
    raise PilotImportError("unsupported_pilot_command")
