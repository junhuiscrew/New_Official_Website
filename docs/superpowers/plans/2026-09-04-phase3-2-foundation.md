# Junhui Global Website Phase 3.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 Phase 3.1 Monorepo 上交付可运行、可迁移、可审计的 Authentication、RBAC、Localization 与 Publication Foundation。

**Architecture:** 保留 Nuxt SSR + FastAPI 模块化单体 + PostgreSQL/Redis/MinIO，通过 HttpOnly Cookie、短期访问令牌、可轮换并可撤销的刷新会话建立认证边界。内容发布、翻译状态、路由、修订与审计由共享领域模型和事务服务承载；Admin 仅提供功能验证 UI，所有授权由 API 服务端强制执行。

**Tech Stack:** Nuxt 4、Vue 3、TypeScript、FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL 17、Redis 8、Argon2id、PyJWT、Docker Compose、pytest、Vitest。

---

### Task 1: 配置、安全边界与 API Base

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `apps/api/app/core/config/settings.py`
- Modify: `apps/api/app/main.py`
- Create: `packages/config/src/api-base.ts`
- Modify: `apps/website/nuxt.config.ts`
- Modify: `apps/admin/nuxt.config.ts`
- Test: `apps/api/tests/test_settings.py`
- Test: `apps/api/tests/test_cors.py`
- Test: `apps/website/tests/api-base.test.ts`
- Test: `apps/admin/tests/api-base.test.ts`

- [ ] **Step 1: 写配置与 API Base 失败测试**

```python
def test_production_rejects_default_secrets():
    with pytest.raises(ValidationError):
        Settings(app_env="production")
```

```ts
expect(resolveApiBase(true, '/api/v1', 'http://api:8000/api/v1')).toBe('http://api:8000/api/v1')
expect(resolveApiBase(false, '/api/v1', 'http://api:8000/api/v1')).toBe('/api/v1')
```

- [ ] **Step 2: 运行定向测试并确认因缺少实现而失败**

Run: `pytest tests/test_settings.py tests/test_cors.py -q`
Expected: FAIL，Settings 尚未验证生产 Secret，应用尚未注册安全 CORS allowlist。

Run: `pnpm --filter @junhui/website test && pnpm --filter @junhui/admin test`
Expected: FAIL，共享 API Base resolver 尚不存在。

- [ ] **Step 3: 实现生产 fail-fast、显式 CORS 与 server/client API Base resolver**

```ts
export function resolveApiBase(isServer: boolean, publicBase: string, internalBase: string): string {
  return isServer ? internalBase : publicBase
}
```

- [ ] **Step 4: 重跑定向测试并确认通过**

### Task 2: 数据库模型与 Alembic Migration

**Files:**
- Modify: `apps/api/app/modules/users/models.py`
- Modify: `apps/api/app/modules/localization/models.py`
- Create: `apps/api/app/modules/auth/models.py`
- Create: `apps/api/app/modules/content/models.py`
- Create: `apps/api/app/modules/audit/models.py`
- Modify: `apps/api/app/core/database/base.py`
- Create: `apps/api/alembic/versions/20260904_0002_phase32_foundation.py`
- Test: `apps/api/tests/test_phase32_migrations.py`

- [ ] **Step 1: 写 PostgreSQL migration 失败测试**

```python
assert {"auth_sessions", "translation_statuses", "content_publications", "content_routes", "content_revisions", "audit_logs"}.issubset(inspector.get_table_names())
```

- [ ] **Step 2: 运行测试并确认新表、CITEXT 与 partial unique index 尚不存在**
- [ ] **Step 3: 创建 migration，启用 CITEXT、转换 email、建立单默认语言索引与六张基础表**
- [ ] **Step 4: 从空 PostgreSQL 数据库执行 `alembic upgrade head` 并确认通过**

### Task 3: Authentication、Cookie、Refresh Rotation 与 Audit

**Files:**
- Create: `apps/api/app/core/security/passwords.py`
- Create: `apps/api/app/core/security/tokens.py`
- Create: `apps/api/app/core/security/csrf.py`
- Create: `apps/api/app/modules/auth/schemas.py`
- Create: `apps/api/app/modules/auth/service.py`
- Create: `apps/api/app/modules/auth/dependencies.py`
- Create: `apps/api/app/api/v1/auth.py`
- Modify: `apps/api/app/api/v1/router.py`
- Test: `apps/api/tests/test_authentication.py`

- [ ] **Step 1: 写正确登录、错误密码、inactive、大小写登录、refresh rotation、logout revoke 与 current-user 失败测试**
- [ ] **Step 2: 运行测试并确认因认证模块不存在而失败**
- [ ] **Step 3: 实现 Argon2id、短期 JWT access cookie、HMAC 摘要 refresh session、HttpOnly/Secure/SameSite cookie 与 CSRF 双提交校验**
- [ ] **Step 4: 重跑认证测试并确认旧 refresh token 轮换后不可复用**

### Task 4: Permission Seed 与服务端 RBAC

**Files:**
- Modify: `apps/api/app/seed.py`
- Create: `apps/api/app/modules/users/schemas.py`
- Create: `apps/api/app/modules/users/service.py`
- Create: `apps/api/app/api/v1/users.py`
- Create: `apps/api/app/api/v1/rbac.py`
- Test: `apps/api/tests/test_rbac.py`
- Test: `apps/api/tests/test_seed_phase32.py`

