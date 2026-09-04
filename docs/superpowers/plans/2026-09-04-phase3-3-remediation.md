# Phase 3.3 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Structured Core 的 Translation、Publication、Route、Revision、RBAC 与 Admin CRUD 生命周期一致性，使 Phase 3.3 达到最终验收门槛。

**Architecture:** 保留既有 Master Entity + Translation + Publication + Route + Revision + Audit 模型，在 Catalog service 内增加统一 locale lifecycle、撤回索引、业务退役与完整快照服务；API 返回聚合编辑 DTO，并按实体类型绑定细粒度权限。Admin 使用可复用 composable 和表单组件提供最小真实 CRUD，不扩展 Phase 3.4 内容类型。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL、Nuxt 4、Vue 3、TypeScript、Vitest、pytest、Docker Compose。

---

### Task 1: Translation / Publication / Route lifecycle

**Files:**
- Modify: `apps/api/app/modules/catalog/services.py`
- Modify: `apps/api/app/modules/content/services/indexable.py`
- Test: `apps/api/tests/test_catalog_remediation.py`
- Test: `apps/api/tests/test_content_routes.py`

- [x] 写 published Translation 编辑、missing locale 首次补翻译、human reviewed 失效与重新发布的失败测试。
- [x] 运行目标 pytest，确认失败原因分别为 Publication/Route 未撤回、生命周期记录缺失、索引条件不足。
- [x] 实现 `ensure_locale_content_lifecycle()`、翻译编辑撤回公开状态和严格 `list_indexable_routes()`。
- [x] 运行目标 pytest，确认生命周期和索引源测试通过。

### Task 2: Business lifecycle, locale revisions and Product routes

**Files:**
- Modify: `apps/api/app/modules/catalog/services.py`
- Modify: `apps/api/app/api/v1/catalog.py`
- Test: `apps/api/tests/test_catalog_remediation.py`

- [x] 写 retired Product、disabled Material、默认 locale revision、en translation revision、draft category route 更新和 published category 409 的失败测试。
- [x] 运行目标 pytest 并记录预期失败。
- [x] 实现默认 Locale 选择、按实际 locale 写 Translation revision、归档时撤回 Publication/Route、产品分类路由同步与发布冻结。
- [x] 运行目标 pytest，确认全部通过。

### Task 3: Internal metadata lifecycle and complete revisions

**Files:**
- Modify: `apps/api/app/modules/catalog/services.py`
- Create: `apps/api/alembic/versions/20260904_0005_phase33_remediation.py`
- Test: `apps/api/tests/test_catalog_remediation.py`
- Test: `apps/api/tests/test_phase32_migrations.py`

- [x] 写 ProductModel/Specification metadata 无独立 Publication/Route，以及 relation/translation snapshot 包含实际内容的失败测试。
- [x] 运行目标 pytest 并确认旧行为被测试捕获。
- [x] 将 ProductModel、SpecificationGroup、SpecificationDefinition 调整为内部生命周期，保留 TranslationStatus、Revision、Audit；实现完整 relation/translation snapshot。
- [x] 新增精确 cleanup migration，只归档/停用上述 owner_type 的遗留记录。
- [x] 运行目标 pytest 与 migration contract。

### Task 4: Granular RBAC and aggregate detail APIs

**Files:**
- Modify: `apps/api/app/api/v1/catalog.py`
- Modify: `apps/api/app/modules/catalog/services.py`
- Test: `apps/api/tests/test_catalog_api.py`
- Test: `apps/api/tests/test_catalog_rbac.py`

- [x] 写 material/technology/application/solution 细粒度读写权限失败测试，以及 Product/知识实体 detail DTO 契约测试。
- [x] 运行目标 pytest，确认 catalog.* 误授权和 DTO 字段缺失。
- [x] 为动态路由绑定 `<entity>.read/create/update/archive`，增加聚合 detail、规格列表/值和编辑所需关系读取 API。
- [x] 运行 API/RBAC 测试，确认 sales 写操作 403、seo_manager 只读、content_admin 可写。

### Task 5: Minimal real Admin CRUD

**Files:**
- Create: `apps/admin/app/composables/useCatalogApi.ts`
- Create: `apps/admin/app/components/catalog/TranslationFields.vue`
- Modify: `apps/admin/app/pages/catalog/categories.vue`
- Modify: `apps/admin/app/pages/catalog/products.vue`
- Modify: `apps/admin/app/pages/catalog/materials.vue`
- Modify: `apps/admin/app/pages/catalog/technologies.vue`
- Modify: `apps/admin/app/pages/catalog/applications.vue`
- Modify: `apps/admin/app/pages/catalog/solutions.vue`
- Modify: `apps/admin/app/pages/catalog/specifications.vue`
- Modify: `apps/admin/app/assets/css/main.css`
- Test: `apps/admin/tests/catalog-contract.test.ts`

- [x] 先把 Admin contract 改为验证真实 GET/POST/PATCH/archive、translation tabs、relations、spec values 交互代码并确认失败。
- [x] 实现统一带 Cookie/CSRF 的 Catalog API composable、双语输入组件、实体列表/创建/编辑/归档和 Product 聚合编辑。
- [x] 运行 Admin Vitest、typecheck 与 Prettier，修复所有错误。

### Task 6: PostgreSQL, migration, seed and full verification

**Files:**
- Modify: `apps/api/tests/test_postgresql_integration.py`
- Create: `docs/architecture/phase3-3-remediation-report.md`

- [x] 增加 PostgreSQL 生命周期、索引源、migration cleanup 与 seed 幂等回归。
- [x] 运行 Ruff、Backend pytest、PostgreSQL integration、空库升级、0001→latest、seed 两次。
- [x] 运行 Website/Admin Vitest、typecheck、Prettier check、production build。
- [x] 重建并启动 Docker Compose，验证 PostgreSQL、Redis、MinIO、API、Website、Admin、Nginx healthy。
- [x] 生成 remediation report，填写 base SHA、branch、待提交 final SHA 说明、修复项、迁移、CRUD、测试、构建、Docker 与 SEO/GEO 冲突检查。
