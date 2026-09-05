# Phase 3.6 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five accepted Phase 3.6 gaps and complete an opt-in, isolated, real-service browser QA run without expanding into Phase 3.7.

**Architecture:** Preserve the existing Structured Core, Publication/Route, SEO/GEO, media, and RFQ layers. Extend the existing public collection serializers and server-owned metadata, validate RFQ sources through a fixed entity registry, and make Nuxt consume explicit success/not-found/server-error states. QA data is created through existing services in a run-scoped namespace and is never part of normal seed data.

**Tech Stack:** FastAPI 0.116.1, SQLAlchemy 2.0.43, PostgreSQL 17, Redis 8, MinIO, Nuxt 4.5.2, Vue 3.5.42, TypeScript 5.9.2, Vitest 3.2.4, Playwright CLI, Docker Compose.

---

### Task 1: Add failing remediation contracts

**Files:**
- Create: `apps/api/tests/test_phase36_remediation.py`
- Create: `apps/website/tests/phase36-remediation.test.ts`

- [ ] Add backend tests for real home SEO/schema, full product and knowledge cards, empty-home noindex, invalid filters, zero-result combinations, out-of-range pages, filtered noindex, and self-canonical pagination.
- [ ] Add parameterized RFQ tests for product, material, technology, application, solution, case study, knowledge article, and manufacturing capability sources, plus incomplete/private/unknown/internal-ID rejection.
- [ ] Add frontend tests for API error preservation, no stale metadata, RFQ query propagation, unique document landmarks/IDs/H1, and functional skip links.
- [ ] Run the focused tests and record the expected failures before implementation.

### Task 2: Close homepage SEO and rich-card delivery

**Files:**
- Modify: `apps/api/app/modules/discovery/public_collections.py`
- Modify: `apps/api/app/modules/discovery/schema_generator.py` only if an existing safe schema helper needs a reusable input shape
- Modify: `apps/website/app/types/public.ts`
- Modify: `apps/website/app/components/HomePage.vue`
- Modify: `apps/website/tests/phase36-homepage.test.ts`

- [ ] Build a localized home metadata DTO with a nonempty title/description, absolute self-canonical, explicit robots, strict reciprocal eligible-language hreflang, and existing schema generators.
- [ ] Return `noindex, follow` for a substantively empty home and preserve environment-level noindex overrides in Nuxt.
- [ ] Refactor `_published_rows` to return gated rows for reuse, then apply `_product_card_payloads` and `_authority_card_payloads` to homepage products and knowledge in batch.
- [ ] Add safe public-media enrichment for case and other supported home cards without exposing private storage or unapproved identity.
- [ ] Update the Nuxt home contract so raw SSR HTML emits backend-owned description, canonical, hreflang, robots, and JSON-LD.

### Task 3: Correct listing pagination, filters, and errors

**Files:**
- Modify: `apps/api/app/modules/discovery/public_collections.py`
- Modify: `apps/api/app/api/v1/public.py`
- Modify: `apps/website/app/components/ProductListingView.vue`
- Modify: `apps/website/app/components/PaginationNav.vue`
- Modify: `apps/website/app/pages/[lang]/products/index.vue`
- Modify: `apps/website/app/pages/[lang]/products/[category]/index.vue`
- Modify: related catalog/authority list pages only where they share the same error contract
- Modify: `apps/website/tests/phase36-products.test.ts`

- [ ] Validate each requested filter against a currently public resource before applying combinations.
- [ ] Return 404 for nonexistent/unpublished filters, zero-result combinations, and pages beyond the real page count; retain page-one empty roots as 200/noindex.
- [ ] Generate page-specific normalized canonical URLs, remove `page=1`, sort parameters, mark temporary/nondefault-page-size views `noindex, follow`, and omit their hreflang/schema alternates.
- [ ] Keep published category landing pages available when they have descriptive content but no products, with noindex until products exist.
- [ ] Preserve backend 404 versus 5xx in Nuxt and clear stale list/meta state during client navigation.
- [ ] Render only real crawlable previous/next/page links and suppress nonexistent next links.

