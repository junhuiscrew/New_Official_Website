# Junhui Global Website

Junhui Global Website 是面向全球塑料机械行业的螺杆、机筒及相关塑化部件 B2B 官网基础工程，正式主域名为 `https://junhuiscrewbarrel.com`。

仓库当前完成 Phase 3.5 Remediation：在既有 Structured Core、Authority Content、SEO/GEO 与统一发布生命周期上，补齐真实 MinIO/S3 对象存储、RFQ 私有附件、Celery 恶意软件扫描流程、Company Trust 生命周期和对应 Admin/Public 闭环。最终首页视觉、完整 Page Builder、生产部署和批量内容仍不在本阶段范围内。

## 目录

```text
apps/
  website/        Public Website，Nuxt SSR placeholder
  admin/          Admin、Trust/Media/Downloads/RFQ 管理页面
  api/            FastAPI 模块化单体、Celery Worker、Alembic 与测试
packages/
  config/         Website/Admin 共享 API Base 解析
  ui/             共享 UI 包边界
  types/          共享 TypeScript 类型边界
  content-blocks/ Flexible Blocks 类型边界
infra/
  nginx/          开发与 Staging 反向代理配置
  scripts/        本地验证脚本
docs/architecture/ ADR、迁移策略与完成报告
```

## 本地启动

前置要求：Docker Desktop 与 Docker Compose。仓库默认值只用于本地开发；自定义配置时复制 `.env.example` 为 `.env`，不要提交真实 Secret。

```bash
docker compose up -d --build
docker compose ps
```

API 启动顺序固定为：

```bash
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Seed 可重复执行，只补充缺失的 2 个 Locale、8 个系统 Role、完整 Permission Matrix、9 个 Knowledge Category 和缺失的系统映射，不删除后续自定义映射。

| 服务               | 地址 / 端口                                               |
| ------------------ | --------------------------------------------------------- |
| Website            | http://localhost:3000/zh-cn/ 与 http://localhost:3000/en/ |
| Admin              | http://localhost:3001/login                               |
| API live           | http://localhost:8010/api/v1/health/live                  |
| API ready          | http://localhost:8010/api/v1/health/ready                 |
| API Docs           | http://localhost:8010/docs                                |
| Nginx 同源入口     | http://localhost:8080/                                    |
| PostgreSQL         | localhost:5432                                            |
| Redis              | localhost:6379                                            |
| MinIO S3 / Console | http://localhost:9000 / http://localhost:9001             |

`worker` 通过 Redis 接收 RFQ 私有附件扫描任务。开发环境可关闭外部扫描器；Staging/Production 在扫描器不可用时会 fail-closed，将文件保持为不可下载状态。

Website 根路径以 308 跳转到 `/zh-cn/`。浏览器统一使用同源 `/api/v1`，Nuxt SSR 在容器内使用 `http://api:8000/api/v1`。Admin 的 HTML 与响应头全局设置 `noindex, nofollow`。

## Bootstrap Super Admin

项目没有默认管理员或默认密码。首次初始化必须显式执行安全 Bootstrap；推荐交互输入密码，避免密码进入 shell history：

```bash
docker compose exec api python -m app.cli create-super-admin
```

自动化环境可临时注入 `BOOTSTRAP_ADMIN_EMAIL`、`BOOTSTRAP_ADMIN_PASSWORD` 和 `BOOTSTRAP_ADMIN_DISPLAY_NAME`。密码必须通过强度检查，邮箱按大小写不敏感唯一；已有账号会安全失败，不会覆盖密码或角色。

## Authentication 与权限

- 密码使用 Argon2id，仅保存哈希。
- Access JWT 为短期 HttpOnly Cookie；Refresh Credential 是高熵随机值，仅以 HMAC 摘要存入 `auth_sessions`，每次 refresh 轮换并撤销旧 session；旧凭据重放会撤销该用户仍有效的后继 refresh session。
- Refresh Credential 不进入 `localStorage` 或响应 JSON。
- 写请求使用 SameSite Cookie 加双提交 CSRF 校验。
- FastAPI 通过 `require_permission(...)` 做最终授权；Admin Route Guard 只负责用户体验。
- `/api/v1/auth/login`、`refresh`、`logout`、`me` 提供完整会话生命周期；Admin 在客户端收到 access 401 时会使用 HttpOnly refresh Cookie 自动续期一次。

