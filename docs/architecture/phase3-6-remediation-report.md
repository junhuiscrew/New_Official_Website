# Junhui Global Website — Phase 3.6 Remediation Completion Report

报告日期：2026-09-06

项目：`junhuiscrew/New_Official_Website`

正式主域名：`https://junhuiscrewbarrel.com`

交付状态：**实现与本地验收完成，等待用户最终复验；本报告不宣布 Phase 3.6 FINAL PASS。**

## 1. Branch 与提交基线

| 项目 | 实际值 |
| --- | --- |
| 基线分支 | `phase-3.6` |
| 修复分支 | `phase-3.6-fix` |
| 用户指定并核对的 Base SHA | `9af5b286e7f632c8c7124b9f078579e8c1252b3f` |
| 实际 Base SHA | `9af5b286e7f632c8c7124b9f078579e8c1252b3f` |
| Implementation SHA | `ff38bdde5345cb7d6c630748619d8e7d65f14b9a` |
| 远端 | `origin https://github.com/junhuiscrew/New_Official_Website.git` |
| 远端操作 | **未 push、未 merge、未部署** |

本轮从指定基线创建并使用 `phase-3.6-fix`。开始时核对了工作区、远端、分支和基线差异；没有执行 `reset --hard`、强制回退或历史覆盖。基线之后的本地提交均保留。

本轮提交链：

```text
ba36070 fix: complete phase 3.6 remediation
2965ba5 fix: close phase 3.6 remediation QA gaps
5cf977f test: capture bilingual SSR evidence
ff38bdd fix: close phase 3.6 remediation QA gaps
```

## 2. R36-01：首页 SEO / Schema 闭环

状态：**PASS**

- `GET /api/v1/public/home/{locale}` 由真实后端组合首页顶层 `seo` 与 `schema`。
- English 首页 canonical 为 `https://junhuiscrewbarrel.com/en/`；简体中文首页 canonical 为 `https://junhuiscrewbarrel.com/zh-cn/`。
- 中英文首页 SSR 均输出本地化 description、self-canonical、严格可用的 hreflang 与可解析 JSON-LD。
- 首页没有借用 `/about/` canonical。
- WebPage Schema 只在真实已发布 Company 可用时连接 Organization/WebSite；无公司事实时不会制造 Organization、地址、评分、Offer 或专家信息。
- Home 空内容与单语内容保持既定 robots/hreflang 门禁；未知或不可索引 alternate 不被伪造。
- 新增真实上游中断测试：停止 API 后，Nuxt 首次请求返回 500 友好恢复页；没有把 5xx 伪装成空集合或 404；API 随后恢复 200。

主要修改：

- `apps/api/app/modules/discovery/public_collections.py`
- `apps/api/app/modules/discovery/schema_generator.py`
- `apps/api/tests/test_phase36_public_collections.py`
- `apps/website/tests/phase36-homepage.test.ts`
- `scripts/phase36-http-evidence.ps1`
- `scripts/phase36-upstream-5xx-evidence.ps1`

真实 HTTP/SSR 证据：中英文 Home API 和 SSR 均为 200；两种语言均有 description、self-canonical、alternate、JSON-LD、唯一 `main`、唯一 `main-content`、唯一 H1、无重复 ID，skip link 指向 `#main-content`。

## 3. R36-02：首页卡片数据闭环

状态：**PASS**

- Home 与公开列表复用完整 Public Card serializer，未建立第二套卡片字段映射。
- 已发布 Product 卡片返回真实 public-media 主图、公开分类链接与最多四项清洁规格 DTO。
- Product Detail 返回五类规格：`text`、`number`、`range`、`boolean`、`enum`。
- Knowledge 卡片在真实数据存在时返回作者与发布日期。
- Case 保持匿名公开 DTO，不泄露客户真实名称、地址、Logo 或内部 owner 数据。
- public-media 对象经真实 MinIO 和公开媒体代理解码；无媒体、无作者、无日期时保持空值，不伪造素材或当前时间。
- 保留 Translation + Publication + Route + SEO robots 的严格公开门禁，并使用批量查询避免每卡 N+1。

