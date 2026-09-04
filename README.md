# Junhui Global Website

Junhui Global Website 是面向全球塑料机械行业的螺杆、机筒及相关塑化部件 B2B 官网、工程知识中心与 RFQ 获客平台。正式主域名为 `https://junhuiscrewbarrel.com`。

当前仓库完成 Phase 3.1 基础工程：Monorepo、两个最小 Nuxt SSR 应用、FastAPI 模块化单体、PostgreSQL/Redis/MinIO、Alembic、基础 RBAC/locale 模型与本地 Docker Compose。最终首页、完整 CMS、RFQ 和产品内容不在本阶段范围内。

## 目录

```text
apps/
  website/        Public Website，Nuxt SSR
  admin/          Admin CMS 壳，Nuxt SSR
  api/            FastAPI 模块化单体
packages/
  ui/             共享 UI 包边界（未实现组件库）
  types/          共享 TypeScript 类型边界
  config/         共享配置边界
  content-blocks/ Flexible Blocks 类型边界
infra/
  docker/         Docker 说明
  nginx/          本地反向代理配置
  backup/         未来备份策略边界
  scripts/        本地验证脚本
docs/             架构、CMS、SEO、GEO、API 与迁移文档
```

## 一条命令启动

前置要求：Docker Desktop 已启动，Docker Compose 可用。无需先创建 `.env`；Compose 内置的默认值只用于本地开发。如需自定义，请复制 `.env.example` 为 `.env` 并替换示例密码。

```bash
docker compose up -d
```

API 容器启动时会自动执行：

```bash
alembic upgrade head
python -m app.cli seed
```

Seed 是幂等的，重复启动不会重复插入基础语言和角色。

## 本地服务

| 服务 | 地址 / 端口 |
|---|---|
| Website | http://localhost:3000/zh-cn/ 与 http://localhost:3000/en/ |
| Admin | http://localhost:3001/ |
| API | http://localhost:8010/api/v1/health |
| API Docs | http://localhost:8010/docs |
| Nginx 聚合入口 | http://localhost:8080/ |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| MinIO S3 API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |

Website 根路径 `/` 使用 308 跳转到 `/zh-cn/`。Admin 输出 `noindex, nofollow`。MinIO 初始化 `public-media` 与 `private-rfq` 两个 bucket，后者禁止匿名访问；Phase 3.1 不实现 RFQ 上传业务。

## 常用 Docker 命令

```bash
docker compose ps
docker compose logs -f api
docker compose exec api alembic current
docker compose exec api python -m app.cli seed
powershell -ExecutionPolicy Bypass -File infra/scripts/verify-local.ps1
docker compose down
```

`docker compose down` 保留数据库、Redis 与 MinIO named volumes。只有明确需要清空本地数据时才使用 `docker compose down -v`。

## 本机开发

### Frontend

需要 Node.js 24 和 pnpm 11.19：

```bash
pnpm install
pnpm dev:website
pnpm dev:admin
```

### API

需要 Python 3.12：

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload
```

Windows PowerShell 下虚拟环境 Python 路径为 `.venv\Scripts\python.exe`。直接在宿主机运行 API 时，需要把 `DATABASE_URL` 指向可访问的 PostgreSQL。Compose 默认将容器内 8000 映射到宿主机 8010，以避免常见的本地 8000 端口冲突；可通过 `API_HOST_PORT` 修改。

## 测试与质量检查

```bash
cd apps/api
.venv/Scripts/python -m pytest -p pytest_asyncio.plugin
.venv/Scripts/python -m ruff check app tests

cd ../..
pnpm test
pnpm typecheck
pnpm format:check
pnpm build
```

后端测试使用仓库内 `.pytest-tmp` 临时目录，并以 SQLite 验证数据库抽象、migration 与幂等 Seed；最终验收还会在 Docker PostgreSQL 17 上执行真实 migration 与 Seed。

## 数据与安全说明

- `.env.example` 只含本地示例值，不含真实 secret。
- 不要提交 `.env`、对象存储密钥或生产数据库凭据。
- `private-rfq` 仅是本阶段的私有 bucket 基线；Signed URL、下载审计与 RFQ 流程属于后续阶段。
- 当前没有默认管理员账户或密码；Authentication + RBAC 完整实现属于 Phase 3.2。

## Phase 3.1 完成报告

完成后的实际目录、版本、验证结果与已知问题见 `docs/architecture/phase3-1-completion-report.md`。
