# Junhui Global Website — Codex 正式交接文件（Phase 3.3）

版本：V1.0  
日期：2026-09-04  
项目：Junhui Global Website  
正式主域名：`https://junhuiscrewbarrel.com`  
GitHub：`junhuiscrew/New_Official_Website`  
基线分支：`phase-3.2`

---

# 0. 本文件用途

本文件用于把已经通过完成报告验收和 GitHub 源码级验收的 Phase 3.2 项目，正式交接给 Codex 执行：

> **Phase 3.3 — Structured Core Content Model + Catalog Foundation**

本阶段第一次正式进入网站核心业务数据层，但仍然不进入最终视觉设计，也不做完整自由 Page Builder。

本阶段目标是把未来官网最关键的结构化实体和关系真正落到 PostgreSQL、FastAPI、Admin 基础管理和发布体系中：

```text
Product
ProductCategory
ProductModel
Specification
Material
Technology
Application
Solution
```

并与 Phase 3.2 已完成的：

```text
Locale
Translation
Publication
ContentRoute
Revision
Audit
RBAC
```

正确连接。

---

# 1. Phase 3.2 已通过验收的基础

Phase 3.2 已完成并通过源码审查：

- Authentication
- Argon2id Password
- Access JWT
- Refresh Session Rotation
- HttpOnly Cookie
- CSRF
- RBAC
- Permission Matrix
- Bootstrap Super Admin
- CITEXT Email
- Locale 单一默认语言
- Locale CRUD
- Translation Status
- Publication Status
- Content Route
- Canonical Route Constraint
- Revision
- Audit Log
- CORS
- Same-Origin / API Base
- Admin 全局 noindex
- Staging Basic Auth + noindex
- Production Secret fail-fast
- `/health/live`
- `/health/ready`
- PostgreSQL integration tests
- Staging smoke test

Phase 3.3 必须建立在现有代码上继续，禁止重写 Phase 3.2 核心认证与发布基础。

---

# 2. Phase 3.3 总体目标

本阶段要正式建立：

## Structured Core

```text
ProductCategory
Product
ProductModel
SpecificationGroup
SpecificationDefinition
ProductSpecValue
Material
Technology
Application
Solution
```

并建立显式业务关系：

```text
Product ↔ Material
Product ↔ Technology
Product ↔ Application
Product ↔ Solution

Material ↔ Technology
Material ↔ Solution

Application ↔ Solution
```

所有实体必须：

- 多语言
- 支持 Publication
- 支持 Content Route
- 支持 Revision
- 支持 Audit
- 支持 RBAC
- 预留 SEO/GEO 接入
- 可通过 Admin 基础页面管理
- 不依赖 Rich Text 作为核心数据源

---

# 3. 本阶段仍然禁止事项

Phase 3.3 禁止：

- 最终首页 UI
- 最终 Product Detail 视觉
- 完整 Page Builder
- Case Study 完整业务
- Knowledge Article 完整业务
- FAQ 完整业务
- RFQ 完整业务
- 搜索引擎生产 Sitemap 全量发布
- 最终 Schema 系统
- 批量导入真实产品内容
- AI 批量写 SEO 文章
- Elasticsearch / OpenSearch
- Kafka
- Kubernetes
- 微服务拆分
- 生产部署

可以做最小 Admin CRUD，但只为验证数据模型和工作流。

---

# 4. ProductCategory

## 4.1 表

### product_categories

字段至少：

- id UUID
- parent_id UUID nullable
- slug
- status / lifecycle flag（不要与 Publication status 重复）
- sort_order
- cover_media_id nullable（可以先预留）
- created_at
- updated_at

### product_category_translations

- id UUID
- category_id
- locale_id
- name
- short_description
- description
- created_at
- updated_at

Unique：

```text
(category_id, locale_id)
```

## 4.2 层级要求

必须支持树状分类：

