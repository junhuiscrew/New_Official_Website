# Phase 3.3 完成报告：Structured Core Content Model + Catalog Foundation

日期：2026-09-04  
仓库：`junhuiscrew/New_Official_Website`  
基线：`phase-3.2`  
正式主域名：`https://junhuiscrewbarrel.com`

## 1. 实际修改目录树

```text
apps/
├─ api/
│  ├─ alembic/versions/20260904_0004_structured_core.py
│  ├─ app/api/v1/catalog.py
│  ├─ app/modules/catalog/{__init__.py,enums.py,models.py,schemas.py,services.py}
│  ├─ app/modules/content/services/indexable.py
│  └─ tests/{test_catalog_api.py,test_catalog_models.py,test_catalog_services.py}
└─ admin/app/pages/catalog/
   ├─ index.vue
   ├─ categories.vue
   ├─ products.vue
   ├─ specifications.vue
   ├─ materials.vue
   ├─ technologies.vue
   ├─ applications.vue
   └─ solutions.vue
docs/
├─ architecture/migration-runtime-strategy.md
└─ architecture/phase3-3-completion-report.md
```

同时更新 Alembic metadata 导入、v1 router、权限 Seed、路由测试及 PostgreSQL 集成测试；交接原文保存在仓库根目录 `Junhui-Codex-Handoff-Phase3.3.md`。

## 2. 技术栈及版本

- FastAPI 0.116.1、Python 3.12、SQLAlchemy 2.0.43、Alembic 1.16.5、Pydantic 2.13.5。
- PostgreSQL 17.6、Redis 8.2、MinIO RELEASE.2025-09-07T16-13-09Z。
- Nuxt 4.5.2、Vue 3.5.42、TypeScript 5.9.2、pnpm 11.19.0、Node 24 Alpine。
- 认证、Argon2id、RBAC、Locale、CORS、Publication、Route、Revision、Audit 沿用 Phase 3.2。

## 3. 新 migration

`20260904_0004_structured_core.py` 创建全部 Structured Core master、translation、relation 表及约束，已在 PostgreSQL 测试容器从 `20260904_0003` 升级并通过。

## 4. Structured Core 表

Master：`product_categories`、`products`、`product_models`、`specification_groups`、`specification_definitions`、`product_spec_values`、`materials`、`technologies`、`applications`、`solutions`。

Translation：上述核心实体均有独立 translation 表（包括 ProductModel、SpecificationGroup、SpecificationDefinition）。翻译表以 `(owner_id, locale_id)` 唯一约束，并和现有 `translation_statuses` 同事务写入。

Relation：`product_materials`、`product_technologies`、`product_applications`、`product_solutions`、`material_technologies`、`material_solutions`、`application_solutions`，均使用复合主键和受限外键；产品四类关系提供事务化替换 API。

## 5. Category Tree 设计

`product_categories.parent_id` 自引用且禁止自引用；服务层锁定父链，检测任意可达循环。Tree API 以 `sort_order, id` 稳定排序。已投入使用的分类通过 `disabled/retired` 生命周期处理，不提供物理删除。

## 6. Product / ProductModel

Product 归属启用 Category，`slug` 使用小写 kebab-case；ProductModel 在单一 Product 范围内以 `model_code` 唯一。已发布实体的 slug 原地修改会被拒绝，避免 canonical route 漂移。

## 7. Specification

支持 `text`、`number`、`range`、`boolean`、`enum` 五种类型。`ProductSpecValue` 对 Product/ProductModel 实行 owner XOR；数据库约束保证恰好一个值列，服务层再按 Definition.value_type 校验，范围下限不得大于上限。

## 8. Material / Technology / Application / Solution

四类实体拥有独立 master、translation、lifecycle、slug、publication、route、revision、audit，并通过显式 relation 表互联；没有将结构化数据塞回 Rich Text。

## 9. Publication Integration

创建实体时按已有 Locale 初始化 `TranslationStatus`；有翻译的语言创建 draft `ContentPublication`。发布状态仍统一使用 `draft/review/scheduled/published/archived`，只允许已审核翻译进入 published。

## 10. Route Integration

路由统一使用 `/{locale}/.../`、小写 kebab-case、尾斜杠和 canonical 唯一约束。产品路径为 `/{locale}/products/{category}/{product}/`。新增 `list_indexable_routes()`，仅返回启用 Locale 且 `published + active + indexable + canonical` 的结构化路由，作为 SEO/GEO 索引源。

## 11. Revision Integration

创建实体的 master、translation 快照通过现有 `store_revision()` 写入 `content_revisions`，使用 PostgreSQL advisory lock 分配递增版本号。更新/关系变更继续通过统一服务入口扩展，未引入第二套内容版本模型。

