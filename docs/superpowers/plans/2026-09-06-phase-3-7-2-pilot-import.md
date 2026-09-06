# Phase 3.7.2 Pilot Draft Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import one authorized “注塑机氮化料筒” bilingual Draft with four approved media derivatives into an isolated local HTTPS environment through the existing APIs, while keeping every public lifecycle gate closed.

**Architecture:** Add only the missing Product primary-media and structured translation form wiring, then provide a narrowly scoped, manifest-driven API client for dry-run/apply/verify. A Phase 3.7 Compose overlay supplies separate volumes, local TLS, Basic Auth and noindex; the real batch manifest, derivatives, credentials and backups stay under ignored local directories.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL 17, MinIO, Nuxt 3/Vue 3/TypeScript, Docker Compose, Nginx TLS, httpx, Pillow, pytest, Vitest.

---

### Task 1: Product primary-media contract

**Files:**
- Modify: `apps/api/app/modules/catalog/schemas.py`
- Modify: `apps/api/app/modules/catalog/services.py`
- Test: `apps/api/tests/test_phase37_pilot.py`

- [ ] **Step 1: Write failing API tests for Product media acceptance and rejection**

Create `test_product_primary_media_requires_ready_public_asset` and `test_product_primary_media_round_trips_in_detail` using the existing authenticated Catalog test client. The assertions must cover a public ready asset, a private asset, a non-ready asset and an unknown UUID:

```python
response = await client.post(
    "/api/v1/catalog/products",
    json={
        "category_id": category_id,
        "slug": "pilot-nitrided-barrel",
        "primary_media_id": str(public_asset.id),
        "translations": [],
    },
)
assert response.status_code == 201
detail = await client.get(f"/api/v1/catalog/products/{response.json()['data']['id']}")
assert detail.json()["data"]["primary_media_id"] == str(public_asset.id)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest apps/api/tests/test_phase37_pilot.py -q`

Expected: FAIL because `ProductCreate` ignores `primary_media_id` and the service does not validate media state.

- [ ] **Step 3: Add the minimal schema and service validation**

Add the existing database field to both request models:

```python
class ProductCreate(BaseModel):
    primary_media_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    primary_media_id: uuid.UUID | None = None
```

Add one focused helper and call it before constructing or updating a Product:

```python
async def _validate_primary_media(
    session: AsyncSession,
    media_id: uuid.UUID | None,
) -> None:
    """
    验证产品主媒体可以通过公开媒体代理交付。

    输入：session 数据库会话；media_id 可空媒体ID。
    输出：None；非法媒体抛出稳定业务异常。
    """
    if media_id is None:
        return
    asset = await session.get(MediaAsset, media_id)
    if (
        asset is None
        or asset.visibility != "public"
        or asset.storage_bucket != "public-media"
        or asset.upload_status != "ready"
    ):
        raise AppException(422, "product_primary_media_invalid", "产品主媒体必须是可用的公开媒体")
```

Pass `primary_media_id` to `Product(...)`, include it in Product updates, and keep `_serialize()` as the single response serializer because it already emits all Product columns.

- [ ] **Step 4: Run the focused and existing Catalog tests**

Run: `python -m pytest apps/api/tests/test_phase37_pilot.py apps/api/tests/test_catalog_api.py apps/api/tests/test_catalog_remediation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the backend contract**

```bash
git add apps/api/app/modules/catalog/schemas.py apps/api/app/modules/catalog/services.py apps/api/tests/test_phase37_pilot.py
git commit -m "feat: wire product primary media"
```

### Task 2: Product Admin structured draft fields

**Files:**
- Modify: `apps/admin/app/pages/catalog/products.vue`
- Modify: `apps/admin/tests/catalog-contract.test.ts`

- [ ] **Step 1: Add failing Admin contract assertions**

Require Product Admin to load `/media`, bind `primary_media_id`, and preserve all existing translation fields:

```typescript
expect(source).toContain("api.detail<MediaItem[]>('/media')")
expect(source).toContain('v-model="form.primary_media_id"')
expect(source).toContain('short_description')
expect(source).toContain('highlights_jsonb')
```

- [ ] **Step 2: Run the Admin test and verify RED**

Run: `pnpm --filter @junhui/admin test -- catalog-contract.test.ts`

Expected: FAIL because Product Admin currently only maps `description`.

- [ ] **Step 3: Implement the minimum maintainable form**

Add a public media selector and map the three translation fields without changing the shared Translation component API:

```typescript
interface MediaItem {
  id: string
  type: string
  url: string | null
}