浏览器证据中的代表 Product 图片 `naturalWidth=1`（有效可解码 QA PNG），规格数量为 5；Home API 检测到产品主媒体、四类卡片规格、Knowledge 作者和发布日期。

## 4. R36-03：分页、筛选与错误处理

状态：**PASS**

- 有效 `page=2` 返回 200，并使用 `https://junhuiscrewbarrel.com/en/products/?page=2` 作为 self-canonical。
- 有效临时 `page_size`/组合筛选返回 `noindex, follow`，不输出 hreflang，不进入 Sitemap。
- 不存在筛选、合法但零结果组合、越界分页均返回 404。
- 根集合第一页空态仍可 200 + `noindex, follow`；越界页不会变成 200 空列表。
- `canonical_override` 只有严格等于正式 origin + 当前 route path 才可参与公开路由；非 self-canonical 页面不会进入 Sitemap/hreflang。
- 前端保留 API 404/422/5xx 语义；真实 API 中断显示 500 恢复页，不泄露内部错误。
- 浏览器从 404 筛选/越界页恢复到有效 Product listing 后重新显示 24 张卡片，没有遗留旧筛选状态。

主要修改：

- `apps/api/app/modules/discovery/public_delivery.py`
- `apps/api/app/modules/discovery/public_collections.py`
- `apps/website/app/components/ProductListingView.vue`
- `apps/website/app/components/LocalePlaceholder.vue`
- `apps/website/app/utils/publicRequest.ts`
- Product/Knowledge/Case 列表页面及对应 Vitest/pytest 回归测试

## 5. R36-04：RFQ 多来源贯通

状态：**PASS**

- 前后端统一使用已冻结白名单：`product`、`material`、`technology`、`application`、`solution`、`case_study`、`knowledge_article`、`manufacturing_capability`。
- CTA 只传 `source_type + source_slug`；不会接受客户端 ORM 表名、owner UUID 或内部 source URL。
- 后端按类型重新查询并验证 enabled entity、enabled locale、published translation/publication、canonical active/indexable route、self-canonical 与 robots eligibility。
- 有效来源由服务端持久化 owner type、owner ID 和 canonical source URL；公共响应仍只返回 reference/status 及短期页面内附件 token，不暴露内部字段。
- 参数缺一半、未知类型、未发布/禁用/缺翻译/非 self-canonical 来源稳定返回 422；无来源 RFQ 仍可提交。
- RFQ Origin、Redis rate limit、honeypot、附件 MIME/签名/大小、Malware、private-rfq、signed download 等 Phase 3.5 安全边界未放宽。
- RFQ rate-limit key 新增可配置 namespace；QA 强制使用 `rfq:public:qa36:{run-id}`，不污染普通本地限流状态。

真实浏览器 + 数据库反查确认 Product、Knowledge、Case 三种来源均保存正确；共创建 3 个 QA RFQ，Product 旅程包含 2 个 item 与 1 个真实 private-rfq 附件对象。

## 6. R36-05：完整页面 HTML 结构

状态：**PASS**

- 默认布局保留唯一 `<main id="main-content" tabindex="-1">`。
- Product Detail 等页面根元素不再嵌套 `main`。
- 验收针对 layout + page 的完整 SSR/浏览器 DOM，而不是只检查单组件字符串。
- 中英文首页、Home/Product 的 320–1920 宽度矩阵均满足：一个 `main`、一个 `#main-content`、一个 H1、没有 `main main`、所有非空 ID 唯一。
- skip link 目标存在；移动菜单展开、Products accordion、Product、Gallery、RFQ 链路可操作。

