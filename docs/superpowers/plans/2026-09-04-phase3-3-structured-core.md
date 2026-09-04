# Phase 3.3 Structured Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 Phase 3.2 基础上建立可发布、可审计、可多语言的 Structured Core Catalog，并提供最小 Admin/API 验证工作流。

**Architecture:** 继续使用 Master Entity + Translation + Publication + Route + Revision + Audit。Catalog 业务实体和显式关系使用 SQLAlchemy 2.x 模型；所有写入通过事务服务完成，同时创建翻译状态、默认草稿 Publication、canonical Route 和 Revision/Audit。Admin 只提供验证型 CRUD，不实现最终视觉或完整 CMS。

**Tech Stack:** FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL 17/CITEXT/JSONB、Nuxt 4/Vue 3/TypeScript、Vitest、Docker Compose。

---

### Task 1: Baseline and failing contract tests

**Files:**
- Create: `apps/api/tests/test_catalog_models.py`
- Create: `apps/api/tests/test_catalog_services.py`
- Create: `apps/api/tests/test_catalog_api.py`
- Modify: `apps/api/tests/test_seed_phase32.py`
- Modify: `apps/api/tests/test_postgresql_integration.py`

- [ ] **Step 1: Write failing model and service tests**
  Cover entity creation, translation uniqueness, category self/cycle rejection, model-code scope, specification XOR/type checks, relation uniqueness, lifecycle soft archive, and publication metadata creation.
- [ ] **Step 2: Run the focused tests and confirm they fail because catalog modules do not exist**
  Run `cd apps/api; .venv/Scripts/python -m pytest tests/test_catalog_models.py tests/test_catalog_services.py -q`.
- [ ] **Step 3: Write failing API/RBAC contract tests**
  Cover catalog list/detail/create/update/archive, relation replacement, specification endpoints, CSRF, editor/reviewer/sales/SEO permission boundaries, and audit creation.
- [ ] **Step 4: Run API tests and confirm expected 404/ImportError failures**
  Run `cd apps/api; .venv/Scripts/python -m pytest tests/test_catalog_api.py -q`.

### Task 2: Structured Core models and migration

**Files:**
- Create: `apps/api/app/modules/catalog/models.py`
- Create: `apps/api/app/modules/catalog/enums.py`
- Create: `apps/api/alembic/versions/20260904_0004_structured_core.py`
- Modify: `apps/api/app/core/database/base.py`
- Modify: `apps/api/app/modules/content/models.py`

- [ ] **Step 1: Add lifecycle/value-type enums and SQLAlchemy models**
  Add ProductCategory, Product, ProductModel, SpecificationGroup, SpecificationDefinition, ProductSpecValue, Material, Technology, Application, Solution; all columns use English names and Chinese comments.
- [ ] **Step 2: Add translation models**
  Add one translation table per core entity with `(entity_id, locale_id)` unique constraints and structured text/JSON fields only.
- [ ] **Step 3: Add explicit relation tables**
  Add product_materials, product_technologies, product_applications, product_solutions, material_technologies, material_solutions, application_solutions with composite PKs, ordering, notes and recommendation level.
- [ ] **Step 4: Add migration 0004**
  Create tables, foreign keys, check constraints, partial/unique indexes, and downgrade in dependency reverse order. Keep existing migrations unchanged.
- [ ] **Step 5: Run migration metadata/unit tests**
  Run `python -m pytest tests/test_catalog_models.py tests/test_phase32_migrations.py -q` and inspect generated constraints.

### Task 3: Catalog services and content-system integration

**Files:**
- Create: `apps/api/app/modules/catalog/services.py`
- Create: `apps/api/app/modules/catalog/schemas.py`
- Create: `apps/api/app/modules/catalog/publication.py`
- Create: `apps/api/app/modules/catalog/routes.py`
- Create: `apps/api/app/modules/catalog/revisions.py`
- Modify: `apps/api/app/modules/content/services/routes.py`
- Modify: `apps/api/app/modules/content/services/revisions.py`

- [ ] **Step 1: Implement stable slug/path validation**
  Enforce lower kebab-case, shared language-independent slugs, category/product route templates, canonical-only publication, and no direct published slug mutation.
- [ ] **Step 2: Implement category tree operations**
  Lock ancestors/target in stable order, reject self-parent and reachable cycles, sort by `sort_order,id`, and refuse deleting referenced/child categories; archive instead.
- [ ] **Step 3: Implement dynamic specification validation**
  Validate exactly one product/product-model owner, exactly one value column matching `text/number/range/boolean/enum`, valid min/max ranges, unit rules, and definition/value ownership.
- [ ] **Step 4: Implement catalog transaction service**
  Create/update master + translations + translation statuses + draft publication + canonical route + revision + audit in one transaction. Relation replacement is explicit and duplicate-safe.
- [ ] **Step 5: Run service tests and PostgreSQL integration tests**
  Run focused tests first, then `docker compose --profile test up --build --abort-on-container-exit --exit-code-from api-test api-test`.

### Task 4: Seed and RBAC extension