## 测试与质量检查

宿主机测试：

```bash
cd apps/api
.venv/Scripts/python -m pytest -p no:cacheprovider
.venv/Scripts/python -m ruff check --no-cache app tests alembic

cd ../..
pnpm test
pnpm typecheck
pnpm format:check
pnpm build
```

真实 PostgreSQL 17 + Redis + MinIO 隔离测试（自动执行 migrations、seed 和完整后端测试）：

```bash
docker compose --profile test up --abort-on-container-exit --exit-code-from api-test api-test
docker compose rm -sf api-test postgres-test redis-test
```

运行态验证：

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/verify-local.ps1
```

## Staging 与生产安全

Staging overlay 要求外部 htpasswd 文件和显式 Secret：

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml config
```

`docker-compose.staging.yml` 仅暴露 Nginx 入口，PostgreSQL、Redis、MinIO、API、Website 与 Admin 均不发布宿主端口；入口启用 Basic Auth、全站 `X-Robots-Tag: noindex, nofollow`，并关闭 sitemap、analytics 与 marketing email。Nginx 会覆盖客户端提供的转发头，API 只信任 `TRUSTED_PROXY_CIDRS` 中的直连代理；生产负载均衡的网段需要按实际部署单独配置。所有非 development 环境若仍使用示例 Secret 会 fail-fast；Staging/Production 还要求带用户名/密码的数据库 URL 与非本地 HTTPS CORS allowlist。生产迁移顺序、回滚与并发策略见 `docs/architecture/migration-runtime-strategy.md`。

## 常用命令

```bash
docker compose logs -f api
docker compose exec api alembic current
docker compose exec api python -m app.cli seed
docker compose down
```

`docker compose down` 保留 named volumes；只有明确需要清空本地数据时才使用 `docker compose down -v`。

## Phase 3.4 Authority 与 Discovery

- Admin 最小真实 CRUD：`/cases`、`/knowledge`、`/faqs`、`/experts`。
- SSR 公开模板：`/{lang}/products/{category}/{slug}`、`/{lang}/case-studies/{slug}`、`/{lang}/knowledge/{category}/{slug}`。
- 公开发现文件：`/sitemap.xml`、`/robots.txt`，以及由 `LLMS_TXT_ENABLED` 控制的 `/llms.txt`。
- Public DTO 只返回同时满足 Entity、Locale、Translation、Publication、canonical Route 与 SEO robots_index 门槛的内容。
- FAQPage Schema 由 `FAQ_SCHEMA_ENABLED` 控制，默认关闭；系统不会生成虚构 Offer、价格、Review、Rating 或人物。
- Redirect Manager 使用精确 host/path 规则，并拒绝 self、loop、chain、duplicate 与不安全目标；已发布 URL 必须通过单事务 URL Change API 变更。
- Case 客户名称、地址、Logo 采用逐字段公开许可；未获许可的数据不会进入 Public DTO、Schema、SEO 或 GEO。

## Phase 3.5 Trust、Media 与 RFQ

- `public-media` 与 `private-rfq` 使用独立 MinIO bucket；公共媒体通过同源应用代理交付，浏览器不会看到 Docker 内部端点。
- RFQ 支持多 Item 与匿名附件；附件经过扩展名、MIME、文件头、文件名、大小、SHA256 和恶意软件状态校验。
- 私有下载必须同时满足认证、`rfq.download_private_file`、RFQ 归属、`clean + ready`，之后才签发短期 S3 Presigned GET。
- Trust、Media、Downloads 与 RFQ Admin 页面均连接真实 API；公开 Trust 索引只显示满足统一可索引门槛的真实数据。
- 当前修复验收记录见 `docs/architecture/phase3-5-remediation-report.md`。

## Phase 3.2 文档

- `Junhui-Codex-Handoff-Phase3.2.md`：本阶段冻结规范
- `docs/architecture/adr-content-route-publication.md`：Publication/Route/SEO/GEO 事务边界
- `docs/architecture/migration-runtime-strategy.md`：正式部署迁移策略
- `docs/architecture/phase3-2-completion-report.md`：实际实现和验收结果
