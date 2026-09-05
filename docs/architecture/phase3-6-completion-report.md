# Phase 3.6 Completion Report

## 1. 交付标识与结论

- 项目：`junhuiscrew/New_Official_Website`
- Branch / 分支：`phase-3.6`
- 基线分支：`phase-3.5-final-patch-v3`
- Base SHA：`6e696a0e91f0a3d9974269d6bb41ef35ed7963e9`
- Final implementation SHA：`a1ed84b3d3826c592871b0d4d06902bdcc5356ea`
- Task 12 UI/浏览器修正 SHA：`b3e1778f68b4e8f4e05a7a8d81ee4a69ced74322`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 验收结论：Phase 3.6 工程范围通过。Lighthouse 与真实内容填充后的 Core Web Vitals 尚未量化，相关边界见第 12 节。
- 本报告在实现提交后单独提交；报告提交 SHA 由 Git 提交记录标识，不在文件内自引用。

本阶段没有 push、merge、production deployment、Search Console 提交、Analytics 启用或 Phase 3.7 实施。

## 2. 架构与 Migration 0010

Phase 3.6 保持 Master Entity + Translation + Publication + ContentRoute + Revision + Audit + RBAC 的既有架构，没有建立第二套 CMS 生命周期、Homepage 数据模型或前端 Schema 生成器。

新增迁移 `20260905_0010`：

- `down_revision` 为 `20260904_0009`，迁移链保持单一线性 head；
- PostgreSQL 安装或复用 `pg_trgm`；
- 为 Product、Material、Application、Solution 的 `name`，以及 Knowledge Article、Case Study 的 `title` 建立六个 `GIN ... gin_trgm_ops` 索引；
- downgrade 只删除本迁移的六个命名索引，不删除可能被其他模块复用的扩展；
- SQLite 单元迁移路径显式跳过 PostgreSQL 专属扩展和操作符类。

实际验证：

- 运行中 API 数据库的 `alembic current` 与代码的 `alembic heads` 均为 `20260905_0010 (head)`；
- 在 `postgres-test` 中创建临时空数据库，从空库依次执行 0001–0010，最终 current 为 `20260905_0010 (head)`；
- 在第二个临时 PostgreSQL 数据库先执行 `20260904_0001`，再执行 `upgrade head`，最终 current 同样为 `20260905_0010 (head)`；
- 两个临时数据库验证后精确删除；没有删除或重建任何 Docker volume。

上述两条隔离迁移路径使用以下完整命令执行；创建和删除命令均返回 `CREATE DATABASE` / `DROP DATABASE`：

```powershell
docker compose exec -T postgres-test psql -U junhui_test -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE junhui_task13_empty_20260905;"
docker compose --profile test run --rm -e DATABASE_URL=postgresql+asyncpg://junhui_test:junhui-test-only@postgres-test:5432/junhui_task13_empty_20260905 api-test sh -c "alembic upgrade head && alembic current"
docker compose exec -T postgres-test psql -U junhui_test -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE junhui_task13_empty_20260905;"
docker compose exec -T postgres-test psql -U junhui_test -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE junhui_task13_from0001_20260905;"
docker compose --profile test run --rm -e DATABASE_URL=postgresql+asyncpg://junhui_test:junhui-test-only@postgres-test:5432/junhui_task13_from0001_20260905 api-test sh -c "alembic upgrade 20260904_0001 && alembic current && alembic upgrade head && alembic current"
docker compose exec -T postgres-test psql -U junhui_test -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE junhui_task13_from0001_20260905;"
```

## 3. Public API、DTO 与数据边界

### 3.1 聚合、列表与搜索

- `GET /api/v1/public/navigation/{locale}` 为 Desktop/Mobile Navigation 与 Footer 提供发布态数据。
- `GET /api/v1/public/home/{locale}` 聚合 Company、产品分类、精选产品、Material、Solution、Capability、Application、Case、Knowledge 与 Trust 摘要，避免首页逐区块串行请求。
- 公共列表使用统一分页 envelope、稳定排序和 Category/Material/Application 等白名单筛选。
- 搜索只覆盖 Product、Material、Application、Solution、Knowledge Article 与 Case Study；PostgreSQL 使用加权 FTS，并以标题 trigram 作为拼写容错后备。
- Navigation/Home 的短公开缓存与其他敏感接口隔离；RFQ、Auth、Private File 和 presigned URL 不进入公开缓存。

