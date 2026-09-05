# Phase 3.6 Final Website UI 设计规范

## 1. 文档状态

- 项目：`junhuiscrew/New_Official_Website`
- 分支：`phase-3.6`
- 基线分支：`phase-3.5-final-patch-v3`
- 基线 SHA：`6e696a0e91f0a3d9974269d6bb41ef35ed7963e9`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 状态：已由项目负责人逐节确认，可进入实施计划

本规范落实 `Junhui-Codex-Handoff-Phase3.6.md`，只覆盖最终官网前台、必要的只读 Public DTO/API、响应式、Accessibility、Performance 与回归验证。禁止进入 Production Deployment、Page Builder、批量内容导入或 Phase 3.7。

## 2. 目标与边界

Phase 3.6 把现有 Product、Material、Technology、Application、Solution、Case、Knowledge、Company Trust、Media、RFQ 与 SEO/GEO 能力组合成面向全球 B2B 获客的最终公开站点。

必须保留：

- Nuxt SSR 默认渲染；
- Master Entity + Translation + Publication + ContentRoute + Revision + Audit + RBAC；
- 后端统一 canonical、hreflang、robots、Schema 与 GEO visible source；
- Phase 3.5 的 RFQ、MinIO、Malware、Private File 与 Presigned URL 安全边界；
- 所有业务事实来自数据库/Public DTO。

允许的后端变更仅限公开展示所需的只读聚合接口、列表接口和 DTO 清理。不得新增 Homepage 数据模型、第二套路由/发布/翻译体系或新的 CMS 生命周期。

## 3. 品牌资产与素材策略

- Logo 图形以用户提供的蓝绿圆形标志为准。
- 横向品牌组合以“骏辉螺杆 / JUNHUI SCREW”参考图为基准，实际资产必须去除棋盘背景并适配深浅色背景。
- Logo 是唯一允许直接随 Website 构建发布的静态品牌资产。
- 工厂与产品图片必须通过现有 `public-media` 和 Public DTO 输出；不在 Vue 模板中硬编码业务图片路径。
- Phase 3.6 只选择少量真实素材验证组件和页面；其余产品及媒体由项目负责人后续在 Admin 中录入，禁止批量导入。
- 本机 `D:\骏辉螺杆\图片\产品图片` 当前包含 186 个候选图片文件，只作为真实素材池，不自动映射为数据库产品事实。
- 旧官网 `https://www.junhuiscrew.com/` 仅用于核对既有产品命名、产品分类、工厂视觉和公开联系方式；任何事实进入新站前仍必须通过现有数据库生命周期发布。

## 4. 技术架构

### 4.1 Public API

新增或完善以下只读接口：

- `GET /api/v1/public/home/{locale}`：返回已发布的 Company 摘要、产品分类、精选产品、Application、Solution、Capability、Case、Knowledge 与 Trust 摘要。
- `GET /api/v1/public/navigation/{locale}`：返回 Desktop/Mobile Navigation、精选 Mega Menu 项和 Footer 公开信息。
- Product、Knowledge、Case 及 Catalog Entity 列表接口：支持白名单筛选、稳定分页与 Published/indexable 门禁。
- `GET /api/v1/public/search/{locale}?q=`：使用 PostgreSQL FTS/pg_trgm 搜索 Product、Material、Application、Solution、Knowledge 与 Case。
- Product Detail DTO：输出干净规格、公开媒体、Models 与 canonical Relation Link DTO。

所有 DTO 必须满足：

- 不输出内部 UUID、owner ID、Storage Path、私有字段或 raw ORM；
- 只输出 enabled entity、enabled locale、published translation、published publication、canonical + active + indexable route，并尊重 `seo_documents.robots_index`；
- 只有确需独立 Route 的实体才进入 Sitemap/索引源；
- Schema、Breadcrumb、canonical 与 hreflang 沿用现有后端 generator 和 strict alternate 逻辑。

### 4.2 Nuxt SSR 数据流

