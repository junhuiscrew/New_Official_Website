# Junhui Global Website Phase 3.1 完成报告

报告日期：2026-09-04  
正式主域名：`https://junhuiscrewbarrel.com`  
实施范围：Repository Foundation、Docker 本地环境、FastAPI/SQLAlchemy/Alembic 基础工程、核心 RBAC/locale 模型、最小 Nuxt SSR 应用与基础测试。

## 1. 完成结论

Phase 3.1 约定的 Monorepo、Website/Admin/API、本地 PostgreSQL/Redis/MinIO/Nginx 编排、SQLAlchemy 2.x、首版 Alembic migration、六张基础表、确定性 Seed、健康检查、统一异常/响应、测试与本地文档均已创建并实际运行。

Docker 最终状态为 PostgreSQL、Redis、MinIO、API、Website、Admin、Nginx 全部 `healthy`；一次性 `minio-init` 正常退出码为 0。未实现最终首页、完整 CMS、RFQ 流程、批量产品页、生产部署或复杂微服务。

## 2. 实际目录树

以下树排除 `.git/`、`.venv/`、`node_modules/`、`.nuxt/`、`.output/` 和测试缓存：

```text
junhui-global-website/
├── .dockerignore
├── .editorconfig
├── .env.example
├── .gitignore
├── .prettierignore
├── .prettierrc.json
├── README.md
├── docker-compose.yml
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── apps/
│   ├── website/
│   │   ├── Dockerfile
│   │   ├── nuxt.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── app/
│   │   │   ├── app.vue
│   │   │   ├── site-config.ts
│   │   │   ├── assets/css/main.css
│   │   │   ├── components/LocalePlaceholder.vue
│   │   │   └── pages/
│   │   │       ├── en/index.vue
│   │   │       └── zh-cn/index.vue
│   │   └── tests/site-contract.test.ts
│   ├── admin/
│   │   ├── Dockerfile
│   │   ├── nuxt.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── app/
│   │   │   ├── admin-config.ts
│   │   │   ├── app.vue
│   │   │   ├── assets/css/main.css
│   │   │   └── pages/index.vue
│   │   └── tests/admin-contract.test.ts
│   └── api/
│       ├── Dockerfile
│       ├── alembic.ini
│       ├── pyproject.toml
│       ├── alembic/
│       │   ├── env.py
│       │   ├── script.py.mako
│       │   └── versions/20260904_0001_phase31_core.py
│       ├── app/
│       │   ├── main.py
│       │   ├── cli.py
│       │   ├── seed.py
│       │   ├── api/v1/{health.py,router.py}
│       │   ├── core/
│       │   │   ├── config/settings.py
│       │   │   ├── database/{base.py,session.py}
│       │   │   ├── exceptions/handlers.py
│       │   │   ├── pagination.py
│       │   │   └── responses.py
│       │   ├── modules/
│       │   │   ├── localization/models.py
│       │   │   └── users/models.py
│       │   └── workers/celery_app.py
│       └── tests/
│           ├── conftest.py
│           ├── test_database.py
│           ├── test_health.py
│           ├── test_migrations.py
│           └── test_seed.py
├── packages/
│   ├── ui/README.md
│   ├── types/README.md
│   ├── config/README.md
│   └── content-blocks/README.md
├── infra/
│   ├── docker/README.md
│   ├── nginx/nginx.conf
│   ├── backup/README.md
│   └── scripts/verify-local.ps1
└── docs/
    ├── architecture/phase3-1-completion-report.md
    ├── api/README.md
    ├── cms/README.md
    ├── seo/README.md
    ├── geo/README.md
    ├── migration/README.md
    └── superpowers/
        ├── plans/2026-09-04-phase3-1-foundation.md
        └── specs/2026-09-04-phase3-1-foundation-design.md
```

## 3. 技术栈及实际版本

### Frontend

| 组件 | 版本 |
|---|---:|
| Node.js（容器） | 24.20.0 |
| pnpm | 11.19.0 |
| Nuxt | 4.5.2 |
| Vue | 3.5.42 |
| Vue Router | 5.3.1 |
| TypeScript | 5.9.2 |
| Vitest | 3.2.4 |
| vue-tsc | 3.0.6 |
| Prettier | 3.6.2 |

Nuxt 最终构建组合为 Nuxt 4.5.2、Nitro 2.13.4、Vite 8.2.2 与 Vue 3.5.42。

### Backend

| 组件 | 版本 |
|---|---:|
| Python（容器） | 3.12.14 |
| FastAPI | 0.116.1 |
| SQLAlchemy | 2.0.43 |
| Alembic | 1.16.5 |
| Pydantic | 2.13.5 |
| Pydantic Settings | 2.10.1 |
| asyncpg | 0.30.0 |
| Celery | 5.5.3 |
| Uvicorn | 0.35.0 |
| pytest | 8.4.2 |
| Ruff | 0.12.11 |

