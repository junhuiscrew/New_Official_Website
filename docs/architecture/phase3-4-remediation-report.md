# Phase 3.4 Remediation Completion Report

## 1. Branch 与 SHA

- Repository: `junhuiscrew/New_Official_Website`
- Branch: `phase-3.4-fix`
- Base branch: `origin/phase-3.4`
- Base SHA: `99030906e428aa4d0ef33ba2b3a8900ab2cc800c`
- Final implementation SHA: `d6bb75664dc30fc9026e79569471b3594fa33326`
- Official origin: `https://junhuiscrewbarrel.com`
- Scope: 仅完成 Phase 3.4 Remediation 的 5 项修复，没有进入 Phase 3.5。

## 2. 五项修复结果

### 2.1 GEO 服务端可见事实

- 从 `GeoDocumentUpsert` 删除 `visible_source_text`，并设置 `extra="forbid"`，客户端不能再提交或伪造该字段。
- 新增 `build_visible_source_text(session, owner_type, owner_id, locale_id)`，只从数据库真实内容聚合 Product、Case、Knowledge、Expert 可见事实。
- Product 事实来自名称、简述、正文、亮点、公开规格和已发布 FAQ。
- Case 事实来自公开翻译、页面结构化字段和已发布 FAQ；客户名称、地址和 Logo 仅在对应公开许可为 true 时进入事实池。
- Knowledge 事实来自标题、摘要、Markdown 正文、已发布 FAQ 和公开 Source Citation。
- Expert 事实来自姓名、职位、简介、专业领域与公开从业年限。
- `upsert_geo_document()` 在服务端聚合事实后执行 direct answer、key facts、evidence 逐项校验。
- 新增权限保护的只读预览：`GET /api/v1/discovery/geo-visible-source/{owner_type}/{owner_id}/{locale_id}`。
- Admin GEO 编辑器移除可编辑正文输入，只显示服务端只读预览。

### 2.2 canonical_override、Sitemap 与 hreflang

- `list_indexable_routes()` 仅保留无 override 或 override 等于 `https://junhuiscrewbarrel.com{route.path}` 的 self-canonical 页面。
- `_published_alternates()` 使用相同 self-canonical 条件，非 self-canonical 页面不会进入 hreflang。
- Public relation Link DTO 同样排除非 self-canonical 目标。
- SEO Health 新增 `canonical_override_excludes_sitemap`。
- Sitemap 继续复用统一 `list_indexable_routes()`，没有建立第二套索引逻辑。

### 2.3 Author / Expert 公开交付

- 保留 `author_expert` 为索引源，并补齐：
  - `GET /api/v1/public/experts/{locale_slug}/{slug}`
  - Nuxt SSR `/{lang}/experts/{slug}/`
  - Person Schema 与 Breadcrumb Schema
  - SEO、GEO、hreflang、已发布 authored Knowledge Link DTO
- 公开门槛要求实体 enabled、真实人物已核验、公开资料开关启用、Locale enabled、Translation published、Publication published、canonical、active、indexable、SEO robots_index。
- 为保证 Sitemap 与 Public Handler 全类型一致，同时补齐 ProductCategory、Material、Technology、Application、Solution 的最小 Public DTO/API/SSR handler；未扩展其业务 CRUD。

### 2.4 Structured Relations Link DTO

- Product、Case、Knowledge 的关系从 UUID 列表升级为统一 Link DTO：

```json
{
  "type": "material",
  "slug": "nitrided-steel",
  "name": "Nitrided steel",
  "url": "/en/materials/nitrided-steel/",
  "summary": "Wear-resistant material"
}
```

- 目标必须满足完整公开门槛且为 self-canonical；draft、disabled、retired、missing translation、noindex、inactive 和非 self-canonical 目标都会被过滤。
- Product、Case、Knowledge、Expert SSR 通过 `PublicRelationLinks.vue` 输出真实 `<a href>` 内部链接。
- SEO Health 新增 `missing_internal_links`、`broken_relation_target`、`indexable_route_missing_public_handler`。

### 2.5 Redirect 目标域

- Redirect source 允许：
  - `junhuiscrewbarrel.com`
  - `www.junhuiscrewbarrel.com`
  - `junhuiscrew.com`
  - `www.junhuiscrew.com`
- Redirect target 只允许 HTTPS `junhuiscrewbarrel.com`。
- www 正式域、旧域及其 www 形式作为 target 均返回 `unsafe_redirect_target`。
- self、loop、chain、duplicate 与 unsafe target 检测继续保留。

## 3. API 与 SSR 交付

新增或补齐的公开接口：

- `/api/v1/public/experts/{locale_slug}/{slug}`
- `/api/v1/public/product-categories/{locale_slug}/{slug}`
- `/api/v1/public/{resource}/{locale_slug}/{slug}`，其中 resource 仅允许 materials、technologies、applications、solutions
- `/api/v1/discovery/geo-visible-source/{owner_type}/{owner_id}/{locale_id}`

新增 SSR 页面：

- `/{lang}/experts/{slug}/`
- `/{lang}/products/{category}/`（ProductCategory）
- `/{lang}/materials/{slug}/`
- `/{lang}/technologies/{slug}/`
- `/{lang}/applications/{slug}/`
- `/{lang}/solutions/{slug}/`