### 3.2 Public Product DTO

产品规格统一输出 `name`、`value`、`unit`、`group`、`type`，覆盖 `text`、`number`、`range`、`boolean`、`enum`。Product Card 最多显示四项公开规格；详情页使用 `SpecTable`，不显示 raw ORM、`<pre>` 或原始 JSON。

Public DTO 使用显式 allowlist。自动化回归覆盖：

- 不返回内部 UUID、owner ID、时间戳、storage key/path、private bucket 或 RFQ 内部字段；
- 只返回 enabled entity、enabled locale、published translation/publication、canonical + active + indexable route，并尊重 `robots_index` 与 canonical override；
- Product/Knowledge/Case/Catalog/Trust 的关系输出 canonical Link DTO；
- Public Media 经 `/api/v1/public/media/{id}` 代理，公开图片要求可用 alt；
- Case 只输出已获授权的客户身份字段，未授权名称、Logo、地址和身份不会进入 DTO、SEO、GEO 或 Schema。

## 4. 最终 UI、导航与 Footer

公开站使用 Blue/White、Deep Navy、Brand Green、Neutral Gray 与状态色的 Design Tokens；Typography、4/8 spacing、约 1280px 内容宽度、克制圆角/阴影、focus ring 与 reduced-motion 均在统一 CSS 层定义。没有新增大型 UI Framework、远程阻塞字体、WebGL、重型视差或轮播 Hero。

Desktop Header 的一级顺序为 Products、Solutions、Materials、Applications、Capabilities、Case Studies、Knowledge、About，右侧提供 Search、Language 与 Request a Quote。Products/Solutions 使用已发布数据驱动 Mega Menu；Material/Application 只展示精选发布项。

Mobile Nav 使用 hamburger + accordion，包含 Search、Language 与 RFQ CTA；具备 `aria-expanded`、可见焦点、Escape 关闭、焦点回收和 body scroll lock。Footer 条件显示 Company、Products、Solutions、Knowledge、Contact、Legal 与 Language；公司联系方式只来自公开 Company DTO。

## 5. Homepage

Homepage 通过一次 SSR 聚合请求组合：

1. 单 H1 Hero、Request a Quote 与 Explore Products；
2. Product Categories；
3. Trust Strip；
4. Material / Problem 入口；
5. Manufacturing Capabilities；
6. Featured Products；
7. Applications；
8. Case Studies；
9. Technical Knowledge；
10. Trust summary；
11. RFQ CTA。

所有业务区块按发布数据条件渲染；无真实数据时隐藏区块，不制造年份、数量、证书、规格或工厂事实。当前本地 seed 只有系统数据，没有发布 Company/Product 内容，因此浏览器实测首页显示通用 RFQ 恢复路径，而不是虚构工业业务文案或图片。

## 6. 页面族验收