```text
Products
├── Injection Molding Screws
├── Injection Molding Barrels
├── Injection Molding Components
├── Extrusion Screws & Barrels
├── Twin Screws & Barrels
└── Tie Bars & Nuts
```

要求：

- parent_id self FK
- 禁止 parent=self
- Service 层检测循环
- 分类树查询稳定排序
- 删除存在子分类时默认拒绝
- 已有 Product 引用时默认拒绝物理删除

V1 推荐采用软停用/归档，而不是物理删除。

---

# 5. Product

## 5.1 products

字段至少：

- id UUID
- category_id
- code nullable
- slug
- status（业务可用状态，不等于 publication）
- featured bool
- sort_order
- primary_media_id nullable
- created_at
- updated_at

## 5.2 product_translations

- id
- product_id
- locale_id
- name
- short_description
- description
- highlights_json / highlights_jsonb
- created_at
- updated_at

Unique：

```text
(product_id, locale_id)
```

## 5.3 重要原则

不要把：

- 材料
- 工艺
- 应用
- 问题
- 产品参数

保存成产品正文里的字符串列表。

它们必须通过结构化关系/规格系统连接。

---

# 6. ProductModel

用于：

```text
JH-S1
JH-S25
JH-S30
JH-S50
JH-S65

JH-B35
JH-B50
JH-B60
```

## 6.1 product_models

- id
- product_id
- model_code
- status
- sort_order
- created_at
- updated_at

Unique 推荐：

```text
(product_id, model_code)
```

如果后续确认 JH 型号全站唯一，可另做全局 unique；本阶段优先采用 product-scoped unique，避免过早限制。

## 6.2 product_model_translations

- product_model_id
- locale_id
- name
- description

Unique：

```text
(product_model_id, locale_id)
```

---

# 7. Dynamic Specification System

这是本阶段的重点，必须避免 EAV 失控。

采用：

```text
SpecificationGroup
↓
SpecificationDefinition
↓
ProductSpecValue
```

## 7.1 specification_groups

字段：

- id
- code
- sort_order
- status
- created_at
- updated_at

示例：

```text
dimensions
mechanical-properties
surface-treatment
heat-treatment
processing-range
compatibility
```

## 7.2 specification_group_translations

- group_id
- locale_id
- name

Unique：

```text
(group_id, locale_id)
```

## 7.3 specification_definitions

字段：

- id
- group_id
- code
- value_type
- default_unit nullable
- is_filterable
- sort_order
- status
- created_at
- updated_at

value_type 只允许：

```text
text
number
range
boolean
enum
```

数据库 Check Constraint 或 Enum 必须限制。

## 7.4 specification_definition_translations

- definition_id
- locale_id
- name
- help_text

## 7.5 product_spec_values

字段：

- id
- product_id nullable
- product_model_id nullable
- definition_id
- value_text nullable
- value_number nullable
- value_min nullable
- value_max nullable
- value_boolean nullable
- enum_value nullable
- unit_override nullable
- sort_order
- is_public
- created_at
- updated_at

### 强制业务规则

必须保证：

> product_id 与 product_model_id **恰好一个** 有值。

推荐数据库 Check Constraint：

```text
(product_id IS NOT NULL) <> (product_model_id IS NOT NULL)
```

### Value Type 一致性

Service 层必须检查 value_type 与对应 value 字段一致，不能一条规格同时写多个冲突值字段。

---

# 8. Material

## materials

- id
- slug
- abbreviation nullable
- status
- featured
- sort_order
- created_at
- updated_at

## material_translations

- material_id
- locale_id
- name
- definition
- processing_characteristics
- screw_impact
- recommendations
- limitations

首批真实材料后续会包含 ABS、PP、PA、PA66、LCP、PC、PBT、PVC、PPS、PPA、POM、PEI、PMMA、TPU、TPE、PTFE、BMC、Silicone/LSR、TR90、PLA、PPSU、PEEK 等。

Phase 3.3 只需要少量测试 fixture，不批量正式录入。

