# Phase 3.5 Completion Report

## 1. 交付标识

- 项目：`junhuiscrew/New_Official_Website`
- 分支：`phase-3.5`
- 基线：`phase-3.4-fix`
- Base SHA：`fd92f65b60af681abfdc6018d3960646804be416`
- Implementation SHA：`9f17a2a956b259c9cf44c555fb38a756a3ddb3d2`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 本报告提交：在实现提交后单独提交，以下测试均针对实现提交及其后端增量修正后的工作树执行。

## 2. 实际目录树（Phase 3.5 新增/变更重点）

```text
junhui-global-website/
├─ apps/
│  ├─ api/
│  │  ├─ alembic/versions/20260904_0008_company_trust_media.py
│  │  ├─ alembic/versions/20260904_0009_rfq_foundation.py
│  │  ├─ app/api/v1/{media,rfq,trust}.py
│  │  ├─ app/modules/company/{models,schemas,services}.py
│  │  ├─ app/modules/media/{models,services}.py
│  │  ├─ app/modules/rfq/{models,schemas,services}.py
│  │  └─ tests/test_phase35_foundation.py
│  ├─ admin/app/pages/{trust,media,downloads,rfqs}.vue
│  └─ website/app/pages/[lang]/
│     ├─ about.vue
│     ├─ capabilities/{index,[slug]}.vue
│     ├─ certificates/index.vue
│     ├─ downloads/index.vue
│     ├─ exhibitions/{index,[slug]}.vue
│     ├─ honors/index.vue
│     ├─ patents/index.vue
│     └─ request-a-quote/index.vue
├─ docs/architecture/phase3-5-completion-report.md
└─ docker-compose.yml
```

## 3. 技术栈及版本

- Python 3.12.3、FastAPI 0.116.1、SQLAlchemy 2.0.43、Alembic 1.16.5、Pydantic Settings 2.10.1。
- PostgreSQL 17.6、Redis 8.2、MinIO `RELEASE.2025-09-07T16-13-09Z`。
- Nuxt 4.5.2、Vue 3.5.42、Vite 8.2.2、pnpm 11.19.0、Node 24 Alpine。
- Celery 5.5.3（扫描任务基础设施沿用现有 worker 结构）。

## 4. Docker 服务

`docker compose up -d --build` 已实际运行并通过健康检查：`postgres`、`redis`、`minio`、`api`、`website`、`admin`、`nginx`；`minio-init` 正常退出（桶初始化成功）。

对外本地地址：API `http://localhost:8010`，Website `http://localhost:3000`，Admin `http://localhost:3001`，Nginx `http://localhost:8080`，MinIO Console `http://localhost:9001`。

HTTP 冒烟结果：`/api/v1/health/ready`、Website `/zh-cn/`、Admin `/`、`/sitemap.xml` 均返回 200。

## 5. Company Trust 模型

已建立 Master Entity + Translation 结构：

- `company_profiles` / `company_profile_translations`
- `manufacturing_capabilities` / translations
- `equipment` / translations
- `certificates` / translations
- `patents` / translations
- `honors` / translations
- `exhibitions` / translations
- 能力-设备、能力-证书、能力-专利、技术-设备等显式关系表。

Trust API 使用 granular RBAC，公开 DTO 只读取 enabled、已发布翻译、published publication、canonical active/indexable route 的内容；设备默认作为能力页结构化模块，不建立独立公开页。没有写入任何假证书、假专利、假设备、假荣誉或假 RFQ。

Company Profile 公开 DTO 和 Organization JSON-LD 只从真实公司档案读取，未配置真实资料时公开接口返回 404。

## 6. Media Library 与 Public Downloads

- `media_assets`、`media_asset_translations`、`download_resources`、`download_resource_translations` 已迁移。
- `public-media` 与 `private-rfq` 通过数据库 CHECK 约束绑定 visibility，禁止跨桶。
- Public Media 支持 JPG/PNG/WEBP/PDF/MP4/WEBM；RFQ 私有附件支持 JPG/PNG/WEBP/PDF/DWG/DXF/STEP/STP/IGES/IGS。
- 上传校验包含 extension allowlist、MIME、文件头签名、文件名清洗、SHA256、单文件大小；RFQ 另有限制总大小与文件数量。
- 公共媒体接口只返回公开 DTO；公开下载列表只返回 `public-media`、`ready` 资产；不存在向公开接口泄露 private bucket、storage key 或签名的路径。
- 私有下载需要认证、`rfq.download_private_file`、文件属于目标 RFQ、`malware_scan_status=clean`、`upload_status=ready`，并签发 60–900 秒 HMAC URL。
- 恶意软件状态已建模为 `pending/clean/infected/failed/not_required`；开发/测试可显式关闭扫描，生产未配置扫描器时附件进入 quarantine，不会签发下载。