测试宽度：`320, 375, 430, 768, 1024, 1280, 1440, 1920`。Home 与 Product 共 16 个 viewport 样本均为 200，且没有横向溢出。

## 7. QA36：隔离有内容浏览器验收

状态：**PASS（本地 Chromium）；真实 Safari/Lighthouse 见限制项。**

### 7.1 隔离与安全门禁

新增显式 opt-in QA CLI：

```text
python -m app.cli phase36-qa-setup
python -m app.cli phase36-qa-verify --run-id remediation-20260905
python -m app.cli phase36-qa-cleanup --run-id remediation-20260905
```

执行前必须同时满足：

- `APP_ENV` 只能为 `development`/`test`；
- `PHASE36_QA_CONFIRM=LOCAL_QA_ONLY`；
- `PHASE36_QA_ISOLATION=LOCAL_COMPOSE_ONLY`；
- DB/Redis/MinIO 必须解析为本机或 Compose 内部目标；
- `PHASE36_QA_DATABASE_NAME` 必须与实际 URL database 精确相等；
- 桶名必须为既有 `public-media`/`private-rfq`；
- `RFQ_RATE_LIMIT_NAMESPACE` 必须精确为 `rfq:public:qa36:{run-id}`。

普通 Seed、Compose startup 和 production 不会调用 QA fixture。Setup 幂等并能修复中断后的部分数据；Cleanup 只按 manifest 精确删除本次 run 的 DB、Redis key、public-media 与 private-rfq 对象，不清库、不清桶。Cleanup/Verify 输出只含计数和布尔值，不打印 RFQ token、签名 URL、storage key 或 UUID。

本轮实际验证 Cleanup 能删除：3 个 RFQ、1 个 private 对象、43 个内容实体、332 个 lifecycle 记录、6 个规格记录、2 个 public 对象和 2 个专属 Redis key；随后 Setup 重新建立 26 个可分页 Product，最终 Verify 返回 RFQ 来源三类均为 true、附件记录 1、private object exists=true。

### 7.2 正向旅程

使用真实 FastAPI + PostgreSQL + Redis + MinIO + Nuxt SSR + Nginx，以及 Chromium `152.0.7977.82` 完成：

1. Home → Product → RFQ → 两个 Item → 私有附件上传；
2. Search → Knowledge → 关联 Product；
3. English Product → 对应 zh-CN Product，语言、H1、canonical、alternate 同步；
4. 缺少翻译时回退 `/zh-cn/`；
5. Knowledge → RFQ 与匿名 Case → RFQ，后端来源持久化正确；
6. Mobile menu → Products accordion → Listing → Product → Gallery → RFQ；
7. 有效 page 2 → 不存在筛选/零结果/越界 404 → 恢复正常 listing；
8. 320–1920 responsive、DOM landmark、H1、重复 ID、横向溢出检查。

浏览器结果：`consoleErrors=[]`、`pageErrors=[]`；Case 私有客户名称未泄露；附件上传接口和 3 次 RFQ 创建均为 201。网络证据中的 media ID、RFQ reference、token 与 file ID 均已脱敏或不记录。

## 8. 修改文件

相对 Base SHA 的主要文件如下：

