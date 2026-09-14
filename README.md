# Junhui Global Website

Junhui Global Website 是舟山骏辉塑料机械有限公司面向全球塑料机械行业的双语 B2B 官网与内容管理系统。项目使用 Nuxt/Vue 前台与后台、FastAPI 模块化 API、PostgreSQL、Redis、MinIO、Celery 和 Nginx，正式规范域名为 `https://junhuiscrewbarrel.com`。

当前处于 **Phase 3.7 持续验收与演示完善阶段**。代码、原始批准内容和完整 Demo 均只运行在本机隔离环境；没有生产部署，也没有修改公共 DNS。新对话继续维护前，必须先阅读 [交接文档-新对话.md](./交接文档-新对话.md)。

## 当前状态

| 项目            | 当前状态                                                    |
| --------------- | ----------------------------------------------------------- |
| GitHub          | `junhuiscrew/New_Official_Website`                          |
| 开发分支        | `phase-3.7`                                                 |
| 当前已推送 HEAD | `d3e4435da63c583a3c46b395d3875ca573801ea1`                  |
| 最新迁移        | `20260910_0016_demo_fixed_utility_site_pages`               |
| 原始内容实例    | `junhui-phase37-pilot`，保留 COPY-V1、8 组 SEO 和原业务数据 |
| 完整演示实例    | `junhui-demo-r2`，独立 PostgreSQL/Redis/MinIO 数据卷        |
| 本机入口        | 仅 `127.0.0.1:443`，HTTPS，VPN 可保持开启                   |
| 搜索引擎保护    | 全站外层 `noindex`，Sitemap 关闭                            |
| Privacy         | P1 技术能力已实现；主实例与 Demo 均未发布正式政策           |
| 生产环境        | 未部署、未授权上线                                          |

## 两套本机环境

### 1. 原始批准内容预览

这套环境保存 Batch01 公司与三款产品的获准内容，不得被 Demo 数据覆盖。

| 服务     | 地址                                                    |
| -------- | ------------------------------------------------------- |
| 中文网站 | `https://junhuiscrewbarrel.com/zh-cn/`                  |
| 英文网站 | `https://junhuiscrewbarrel.com/en/`                     |
| 后台     | `https://admin.junhuiscrewbarrel.com/`                  |
| API      | `https://api.junhuiscrewbarrel.com/api/v1/health/ready` |

当前边界：

- COPY-V1 的公司与三款产品共 16 个中英文字段保持批准版本；
- About、Products、screws、barrels 共 8 组 SEO 已保存并验证；
- P01/P02/P03 参数值仍为 `0/0/0`，F05 英文仍空缺；
- 三款主图尺寸元数据已修复，原文件、哈希、媒体 ID 与关联不变；
- 旧试点产品保持 draft、Route 关闭；
- Privacy P1 只保存私有 draft，没有 current 版本，公开 Privacy 仍不可用；
- 内部 Publication/Route 只服务本地受保护预览，不代表生产发布。

### 2. Demo R2 完整演示

Demo 与原始实例数据分离，用于展示完整网站和后台运营体验。

| 服务      | 地址                                                         |
| --------- | ------------------------------------------------------------ |
| 中文 Demo | `https://demo.junhuiscrewbarrel.com/zh-cn/`                  |
| 英文 Demo | `https://demo.junhuiscrewbarrel.com/en/`                     |
| Demo 后台 | `https://admin-demo.junhuiscrewbarrel.com/`                  |
| Demo API  | `https://api-demo.junhuiscrewbarrel.com/api/v1/health/ready` |

Demo 当前包含：

- 90 条双语演示内容；
- 9 个演示产品、完整栏目关系与规格示例；
- 48 项媒体（43 张图片、2 段真实 WebM、3 个 PDF）；
- 首页 14 个模块的真实 renderer、后台配置和有意义演示内容；
- About、Contact、Products、RFQ、材料、工艺、应用、方案、案例、知识、下载等页面；
- 中文运营后台、媒体具体使用位置、角色权限编辑、询盘分页与筛选；
- About、Contact、RFQ 六个双语页面的完整 SSR SEO 元数据；
- 12 条明确标注为 Demo 的虚构询盘，无真实附件或邮件。

所有 Demo 文字、规格、案例、作者、证书、设备和生成式图片都必须按演示资料处理，不能直接迁入生产。

## 日常启动

前置条件：Docker Desktop 正常运行，首次 Setup 已完成 hosts、本地 CA 和代理精确直连设置。

### 启动完整 Demo

推荐使用桌面快捷方式“打开骏辉完整演示站”，或在当前工作树执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\Junhui-Demo-R2-Launcher.ps1 -Action Start
```

查询状态或停止（保留数据卷）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\Junhui-Demo-R2-Launcher.ps1 -Action Status -NoOpen

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\Junhui-Demo-R2-Launcher.ps1 -Action Stop -NoOpen
```

### 启动原始批准内容预览