### Infrastructure

| 组件 | 版本 |
|---|---:|
| PostgreSQL | 17.6 |
| Redis | 8.2.9 |
| MinIO | RELEASE.2025-09-07T16-13-09Z |
| MinIO Client | RELEASE.2025-08-13T08-35-41Z |
| Nginx | 1.28.3 |
| Docker Compose | 5.3.1 |

## 4. Docker 服务

| 服务 | 宿主端口 | 作用 | 最终状态 |
|---|---|---|---|
| `postgres` | 5432 | 主数据库 | healthy |
| `redis` | 6379 | Cache / Celery broker 基础设施 | healthy |
| `minio` | 9000 / 9001 | S3 API / Console | healthy |
| `minio-init` | 无 | 幂等创建 bucket 与访问策略 | exited (0) |
| `api` | 8010 → 8000 | FastAPI + 自动 migration/Seed | healthy |
| `website` | 3000 | Nuxt SSR public placeholder | healthy |
| `admin` | 3001 | Nuxt SSR admin placeholder | healthy |
| `nginx` | 8080 | 本地 Website/API 反向代理 | healthy |

宿主机 8000 已被工作区外的 `stars_sea_erp-backend-1` 占用，因此本项目默认使用 8010，不停止或修改无关容器。`API_HOST_PORT` 可覆盖该映射；容器内部端口仍为 8000。

MinIO bucket：

- `public-media`：匿名策略 `download`；
- `private-rfq`：匿名策略 `private`。

## 5. 数据库基础模型

| 表 | 用途 | 关键约束 |
|---|---|---|
| `users` | 后台用户账户 | UUID PK、唯一 email、password hash、启用状态 |
| `roles` | RBAC 角色 | UUID PK、唯一 name、系统角色标记 |
| `permissions` | 原子权限 | UUID PK、唯一 code |
| `user_roles` | 用户—角色显式多对多 | `(user_id, role_id)` 联合 PK、级联删除、分配人/时间 |
| `role_permissions` | 角色—权限显式多对多 | `(role_id, permission_id)` 联合 PK、级联删除、授权时间 |
| `locales` | 多语言配置 | UUID PK、唯一 code/slug、默认/启用状态、排序 |

PostgreSQL 实测显示六张表每个字段均存在中文 comment：`users` 7/7、`roles` 7/7、`permissions` 6/6、`user_roles` 4/4、`role_permissions` 3/3、`locales` 10/10。

未来 Catalog、Knowledge Graph、CMS、SEO/GEO、RFQ 等实体未在本阶段提前建表；保留 Master Entity + Translation tables 与显式业务关系的冻结方向。

## 6. Alembic migrations

当前仅一版：

| Revision | 文件 | 内容 |
|---|---|---|
| `20260904_0001` | `apps/api/alembic/versions/20260904_0001_phase31_core.py` | 创建六张基础表、索引、外键、联合主键与中文注释 |

容器内执行 `alembic current` 与 `alembic heads` 均返回 `20260904_0001 (head)`。API 启动命令先执行 `alembic upgrade head`，失败时不会启动 Uvicorn。

## 7. Seed 内容

### Locales（2）

| code | slug | 默认 | 启用 |
|---|---|---:|---:|
| `zh-CN` | `zh-cn` | 是 | 是 |
| `en` | `en` | 否 | 是 |

### Roles（8）

`super_admin`、`content_admin`、`editor`、`translator`、`reviewer`、`seo_manager`、`sales`、`media_manager`。

Seed 按唯一字段查询并只补缺失记录。容器启动后再次执行 `python -m app.cli seed`，数据库仍为 2 个 locale 与 8 个 role，证明幂等。

## 8. 本地启动方式

```bash
cd junhui-global-website
docker compose up -d
docker compose ps
```

常用地址：

- Website：`http://localhost:3000/zh-cn/`、`http://localhost:3000/en/`
- Admin：`http://localhost:3001/`
- API：`http://localhost:8010/api/v1/health`
- API Docs：`http://localhost:8010/docs`
- Nginx：`http://localhost:8080/`
- MinIO Console：`http://localhost:9001`

停止但保留数据：

```bash
docker compose down
```

完整本机开发、测试和手动 migration/Seed 命令见仓库根 `README.md`。

## 9. 测试与验证结果