---

# 9. Technology

## technologies

- id
- slug
- status
- featured
- sort_order

## technology_translations

- technology_id
- locale_id
- name
- definition
- process_description
- benefits
- limitations

未来包括：

```text
nitriding
chrome-plating
quenching
heat-treatment
tempering
coating
pta-hardfacing
bimetallic-sintering
```

---

# 10. Application

## applications

- id
- slug
- status
- featured
- sort_order

## application_translations

- application_id
- locale_id
- name
- description
- technical_requirements
- common_problems

---

# 11. Solution

## solutions

- id
- slug
- status
- featured
- sort_order

## solution_translations

- solution_id
- locale_id
- name
- definition
- symptoms
- causes
- diagnosis
- solution
- limitations

---

# 12. Explicit Relation Tables

禁止把核心关系全部做成通用 `entity_links`。

本阶段必须使用显式 relation table：

- product_materials
- product_technologies
- product_applications
- product_solutions
- material_technologies
- material_solutions
- application_solutions

所有 relation table：

- FK
- 防重复
- 稳定排序
- 明确 ondelete
- 可选 notes / recommendation_level

---

# 13. Translation Integration

每个 Structured Core 实体必须与现有 `translation_statuses` 配合。

创建 Master Entity 时：

- 不要求所有语言都有翻译
- zh-CN 可以 draft
- en 可以 missing

只有存在：

```text
TranslationStatus
+
Publication
+
Canonical ContentRoute
```

并满足 Phase 3.2 发布规则后，才能公开。

不要直接以 `product.status = active` 作为公开依据。

---

# 14. Publication Integration

Structured Core 公开状态继续由 `content_publications` 负责。

Product / Material / Technology / Application / Solution 必须通过已有统一 Publication service。

业务表可以有业务生命周期状态，但搜索公开状态只有 Publication + Route 决定。

---

# 15. Content Route Integration

公开路径至少支持：

### Product

```text
/{lang}/products/{category-slug}/{product-slug}/
```

### Material

```text
/{lang}/materials/{slug}/
```

### Technology

```text
/{lang}/technologies/{slug}/
```

### Application

```text
/{lang}/applications/{slug}/
```

### Solution

```text
/{lang}/solutions/{slug}/
```

### ProductCategory

```text
/{lang}/products/{category-slug}/
```

路径继续遵循小写、kebab-case、语言前缀、尾 `/`。

---

# 16. Slug 约束

Master entity 的 slug 作为语言无关稳定技术 slug。

例如：

```text
pa66
nitriding
screw-wear
jh-s50
```

所有语言共享 slug。

已发布后默认禁止直接修改 slug；未来修改必须走 Redirect 原子事务。

---

# 17. Revision Integration

每次 Structured Core 内容发生关键修改，应可生成 Revision Snapshot。

Snapshot 至少覆盖：

- Master fields
- Translation fields
- Specifications
- Relations
- Publication-impacting metadata

本阶段不要求最终 Diff UI，但必须有 service 和测试。

---

# 18. Audit Integration

至少记录：

- product.create/update/archive
- product_category.create/update
- product_model.create/update
- specification.update
- material.create/update
- technology.create/update
- application.create/update
- solution.create/update
- relation.change

Audit 不得记录密码、token、secret。

---

# 19. RBAC 扩展

新增 Structured Core 权限，建议：

```text
catalog.read
catalog.create
catalog.update
catalog.archive

specification.read
specification.manage

material.read
material.create
material.update
material.archive

technology.read
technology.create
technology.update
technology.archive

application.read
application.create
application.update
application.archive

solution.read
solution.create
solution.update
solution.archive
```

Publication 继续使用已有 `content.publish`，不要新建另一套发布权限绕开统一发布服务。

角色建议：

- editor：create/update
- content_admin：完整 structured content 管理
- reviewer：review/publish
- seo_manager：read + SEO/GEO
- translator：translation
- sales：无 Catalog 修改
- media_manager：无 Catalog 修改