## 7. RFQ Foundation

- `rfqs`、`rfq_items`、`rfq_files` 已建立；一个 RFQ 支持多个项目和项目级关联。
- 公共 `POST /api/v1/public/rfqs` 使用 Origin/Referer 校验、honeypot、隐私同意、字段和数量限制，并使用 Redis 按 IP 小时/日双窗口限流。
- 公共响应只包含 `{reference, status}`，不返回 UUID、assigned user、内部状态、storage path 或 signed URL。
- 来源归因只接受正式主域下的 enabled Product；销售分配、状态机、审计日志和私有附件元数据接口已提供。
- Admin 已增加 RFQ 列表/详情、Trust、Media、Downloads 最小工作页；Website 已增加 About、Trust 索引/详情、Downloads 和 `/request-a-quote/` 最小 SSR/Form 页面。

## 8. Migration 与 Seed

- 未修改 `0001`–`0007`。
- `0008`：Company Trust、Media Library、Public Downloads。
- `0009`：RFQ、RFQ Items、RFQ 私有附件。
- 空数据库 `0001 → latest` 已在干净 Docker PostgreSQL 中执行成功。
- Seed 保持幂等；仅扩展 Trust、Media、Download、RFQ granular permissions，不创建任何虚假业务内容或管理员。

## 9. SEO / GEO 一致性

- 继续复用既有 Publication、ContentRoute、TranslationStatus、Revision、Audit、RBAC，不建立第二套生命周期。
- Trust 可索引公开内容统一经过 enabled entity、enabled locale、published translation、published publication、canonical active/indexable route 门槛；索引 owner/handler 集合已同步扩展 capability 与 exhibition。
- Public DTO 不包含 private RFQ 文件；Admin 页面维持 `noindex,nofollow`。
- 已按 `$seo-rank` 检查 canonical、locale、publication、route 和 sitemap 约束，按 `$geo-rank` 检查公开事实来源、可见结构化内容和隐私边界；未发现与冻结交接规范冲突。

## 10. 实际测试结果

| 检查项 | 结果 |
|---|---|
| Ruff | PASS（All checks passed） |
| Backend pytest（本地） | PASS：159 passed，7 skipped，1 warning |
| PostgreSQL integration（干净 Docker DB） | PASS：166 passed，1 warning |
| Migration 0001 → latest | PASS，0008/0009 日志可见 |
| Seed idempotency | PASS（集成测试覆盖） |
| Media security | PASS（扩展名、MIME、签名、双扩展名、SHA256、私有桶边界） |
| RFQ security / response contract | PASS |
| Website Vitest | PASS：11 tests |
| Admin Vitest | PASS：18 tests |
| Typecheck | PASS（Website + Admin） |
| Prettier format check | PASS |
| Production build | PASS（Website + Admin Nuxt SSR/Nitro） |
| Docker Compose health | PASS（全部持久服务 healthy） |
| HTTP smoke | PASS：ready、website、admin、sitemap 均 200 |

唯一警告为 Starlette TestClient 的 AnyIO deprecation；Nuxt 构建中的 plugin timing/trailing-slash warning 不影响构建产物。

## 11. 已知问题与边界

1. 当前 Media API 已完成安全校验、桶边界、对象键和状态机基础；MinIO 对象实际写入适配器仍应在后续阶段接入真实上传流和异步扫描 worker。
2. Trust Admin 页面是最小可操作基础，不扩展为完整内容运营工作流。
3. RFQ 尚未进入生产部署、邮件通知、完整反垃圾供应商或 CAPTCHA 实现；已保留安全接口边界和限流配置。
4. 没有开始最终首页、最终 Design System、Page Builder、批量真实内容、生产部署或微服务拆分。

## 12. Phase 3.6 建议

优先接入 MinIO/S3 上传适配器与 ClamAV（或等价扫描器）异步 worker，补齐真实公开媒体/下载对象写入、失败重试和保留策略；随后再做 Trust/Media/RFQ 的审计检索、通知和运营体验。继续保持 `public-media` / `private-rfq` 隔离、统一 Publication/Route/Translation 生命周期及正式主域 canonical 规则。