const media = ref<MediaItem[]>([])

function translationFields(translation: Record<string, unknown>) {
  return {
    short_description: String(translation.short_description || ''),
    description: String(translation.description || ''),
    highlights_jsonb: Array.isArray(translation.highlights_jsonb)
      ? JSON.stringify(translation.highlights_jsonb, null, 2)
      : '[]',
  }
}
```

Before submission, parse `highlights_jsonb` into an array and show a form error for invalid JSON. Include `primary_media_id: form.primary_media_id || null` in Product create/update payloads. Keep all comments in Chinese per `AGENTS.md`.

- [ ] **Step 4: Run Admin tests and typecheck**

Run: `pnpm --filter @junhui/admin test && pnpm --filter @junhui/admin typecheck`

Expected: PASS.

- [ ] **Step 5: Commit the Admin wiring**

```bash
git add apps/admin/app/pages/catalog/products.vue apps/admin/tests/catalog-contract.test.ts
git commit -m "feat: expose product draft media and summaries"
```

### Task 3: Manifest-driven pilot import tool

**Files:**
- Modify: `apps/api/pyproject.toml`
- Create: `apps/api/app/phase37_pilot.py`
- Modify: `apps/api/app/cli.py`
- Create: `docs/content/templates/phase3-7-pilot-manifest.example.json`
- Test: `apps/api/tests/test_phase37_pilot.py`

- [ ] **Step 1: Write failing pure-function and CLI tests**

Cover manifest scope, approved filename allowlist, SHA mismatch, image derivation, dry-run classifications and secret redaction:

```python
def test_webp_derivative_removes_exif(tmp_path: Path, jpeg_with_exif: Path) -> None:
    result = build_webp_derivative(jpeg_with_exif, tmp_path / "product-01.webp")
    with Image.open(result.path) as image:
        assert image.format == "WEBP"
        assert not image.getexif()
    assert result.sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()


def test_scope_rejects_unapproved_fifth_image(manifest: PilotManifest) -> None:
    with pytest.raises(PilotImportError, match="source_not_approved"):
        manifest.require_source("05-nissei.jpg")
```

Test `build_parser()` exposes `phase37-pilot-dry-run`, `phase37-pilot-apply` and `phase37-pilot-verify` with `--manifest`, `--source-root`, `--output-dir` and `--api-base`.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest apps/api/tests/test_phase37_pilot.py -q`

Expected: FAIL because `app.phase37_pilot` and the CLI commands do not exist.

- [ ] **Step 3: Add pinned local-tool dependencies**

Add to the `dev` extra without changing runtime API dependencies:

```toml
dev = [
    "junhui-global-api[test]",
    "pillow==11.3.0",
    "ruff==0.12.11",
]
```

- [ ] **Step 4: Implement strict manifest and derivative models**

Define Pydantic models with Chinese docstrings for inputs/outputs. Enforce exactly one approved product, four source images, the fixed external keys/slugs, `draft_import=true`, `protected_preview_publish=false`, and target environment `phase37-local-https`.

The derivative function must use `ImageOps.exif_transpose`, RGB conversion and deterministic WebP output:

```python
with Image.open(source) as original:
    normalized = ImageOps.exif_transpose(original).convert("RGB")
    normalized.save(output, "WEBP", quality=82, method=6, exif=b"")
```

- [ ] **Step 5: Implement API dry-run/apply/verify orchestration**

The API client logs in using environment-only credentials, keeps the session Cookie and CSRF token, and optionally sends external Basic Auth. It must:

- list locales and resolve `zh-CN`/`en`;
- list categories/products and classify slug results;
- reject any existing same slug not already mapped by this manifest;
- upload four derived images, then update both media translations;
- create the category and product through Catalog API;
- set the first returned media ID as `primary_media_id`;
- omit ProductModel, relation and specification writes for this batch;
- verify two draft TranslationStatus rows, two draft Publications and two canonical inactive/noindex Routes;
- redact passwords, Cookie, CSRF, storage paths and internal IDs from normal console evidence.

- [ ] **Step 6: Add a safe public example manifest**

The committed example includes only external keys, public source URL, approved display names and field policy. It records `"source_hashes": "private-manifest-only"` instead of concrete source hashes, and must not contain real local paths, credentials, API IDs, storage keys or approval signatures.

- [ ] **Step 7: Run import-tool tests and Ruff**

Run: `python -m pytest apps/api/tests/test_phase37_pilot.py -q && python -m ruff check --no-cache apps/api`

Expected: PASS.

- [ ] **Step 8: Commit the import tool**

```bash
git add apps/api/pyproject.toml apps/api/app/phase37_pilot.py apps/api/app/cli.py apps/api/tests/test_phase37_pilot.py docs/content/templates/phase3-7-pilot-manifest.example.json
git commit -m "feat: add guarded phase 3.7 pilot importer"
```

### Task 4: Isolated local HTTPS stack

**Files:**
- Create: `docker-compose.phase37.yml`
- Create: `infra/nginx/nginx.phase37.conf`
- Create: `scripts/phase37-local-https.ps1`
- Modify: `.gitignore`
- Modify: `.env.example`
- Modify: `infra/docker/README.md`
- Test: `apps/api/tests/test_phase37_pilot.py`

- [ ] **Step 1: Add failing configuration contract tests**

