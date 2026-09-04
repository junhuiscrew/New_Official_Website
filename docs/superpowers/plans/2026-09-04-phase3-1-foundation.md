# Junhui Global Website Phase 3.1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建并实测 Junhui Global Website Phase 3.1 Monorepo、本地基础设施、核心数据模型与最小 SSR 应用。

**Architecture:** pnpm workspace 管理两个 Nuxt SSR 应用，FastAPI 模块化单体使用 SQLAlchemy async + Alembic 管理 PostgreSQL。Docker Compose 编排 PostgreSQL、Redis、MinIO、API、Website 与 Admin，Seed 通过独立幂等命令执行。

**Tech Stack:** Nuxt、Vue 3、TypeScript、Python 3.12、FastAPI、Pydantic Settings、SQLAlchemy 2.x、Alembic、PostgreSQL、Redis、MinIO、Docker Compose、pytest、Vitest。

---

### Task 1: Repository foundation

**Files:** `package.json`, `pnpm-workspace.yaml`, `.env.example`, `.gitignore`, `README.md`, `packages/*/README.md`

- [x] 创建 workspace、工程目录与无真实密钥的环境变量样例。
- [x] 初始化 Git，并校验 `.env`、缓存、构建产物不会被跟踪。
- [x] 校验根目录脚本能统一执行前端 build/test。

### Task 2: Backend tests first

**Files:** `apps/api/tests/test_health.py`, `apps/api/tests/test_database.py`, `apps/api/tests/test_migrations.py`, `apps/api/tests/test_seed.py`

- [x] 先编写 health、数据库、migration、locale/RBAC Seed 的行为测试。
- [x] 运行测试，确认实现缺失时测试按预期失败。
- [x] 保留测试作为后端实现契约。

### Task 3: FastAPI foundation and core models

**Files:** `apps/api/app/**`, `apps/api/pyproject.toml`, `apps/api/alembic.ini`, `apps/api/alembic/**`

- [x] 创建类型化配置、async engine/session、Declarative Base、统一响应和异常处理。
- [x] 创建 `/api/v1/health`、API v1 router 与分页参数骨架。
- [x] 创建 users/roles/permissions/user_roles/role_permissions/locales 模型，所有数据库字段添加中文 comment。
- [x] 创建首版 Alembic migration 和幂等 Seed 命令。
- [x] 运行 pytest，修复至全部通过。

### Task 4: Minimal Nuxt SSR applications

**Files:** `apps/website/**`, `apps/admin/**`

- [x] 为 website 先创建路由/元数据测试，再实现 `/`、`/zh-cn/`、`/en/` 最小 SSR 页面。
- [x] 根路由服务端 308 跳转；语言页输出 self-canonical、互相 hreflang、唯一 metadata、可见 H1。
- [x] 为 admin 先创建 placeholder/noindex 测试，再实现最小 SSR 页面。
- [x] 运行前端 tests 和 builds，修复至全部通过。

### Task 5: Docker local environment

**Files:** `docker-compose.yml`, `apps/*/Dockerfile`, `infra/docker/**`, `infra/nginx/**`, `infra/scripts/**`

- [x] 配置 PostgreSQL、Redis、MinIO、API、Website、Admin 及健康检查。
- [x] 启动 Compose，确认数据库、中间件和应用容器健康。
- [x] 在容器内执行 `alembic upgrade head` 与幂等 Seed。
- [x] 实测 API、Website、Admin HTTP 响应。

### Task 6: Documentation and final verification

**Files:** `README.md`, `docs/architecture/phase3-1-completion-report.md`

- [x] 记录完整目录树、锁定版本、服务端口、模型、migration、Seed 和启动方式。
- [x] 重新运行 backend tests、frontend tests/builds、Compose 状态和 HTTP smoke tests。
- [x] 检查 secrets、Phase 3.1 范围以及 SEO/GEO 约束冲突。
- [x] 把实际命令、通过数量和已知问题写入完成报告。