```text
.env.example
.gitignore
apps/api/app/cli.py
apps/api/app/core/config/settings.py
apps/api/app/modules/discovery/public_collections.py
apps/api/app/modules/discovery/public_delivery.py
apps/api/app/modules/discovery/schema_generator.py
apps/api/app/modules/rfq/schemas.py
apps/api/app/modules/rfq/services.py
apps/api/app/phase36_qa.py
apps/api/tests/test_phase36_public_collections.py
apps/api/tests/test_phase36_public_dtos.py
apps/api/tests/test_phase36_remediation.py
apps/website/app/components/LocalePlaceholder.vue
apps/website/app/components/ProductCard.vue
apps/website/app/components/ProductListingView.vue
apps/website/app/components/PublicCatalogEntityPage.vue
apps/website/app/components/RfqCta.vue
apps/website/app/composables/useLocalePath.ts
apps/website/app/pages/[lang]/case-studies/index.vue
apps/website/app/pages/[lang]/experts/index.vue
apps/website/app/pages/[lang]/knowledge/index.vue
apps/website/app/pages/[lang]/products/[category]/[slug].vue
apps/website/app/pages/[lang]/products/[category]/index.vue
apps/website/app/pages/[lang]/products/index.vue
apps/website/app/pages/[lang]/request-a-quote/index.vue
apps/website/app/types/public.ts
apps/website/app/utils/publicRequest.ts
apps/website/nuxt.config.ts
apps/website/tests/phase36-content.test.ts
apps/website/tests/phase36-foundation.test.ts
apps/website/tests/phase36-homepage.test.ts
apps/website/tests/phase36-products.test.ts
apps/website/tests/phase36-remediation.test.ts
docker-compose.yml
docs/superpowers/plans/2026-09-05-phase-3-6-remediation.md
docs/testing/phase3-6-remediation-browser-qa.md
scripts/phase36-browser-qa.js
scripts/phase36-http-evidence.ps1
scripts/phase36-upstream-5xx-evidence.ps1
```

没有修改 `apps/api/alembic/versions/0001–0010`，没有新增数据库表或 Homepage 业务模型。

## 9. Tests、Migration、Build 与 Docker

所有结果均来自本轮实际执行；没有沿用 Phase 3.6 旧报告数量。

| 检查 | 实际命令/方式 | 结果 |
| --- | --- | --- |
| Ruff | 主项目 API venv：`python -m ruff check --no-cache apps/api` | **PASS**，`All checks passed!` |
| Full Backend + PostgreSQL/Redis/MinIO | `docker compose --profile test run --rm -v <current-worktree>/apps/api:/app api-test` | **PASS**，先执行 Alembic upgrade + Seed，随后 `241 passed, 1 warning in 84.60s`，无 skip |
| Empty DB → latest | 临时数据库 `qa36_empty_final`，`alembic upgrade head` | **PASS**，`20260905_0010 (head)`；临时库已删除 |
| 0001 → latest | 临时数据库 `qa36_from_0001_final`，先 upgrade `20250830_0001` 再 upgrade head | **PASS**，`20260905_0010 (head)`；临时库已删除 |
| Main DB migration | `docker compose exec -T api alembic current` | **PASS**，`20260905_0010 (head)` |
| Seed idempotency | `docker compose exec -T api python -m app.cli seed` 连续两次 | **PASS**，两次均 `Phase 3.2 system seed completed.` |
| Website Vitest | `pnpm --filter @junhui/website test` | **PASS**，11 files，`118 passed` |
| Admin Vitest | `pnpm --filter @junhui/admin test` | **PASS**，6 files，`23 passed` |
| Typecheck | `pnpm typecheck` | **PASS**，Website/Admin `nuxt typecheck` exit 0 |
| Prettier | `pnpm format:check` | **PASS**，`All matched files use Prettier code style!` |
| Production Build | `pnpm build` | **PASS**，Website/Admin 均 `Build complete!`，exit 0 |
| Browser QA | `node scripts/phase36-browser-qa.js`（配置本机 Playwright Chromium） | **PASS**，Chromium `152.0.7977.82`，上述正向旅程全部完成 |
| HTTP/SSR evidence | `powershell -File scripts/phase36-http-evidence.ps1` | **PASS**，双语 API/SSR、分页、门禁、DOM 全部断言通过 |
| Real upstream 5xx | `powershell -File scripts/phase36-upstream-5xx-evidence.ps1` | **PASS**，500 友好恢复、无内部错误泄露、API 恢复 200 |
| Compose health | `docker compose ps` | **PASS**，10 个常驻服务均 running/healthy |
| API live/ready | API 容器内请求 `/api/v1/health/live` 与 `/api/v1/health/ready` | **PASS**，均为 200 |
| Website/Admin HTTP | `http://localhost:3000/`、`http://localhost:3001/` | **PASS**，均为 200 |