Seed 必须幂等。

---

# 20. FastAPI Module Organization

建议：

```text
modules/catalog/
├── categories/
├── products/
├── specifications/
├── materials/
├── technologies/
└── applications/

modules/solutions/
```

每个模块：

```text
models.py
schemas.py
service.py
```

Admin API 按模块拆分。

---

# 21. API 范围

Admin Structured Core API 至少支持：

- ProductCategory：list/create/update/tree
- Product：list/detail/create/update/archive
- ProductModel：create/update/archive
- Specification：groups/definitions/values
- Material：list/create/update/archive
- Technology：list/create/update/archive
- Application：list/create/update/archive
- Solution：list/create/update/archive
- Relations：事务化更新

所有写 API 必须：

- Authentication
- RBAC
- CSRF
- Audit

---

# 22. Admin UI 范围

Phase 3.3 只做业务建模验证型 Admin。

允许：

- Product Categories
- Products
- Product Models
- Specifications
- Materials
- Technologies
- Applications
- Solutions

页面要求：

- list
- create
- edit
- basic validation
- zh-CN / en translation tabs
- relation selector
- publication / translation 基础状态显示

不要求最终 UI、批处理、最终编辑器或完整 Dashboard。

---

# 23. Admin Translation UX

明确分离：

```text
Master Data
```

与：

```text
zh-CN Translation
English Translation
```

不同语言不是两个独立实体。

---

# 24. SEO/GEO 接口预留

本阶段不要求完整实现 `seo_documents` / `geo_documents` CRUD。

但 owner_type 至少预留：

```text
product
product_category
material
technology
application
solution
```

避免以后 SEO/GEO 字段重复塞入业务表。

---

# 25. Sitemap / hreflang / canonical 数据源

至少实现统一 service：

```text
list_indexable_routes()
```

仅返回：

- active
- indexable
- canonical
- published
- locale enabled

的 Route。

后续 sitemap / hreflang / canonical 都必须复用同一判断源。

---

# 26. Search Foundation

可启用 PostgreSQL `pg_trgm` 并增加必要索引。

本阶段不引入 Elasticsearch/OpenSearch，也不做完整全文检索。

---

# 27. Seed / Fixture

只提供最小测试 fixture，例如：

- Category：Injection Molding Screws
- Product：JH-S50 Test Product
- Material：PA66、PEEK
- Technology：Nitriding、PTA Hardfacing
- Application：Automotive Components
- Solution：Glass Fiber Abrasion

Fixture 只用于开发测试，不自动成为生产正式内容。

---

# 28. Migration

不要修改已有 migration。

新增 migration，例如：

```text
0004_structured_core
```

必要时拆成：

```text
0004_catalog_core
0005_knowledge_graph_relations
```

要求：

- 空 PostgreSQL 完整升级
- 0001 → latest 测试
- downgrade
- constraints
- relation unique
- specification check

---

# 29. 数据完整性测试

至少覆盖：

## Category

- self parent reject
- circular hierarchy reject

## Product

- category FK
- translation unique

## ProductModel

- duplicate model_code scoped to product reject

## Specification

- product/product_model XOR
- value_type consistency
- invalid range reject
- duplicate definition/value reject

## Relations

- duplicate reject
- delete behavior

## Publication

- human_reviewed gate
- published route active/indexable

## Route

- duplicate path
- canonical uniqueness

## Audit

- write API 会生成 audit

## RBAC

- editor 可编辑不能发布
- reviewer 可发布
- sales 禁止 Catalog 写
- seo_manager 默认不能改业务核心内容

---

# 30. 业务状态命名

避免和 Publication 的 `archived` 混淆。

Structured Core 业务生命周期推荐：

```text
enabled
disabled
retired
```

Publication 继续：

```text
draft
review
scheduled
published
archived
```

---

