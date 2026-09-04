# Phase 3.3 Remediation 完成报告

生成日期：2026-09-04  
正式主域名：`https://junhuiscrewbarrel.com`

## 1. Base SHA / Final SHA / Branch

- Base SHA：`9d94ada04748e0ff04ca601387df84d5125f130e`
- Branch：`phase-3.3-fix`
- Final SHA：当前修复成果仍位于工作树，尚未创建提交；提交后应以 `git rev-parse HEAD` 回填。本报告不把 base SHA 冒充为修复后的 final SHA。
- 范围：仅 Phase 3.3 Remediation；未进入 Phase 3.4。

## 2. 修复文件树

```text
junhui-global-website/
├─ apps/
│  ├─ api/
│  │  ├─ alembic/versions/
│  │  │  └─ 20260904_0005_phase33_remediation.py
│  │  ├─ app/
│  │  │  ├─ api/v1/catalog.py
│  │  │  └─ modules/
│  │  │     ├─ catalog/
│  │  │     │  ├─ schemas.py
│  │  │     │  └─ services.py
│  │  │     └─ content/services/
│  │  │        ├─ indexable.py
│  │  │        └─ publication.py
│  │  └─ tests/
│  │     ├─ test_catalog_api_remediation.py
│  │     ├─ test_catalog_remediation.py
│  │     ├─ test_content_routes.py
│  │     ├─ test_phase33_remediation_migration.py
│  │     └─ test_postgresql_integration.py
│  └─ admin/
│     ├─ app/
│     │  ├─ app.vue
│     │  ├─ assets/css/main.css
│     │  ├─ components/catalog/
│     │  │  ├─ EntityCrud.vue
│     │  │  └─ TranslationFields.vue
│     │  ├─ composables/useCatalogApi.ts
│     │  └─ pages/catalog/
│     │     ├─ index.vue
│     │     ├─ categories.vue
│     │     ├─ products.vue
│     │     ├─ specifications.vue
│     │     ├─ materials.vue
│     │     ├─ technologies.vue
│     │     ├─ applications.vue
│     │     └─ solutions.vue
│     └─ tests/catalog-contract.test.ts
└─ docs/
   ├─ architecture/phase3-3-remediation-report.md
   └─ superpowers/plans/2026-09-04-phase3-3-remediation.md
```

## 3. Translation lifecycle 修复

- 新增统一事务服务 `invalidate_publication_after_translation_edit()`。
- 修改已发布或已审核 Translation 时，同一事务内将 TranslationStatus 退回 `draft`，清除 reviewer 与发布时间。
- 对应 Publication 从 `published`/`scheduled` 退回 `review`，对应 Route 同步设置 `is_active=false`、`is_indexable=false`。
- 修改内容与生命周期变化分别写入 Revision 和 Audit，不再出现“正文已变但旧发布状态仍可索引”的窗口。
- 补充“编辑后退出索引、重新发布后恢复”和 `human_reviewed` 失效回归测试。

## 4. Missing locale lifecycle 修复

- 首次新增某个 Locale 的 Translation 时，幂等创建 TranslationStatus、draft Publication 与 Canonical Route。
- 新 Route 默认 inactive + noindex，必须完成翻译审核与正式发布后才能进入公开索引源。
- 重复保存同一 Locale 不会产生重复 Publication 或 Canonical Route。

## 5. retire/disable indexability 修复

- Product 进入 `retired`、Material/Technology/Application/Solution 等公开实体进入非 `enabled` 状态时，统一归档 Publication，并关闭 Route 的 active/indexable 标记。
- `list_indexable_routes()` 还会读取实际业务实体状态作为第二道约束，避免仅依赖生命周期表中的历史值。
- 已增加 retired Product 与 disabled Material 不可索引回归测试。

## 6. Revision locale 修复

- Master Entity Revision 的 Locale 通过 `locales.is_default=true` 明确取得，不再依赖 UUID 排序。
- Translation 修改 Revision 使用实际被修改的 Locale。
- Translation Revision snapshot 包含修改后的翻译字段；Relation Revision snapshot 包含实际关系 ID 集合。

## 7. Product category/route 规则

- Draft Product 更换 Category 或 slug 时，幂等更新所有 draft Canonical Route，并执行路径冲突检查。
- 任一 Locale 已发布时禁止更换 Category，API 返回 HTTP 409 与 `published_category_frozen`。
- Category Route 规则继续使用稳定 slug 与父级 Category 路径，不引入新 URL 体系。