- [ ] **Step 1: 写 36 个权限、8 个角色矩阵、403/成功、sales 禁止 SEO、media_manager 禁止 RFQ 私有下载的失败测试**
- [ ] **Step 2: 运行测试并确认权限依赖与矩阵尚不存在**
- [ ] **Step 3: 实现 `get_current_user`、`require_permission`、`require_any_permission`、`require_role` 与只增补不删除自定义映射的幂等 Seed**
- [ ] **Step 4: 重跑 RBAC 与 Seed 测试两次并确认结果一致**

### Task 5: Bootstrap Super Admin

**Files:**
- Modify: `apps/api/app/cli.py`
- Create: `apps/api/app/modules/users/bootstrap.py`
- Test: `apps/api/tests/test_bootstrap_super_admin.py`

- [ ] **Step 1: 写 email normalize、密码强度、重复用户安全退出、角色绑定和 audit 失败测试**
- [ ] **Step 2: 运行测试并确认 `create-super-admin` 尚不受支持**
- [ ] **Step 3: 实现交互输入或环境变量输入，不在仓库保存固定账号或密码**
- [ ] **Step 4: 使用一次性测试凭据运行命令并确认 Argon2id hash 与 audit 记录存在**

### Task 6: Locale Management

**Files:**
- Create: `apps/api/app/modules/localization/schemas.py`
- Create: `apps/api/app/modules/localization/service.py`
- Create: `apps/api/app/api/v1/locales.py`
- Test: `apps/api/tests/test_locales.py`

- [ ] **Step 1: 写 list/create/update/enable/sort/set-default、重复 code/slug、禁止禁用默认语言失败测试**
- [ ] **Step 2: 运行测试并确认 locale API 尚不存在**
- [ ] **Step 3: 实现事务化 set-default，并依赖 `locale.read`/`locale.manage`**
- [ ] **Step 4: 重跑测试并直接向 PostgreSQL 写入第二个默认语言，确认数据库拒绝**

### Task 7: Publication、Route、Translation 与 Revision

**Files:**
- Create: `apps/api/app/modules/content/enums.py`
- Create: `apps/api/app/modules/content/services/publication.py`
- Create: `apps/api/app/modules/content/services/routes.py`
- Create: `apps/api/app/modules/content/services/revisions.py`
- Test: `apps/api/tests/test_publication.py`
- Test: `apps/api/tests/test_content_routes.py`
- Test: `apps/api/tests/test_revisions.py`
- Create: `docs/architecture/adr-content-route-publication.md`

- [ ] **Step 1: 写状态转换、translator 禁止发布、duplicate path、published transaction、revision rollback contract 失败测试**
- [ ] **Step 2: 运行测试并确认领域服务尚不存在**
- [ ] **Step 3: 实现小写 kebab-case 路径验证与单事务 publication/translation/route 一致更新**
- [ ] **Step 4: 重跑测试并确认 archived route 不 active、不 indexable**

### Task 8: Health、Admin Guard 与索引控制

**Files:**
- Modify: `apps/api/app/api/v1/health.py`
- Create: `apps/admin/app/composables/useAuth.ts`
- Create: `apps/admin/app/middleware/auth.global.ts`
- Create: `apps/admin/app/pages/login.vue`
- Create: `apps/admin/app/pages/forbidden.vue`
- Create: `apps/admin/app/pages/users.vue`
- Create: `apps/admin/app/pages/roles.vue`
- Create: `apps/admin/app/pages/locales.vue`
- Modify: `apps/admin/app/pages/index.vue`
- Test: `apps/api/tests/test_health.py`
- Test: `apps/admin/tests/auth-guard.test.ts`

- [ ] **Step 1: 写 live/ready、Admin 全局 meta/header noindex 与 guard policy 失败测试**
- [ ] **Step 2: 运行测试并确认缺少拆分 health 与 guard**
- [ ] **Step 3: 实现 PostgreSQL/Redis readiness、兼容旧 health、Admin 功能壳和服务端权限结果处理**
- [ ] **Step 4: 用 HTTP 请求验证 Admin HTML meta 和 `X-Robots-Tag`**

### Task 9: Staging 与 Migration Runtime

**Files:**
- Create: `docker-compose.staging.yml`
- Create: `infra/nginx/nginx.staging.conf`
- Create: `docs/architecture/migration-runtime-strategy.md`
- Modify: `infra/nginx/nginx.conf`
- Test: `apps/api/tests/test_deployment_contracts.py`

- [ ] **Step 1: 写 staging Basic Auth/noindex、production migration-before-start 文档契约失败测试**
- [ ] **Step 2: 运行测试并确认环境配置尚不存在**
- [ ] **Step 3: 实现 staging 独立覆盖配置，凭据仅通过外部 htpasswd 文件注入**
- [ ] **Step 4: 验证未认证 staging 请求为 401，认证后响应仍带 noindex header**

### Task 10: Docker PostgreSQL Integration Test 与最终验收

**Files:**
- Modify: `apps/api/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `infra/scripts/verify-local.ps1`
- Modify: `README.md`
- Create: `docs/architecture/phase3-2-completion-report.md`

- [ ] **Step 1: 建立独立 `postgres-test` 与 `api-test` profile，避免污染开发数据库**
- [ ] **Step 2: 运行 `docker compose --profile test up --build --abort-on-container-exit --exit-code-from api-test api-test`**
- [ ] **Step 3: 运行 `docker compose up -d --build`、migration、Seed、认证与权限 smoke test**
- [ ] **Step 4: 运行 `pnpm test`、`pnpm typecheck`、`pnpm build` 与后端 pytest/ruff**
- [ ] **Step 5: 检查 Website/Admin 渲染、Admin noindex、staging policy 与全部容器 health**
- [ ] **Step 6: 按交接文件第 20 节写入完成报告，逐项记录命令、版本、结果、已知问题及 Phase 3.3 建议**