唯一 pytest warning 为 Starlette TestClient 使用 AnyIO `BlockingPortal` alias 的依赖级 deprecation。Nuxt 构建另有 Rolldown plugin timing 提示以及 Admin Nitro 的 Node `DEP0155` 依赖级 deprecation；均未造成失败。

一次尝试在 `api-test` image 内执行 Ruff 返回 `No module named ruff`，因此该次记录为 **NOT RUN（容器不含 Ruff）**；随后已用项目 API venv 成功执行 Ruff，最终 Ruff 结果为 PASS。

## 10. 脱敏证据

本地证据目录（由 `.gitignore` 排除，不随 Git 提交）：

```text
artifacts/phase3-6-remediation/browser-qa.json
artifacts/phase3-6-remediation/http-ssr-evidence.json
artifacts/phase3-6-remediation/upstream-5xx-evidence.json
artifacts/phase3-6-remediation/home-desktop.png
artifacts/phase3-6-remediation/product-mobile.png
artifacts/phase3-6-remediation/rfq-submitted.png
```

JSON 中的 media/file 标识已替换为 `[REDACTED]`；没有保存凭据、RFQ submission token、私有 signed URL、数据库导出或客户隐私数据。

## 11. SEO / GEO 冲突检查

状态：**未发现与 `$seo-rank` / `$geo-rank` 核心原则冲突。**

- canonical、hreflang、robots、Sitemap eligibility 继续由后端统一 Publication/Route/SEO 决策生成，Vue 不建立第二套规则。
- 有效分页 self-canonical；临时筛选 noindex 且不进入 Sitemap/hreflang；不存在与零结果页面返回 404。
- Home、Product、Knowledge、Case 的 Schema/SEO/GEO 只使用用户可见且已发布数据；不生成假价格、Offer、Review、Rating、Author、Company facts。
- Product 规格、Knowledge 作者/日期、GEO visible source、关系链接均来自公开 DTO；不存在 AI-only 隐藏事实。
- Case privacy allowlist、public-media/private-rfq 隔离、RFQ 来源服务端验证均保持不变。
- 本轮实现改善可发现性、可抽取性与索引一致性，但不保证搜索排名、Rich Result 或 AI 引用。

## 12. 限制与已知问题

1. **Lighthouse：NOT RUN。** 当前验收重点为有内容 Chromium 旅程、SSR/DOM、真实 API/DB/MinIO 与 responsive matrix；没有把缺失的 Lighthouse 分数填写为 PASS。
2. **真实 Safari/WebKit：BLOCKED。** 当前 Windows 环境没有真实 Safari；本轮浏览器验收使用 Chromium `152.0.7977.82`。上线前仍需在真实 Apple/WebKit 环境复核。
3. QA fixture 是本地隔离、显式 opt-in 的测试数据，不是正式内容，不可导入 production。
4. 浏览器截图和 JSON 证据因可能包含本地 QA 表单状态而只保存在 ignored artifact 目录；如需共享，应再次人工脱敏后单独交付。
5. Starlette/AnyIO、Nuxt/Rolldown 与 Node `DEP0155` warning 为依赖级提示，当前不阻断运行，后续依赖维护时处理。

## 13. 结论与等待复验

R36-01、R36-02、R36-03、R36-04、R36-05 与 QA36 已按交接文档完成本地实现和验收。当前分支保持 `phase-3.6-fix`，Implementation SHA 为 `ff38bdde5345cb7d6c630748619d8e7d65f14b9a`；未 push、未 merge、未部署，也没有进入 Phase 3.7。

本报告只提交可复验事实。Phase 3.6 是否 FINAL PASS 由用户后续验收决定。