# 31. Physical Delete Policy

默认禁止物理删除已投入使用的 Product / Material / Technology / Application / Solution / Category。

优先使用：

```text
disabled
retired
```

只有从未发布、无关系、无历史价值的测试数据才允许 hard delete。

---

# 32. Transaction Policy

包含以下内容的写操作应尽量保持一个数据库事务：

```text
Master Entity
+
Translation
+
Relations
+
Revision
+
Audit
```

不允许半成功。

---

# 33. Performance 基线

避免 N+1。

列表 API：

- pagination
- stable sort
- 不默认加载所有 relations/translations

Detail API：

按需要加载 translations/models/specifications/relations。

---

# 34. Security

所有 Admin write：

- Auth
- Permission
- CSRF

Rich Text 本阶段优先不要允许任意 HTML；可先使用 plain text、Markdown 或 structured JSON。

---

# 35. Phase 3.3 测试要求

Backend：

- unit
- PostgreSQL integration
- migration
- seed
- RBAC
- transaction
- publication
- route
- relations
- specification constraints

Frontend/Admin：

- Vitest
- typecheck
- build
- CRUD contract tests

Docker 最终必须 healthy。

---

# 36. Phase 3.3 验收标准

完成后必须：

- [ ] ProductCategory 完成
- [ ] Product 完成
- [ ] ProductModel 完成
- [ ] Specification 系统完成
- [ ] Material 完成
- [ ] Technology 完成
- [ ] Application 完成
- [ ] Solution 完成
- [ ] 显式 relation tables 完成
- [ ] 多语言 translation tables 完成
- [ ] TranslationStatus 集成
- [ ] Publication 集成
- [ ] ContentRoute 集成
- [ ] Revision 集成
- [ ] Audit 集成
- [ ] 新 RBAC 权限完成
- [ ] Admin 基础 CRUD 完成
- [ ] 关系编辑完成
- [ ] Specification 动态类型校验完成
- [ ] Alembic migration 完成
- [ ] PostgreSQL integration tests 全通过
- [ ] Backend tests 全通过
- [ ] Admin/Frontend tests 全通过
- [ ] Typecheck 全通过
- [ ] Production build 全通过
- [ ] Docker Compose healthy
- [ ] 未越界做最终 UI / Page Builder / RFQ
- [ ] `$seo-rank` / `$geo-rank` 冲突检查通过

---

# 37. Codex 完成后必须生成

```text
docs/architecture/phase3-3-completion-report.md
```

报告至少包含：

1. 实际修改目录树
2. 新 migration
3. Structured Core 表
4. Translation 表
5. Relation 表
6. Category Tree 设计
7. Product / ProductModel
8. Specification
9. Material / Technology / Application / Solution
10. Publication Integration
11. Route Integration
12. Revision Integration
13. Audit Integration
14. 新 Permission Matrix
15. Admin 页面
16. API 列表
17. Seed / Fixture
18. 数据完整性约束
19. 测试结果
20. Docker 最终状态
21. 已知问题
22. Phase 3.4 建议
23. `$seo-rank` / `$geo-rank` 冲突检查

---

# 38. Phase 3.4 预期方向

Phase 3.3 通过后，下一阶段才考虑：

> Case Study + Knowledge Article + FAQ + Author/Expert + SEO/GEO Documents + Sitemap/Schema/Redirect 完整化

---

# 39. 执行原则

优先级：

1. Data Integrity
2. Structured Content
3. Transaction Consistency
4. Translation Correctness
5. Publication Correctness
6. Route / SEO Consistency
7. RBAC / Audit
8. Admin Usability
9. Visual Design Last

普通工程细节由 Codex 自主处理。

只有会改变以下冻结项时才向用户提问：

- 主域名
- 核心技术栈
- Structured Core 原则
- Master Entity + Translation 模型
- Publication/Route 事务模型
- SEO/GEO 核心规则

否则继续执行，不频繁中断。