Read the Compose/Nginx/script files and assert separate project naming, TLS port 443, three hostnames, Basic Auth, noindex, production canonical origin, ignored certificate/private directories, and no literal secrets.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest apps/api/tests/test_phase37_pilot.py -q`

Expected: FAIL because the Phase 3.7 overlay and TLS files do not exist.

- [ ] **Step 3: Add the Compose overlay and TLS proxy**

Use `name: junhui-phase37-pilot`, remove direct database/MinIO/API/Nuxt host ports, expose only Nginx `443:443`, mount ignored certificates and htpasswd, and keep `APP_ENV=staging`, secure cookies, sitemap disabled, analytics disabled and marketing email disabled.

Nginx must define separate `server_name` blocks for `junhui.test`, `admin.junhui.test` and `api.junhui.test`. Every business response gets:

```nginx
add_header X-Robots-Tag "noindex, nofollow" always;
auth_basic "Junhui Phase 3.7 Pilot";
auth_basic_user_file /etc/nginx/phase37.htpasswd;
```

- [ ] **Step 4: Add explicit certificate/hosts preparation**

The PowerShell script uses the installed OpenSSL to generate a local CA and a SAN certificate for the three `.test` hosts under ignored `data/phase3-7/tls`. `-InstallTrustAndHosts` is required before it changes Windows trust or hosts; default execution only generates files and prints the exact pending actions.

- [ ] **Step 5: Document environment creation**

Document random secret generation, external `.env.phase37`, bootstrap-admin command, Compose start/stop without `down -v`, backup paths, and `curl --resolve` checks. Do not document example production credentials.

- [ ] **Step 6: Run contract tests and Compose config validation**

Run:

```bash
python -m pytest apps/api/tests/test_phase37_pilot.py -q
docker compose -f docker-compose.yml -f docker-compose.phase37.yml --env-file .env.phase37 config --quiet
```

Expected: PASS with an external ignored env file.

- [ ] **Step 7: Commit the isolated environment**

```bash
git add docker-compose.phase37.yml infra/nginx/nginx.phase37.conf scripts/phase37-local-https.ps1 .gitignore .env.example infra/docker/README.md apps/api/tests/test_phase37_pilot.py
git commit -m "chore: add isolated phase 3.7 https environment"
```

### Task 5: Execute the authorized batch

**Files:**
- Create locally, ignored: `data/phase3-7/pilot-001/manifest.json`
- Create locally, ignored: `data/phase3-7/pilot-001/derived/*.webp`
- Create locally, ignored: `data/phase3-7/pilot-001/evidence/*.json`
- Create locally, ignored: `data/phase3-7/pilot-001/backups/*`

- [ ] **Step 1: Build the private manifest from the four approved source files**

Record the exact source SHA-256 values, public source URL, approval scope, reviewer role, batch ID and the isolated target. Explicitly record the fifth “日精” image as out of scope.

- [ ] **Step 2: Generate TLS and isolated credentials**

Run the preparation script without installation first, inspect its outputs, then install only the local CA/hosts entries for the three approved `.test` names. Store all secrets in `.env.phase37`, which is ignored.

- [ ] **Step 3: Start and migrate the isolated Compose project**

Run: `docker compose -f docker-compose.yml -f docker-compose.phase37.yml --env-file .env.phase37 up -d --build`

Expected: all Phase 3.7 services become healthy; PostgreSQL reports Alembic `20260905_0010` and seed is idempotent.

- [ ] **Step 4: Create an isolated bootstrap administrator**

Use random environment-only credentials with `python -m app.cli create-super-admin` inside the Phase 3.7 API container. Do not print or copy the password into evidence.

- [ ] **Step 5: Back up and restore before import**

Create a PostgreSQL custom-format dump and MinIO object inventory under the ignored batch backup directory. Restore the dump into a separate temporary validation database and compare migration/version and pre-import row counts. Do not delete any active volume or bucket.

- [ ] **Step 6: Run dry-run and inspect classifications**

Run `phase37-pilot-dry-run`; expect one category `create`, one product `create`, four media `create`, two locales `no-op`, all specifications/relations `blocked`, and no database/object count changes.

- [ ] **Step 7: Apply once and verify idempotency**

Run `phase37-pilot-apply`, then run it again. The first run creates only the approved batch; the second returns only `no-op`. Verify four MinIO public objects, one category, one product, two translations, draft lifecycle records, revision and audit entries.

- [ ] **Step 8: Verify public gates remain closed**

Assert Product public API returns 404, Sitemap contains neither pilot route, and SSR does not expose the Draft. Verify Nginx requires Basic Auth and emits noindex on Website/Admin/API responses.

### Task 6: Full verification and pilot report

**Files:**
- Create: `docs/content/phase3-7-pilot-report.md`
- Modify: `docs/architecture/phase3-7-1-readiness-report.md`

- [ ] **Step 1: Run code verification**

Run Ruff, focused/full backend tests as affected, PostgreSQL/MinIO integration, Admin/Website Vitest, typecheck, Prettier check and production builds. Record each exact command, exit code, timestamp and actual result; do not copy old counts.

- [ ] **Step 2: Run isolated HTTPS/HTTP verification**

Check `junhui.test`, `admin.junhui.test` and `api.junhui.test`; validate TLS chain, Basic Auth, Secure cookies, noindex, health, media proxy and Draft invisibility. Save only redacted response summaries.

- [ ] **Step 3: Write the pilot report**

Document branch/SHA, batch hash, source policy, user approvals, media derivative hashes, create/no-op/blocked results, backup/restore, lifecycle state, tests, HTTPS, SEO/GEO gate checks, known limitations and the explicit stop before review/publish. Do not include credentials, source local paths, internal IDs or storage keys.

- [ ] **Step 4: Correct the readiness report history without erasing it**

Append a dated follow-up noting that the earlier `WAITING_FOR_INPUT` items were subsequently resolved for pilot-001 only. Preserve the original 3.7.1 findings and make clear that the “日精” product and protected preview publishing remain unapproved.

- [ ] **Step 5: Run final sensitive scan and diff checks**

Run `git diff --check`, scan tracked changes for password/Cookie/token/private URL/storage key patterns, confirm `data/phase3-7` and `.env.phase37` are untracked/ignored, and record the clean result.

- [ ] **Step 6: Commit the reports**

```bash
git add docs/content/phase3-7-pilot-report.md docs/architecture/phase3-7-1-readiness-report.md
git commit -m "docs: report phase 3.7 pilot draft import"
```

- [ ] **Step 7: Stop for user review**

Do not review or publish translations. Provide the local Admin URL and Draft verification summary, then wait for the user to inspect the Chinese/English content.