- 全局 Layout 在 SSR 阶段取得 Navigation 与 Footer DTO。
- 页面正文使用 `useAsyncData` 服务端加载，核心内容不会依赖 `mounted` 后请求。
- 页面 Head 只序列化后端返回的 SEO、alternate 与 Schema，不在 Vue 重建 Schema 或索引判断。
- API 返回不存在、未发布或不可索引内容时生成标准 404。
- Language Switch 优先使用当前 owner 的 alternate URL；目标翻译不存在时跳转目标语言首页。
- Search 与带筛选参数的列表页使用稳定 canonical；Search 为 `noindex, follow`。

### 4.3 缓存

- 仅公开 GET DTO 可使用明确的 `Cache-Control`/ETag。
- Auth、Admin、RFQ、Private File、Malware 状态和 Presigned URL 禁止进入公开缓存。
- Homepage 聚合避免逐区块串行请求；页面正文保持服务端可见。

## 5. Design Tokens

视觉方向为 Modern Industrial / Precision Manufacturing / Global B2B。

- Primary Blue：导航、链接、Primary CTA 与选中状态。
- Deep Navy：Header、Hero、Footer 和高对比技术区。
- Brand Green：只用于 Logo 呼应、小型状态和重点提示。
- Neutral Gray：正文、背景、边界、规格表与金属层次。
- White：主要内容表面。
- Success/Warning/Error：表单和系统状态，必须达到可读对比度。
- Typography：高性能系统字体栈；H1/H2/H3/body/small/label/technical number 分级明确。
- Spacing：4/8px 基准；主内容宽度约 1280px。
- Radius/Shadow：克制圆角和轻阴影，优先边界与留白，不形成电商卡片堆叠。

禁止大面积科技渐变、玻璃拟态、夸张 3D、重型视差、WebGL、假工业图和假电商元素。

## 6. 全局导航与 Footer

### 6.1 Desktop Header

主导航顺序固定为：Products、Solutions、Materials、Applications、Capabilities、Case Studies、Knowledge、About。右侧提供 Search、Language 与 Request a Quote。

Products Mega Menu 展示已发布产品族、精选产品和 View All Products；Solutions Mega Menu 分为普通方案与 Solve a Problem。Material/Application 只显示精选 Published 项，不把全部条目塞入菜单。

### 6.2 Mobile Navigation

- Hamburger 打开全屏侧滑面板；
- 嵌套导航使用 accordion；
- 提供 Search、Language 与 RFQ CTA；
- 支持键盘、可见焦点、Escape 关闭、焦点回收和 body scroll lock；
- 320px 不产生横向滚动。

### 6.3 Footer

Footer 根据公开 Company DTO 条件显示 Company、Products、Solutions、Knowledge、Contact、Legal 与 Language。公司名、电话、邮箱、地址和 Social Link 只在真实配置存在时输出。底部提供 Copyright、Privacy、Terms（存在时）与 Sitemap。

## 7. Homepage

首页按以下顺序组合：

1. Hero：单一 H1、1–2 行价值主张、Request a Quote、Explore Products 与真实工厂/产品媒体；禁止轮播。
2. Product Categories。
3. Why Junhui / Trust Strip，只显示 API 真实事实。
4. Solve by Material / Problem。
5. Manufacturing Capabilities。
6. Featured Products。
7. Applications。
8. Case Studies。
9. Technical Knowledge。
10. Certificates / Patents / Equipment 摘要。
11. RFQ CTA。
12. Footer。

没有 Published 数据的区块整体隐藏；不得用假数量、假证书、假年份或硬编码规格撑版。

## 8. 页面模板

### 8.1 Product Listing 与 Detail

- Listing 支持 Category、Material、Application 三类白名单筛选和分页。
- Product Card 显示公开图片、名称、摘要、分类、2–4 个重要 Public Specs、View Details 与 RFQ。
- Product Detail 顺序：Breadcrumb、Detail Header、Gallery、Key Specifications、Models、Description、Material/Technology/Application/Solution、Capability/Trust、Case、FAQ、Knowledge、RFQ。
- Product Relation 必须是 Published canonical Link DTO，并渲染为真实 `<a>`。

Public Spec DTO 固定为：

```json
{
  "name": "Outer Diameter",
  "value": "65",
  "unit": "mm",
  "group": "Dimensions",
  "type": "number"
}
```

`text`、`number`、`range`、`boolean`、`enum` 均在后端格式化为公开 DTO，前端按类型显示，不使用 `<pre>` 或 raw JSON。