| 页面族 | 最终实现与验证边界 |
| --- | --- |
| Product Listing | Category/Material/Application 白名单筛选、分页、Product Card、公开媒体、最多四项规格、详情与 RFQ 链接；Vitest 与 API 回归覆盖。 |
| Product Detail | Breadcrumb、Gallery、Specifications、Models、Description、Material/Technology/Application/Solution、Capability/Trust、Case、FAQ、Knowledge 与 RFQ；关系仅使用 published canonical Link DTO。 |
| Material | Overview、processing characteristics、common problems、Product/Technology/Application/Solution/Knowledge relations 与 RFQ。 |
| Technology | Explanation、when to use、capability/equipment evidence、Product/Material/Case/Knowledge relations 与 RFQ。 |
| Application | Processing challenges 与 Product/Material/Technology/Solution/Case/Knowledge relations。 |
| Solution | Problem、cause、inspection、recommended approach 与 Material/Technology/Case/Knowledge relations。 |
| Knowledge Center | Category、分页、摘要、Author/Reviewer 与发布日期；定位为技术资料库。 |
| Knowledge Article | Breadcrumb、Summary/Direct Answer、Author/Reviewer、发布日期/复核日期、Body、Key Facts、FAQ、Sources、Relations 与 RFQ。 |
| Case Study | Industry/Country、Problem、Analysis、Solution、Result、Engineer Comment、公开关系与隐私 allowlist。 |
| About | Company Overview、History、Factory Facts、Capabilities、Quality、Equipment、Certificates、Patents、Honors、Exhibitions、Gallery 与 Contact CTA；无 Company 数据时返回标准 404。 |
| Capabilities | Index/detail、公开 Equipment、Technology、Media、Product/Case 与 RFQ。 |
| Certificates / Patents / Honors | 真实发布数据的聚合页；不创建独立详情 URL。 |
| Exhibitions | Index/detail 与已发布媒体/内容。 |
| Downloads | Title、resource type、summary、version、date、size/type 与 Download CTA；后端过滤 missing/broken objects。 |
| RFQ | Contact、Inquiry Items、Attachments、Privacy 四区；多 Item、Add/Remove、文件限制提示、上传状态、成功 reference 与 source context。 |
| Search | `/{lang}/search/?q=`，六类公开内容、按类型分组、查询词保留、无结果恢复入口，并保持 `noindex, follow`。 |
| Language | 简体中文/English；优先 alternate，同内容缺少目标翻译时回退目标语言首页。 |
| 404/500 | 404 提供 Products、Knowledge、Search、RFQ 恢复入口；错误页不暴露堆栈或内部路径。 |

当前本地数据库没有已发布业务实体，因此浏览器无法从真实列表进入 Product/Knowledge/Case/Capability/Exhibition 详情。详情模板、DTO-fed rendering、关系、元数据、隐私和空态由 Website 104 项与 API 218 项自动化测试覆盖；本报告不把未发生的真实内容旅程描述为浏览器实测。

## 7. SEO / GEO 可见 UI

- Nuxt 页面使用 SSR `useAsyncData`；核心正文与公共导航进入服务端 HTML，不依赖 mounted 后再取正文。
- canonical、hreflang、robots、Breadcrumb 与 JSON-LD 使用后端返回数据；前端只安全序列化，不重建第二套索引或 Schema 判断。
- indexable 详情保持唯一 H1 和逻辑标题层级；Search 为 `noindex, follow`，Admin 响应为 `X-Robots-Tag: noindex, nofollow`。
- Breadcrumb 可见 UI 与 Breadcrumb Schema 使用同一后端数据源。
- GEO Direct Answer、Key Facts、Evidence、FAQ、Author/Reviewer 与 Source Citation 都是可见组件；没有真实内容时不渲染对应事实块。
- FAQ Schema、Article/Product/Organization/Person 等结构化数据只使用可见且已发布事实，不制造 rating、review、price、credential 或客户身份。
- 正式 canonical origin 保持 `https://junhuiscrewbarrel.com`，语言切换不使用 IP 强制跳转。

这些实现改善可发现性、可抽取性与实体一致性，但不构成搜索排名、富结果、AI 引用或推荐保证。

## 8. Media、Responsive、Accessibility 与 Performance

### 8.1 Media

`PublicImage`、`PublicVideo` 与 `MediaGallery` 统一处理固有尺寸、responsive sizes、alt/caption、fallback、poster/controls 与 loading。Hero 图使用 eager/preload；below-fold 图片使用 lazy。Gallery 使用 dialog 语义、键盘操作、Escape 与焦点回收。不存在的 WebP/AVIF 转换资源不会被伪造。

### 8.2 Responsive 与浏览器复核

在 production-like Nginx URL `http://localhost:8080/en/` 实测 320、375、430、768、1024、1280、1440、1920 八个宽度：首页每个宽度均为 `scrollWidth == clientWidth`，且 `h1Count == 1`。

在 320px 实测 Mobile Nav：

- 打开后 `aria-expanded=true`、按钮 label 为 `Close menu`、`body.style.overflow=hidden`；
- 按 Escape 后 `aria-expanded=false`、body scroll lock 清除，焦点回到 label 为 `Menu` 的 toggle。

在 1280px 实测 Home、Product/Material/Technology/Application/Solution/Knowledge/Case 列表、About、Capability、Certificates、Patents、Honors、Exhibitions、Downloads、RFQ、Search 与 404 共 18 条路径；每条都只有一个 H1 且无横向溢出。除缺少发布 Company 数据的 About 与故意访问的不存在 URL 返回 404 外，其余列表/功能入口返回 200。