**Files:**
- Modify: `apps/api/app/seed.py`
- Modify: `apps/api/app/modules/users/service.py`
- Modify: `apps/api/tests/test_seed_phase32.py`
- Modify: `apps/api/tests/test_rbac.py`

- [ ] **Step 1: Add 24 catalog/specification permissions**
  Seed idempotently: catalog read/create/update/archive, specification read/manage, and CRUD/archive permissions for material, technology, application and solution.
- [ ] **Step 2: Extend role matrix without replacing Phase 3.2 mappings**
  Give content_admin complete catalog management, editor catalog create/update, reviewer only publication authority, seo_manager read-only catalog, and no catalog writes to sales/media_manager.
- [ ] **Step 3: Add test fixtures only**
  Add minimal test category/product/material/technology/application/solution records; do not import production catalog content.
- [ ] **Step 4: Verify idempotency and permission ceilings**
  Run seed twice and assert stable counts/mappings plus editor/reviewer/sales/SEO behavior.

### Task 5: FastAPI Admin catalog API

**Files:**
- Create: `apps/api/app/api/v1/catalog.py`
- Modify: `apps/api/app/api/v1/router.py`
- Modify: `apps/api/app/core/pagination.py`
- Modify: `apps/api/tests/test_catalog_api.py`

- [ ] **Step 1: Add read endpoints with pagination/stable sort**
  Categories/tree, products/detail, models, specifications, materials, technologies, applications and solutions must avoid default N+1 relation loading.
- [ ] **Step 2: Add protected writes**
  Every write requires current user, exact catalog/specification permission and CSRF; write audit metadata must never include password/token/secret.
- [ ] **Step 3: Add relation and publication-status endpoints**
  Replace explicit relation sets transactionally and expose translation/publication/route summary without allowing a second publication system.
- [ ] **Step 4: Run API contract tests**
  Run `python -m pytest tests/test_catalog_api.py tests/test_rbac.py -q`.

### Task 6: Minimal Admin CRUD validation UI

**Files:**
- Create: `apps/admin/app/pages/catalog/categories.vue`
- Create: `apps/admin/app/pages/catalog/products.vue`
- Create: `apps/admin/app/pages/catalog/specifications.vue`
- Create: `apps/admin/app/pages/catalog/materials.vue`
- Create: `apps/admin/app/pages/catalog/technologies.vue`
- Create: `apps/admin/app/pages/catalog/applications.vue`
- Create: `apps/admin/app/pages/catalog/solutions.vue`
- Modify: `apps/admin/app/pages/index.vue`
- Create: `apps/admin/tests/catalog-contract.test.ts`

- [ ] **Step 1: Add route-guarded list/create/edit shells**
  Keep master fields separate from zh-CN/en translation tabs; show basic validation and publication/translation state.
- [ ] **Step 2: Add relation selectors and specification value editor**
  Use explicit relation IDs and value-type-aware controls; do not provide Rich Text as the structured source of truth.
- [ ] **Step 3: Add Vitest contracts**
  Assert routes, permission-aware navigation, translation tabs, relation controls and no final-home/product-detail UI.
- [ ] **Step 4: Run frontend tests/typecheck/build**
  Run `pnpm test`, `pnpm typecheck`, `pnpm build`, `pnpm format:check`.

### Task 7: SEO/GEO route source and documentation

**Files:**
- Create: `apps/api/app/modules/content/services/indexable.py`
- Create: `apps/api/tests/test_indexable_routes.py`
- Modify: `docs/architecture/adr-content-route-publication.md`
- Create: `docs/architecture/phase3-3-completion-report.md`
- Modify: `README.md`

- [ ] **Step 1: Implement `list_indexable_routes()`**
  Return only active, indexable, canonical routes with published publication and enabled locale; make Product/Category/Material/Technology/Application/Solution owner types explicit.
- [ ] **Step 2: Add SEO/GEO contract tests**
  Verify stable language-prefixed paths, no draft leakage, and that GEO-readable facts come from public structured SSR content rather than hidden fields.
- [ ] **Step 3: Update ADR/README and write completion report**
  Include actual tree, models, translation/relation/publication/revision/audit/RBAC/API/Admin/test/Docker results, known issues, Phase 3.4 recommendations and `$seo-rank`/`$geo-rank` conflict check.

### Task 8: Full verification and handoff

**Files:**
- Modify: `.env.example` only if new runtime settings are required.

- [ ] **Step 1: Run local backend tests and static checks**
  Run non-PostgreSQL pytest, Ruff check/format, and `git diff --check`.
- [ ] **Step 2: Run isolated PostgreSQL/Redis Docker profile**
  Verify 0001→0004 migration, seed, constraints, relations, publication, routes, revisions and audit.
- [ ] **Step 3: Rebuild and verify常驻 Docker services**
  Confirm PostgreSQL, Redis, MinIO, API, Website, Admin and Nginx are healthy.
- [ ] **Step 4: Run frontend tests/typecheck/build and HTTP smoke**
  Confirm website/admin placeholders remain available and no final UI or prohibited subsystem was added.
- [ ] **Step 5: Review working tree and handoff**
  Confirm no secrets, production data, temporary fixtures or forbidden infrastructure are committed; summarize exact commands and results in the completion report.