### 8.2 Catalog Entity

- Material：overview、processing characteristics、common problems、products、technologies、applications、solutions、knowledge、RFQ。
- Technology：explanation、when to use、capability evidence、equipment、products、materials、cases/knowledge、RFQ。
- Application：processing challenges、product、material、technology、solution、case、knowledge、RFQ。
- Solution：problem、cause、inspection、recommended approach、materials、technologies、cases、knowledge、RFQ。

四类页面共用 Detail Header、Breadcrumb、SEO/GEO、Relation Links 和 RFQ CTA，但保持各自语义结构。

### 8.3 Knowledge、Case 与 Expert

- Knowledge Center 是技术资料库，支持分类、分页、作者、审核人、发布日期和摘要。
- Article 顺序：Breadcrumb、Category、H1、Summary/Direct Answer、Author/Reviewer、日期、Body、Key Facts、FAQ、Sources、Relations、RFQ。
- GEO Direct Answer、Key Facts 与 Evidence 必须可见；Source Citation 必须真实可点击。
- Case Study 按 privacy allowlist DTO 渲染 Industry/Country、Problem、Analysis、Solution、Result、Engineer Comment 与公开关系。
- 未授权客户名称、Logo、地址或身份不得进入 HTML、Meta、Schema、GEO 或 Sitemap。

### 8.4 About 与 Trust

- About 组合 Company Overview、History、Factory Facts、Capabilities、Quality、Equipment、Certificates、Patents、Honors、Exhibitions、Gallery 与 Contact CTA；无数据区块不显示。
- Capability 提供 index/detail，并显示公开 Equipment、Technology、Media、Product/Case 与 RFQ。
- Certificate、Patent、Honor 保持聚合页，不创建独立详情 Route。
- Exhibition 提供 index/detail。
- Downloads 输出 title、resource type、summary、version、date、size/type 和 Download CTA；Broken Media 继续由后端过滤。

## 9. RFQ、Search 与 Language

### 9.1 RFQ UX

RFQ 页面分为 Contact、Inquiry Items、Attachments、Privacy 四个区域。保留多 Item、Add/Remove、允许的文件类型、大小提示、Pending/Uploading/Uploaded/Failed 状态与成功 reference。

Product/Material/Solution/Case/Knowledge CTA 进入 RFQ 时携带公开 source context，后端继续重新验证。公开页面不得显示 private signed download、内部 RFQ UUID、assigned user 或 Storage Path。

### 9.2 Search

- URL：`/{lang}/search/?q=`；
- 搜索 Product、Material、Application、Solution、Knowledge 与 Case；
- 结果按类型分组并保留查询词；
- 无结果时提供 Products、Knowledge 与 RFQ 入口；
- RFQ、Admin、Private File 与 Unpublished 内容永不进入结果。

### 9.3 Language Switch

支持简体中文与 English。切换优先走后端 alternate，同一内容缺少目标翻译时回退目标语言首页，不做 IP 强制跳转，也不跳转 404。

## 10. 通用组件

计划组件包括：`SiteHeader`、`MegaMenu`、`MobileNav`、`LanguageSwitcher`、`SiteFooter`、`SearchButton`、`Breadcrumb`、`Hero`、`SectionHeader`、`ProductCard`、`ArticleCard`、`CaseCard`、`TrustMetric`、`SpecTable`、`RelationLinks`、`FAQAccordion`、`GeoAnswer`、`PublicImage`、`PublicVideo`、`MediaGallery`、`RfqCta`、`EmptyState`、`Pagination` 与 `FilterBar`。

每个组件只承担单一职责，接受 DTO/展示配置，不直接执行发布状态判断。

## 11. Media 与性能

- PublicImage 输出固有 width/height、responsive sizes、alt、caption 与 fallback。
- Hero 仅允许一个 LCP 图片，使用 eager/preload；below-fold 图片 lazy load。
- 优先接受 WebP/AVIF，但不伪造缺失的转换资源。
- Gallery 支持 thumbnail、keyboard、lightbox、Escape、焦点回收和移动端手势友好布局。
- Video 使用 poster、controls、metadata 与 lazy load，不自动有声播放。
- 不新增大型 UI Framework，不加载阻塞型远程字体，不启用第三方 Analytics。