Language Switch 实际从 `/en/` 到 `/zh-cn/`，目标页面 `html lang=zh-CN`、一个 H1、console 0 error/0 warning。Homepage 在 320 与 1920 检查时均无 `undefined`/`null` 可见文本；1920 检查破图计数为 0。

Task 12 的 `b3e1778` 包含 responsive、language、honeypot accessibility、security headers 等修正和回归测试。其遗留 console 文件只记录 About 数据缺失 404 与故意访问 404，不能独立证明整套浏览器矩阵；因此 Task 13 重新执行了上述可量化复核。

### 8.3 Accessibility

实现和测试覆盖 semantic `header/nav/main/article/section/footer`、skip link、button/anchor 语义、表单 label、错误摘要/字段错误、`role=status/alert`、focus-visible、`aria-expanded`、alt、Escape、focus return、scroll lock、honeypot 脱离 accessibility tree 与 keyboard order，以及 `prefers-reduced-motion`。

这些是基础 WCAG AA 工程检查，不等同于由人工辅助技术用户完成的正式 WCAG conformance audit。

### 8.4 Performance

- `pnpm build` 的 Website 与 Admin SSR/Nitro production build 均成功。
- 本地 Website 最大 client JS chunk 为 132.50 kB raw / 50.70 kB gzip，Nitro 输出合计 2.73 MB / 712 kB gzip。
- 本地 Admin 最大 client JS chunk 为 92.45 kB raw / 33.13 kB gzip，Nitro 输出合计 2.33 MB / 594 kB gzip。
- 构建保留 SSR，Hero eager/preload、below-fold lazy 与图片固有尺寸用于降低 LCP/CLS 风险。

本机工作区没有 Lighthouse 可执行文件；未安装新工具，也未生成 Mobile/Desktop Lighthouse 报告。因此 Performance、Accessibility、Best Practices、SEO 分数以及 LCP、CLS、INP 没有实测值，不能声明达到设计目标阈值。真实内容与真实媒体进入 staging 后必须重新测量。

## 9. Privacy 与 Security

API 与 Website/Admin 回归覆盖以下边界：

- RFQ 公共响应只返回 reference/status；source slug 由服务端重新验证，不接受客户端内部 source 字段；
- private RFQ bucket、storage path、内部 UUID、assigned user、malware details 与 signed download 不进入公共 DTO；
- 私有下载继续要求认证、权限、所属关系、clean malware 状态和短时签名；
- RFQ 保留 same-origin Origin/Referer、Redis 限流、honeypot、隐私同意与附件扩展名/MIME/文件头/大小检查；
- PostgreSQL 关系约束阻止 RFQ Item/File 跨父对象引用；
- Case 客户身份继续由显式 privacy allowlist 控制；
- Public Search 只索引已发布、可索引内容，并隔离 unpublished、Admin、RFQ 和 private files；
- JSON-LD 使用安全序列化，visible content 与 Schema 数据源一致。

Nginx 实际 200 响应包含：

- `Content-Security-Policy`；
- `X-Content-Type-Options: nosniff`；
- `Referrer-Policy: strict-origin-when-cross-origin`；
- `X-Frame-Options: DENY`；
- `Permissions-Policy: camera=(), geolocation=(), microphone=()`。

本地 HTTP 不启用 HSTS；HSTS 应只在真实 HTTPS production/staging 边界验证后配置。

## 10. Tests / 精确测试与 Build 结果

以下均针对 Final implementation SHA `a1ed84b3d3826c592871b0d4d06902bdcc5356ea` 对应实现执行；测试修复只改变 PostgreSQL 搜索集成测试的唯一查询词，不改变生产搜索逻辑。