## 12. Audit Integration

创建、更新、归档、关系变更、规格变更及发布路由变更写入现有 `audit_logs`，保留 actor、target、action 和结构化 metadata。

## 13. 新 Permission Matrix

新增 22 项权限：`catalog.read/create/update/archive`、`specification.read/manage`，以及 Material、Technology、Application、Solution 各自的 `read/create/update/archive`。`content_admin` 获得全部结构化权限；`editor` 获得 catalog create/update；`reviewer` 和 `seo_manager` 获得只读检查权限；`sales` 不获得 Catalog 写权限。系统总权限数为 58，原 8 个角色保持不变。

## 14. Admin 页面

新增 Catalog 总览、Categories、Products & Models、Specifications、Materials、Technologies、Applications、Solutions 最小占位页。沿用全局认证 Route Guard，所有页面继承 Admin `noindex, nofollow` 与 `X-Robots-Tag` 策略；真正授权始终由 FastAPI Permission dependency 执行。未制作最终首页或产品详情视觉。

## 15. API 列表

- `GET/POST/PATCH /api/v1/catalog/categories`、`GET /categories/tree`
- `GET/POST/PATCH /api/v1/catalog/products`、`GET /products/{id}`、`POST /products/{id}/archive`
- `POST /products/{id}/models`、`PATCH /product-models/{id}`
- `PUT /products/{id}/relations`
- `POST /specifications/groups`、`/definitions`、`/values`
- Material/Technology/Application/Solution 的 list/create/update/archive 一致路由

写 API 统一要求 Auth、Permission、CSRF，并将数据库唯一/FK 冲突映射为稳定 409 错误。

## 16. Seed / Fixture

生产 Seed 只补充系统 Locale、8 个角色、58 个权限及冻结 role-permission mapping，不导入真实产品内容。测试 fixture 创建临时分类、产品、型号和规格，用于 API、关系、约束和生命周期验证。

## 17. 数据完整性约束

包括 lifecycle/status 检查、slug/code 唯一性、ProductModel 产品范围唯一、translation owner-locale 唯一、关系复合主键、外键 RESTRICT、规格 owner XOR/值列 XOR/范围校验，以及既有 email 大小写不敏感唯一和单默认 Locale 约束。

## 18. 测试结果

- 本地 API：`90 passed, 6 skipped`。
- Docker PostgreSQL 测试：`96 passed`（含 migration、seed、PG 约束和集成测试）。
- Ruff：`All checks passed`。
- Website Vitest：`5 passed`；Admin Vitest：`9 passed`；Website/Admin Typecheck：均通过。
- Admin/Website Docker production build：均成功；新增 Admin Catalog 页面已进入 Nitro 产物。
- Compose 服务重建后 API、Website、Admin、PostgreSQL、Redis、MinIO、Nginx 均 healthy。

## 19. Docker 最终状态

本地端口：Website `3000`、Admin `3001`、API `8010`、Nginx `8080`、PostgreSQL `5432`、Redis `6379`、MinIO `9000/9001`。API 启动顺序为 migration → system seed → Uvicorn；readiness 使用 `/api/v1/health/ready`。

## 20. 已知问题

- Catalog 页面目前是模型/权限工作流占位页，不是最终 CMS UI。
- 本阶段没有批量真实产品内容、完整 Product Detail、Page Builder、RFQ 或公开 sitemap 生成器。
- 本地 Windows pytest 默认缓存目录偶有文件锁，验证时使用隔离 `--basetemp`；Docker/Linux 测试不受此影响。
- 关系编辑已提供 Product 四类关系 API，Material↔Technology/Solution 与 Application↔Solution 的管理 UI/专用 API 留待后续阶段。

## 21. Phase 3.4 建议

在不破坏 Master Entity + Translation + Publication + Route + Revision + Audit 的前提下，优先补齐 Catalog detail/read API、关系管理 API、审核/发布操作界面、公开 Product listing/detail 的 SSR 数据契约和 sitemap/index source；随后再评估结构化 SEO Schema 与受控内容组件。继续禁止把结构化核心字段退回 Rich Text，也继续延后最终视觉、完整 RFQ 和自由 Page Builder。

## 22. `$seo-rank` / `$geo-rank` 冲突检查

已按两个规范检查：主域名未改变；Locale 前缀、canonical、稳定 slug、published/active/indexable 过滤一致；Admin/staging 继续全站 noindex；索引源不暴露 draft/missing translation，也没有 AI-only 或隐藏字段替代结构化实体。未发现与交接文件冻结业务决策冲突。