推荐使用桌面快捷方式“打开骏辉本地官网”，或执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\Junhui-LocalPreview-Launcher.ps1 -Action Start
```

Windows PowerShell 5.1 应调用 `*-Launcher.ps1`，不要直接执行含 UTF-8 中文的主脚本。`Stop` 只停止服务并保留数据；禁止使用 `docker compose down -v`，除非用户明确授权删除数据卷。

## 凭据与私有文件

仓库没有公开默认管理员密码。凭据仅保存在被 Git 忽略的本地环境文件：

- 原始实例：`.env.phase37` 中的 `PHASE37_ADMIN_EMAIL` / `PHASE37_ADMIN_PASSWORD`；
- Demo：`.env.demo-r2` 中的 `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`；
- 数据、证书、备份和运行状态：`data/phase3-7/`、`data/demo-r2/`；
- 临时证据与私有采集：`artifacts/` 及根目录证据 ZIP。

不要在聊天、日志、截图或 Git 中输出密码、Cookie、Token、数据库 URL、对象存储密钥、证书私钥、私有 RFQ 或签名下载 URL。后台应用自身登录、RBAC、CSRF、Secure Cookie 和私有附件权限必须保留。

## 架构

```text
apps/
  website/        Nuxt 4 / Vue 3 双语 SSR 官网
  admin/          Nuxt 4 / Vue 3 中文运营后台
  api/            FastAPI、SQLAlchemy、Alembic、Celery 与测试
packages/
  config/         Website/Admin 共享 API Base 解析
  ui/             共享 UI 边界
  types/          共享 TypeScript 类型
  content-blocks/ Flexible Blocks 类型边界
infra/nginx/      开发、隔离预览和本地域名 Nginx 配置
scripts/          本机预览、Demo、验证与证据工具
docs/             架构、内容、SEO、GEO、验收和操作文档
```

核心内容生命周期为：

```text
Master Entity
  -> Translation
  -> Publication
  -> ContentRoute
  -> SeoDocument / GEO / Media / Relations
  -> Revision + Audit + RBAC
```

公开 API 只返回满足实体状态、语言翻译、发布状态、Route 和 SEO 门禁的数据。正式 canonical/hreflang 使用正式规范域名；本机语言导航会安全转换为同站相对路径。

## 主要后台入口

- `/`：工作台
- `/site-overview`：全站模块总览
- `/homepage`：首页 14 模块编排
- `/catalog`、`/catalog/products`、`/catalog/specifications`：目录与产品
- `/trust/company`：企业资料与 About SEO
- `/site-pages/products`：Products 固定页 SEO
- `/site-pages/contact`、`/site-pages/request-a-quote`：Contact/RFQ 固定页 SEO
- `/media`、`/demo-media`：媒体库与 Demo 媒体替换
- `/cases`、`/knowledge`、`/faqs`、`/experts`：内容与作者
- `/downloads`、`/rfqs`、`/roles`、`/users`：下载、询盘、权限与用户
- `/privacy`：Privacy P1 私有草稿和版本管理

## 测试与质量检查

```powershell
pnpm test
pnpm typecheck
pnpm format:check
pnpm build
```

API 本地开发环境：

```powershell
Set-Location apps/api
.venv/Scripts/python -m pytest -p no:cacheprovider
.venv/Scripts/python -m ruff check --no-cache app tests alembic
```

真实 PostgreSQL/Redis/MinIO 隔离测试：

```powershell
docker compose --profile test up --abort-on-container-exit `
  --exit-code-from api-test api-test
```

最近提交 `d3e4435` 前重新通过 Website `155/155` 和 Admin `88/88`。本轮仅更新文档时不应复制历史测试数量冒充新测试结果。

## 维护边界

- 保留原 phase37 与 Demo 两套数据卷，禁止清库、全量重导或互相覆盖；
- 不自动把 Demo 内容、参数、媒体、案例或 SEO 写回原始实例；
- Privacy 正式正文、current 切换和 RFQ 正式提交仍需单独授权；
- 不连接腾讯云、NAS、Gmail/SMTP、Analytics 或生产数据库；
- 不修改公共 DNS，不部署，不向搜索平台提交；
- 不用直接 SQL 绕过 CMS、Revision、Audit、权限或发布流程；
- Git 操作前先检查未提交文件，禁止 `git add -A` 把私有证据包和快照带入仓库。

## 关键文档

- [新对话交接文档](./交接文档-新对话.md)
- [Demo R2 实施报告](./docs/content/demo-r2-report.md)
- [Demo R2 维护说明](./docs/content/demo-r2-maintenance-guide.md)
- [中文后台员工使用说明](./docs/content/admin-cn-employee-guide.md)
- [中文后台功能收尾](./docs/content/admin-cn-ux-r1-functional-closeout-report.md)
- [Demo 六页 SEO 收尾](./docs/content/demo-seo-metadata-r1-report.md)
- [Privacy P1 实施报告](./docs/content/privacy-p1-content-version-report.md)
- [官网呈现 R1 报告](./docs/content/website-presentation-r1-report.md)
- [本机域名预览报告](./docs/content/local-domain-preview-report.md)
- [架构与发布事务 ADR](./docs/architecture/adr-content-route-publication.md)
- [迁移与运行策略](./docs/architecture/migration-runtime-strategy.md)