| 命令 | 结果 |
| --- | --- |
| `D:\Python_Project\New_Official_Website\junhui-global-website\apps\api\.venv\Scripts\python.exe -m ruff check --no-cache apps/api` | PASS，`All checks passed!`。从仓库根目录执行；隔离工作树没有本地 `.venv`，实际复用主检出同项目 venv；`--no-cache` 避免既有 cache ACL。 |
| `D:\Python_Project\New_Official_Website\junhui-global-website\apps\api\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=D:\Python_Project\New_Official_Website\junhui-global-website\.worktrees\phase-3.6\.pytest-tmp-task13-final`（工作目录 `apps/api`） | PASS，最终全量复跑为 `208 passed, 10 skipped, 1 warning in 85.63s`；此前同一全量验收为 `208 passed, 10 skipped, 1 warning in 151.28s`。10 个 skip 为 Docker profile 承担的 2 个 Redis/MinIO 与 8 个 PostgreSQL integration 项。 |
| `docker compose --profile test run --rm --build api-test`（修复前） | `217 passed, 1 failed`；失败为持久化 test volume 上历史搜索测试数据触发合法 trigram 模糊命中。 |
| `docker compose --profile test run --rm api-test pytest -q -p no:cacheprovider --basetemp=/tmp/junhui-pytest tests/test_postgresql_integration.py::test_postgresql_public_search_prefers_title_and_has_trigram_indexes` | PASS，最终复跑 `1 passed in 1.78s`；修复后首次 focused 回归为 `1 passed in 1.48s`。 |
| `docker compose --profile test run --rm --build api-test`（最终） | PASS，`218 passed, 1 warning in 74.79s`，无 skip。真实 PostgreSQL、Redis、MinIO、search、security、privacy、publication 与 migration suites 全部执行。 |
| `docker compose exec -T api python -m app.cli seed`（第 1 次） | PASS，exit 0，`Phase 3.2 system seed completed.` |
| 同一 seed 命令（第 2 次） | PASS，exit 0，同一完成输出；验证幂等。 |
| `pnpm --filter @junhui/website test` | PASS，10 files，`104 passed (104)`。 |
| `pnpm --filter @junhui/admin test` | PASS，6 files，`23 passed (23)`。 |
| `pnpm --filter @junhui/website typecheck` | PASS，exit 0。 |
| `pnpm --filter @junhui/admin typecheck` | PASS，exit 0。 |
| `pnpm exec prettier --check .` | PASS，`All matched files use Prettier code style!`。 |
| `pnpm build` | PASS，Website 与 Admin 均输出 `Build complete!`。 |
| `docker compose up -d --build` | PASS，API/Worker/Website/Admin images 构建成功，完整栈启动。 |

唯一 pytest warning 为 Starlette TestClient 对 `anyio.abc.BlockingPortal` alias 的依赖级 deprecation。Nuxt/Rolldown 报告 plugin hook timing 提示；本地 Admin Nitro 构建另有 Node `DEP0155`（依赖 exports trailing slash）deprecation。三者均未导致测试或构建失败。

本地 sandbox 首次 Ruff/pytest/typecheck/Prettier 调用分别遇到既有 cache、SQLite temp、`.nuxt` 或 pnpm store 的 ACL/EPERM；在确认根因后使用 no-cache 或相同命令的沙箱外执行完成验收。没有为这些环境问题修改生产代码。

## 11. Docker 与 HTTP 最终状态

`docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Status}}"` 在 build/up 后显示：

| Service | State | Health |
| --- | --- | --- |
| api | running | healthy |
| worker | running | healthy |
| postgres | running | healthy |
| redis | running | healthy |
| minio | running | healthy |
| website | running | healthy |
| admin | running | healthy |
| nginx | running | healthy |
| postgres-test | running | healthy |
| redis-test | running | healthy |

`minio-init` 是一次性桶初始化服务，成功退出，不属于长期服务。integration profile 的 test dependencies 保持运行；所有 volumes 保留。

HTTP 实测：

- API live `http://localhost:8010/api/v1/health/live`：200，`status=healthy`，version `0.4.0`；
- API ready `http://localhost:8010/api/v1/health/ready`：200，PostgreSQL/Redis 均为 `ready`；
- Website `http://localhost:3000/en/`：200；
- Admin `http://localhost:3001/login`：200，含 `X-Robots-Tag: noindex, nofollow`；
- Nginx `http://localhost:8080/en/`：200，并返回第 9 节安全头。

## 12. 已知问题与测量限制