### Task 4: Validate and persist RFQ multi-source attribution

**Files:**
- Modify: `apps/api/app/modules/rfq/schemas.py`
- Modify: `apps/api/app/modules/rfq/services.py`
- Modify: `apps/api/tests/test_phase35_remediation.py` only for existing product-contract compatibility
- Modify: `apps/website/app/composables/useLocalePath.ts`
- Modify: `apps/website/app/pages/[lang]/request-a-quote/index.vue`
- Modify: all existing public CTA call sites that have a canonical entity slug
- Modify: `apps/website/app/utils/rfqSubmission.ts`
- Modify: `apps/website/tests/phase36-interactions.test.ts`

- [ ] Define the fixed public source-type whitelist and server registry for Product, Material, Technology, Application, Solution, Case Study, Knowledge Article, and Manufacturing Capability.
- [ ] Resolve source slug and active locale through existing publication/translation/canonical/index gates, then persist only the server-derived canonical URL, owner type, and owner ID.
- [ ] Keep product-only item context unchanged and reject half-filled, unknown, unpublished, untranslated, or internal-ID-shaped sources with stable 422 responses before RFQ creation.
- [ ] Pass source type/slug from each real CTA into the localized RFQ form and support removing an invalid source before retry without duplicate submission.

### Task 5: Repair full-document semantics

**Files:**
- Modify: `apps/website/app/components/LocalePlaceholder.vue`
- Modify: `apps/website/app/components/ProductListingView.vue`
- Modify: `apps/website/app/pages/[lang]/products/[category]/[slug].vue`
- Modify: any page discovered by the document contract to contain nested `<main>` or duplicate IDs/H1
- Modify: `apps/website/app/layouts/default.vue` only if skip-link focus behavior requires correction
- Modify: `apps/website/tests/phase36-remediation.test.ts`

- [ ] Keep the default layout as the only normal-page `<main id="main-content" tabindex="-1">`.
- [ ] Replace component/page nested main elements with semantic `section`, `article`, or `div` containers.
- [ ] Render representative full SSR documents and assert one main, one `main-content`, no nested main, one nonempty H1, unique nonempty IDs, and a working skip-link target.

### Task 6: Build isolated opt-in content QA tooling

**Files:**
- Create: `apps/api/app/cli/phase36_qa.py`
- Create: `scripts/phase36-browser-qa.ps1`
- Create: `docs/testing/phase3-6-remediation-browser-qa.md`
- Modify: `.gitignore`
- Modify: `docker-compose.yml` only if the existing stack lacks a safe opt-in command path

- [ ] Add an explicit `PHASE36_QA_CONFIRM=QA_ONLY` and non-production guard before creating data.
- [ ] Create run-scoped bilingual company/content samples, 25+ products, five specification types, one-locale/draft/noindex controls, real public/private MinIO objects, and a manifest through existing service/lifecycle paths.
- [ ] Add manifest-scoped cleanup that refuses broad database, Redis, or bucket deletion.
- [ ] Drive the real FastAPI/PostgreSQL/Redis/MinIO/Nuxt/Nginx stack through the required desktop/mobile browser journeys.
- [ ] Save sanitized API, raw SSR, DOM, console, network summaries, and screenshots under ignored `artifacts/phase3-6-remediation/<run-id>/` paths.

### Task 7: Full verification and completion report

**Files:**
- Create: `docs/architecture/phase3-6-remediation-report.md`

- [ ] Run Ruff and the complete backend pytest suite.
- [ ] Run real PostgreSQL, Redis rate-limit, and MinIO integration suites; migrate empty DB to latest and 0001 to latest; verify seed idempotency.
- [ ] Run Website/Admin Vitest, TypeScript checks, Prettier checks, and production builds.
- [ ] Verify Docker Compose health without deleting volumes.
- [ ] Run the opt-in content browser QA and link only sanitized committed evidence metadata or ignored local evidence paths.
- [ ] Record exact branch, base SHA, implementation SHA, changed files, fresh commands/counts, evidence paths, blockers, limits, and known issues. Do not declare Phase 3.6 FINAL PASS.