| 验证 | 命令/方法 | 结果 |
|---|---|---|
| Python lint | `ruff check app tests` | 通过，0 error |
| Python format | `ruff format --check app tests` | 通过 |
| Backend tests | `pytest -p pytest_asyncio.plugin -q` | 6 passed |
| Frontend tests | `pnpm test` | Website 3 passed；Admin 1 passed |
| TypeScript | `pnpm typecheck` | 两个 Nuxt 应用通过 |
| Frontend format | `pnpm format:check` | 全部匹配 Prettier 规范 |
| Frontend production build | `pnpm build` | Website/Admin 均完成 Nitro node-server 构建 |
| Compose 语法 | `docker compose config --quiet` | 通过 |
| PostgreSQL | Compose health + `psql` | healthy；六表与 Seed 内容正确 |
| Redis | Compose health | healthy |
| MinIO | Compose health + `mc` | healthy；bucket/策略正确 |
| Alembic | `alembic current` / `heads` | 均为 `20260904_0001 (head)` |
| API | GET `/api/v1/health` | 200，统一成功 envelope |
| API docs | GET `/docs` | 200 |
| Website root | GET `/` | 308 → `/zh-cn/` |
| Website locale | GET `/zh-cn/`、`/en/` | 均为 200 |
| Admin | GET `/` | 200，SSR HTML 含 `noindex, nofollow` |
| Nginx | GET `/en/` via 8080 | 200 |

SSR HTML 实测包含：

- 可见 H1 与直接说明；
- `/zh-cn/` 和 `/en/` self-canonical；
- 两个已发布 placeholder 的互反 hreflang；
- `html lang="zh-CN"` / `html lang="en"`；
- Admin `noindex, nofollow`。

## 10. 已知问题

1. 宿主机 8000 被无关项目占用，本项目默认 API 宿主端口为 8010；可通过 `API_HOST_PORT` 调整。
2. pytest 在当前 Windows 环境中会显示 Starlette 对 AnyIO 旧 alias 的第三方弃用警告，不影响 6 项测试通过。
3. Node 24 构建 Nuxt 时会显示上游 Vue package exports trailing-slash 的弃用警告，构建退出码仍为 0。
4. Compose 的 Website/Admin 使用 Nuxt dev server，符合本地开发环境定位；生产镜像、缓存、安全头、CDN 与部署不属于 Phase 3.1。
5. `public-media` 当前具备公开下载基线，但尚无媒体业务上传校验；`private-rfq` 已私有，Signed URL 与 Audit Log 留待 RFQ 阶段。
6. 当前没有默认管理员账户、权限 Seed 或认证端点，符合 Phase 3.2 才进入 Authentication + RBAC 的冻结顺序。

## 11. Phase 3.2 建议

严格按交接文件，下一阶段聚焦 Authentication + RBAC + Localization 完整实现：

1. 增加安全密码哈希、登录/刷新/退出、账户锁定与基础审计；
2. 定义权限命名空间并 Seed 最小权限集，将 8 个角色映射到明确权限；
3. 实现 FastAPI 权限依赖与 Admin 路由守卫，不提前实现完整 CMS；
4. 完成 locale 管理与 `translation_statuses`，定义 Master Entity + Translation tables 的统一接口契约；
5. 增加 PostgreSQL 集成测试、认证安全测试和 RBAC 权限矩阵测试；
6. 为 staging 增加 Basic Auth、全站 noindex 和禁止进入 Sitemap 的环境级策略；
7. 在进入 Catalog 前编写核心实体/翻译表 ADR，冻结 slug、发布状态、revision 与 content_routes 的事务边界。

## 12. `$seo-rank` / `$geo-rank` 冲突检查

结论：未发现与交接文件冻结决策的实质冲突，且交接文件优先级已保持。

| 约束 | Phase 3.1 落地 | 冲突结论 |
|---|---|---|
| 重要内容 SSR | Nuxt `ssr: true`，H1/说明/metadata 均在初始 HTML | 无冲突 |
| 多语言 URL | 仅 `/zh-cn/` 与 `/en/`；`/` 308 到 `/zh-cn/` | 无冲突 |
| self-canonical | 两个语言页分别指向正式主域名自身 URL | 无冲突 |
| hreflang | 仅输出当前两个已实现语言版本并互相引用 | 无冲突 |
| GEO 可见性 | direct answer 在用户可见正文中，不使用隐藏 AI 文本 | 无冲突 |
| Entity 一致性 | 页面与配置统一使用 `Junhui Global Website` 和正式主域名 | 无冲突 |
| Admin 索引控制 | Admin SSR 输出 `noindex, nofollow` | 无冲突 |
| Schema / Sitemap / llms.txt | 未提前实现，避免与尚未存在的可见内容或发布状态不一致 | 与 Phase 3.1 禁止扩域一致 |
| 批量内容 / doorway | 未创建产品页、关键词页或 AI 专用页面 | 无冲突 |

`$seo-rank` 与 `$geo-rank` 通用清单中更完整的 Sitemap、Breadcrumb、JSON-LD、内容证据、作者/来源、内部链接、监测问题池等要求属于后续公开内容与 CMS 阶段。当前只保留不会造成返工的 SSR、稳定主域名、多语言、canonical、hreflang、可见 direct answer 和索引控制基线。