现有 Product、Case、Knowledge SSR 页面已增加真实关系链接；Product 亮点及 Case 公开结构化事实也已明确渲染，保证 GEO 事实不是 AI-only 隐藏内容。

## 4. SEO / GEO Health Checks

本轮增加或冻结的稳定问题代码：

- SEO：
  - `canonical_override_excludes_sitemap`
  - `indexable_route_missing_public_handler`
  - `missing_internal_links`
  - `broken_relation_target`
- GEO：
  - `claim_not_in_server_visible_content`
  - `reviewer_missing_or_unverified`
  - `first_party_evidence_missing`

Health API 会使用服务端事实重新验证现有 GEO 文档，并核验 reviewer 是否为真实人物。

## 5. Migration

- 没有新增数据库结构。
- 未修改 `0001` 至 `0007` 历史 migration。
- Empty DB → latest 已在 PostgreSQL 17.6 容器中成功执行。
- `20260904_0001` → `20260904_0007` 已在清洁 PostgreSQL 容器中成功执行。
- 连续执行两次 `python -m app.cli seed` 均成功，Seed 保持幂等。

## 6. Regression Tests

新增和扩展覆盖：

- 客户端不能提交 `visible_source_text`。
- Product、Case、Knowledge、Expert 服务端可见事实聚合。
- 私密客户名称不进入 GEO 事实池，相关声明不能通过。
- 非 self-canonical 页面不进入 Sitemap 与 hreflang。
- Sitemap owner type 与 Public Handler owner type 完全一致。
- Expert Public DTO、Person Schema 与已发布 Knowledge links。
- Product relation canonical Link DTO，并过滤 draft target。
- www/旧域不能作为 Redirect target，仍可作为 source。
- SEO/GEO remediation issue codes。
- Website Expert SSR、全部 Sitemap 页面族和真实 `<a>` 关系链接。
- Admin GEO 服务端只读事实预览。

## 7. 实际测试结果

| 验证项 | 结果 |
| --- | --- |
| Ruff | `All checks passed` |
| Backend pytest（本机 SQLite/contract） | `154 passed, 7 skipped`；7 项仅因要求 PostgreSQL profile 而跳过 |
| PostgreSQL integration + 全部 backend tests | `161 passed` |
| Empty DB → latest | 通过，依次执行 `0001` 至 `0007` |
| 0001 → latest | 通过 |
| Seed idempotency | 通过，连续执行两次 |
| Website Vitest | `11 passed` |
| Admin Vitest | `18 passed` |
| Website/Admin Typecheck | 通过 |
| Prettier | `All matched files use Prettier code style` |
| Website Production Build | 通过 |
| Admin Production Build | 通过 |
| Docker image build | API、Website、Admin 均通过 |

测试过程中出现的 Starlette `BlockingPortal` deprecation warning 与 Node package trailing-slash deprecation warning 不影响测试或构建结果。

## 8. Docker Compose 状态

按当前源码实际执行 `docker compose up -d --build`。最终持久服务状态：

- PostgreSQL 17.6: healthy
- Redis 8.2: healthy
- MinIO: healthy
- FastAPI: healthy，host `http://localhost:8010`
- Website: healthy，host `http://localhost:3000`
- Admin: healthy，host `http://localhost:3001`
- Nginx: healthy，host `http://localhost:8080`
- MinIO init: 一次性任务成功退出

HTTP 实测：

- `/api/v1/health/ready`: 200，PostgreSQL ready，Redis ready
- Website `/zh-cn/`: 200
- Admin `/`: 200
- `/sitemap.xml`: 200
- OpenAPI 已注册 Expert、GEO visible source preview 与 Catalog public route。

## 9. 已知问题

- Nuxt build 的依赖树仍输出 Node package trailing-slash mapping deprecation warning；本轮未升级依赖，避免超出 remediation 范围。
- Starlette TestClient 输出 AnyIO `BlockingPortal` alias deprecation warning；当前固定版本测试全部通过，建议在后续常规依赖维护窗口处理。
- 当前开发库没有批量真实内容，因此 Sitemap 只输出满足严格发布门槛的已有数据；这是预期行为。
- 代码知识图谱在本轮刷新时因索引器内部文件异常退出，因此代码发现回退为精确仓库检索；不影响应用构建、运行和测试。

## 10. `$seo-rank` / `$geo-rank` 冲突检查

- 已使用 `$seo-rank` 检查 canonical、hreflang、Sitemap、robots_index、内部链接与结构化数据一致性。
- 已使用 `$geo-rank` 检查用户可见答案、事实证据、真实人物、可引用来源和服务端内容一致性。
- 通用 Skill 与正式交接文件没有产生需要改变冻结架构的冲突。
- 本项目约束继续优先：统一 Publication / ContentRoute / Translation 体系、正式非 www 主域、严格索引门槛、Case 隐私白名单、无虚构人物/价格/评价、GEO 不允许 AI-only 隐藏事实。

## 11. Phase 3.5 建议（未实施）

- 在 Phase 3.5 正式交接文件确认后，再开始 Company Trust Content、Equipment、Certificates、Patents、Honors、Media Library 或 Downloads。
- 复用本轮统一 Public Link DTO 和严格索引门槛，不建立第二套路由、发布、翻译或 Sitemap 系统。
- 为后续真实内容录入建立许可证据、来源复核和 stale review 运营流程。
- 本轮没有实现 RFQ、Final Homepage、Final Design System、Page Builder 或 Production Deployment。
