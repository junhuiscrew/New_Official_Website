# Phase 3.7.3 SEO Apply and Privacy Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `phase37-local-https` 中安全应用有真实 CMS owner 的 6 组已批准 SEO 元数据，明确暂停需要模型/迁移的 Products 两组，并完成内部隐私准备与脱敏证据交付。

**Architecture:** 继续使用现有 `SeoDocument` 管理 API、RBAC、CSRF 与 Audit；为 SEO 文档自身增加独立 `seo_document` 修订快照，不混入正文 owner 的修订序列。About 绑定现有 `company_profile`，分类绑定现有 `product_category`；Products 聚合页在没有真实 owner 的情况下不写库，输出新增 `site_page` 实体、迁移和后台编辑入口的最小方案。

**Tech Stack:** FastAPI、SQLAlchemy async、PostgreSQL、Nuxt/Vue SSR、PowerShell、Playwright、Docker Compose。

---

### Task 1: Preserve baseline and validate the approval package

**Files:**
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/preflight.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/seo-apply.ps1`

- [ ] Record branch, HEAD, dirty paths, container image IDs, health, ports and the package SHA-256.
- [ ] Verify every `SHA256SUMS.txt` entry and each approved title/description hash.
- [ ] Read actual Company/category IDs and locale IDs through authenticated Admin/API without exposing credentials.
- [ ] Read current SEO documents, lifecycle state, COPY-V1/frozen product state and initial SSR metadata.
- [ ] Classify each metadata group as `update`, `no-op`, `conflict`, or `blocked_missing_owner`; stop writes on any existing-value conflict.

### Task 2: Add immutable SEO revision snapshots with TDD

**Files:**
- Modify: `apps/api/tests/test_phase34_discovery.py`
- Modify: `apps/api/app/modules/discovery/services.py`

- [ ] Add an async test that creates and updates one `SeoDocument`, then expects two `ContentRevision` rows keyed by `owner_type="seo_document"` and the real SEO document ID.
- [ ] Run the new test and confirm RED because no SEO revision is currently written.
- [ ] In `upsert_seo_document`, flush the real document ID, create a JSON-serializable full SEO snapshot, and call `store_revision` with the real actor and locale.
- [ ] Run the focused test and related discovery tests and confirm GREEN.
- [ ] Do not commit; record `NOT_RUN_USER_PROHIBITED` for commit/push/merge.

### Task 3: Update the affected local API service only

**Files:**
- Reuse: `data/phase3-7/r1-remediation/20260907T140215+0800/no-seed.override.yml`

- [ ] Run Ruff and related API tests against the current worktree.
- [ ] Build the API image from the current dirty worktree.
- [ ] Recreate only the API container with the no-seed override; preserve PostgreSQL/MinIO volumes and do not run migration or Seed.
- [ ] Confirm API, Website, Admin, Worker, Nginx, PostgreSQL, Redis and MinIO remain healthy and that only Nginx exposes host port 443 within the phase37 project.

### Task 4: Apply six owner-backed SEO groups through the real CMS API

**Files:**
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/seo-before-private.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/seo-apply-result-private.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/seo-after-private.json`

- [ ] Login with the existing phase37 Admin account, preserve Basic Auth cookies in memory and send the existing double-submit CSRF header.
- [ ] PUT complete, preservation-safe `SeoDocumentUpsert` payloads for About zh/en and screws/barrels zh/en only.
- [ ] Skip exact matches; abort if any owner-backed current title/description is non-empty and differs from the approved bytes.
- [ ] Do not call Review/Publish because the existing SEO flow has no separate lifecycle and the published route already consumes the document.
- [ ] Read back each document and confirm one `seo.upsert` Audit plus one `seo_document` revision per actual update.

### Task 5: Verify API-to-first-SSR behavior and frozen boundaries

**Files:**
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/seo-readback.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/ssr-readback.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/browser-checks.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/screenshots/*.png`

- [ ] Fetch the eight canonical local pages with Basic Auth and parse the first response HTML, without client-side mutation.
- [ ] Confirm the six applied pages have exact approved title/description and Products zh/en remain the recorded blocked defaults.
- [ ] Confirm canonical, reciprocal hreflang, Schema canonical URLs, HTTPS and outer noindex rules are unchanged.
- [ ] Use Playwright because the Browser plugin is unavailable; verify representative About/category pages, page identity, meaningful DOM, no framework overlay, console health and visible metadata evidence.
- [ ] Re-read Company/P01/P02/P03/categories, parameters 0/0/0, seven definitions, missing F05 English, media, relations, models and old-pilot lifecycle.
- [ ] Confirm anonymous 401, authenticated 200 plus noindex, Sitemap 404 and no phase37 service-port bypass.

### Task 6: Prepare privacy materials without publishing

**Files:**
- Create: `docs/content/privacy-facts-confirmed-v1.md`
- Create: `docs/content/privacy-operations-proposal-v1.md`
- Create: `docs/content/privacy-notice-working-draft.zh-en.md`
- Create: `docs/content/privacy-confirmation-checklist.md`

- [ ] Mark every statement as `USER_CONFIRMED`, `REPORTED_TECHNICAL`, `PROPOSED`, or `UNKNOWN`.
- [ ] Preserve the confirmed operator, Chinese registered address, privacy email and RFQ purpose only in private policy documents.
- [ ] Keep retention/deletion and request handling explicitly not established; do not turn 730 days into an automatic deletion rule.
- [ ] State that MinIO is self-hosted, Gmail is only a contact mailbox, and Tencent Cloud/backup regions remain unknown.
- [ ] Record that `marketing_consent` still exists while launch promotional email is disabled; do not change the UI/model.
- [ ] Keep `/privacy/` unpublished and 404.

### Task 7: Report and package evidence

**Files:**
- Create: `docs/content/phase3-7-3-seo-apply-privacy-prep-report.md`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/share/MANIFEST.json`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/share/SHA256SUMS.txt`
- Create: `data/phase3-7/seo-apply-privacy-prep/20260907T154820+0800/Junhui-Phase3.7.3-SEO-Apply-Privacy-Prep-Evidence-20260907T154820+0800.zip`

- [ ] Report actual update/no-op/conflict/blocked counts, storage paths, revision/audit summaries and exact SSR outcomes.
- [ ] Set `F-R1-004=PARTIAL_BLOCKED_PRODUCTS_STORAGE_MODEL` unless all eight groups are actually stored and verified.
- [ ] Keep `F-R1-001=OPEN_POLICY_AND_OPERATIONS_PENDING`.
- [ ] Include a minimal Products `site_page` model/migration/Admin proposal without implementing it.
- [ ] Package only redacted JSON, report, privacy drafts and representative screenshots; exclude credentials, cookies, tokens, internal UUIDs and private signed URLs.
- [ ] Extract and independently verify every packaged SHA-256 before reporting completion.