工程目标：Lighthouse Performance ≥90、Accessibility ≥95、Best Practices ≥95、SEO ≥95、LCP <2.5s、CLS <0.1。报告记录实测结果，不作排名或 AI 引用保证。

## 12. Accessibility 与 Responsive

- 使用语义化 `header/nav/main/article/section/footer`；每页唯一 H1 和逻辑标题层级。
- Button/Anchor 语义正确，所有交互支持键盘和可见焦点。
- 表单包含 label、错误摘要、字段级错误和 `role=status/alert`。
- Menu、FAQ、Gallery 使用正确的 `aria-expanded`、dialog/focus 行为。
- 满足基础 WCAG AA 对比度，支持 `prefers-reduced-motion`。
- 重点验证 320、375、430、768、1024、1280、1440、1920 宽度。

## 13. Error 与 Empty State

- 404 提供 Products、Knowledge、Search 与 RFQ 恢复入口。
- 500 不暴露堆栈、内部路径或异常详情。
- 无 Product、Case、Certificate、Download 等数据时显示中性 Empty State，不出现 `undefined`、`null`、raw JSON 或未经配置的可信声明。

## 14. Privacy 与 Security

- 不泄露 private RFQ、private bucket、Admin ID、未公开邮箱或 Case 私密信息。
- 保持 CSP、X-Content-Type-Options、Referrer Policy 与 frame 限制。
- JSON-LD 继续安全序列化；Schema、FAQ、Breadcrumb 与可见内容一致。
- RFQ Public Form 保持 same-origin、Origin/Referer、Redis rate limit、honeypot 与现有上传安全链路。
- Public Media 与 private-rfq 的对象存储边界不变。

## 15. Telemetry Hooks

只预留 `rfq_cta_click`、`search_submit`、`download_click`、`language_switch`。Analytics 未配置时事件为 no-op，不发送网络请求。

## 16. 测试与验收

### 16.1 Website

新增 Vitest 覆盖：Desktop/Mobile Header、Language Switch、Homepage 条件区块、Product Card/Spec、Product Relations、Knowledge Metadata、Case Privacy、About 条件区块、Capability Equipment、RFQ Source、Empty State、Search、Breadcrumb 与 404。

如环境支持，使用浏览器执行 Home → Product → RFQ、Search → Knowledge、Language Switch、Mobile Nav 与 RFQ Multi-item 流程，并检查 hydration warning、console error 和网络请求。

### 16.2 Backend/Admin

- Ruff；
- Full backend pytest；
- 真实 PostgreSQL/Redis/MinIO integration；
- Empty DB → latest 与 `0001 -> latest`；
- Seed 连续执行幂等；
- Admin Vitest/Typecheck 回归；
- Sitemap/Public Handler、Privacy、RFQ/Media 安全回归。

### 16.3 Build/Docker

- Website/Admin Vitest；
- Website/Admin Typecheck；
- Prettier；
- Nuxt Production Build；
- Docker Compose build/health；
- API live/ready、Website、Admin 与 Nginx 实际 HTTP 验证。

## 17. 完成报告

最终生成 `docs/architecture/phase3-6-completion-report.md`，逐项记录 Branch/Base/Final SHA、Design Tokens、导航、Footer、Homepage、全部页面族、Public Spec DTO、RFQ、Search、Language、SEO/GEO、Media、Responsive、Accessibility、Performance、Privacy、Tests、Build、Docker、Lighthouse（如运行）、Known Issues、Phase 3.7 建议与 `$seo-rank` / `$geo-rank` 冲突检查。

## 18. 已确认决策

- 采用数据驱动整合式前台，而不是前端静态清单或大量独立请求。
- Logo 为静态品牌资产；业务图片统一经 Public Media/DTO。
- 只选少量真实图片验证，不批量导入；其余产品由项目负责人后续在 Admin 录入。
- Design Tokens、导航、首页结构、页面模板、交互、Accessibility、Performance、安全与测试方案均已确认。
- 未发现本设计与冻结的 Phase 3.1–3.5 架构、`$seo-rank` 或 `$geo-rank` 核心原则冲突。
