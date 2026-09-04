# Phase 3.4 Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 Phase 3.4 验收指出的 5 个 SEO/GEO 交付层问题，并用回归测试证明公开索引、公开 API、SSR、结构化关系和 Redirect 规则保持一致。

**Architecture:** 保留现有 Master Entity + Translation + Publication + ContentRoute + Revision + Audit + RBAC。GEO 校验从数据库聚合可见事实；所有公开 Link DTO 统一经过发布门槛和 canonical route 过滤；Sitemap 与 hreflang 共用 self-canonical 判断；AuthorExpert 继续作为可索引实体并补齐 Public API/SSR/Person Schema；Redirect 目标仅允许正式非 www 主域。

**Tech Stack:** FastAPI、SQLAlchemy 2.x、PostgreSQL、Pydantic、Nuxt 3、Vue 3、TypeScript、Vitest、Pytest、Docker Compose。

---

### Task 1: 固化失败回归测试

**Files:**
- Create: `apps/api/tests/test_phase34_remediation.py`
- Modify: `apps/website/tests/phase34-public-pages.test.ts`
- Modify: `apps/admin/tests/phase34-authority-contract.test.ts`

1. 添加 GEO 服务端事实、canonical/Sitemap/hreflang、Expert public route、Link DTO、Redirect host 与 health issue code 测试。
2. 添加 Website Expert SSR 与关系 `<a>` 合约测试。
3. 添加 Admin 不再提交 `visible_source_text`、只读预览合约测试。
4. 运行聚焦测试，确认旧实现按预期失败。

### Task 2: GEO 服务端可见事实

**Files:**
- Modify: `apps/api/app/modules/discovery/schemas.py`
- Modify: `apps/api/app/modules/discovery/services.py`
- Modify: `apps/api/app/api/v1/discovery.py`
- Modify: `apps/admin/app/components/discovery/GeoEditor.vue`
- Modify: `apps/admin/app/components/authority/AuthorityCrud.vue`

1. 从写入模型移除客户端 `visible_source_text`。
2. 实现 Product / Case / Knowledge / Expert 的服务端可见事实构造器，并确保 Case 隐私字段不进入事实池。
3. `upsert_geo_document()` 只使用服务端事实校验 direct answer、key facts 和 evidence。
4. 提供权限保护的只读可见事实预览 API，Admin 仅展示预览。

### Task 3: Canonical、Sitemap、hreflang 和健康检查一致性

**Files:**
- Modify: `apps/api/app/modules/content/services/indexable.py`
- Modify: `apps/api/app/modules/discovery/public_delivery.py`
- Modify: `apps/api/app/modules/discovery/health_checks.py`
- Modify: `apps/api/app/api/v1/discovery.py`

1. 统一判断 canonical override 是否等于正式 self canonical。
2. 非 self-canonical 页面从 Sitemap 与 hreflang 排除。
3. 输出 `canonical_override_excludes_sitemap` 及交接要求的 SEO/GEO 稳定问题代码。
4. 验证 Sitemap 中每种 URL 都有对应公开 handler。

### Task 4: Expert 公开交付与真实 Link DTO

**Files:**
- Modify: `apps/api/app/modules/discovery/public_delivery.py`
- Modify: `apps/api/app/modules/discovery/schema_generator.py`
- Modify: `apps/api/app/api/v1/public.py`
- Create: `apps/website/app/pages/[lang]/experts/[slug].vue`
- Create: `apps/website/app/components/PublicRelationLinks.vue`
- Modify: Product / Case / Knowledge SSR 页面

1. 增加严格发布门槛下的 Expert DTO、Public API、SSR 与 Person Schema。
2. 把 Product / Case / Knowledge 关系由 UUID 转为 `{type, slug, name, url, summary}`。
3. 只返回已启用、已翻译、已发布、canonical、active、indexable、允许索引的关联目标。
4. SSR 页面用真实 `<a href>` 输出内部链接。

### Task 5: Redirect 目标域修复

**Files:**
- Modify: `apps/api/app/modules/discovery/redirects.py`

1. 明确 source host 白名单与唯一 target host。
2. 拒绝 www 正式域和新旧域作为 target，同时保留其 source 能力。

### Task 6: 验证与完成报告

**Files:**
- Create: `docs/architecture/phase3-4-remediation-report.md`

1. 运行 Ruff、后端单元测试与 PostgreSQL integration tests。
2. 验证 Empty DB → latest、0001 → latest、Seed 幂等。
3. 运行 Website/Admin Vitest、Typecheck、Prettier、Production Build。
4. 重建 Docker Compose 并验证服务健康和公开端点。
5. 记录 Branch、Base SHA、Final SHA、5 项修复、测试、Build、Docker 与 `$seo-rank` / `$geo-rank` 冲突检查。