## 8. ProductModel indexability 决策落地

- ProductModel V1 保留结构化数据、Translation、Revision 与 Audit 能力。
- ProductModel 不创建 ContentPublication、ContentRoute，也不在索引源 owner 类型集合中。
- 迁移会关闭历史遗留 ProductModel 的公开生命周期记录。

## 9. Specification metadata lifecycle 简化

- SpecificationGroup 与 SpecificationDefinition 保留结构化元数据、Translation、Revision 与 Audit。
- 两者不创建 ContentPublication 或 ContentRoute，也不进入公开索引源。
- ProductSpecValue 支持新增与更新，并继续执行动态类型校验。
- 迁移关闭历史遗留 SpecificationGroup/SpecificationDefinition 的公开生命周期记录。

## 10. Granular RBAC 落地

- Material API 使用 `material.read/create/update/archive`。
- Technology API 使用 `technology.read/create/update/archive`。
- Application API 使用 `application.read/create/update/archive`。
- Solution API 使用 `solution.read/create/update/archive`。
- `catalog.*` 不再替代上述资源的服务端授权；Admin Route Guard 仅用于体验，服务端依赖仍是权限事实来源。
- 参数化 API 测试证明仅持有 `catalog.create` 的用户不能创建上述四类实体。

## 11. Admin CRUD 实际页面/功能

- Product：列表、创建、编辑、归档、双语 Translation、Model 增加/退役、四类 Relation 编辑、Specification Value 新增与更新。
- ProductCategory：列表、创建、编辑、父级、状态、排序与双语 Translation。
- Material/Technology/Application/Solution：使用共享真实 CRUD 组件，支持列表、创建、编辑、归档、状态、排序、featured 与双语字段。
- Specification：Group/Definition 列表与创建，Product/Model spec value 新增与更新。
- 共用 `useCatalogApi` 处理 Cookie、CSRF、请求错误和 CRUD 请求；不是静态占位页。
- Admin 导航按 read permission 显示 Catalog 入口，但真正授权仍在 FastAPI。

## 12. Detail DTO/API

- Product Detail 返回编辑页所需：Translations、ProductModels（含 Translation 与 model spec）、Product spec values、Material/Technology/Application/Solution Relations、TranslationStatus、Publication 与 Route 状态。
- ProductCategory 与四类核心实体 Detail 返回 master、Translations、TranslationStatus、Publication 与 Route 状态。
- Specification Group、Definition、Value 提供最小读取接口；Value 提供 PATCH 更新接口。

## 13. 新 migration

- 新增：`20260904_0005_phase33_remediation.py`
- Revision：`20260904_0005`，down revision：`20260904_0004`。
- 行为：将 `product_model`、`specification_group`、`specification_definition` 遗留 Publication 归档，并将对应 Route 设为 inactive/noindex。
- 该数据修正不可安全推断原公开状态，因此 downgrade 明确为 no-op，避免错误地重新暴露内部元数据。
- 未修改 0001–0004 历史 migration。

## 14. 新 regression tests

- Published Translation 编辑后不再 indexable，并验证重新发布恢复。
- `human_reviewed` Translation 编辑后审核状态清除。
- Missing Locale 首次补翻译后 lifecycle 自动且幂等建立。
- retired Product / disabled Material 不再 indexable。
- Revision locale 使用实际/默认 Locale。
- Draft Product 换 Category 更新 Route；Published Product 返回 409。
- ProductModel 无独立 Publication/Route。
- Specification metadata 无公开 Publication/Route。
- 四类资源 granular RBAC 真正生效。
- Product/Material Detail DTO 完整性。
- Relation Revision 包含实际关系数据。
- strict indexable source 七条件。
- 0005 migration head 与历史遗留数据清理。
- PostgreSQL 事务级生命周期与索引回归。
- Admin Product/Material 等真实 CRUD 源码契约与 Translation tab 契约。

## 15. Backend test results

- Ruff：`All checks passed!`
- 本地 pytest：`106 passed, 7 skipped, 1 warning in 28.69s`
- 本地跳过的 7 项均为显式标记、要求真实 PostgreSQL 的集成测试；已在容器环境全部执行。
- 已知 warning：Starlette TestClient 引用 AnyIO 兼容别名的弃用提示，不影响本轮结果。

## 16. PostgreSQL test results