1. 本地 seed 不创建虚假业务内容，因此 About 返回标准 404，Homepage 只显示通用 RFQ 恢复内容，各详情页无法完成真实数据浏览器旅程。这是 Phase 3.7 真实内容录入前的预期数据状态。
2. Lighthouse 本机不可用，没有 Performance/Accessibility/Best Practices/SEO 分数，也没有 LCP/CLS/INP 实测；production 性能门槛尚不能量化声明。
3. 没有真实 Safari 运行环境；本轮浏览器自动化使用本机 Chrome。Safari-compatible layout 仍需在 staging 的真实 Apple/WebKit 环境复核。
4. Task 12 遗留 console 日志中的 404 来自缺失 Company profile 与故意访问不存在页面，不是 hydration mismatch；本轮有效页面检查未见 console warning/error。
5. test profile 使用持久化 PostgreSQL volume。原搜索 integration 查询词公共前缀过长且随机段过短，旧测试记录可被 trigram 合法命中；已使用完整 UUID 隔离，focused 与 full profile 均回归通过。
6. 构建 warning 包括 Rolldown plugin timing、Starlette/AnyIO alias deprecation 与 Admin Nitro 的 Node `DEP0155`；后续依赖升级时应消除，但当前不是运行阻断。

## 13. Phase 3.7 建议

Phase 3.7 应限制在 Content Population + Real Asset Import + Staging QA + SEO/GEO Final Audit + Analytics/Search Console Preparation：

1. 通过 Admin 生命周期录入并发布真实 Company、Product、Material、Technology、Application、Solution、Case、Knowledge、Capability、Trust 与 Media；不在 Vue 硬编码业务事实。
2. 使用获授权的真实工厂/产品媒体，核验 alt/caption、尺寸、格式、Hero LCP 选择与 broken object 报告。
3. 在 staging 用真实内容重复 Home → Product → RFQ、Search → Knowledge、Language Switch、Gallery、RFQ multi-item 与全部详情页浏览器旅程。
4. 在 Mobile/Desktop 执行 Lighthouse，记录 Performance、Accessibility、Best Practices、SEO、LCP、CLS，并在真实交互流量具备后观测 INP。
5. 在 Chrome、Edge、Mobile Chromium 与真实 Safari/WebKit 复核 320–1920 响应式、键盘、screen reader 基础和表单错误体验。
6. 核对旧站高价值 URL 映射、redirect、canonical、hreflang、sitemap 与内部链接，再准备 Search Console/Bing/Analytics；本阶段不启用或提交。
7. 建立固定 GEO 问题池、内容 owner、来源/日期/适用范围和更新节奏；真实测量 mention/citation 与 assisted lead，不作保证。

完成 staging 内容与测量验收后，才进入 Production Deployment、Redirect Migration、Search Console/Bing 与 Analytics 上线。

## 14. `$seo-rank` / `$geo-rank` 冲突检查

逐项复核后未发现 Phase 3.6 实现与两项技能的核心原则冲突：

- People-first 与 evidence-first：业务事实只来自发布数据，无假证书、假案例、假参数、假价格或隐藏关键词正文。
- Discovery foundation：SSR、canonical、hreflang、robots、sitemap source、Breadcrumb 与 crawlable `<a>` 由统一发布/路由门禁控制。
- Intent 与 architecture：Product、Material、Application、Solution、Knowledge、Case 各有明确页面职责和内部关系，不按无价值词形组合批量造页。
- Extractability：Direct Answer、Key Facts、Evidence、FAQ 与可见来源构成自包含内容块，不把 GEO 信息只放在 JSON-LD。
- Entity/Schema consistency：正式域名、语言、Organization/Person/Product/Article/FAQ/Breadcrumb 数据与可见 DTO 同源。
- Trust/governance：Author/Reviewer、日期、Source Citation、Case privacy allowlist 与事实生命周期继续受后端治理。
- International SEO：English/简体中文 alternate 优先，同内容缺失目标翻译时回语言首页，不做 IP 强制跳转。
- Measurement honesty：没有把 Design target、Lighthouse 缺失、Schema、`llms.txt` 或当前代码实现描述为排名/引用保证。

尚未完成但不构成实现冲突的项目是：真实内容与第三方证据填充、旧站 URL migration map 的 staging 终验、固定 GEO monitoring question pool、Search Console/Analytics baseline，以及真实 Lighthouse/Core Web Vitals 数据。这些均明确留在 Phase 3.7 或 production readiness 阶段。