- 使用 `postgres:17.6-alpine` 的独立 tmpfs 测试库。
- 空库到 `20260904_0001`：通过。
- `20260904_0001 → head`：依次运行 0002、0003、0004、0005，通过。
- Seed 连续执行两次：均成功，幂等性通过。
- 容器内完整测试：`113 passed, 1 warning in 29.27s`，包含 7 项 PostgreSQL integration tests。

## 17. Frontend/Admin tests

- Website Vitest：`5 passed`。
- Admin Vitest：`12 passed`。
- Website Nuxt typecheck：通过。
- Admin Nuxt typecheck：通过。
- Prettier `format:check`：全部匹配。

## 18. Build results

- `pnpm build`：Website production build 通过。
- `pnpm build`：Admin production build 通过。
- Docker build：API、Website、Admin 镜像均使用当前工作树重新构建成功。
- 前端版本：Nuxt `4.5.2`、Vue `3.5.42`、TypeScript `5.9.2`、Vitest `3.2.4`、pnpm `11.19.0`。
- 后端关键版本：Python `3.12`、FastAPI `0.116.1`、SQLAlchemy `2.0.43`、Alembic `1.16.5`、pytest `8.4.2`。

## 19. Docker status

最终开发栈已用 `docker compose up -d --build` 重建：

| Service | Version/Image | 状态/验证 |
|---|---|---|
| postgres | `postgres:17.6-alpine` | healthy |
| redis | `redis:8.2-alpine` | healthy |
| minio | `RELEASE.2025-09-07T16-13-09Z` | healthy |
| minio-init | `RELEASE.2025-08-13T08-35-41Z` | exited 0（预期一次性任务） |
| api | current local build | healthy；Alembic `20260904_0005 (head)` |
| website | current local build | healthy；`http://localhost:3000/zh-cn/` 返回 200 |
| admin | current local build | healthy；`http://localhost:3001/` 返回 200 |
| nginx | `nginx:1.28-alpine` | healthy；`http://localhost:8080/zh-cn/` 返回 200 |

API `live` 与 `ready` 均返回 HTTP 200。Docker Compose 版本：`v5.3.1`。

## 20. 已知问题

- 当前工作树尚未提交，因此没有可诚实填写的 remediation Final SHA；不影响代码与运行验证，但 Git 交付时必须回填。
- 测试仍显示上游 Starlette/AnyIO 弃用 warning；本轮无功能失败。
- Admin 是用于验证 Structured Core 与工作流的最小 CRUD，不是最终视觉、完整 CMS 或 Page Builder。
- 尚未加入浏览器级 E2E；当前覆盖为 API integration、Admin/Vitest contract、typecheck、production build 与容器 HTTP 健康验证。
- 0005 downgrade 不恢复被关闭的内部实体公开状态，这是避免错误重新索引的有意安全决策。

## 21. 是否达到 Phase 3.3 最终验收条件

除“生成 Git Final SHA/远端提交”属于后续 Git 交付动作外，本轮代码、migration、regression tests、PostgreSQL integration、前端测试、typecheck、格式检查、production build 与 Docker healthy 门槛均已通过，可申请 Phase 3.3 源码重新验收。

未实现 Case Study、Knowledge Article、FAQ、Author/Expert、SEO/GEO Documents、Sitemap Generator、Schema Generator、Redirect Manager、RFQ、Page Builder、最终首页、最终 Design System 或批量真实内容，范围保持在 Remediation。

## 22. `$seo-rank` / `$geo-rank` 冲突检查

- 已按 `$seo-rank` 将唯一可公开索引源收紧为七项同时成立：Business Entity enabled、Locale enabled、Translation published、Publication published、Canonical Route、Route active、Route indexable。
- 已按 `$geo-rank` 的权威内容可见性原则，使正文/结构化 Translation 修改立即失去审核与公开索引资格，避免 AI 或搜索引擎继续将失效正文视作已发布权威内容。
- ProductModel 与 Specification metadata 明确不拥有独立公开 Route/Publication，避免薄页面和错误实体页进入索引面。
- Missing Locale 默认 draft + inactive + noindex，不因“Translation row 已存在”而提前公开。
- 本轮没有实现 sitemap、schema、SEO/GEO 文档生成或批量内容，符合 remediation 范围限制。
- 未发现交接文件冻结决策与 `$seo-rank` / `$geo-rank` 规范冲突；如有优先级争议，仍以正式交接文件和已冻结业务决策为最高约束。
