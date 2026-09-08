# Phase 3.7.3 首发准备只读审计 R1

- 审计 Run ID：`20260907T112635+0800`
- 唯一运行目标：`phase37-local-https`
- 本地受保护入口：`https://junhui.test/`
- 工作区：`phase-3.7` 现有 linked worktree
- 审计结论：`COMPLETED_WITH_FINDINGS`
- 首发结论：`NOT_LAUNCH_APPROVED`；本报告不是生产上线许可

## 1. 执行摘要

本轮按授权完成只读审计，没有自动修复、重新审核、重新发布、部署、重启、提交询价、上传附件、发送邮件、改 DNS、启用 Sitemap/Analytics，也没有 commit、push 或 merge。

核心结果：

1. 16 个中英文核心内容页全部从真实首次 SSR HTML 读取，均返回 200；每页都有一个 H1、正确 `lang`、一个正式自规范 canonical、`zh-CN/en/x-default` hreflang、互惠返回链接和可解析 JSON-LD。
2. 三款产品均完成桌面端 `zh → en → zh` 实际点击，另完成 P02 的 375px 移动端中文到英文点击；语言链接为相对路径，所有请求留在本地隔离域名。
3. P01/P02/P03 的主图在列表和详情首次 HTML 中均有非空 alt、`700×700` 尺寸属性，浏览器真实解码尺寸也是 `700×700`。
4. 保护与业务索引资格已分开验证：外层仍是 HTTPS、Basic Auth、`X-Robots-Tag: noindex, nofollow`、Sitemap 404；内部已批准的 12 组 Company/分类/产品语言路由仍为 published、active、indexable。
5. 性能方面使用现有 Microsoft Edge DevTools Protocol 与 PerformanceObserver 完成 4 页 × 2 配置 × 3 次，共 24/24 次有效实验室测量；全部命中真实正文，不是 401 或登录页。电脑没有现成 Lighthouse 包或命令，因此没有安装依赖，Lighthouse 分类评分如实记录为 `BLOCKED/NOT_RUN`。
6. 发现 1 个 P0、4 个 P1、2 个 P2 问题和 1 项测量限制。最重要的是：双语 Privacy 链接实际 404，而 RFQ 必选隐私同意项也指向这些链接；中文 Search 对“氮化”没有返回当前已展示的两款氮化产品；导航还暴露了双语共 12 个明确为空的后续栏目页。

## 2. 审计边界和证据解释

本轮将授权包中的 `audit-page-plan.json` 与 `geo-question-review-plan.json` 仅作为待执行计划。所有 `PASS`、`BLOCKED`、`NOT_RUN` 和发现项均来自本轮实际读取，不沿用计划中的空字段或旧测试数量。

只读的含义是：

- 没有调用业务写接口、CMS Review/Publish、RFQ POST、上传、迁移、Seed 或旧 QA 清理脚本；
- 正常 Basic Auth 会话、HTTP 访问日志和基础设施自身的附带记录可能发生，因此没有宣称“全库绝对零写入”；
- 原始 HTML、正文文本、性能单次结果和采集脚本保存在 Git 忽略的私有审计目录；分享包仅收录脱敏摘要和必要截图。

## 3. Git 与实际运行版本

### 3.1 审计开始时 Git 基线

| 项目 | 实际值 |
|---|---|
| Branch | `phase-3.7` |
| HEAD | `0fd6edabfc6d4efa8666cf49c54765b099b24300` |
| HEAD subject | `docs(phase37): record Batch01 COPY-V1 draft update` |
| 与 upstream 比较 | behind 0 / ahead 1 |
| 审计开始时未提交路径 | 20 |

`0fd6edab...` 仅是已提交基线，不包含随后尚未提交的展示修复。审计开始前对 20 个未提交文件逐项记录了状态、SHA-256 与大小，完整清单位于证据包的 `environment-baseline.json`。本轮没有回退或覆盖这些工作。

### 3.2 运行容器

| 服务 | Image ID | 本轮读取时状态 | Started at (UTC) |
|---|---|---|---|
| nginx | `sha256:a8b39bd9cf0f...` | healthy | `2026-09-07T01:14:18Z` |
| website | `sha256:ebd260240e61...` | healthy | `2026-09-07T02:53:06Z` |
| api | `sha256:9fc31f522914...` | healthy | `2026-09-07T02:53:00Z` |
| admin | `sha256:52997f75e8cc...` | healthy | `2026-09-07T02:41:15Z` |
| worker | `sha256:6b1f2ef04a30...` | healthy | `2026-09-07T02:41:04Z` |

为确认运行实例确实包含未提交展示修复，对以下宿主文件与容器内文件做 SHA-256 对照，5/5 一致：

- `apps/api/app/api/v1/media.py`
- `apps/api/app/modules/media/services.py`
- `apps/api/app/phase37_batch01.py`
- `apps/website/app/components/HomePage.vue`
- `apps/website/app/composables/useLocalePath.ts`

因此本轮审计的是当前实际运行代码，不是只按 HEAD 推断的旧版本。本轮未重启任何服务。

## 4. 隔离保护与冻结状态

### 4.1 外层保护

| 检查 | 实际结果 |
|---|---|
| HTTPS 本地入口 | `https://junhui.test/` 可用 |
| Basic Auth | 匿名网站/Admin/API 均 401；认证后均 200 |
| 全站 noindex | 认证与匿名响应均保留 `X-Robots-Tag: noindex, nofollow` |
| Sitemap | `/sitemap.xml` 返回 404，开关仍关闭 |
| 端口边界 | 只有 nginx 暴露宿主 443；Website/API/Admin/Postgres/Redis/MinIO 无宿主端口 |
| 绕过入口 | 未发现直接 origin 绕过 |
| 环境 | staging |
| Analytics / 营销邮件 | 均关闭 |
| 公网隧道 | 未创建 |

本地 `noindex` 和 Sitemap 404 是隔离保护的预期行为，不被判为业务 SEO 缺陷。Google 明确说明 HTTP `X-Robots-Tag: noindex` 可以阻止支持该规则的搜索引擎建立索引；本轮只用它解释本地保护，不将它误当作生产索引状态。[Google noindex 文档](https://developers.google.com/search/docs/crawling-indexing/block-indexing)

### 4.2 内容与生命周期冻结

| 冻结项 | 实际结果 |
|---|---|
| COPY-V1 16 字段 | 16/16 一致 |
| 冻结状态 SHA-256 | `eb3604a43247931034745a6d3494f31c954ab9ba1b304a9d7cc7de075ec2d93b` |
| Company/分类/P01/P02/P03 双语生命周期 | 12/12 为 published |
| 12 条业务路由 | active=true、indexable=true |
| P01/P02/P03 参数值 | 0 / 0 / 0 |
| 七个字段定义 | 未改 |
| F05 英文 | 继续空缺 |
| 型号与关系 | 继续为空 |
| 旧试点 | closed draft，前台 404 |

## 5. 16 页真实首次 SSR 矩阵

采集方式为 Edge 中 `javaScriptEnabled=false` 的认证上下文；因此下表的 Head、H1、链接、图片属性和 JSON-LD 均来自首次服务器 HTML，不依赖 hydration 后补写。

| Alias | 本地路径 | HTTP | Title | Meta description | H1/lang | canonical + hreflang | JSON-LD | 主内容图片 |
|---|---|---:|---|---|---|---|---|---|
| home-zh-cn | `/zh-cn/` | 200 | 骏辉螺杆 | 有 | 1 / zh-CN | 自规范；3 个；互惠 | Organization/WebPage/WebSite | 无主内容图，N/A |
| home-en | `/en/` | 200 | Junhui Screw | 有 | 1 / en | 自规范；3 个；互惠 | Organization/WebPage/WebSite | 无主内容图，N/A |
| about-zh-cn | `/zh-cn/about/` | 200 | 舟山骏辉塑料机械有限公司 | **缺失** | 1 / zh-CN | 自规范；3 个；互惠 | Organization/BreadcrumbList | 无主内容图，N/A |
| about-en | `/en/about/` | 200 | Zhoushan Junhui Plastic Machinery Co., Ltd. | **缺失** | 1 / en | 自规范；3 个；互惠 | Organization/BreadcrumbList | 无主内容图，N/A |
| products-zh-cn | `/zh-cn/products/` | 200 | 产品 | **缺失** | 1 / zh-CN | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 3；alt/尺寸完整 |
| products-en | `/en/products/` | 200 | Products | **缺失** | 1 / en | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 3；alt/尺寸完整 |
| screws-zh-cn | `/zh-cn/products/screws/` | 200 | 螺杆 | 7 字通用描述 | 1 / zh-CN | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 2；alt/尺寸完整 |
| screws-en | `/en/products/screws/` | 200 | Screws | 24 字符通用描述 | 1 / en | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 2；alt/尺寸完整 |
| barrels-zh-cn | `/zh-cn/products/barrels/` | 200 | 机筒 | 7 字通用描述 | 1 / zh-CN | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 1；alt/尺寸完整 |
| barrels-en | `/en/products/barrels/` | 200 | Barrels | 25 字符通用描述 | 1 / en | 自规范；3 个；互惠 | WebPage/WebSite/BreadcrumbList | 1；alt/尺寸完整 |
| P01-zh-cn | `/zh-cn/products/screws/nitrided-screw/` | 200 | 骏辉氮化螺杆 | 有 | 1 / zh-CN | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |
| P01-en | `/en/products/screws/nitrided-screw/` | 200 | Junhui Nitrided Screw | 有 | 1 / en | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |
| P02-zh-cn | `/zh-cn/products/barrels/junhui-nitrided-barrel/` | 200 | 骏辉氮化机筒 | 有 | 1 / zh-CN | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |
| P02-en | `/en/products/barrels/junhui-nitrided-barrel/` | 200 | Junhui Nitrided Barrel | 有 | 1 / en | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |
| P03-zh-cn | `/zh-cn/products/screws/electroplated-screw/` | 200 | 骏辉电镀螺杆 | 有 | 1 / zh-CN | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |
| P03-en | `/en/products/screws/electroplated-screw/` | 200 | Junhui Electroplated Screw | 有 | 1 / en | 自规范；3 个；互惠 | Product/Brand/BreadcrumbList | 1；alt/700×700 |

全部 16 页均有 `zh-CN/en/x-default`，且中英文页面互相返回。互惠返回是 hreflang 的关键要求；缺失返回链接时标记可能被忽略。[Google localized versions 文档](https://developers.google.com/search/docs/specialty/international/localized-versions)

### 5.1 图片、alt 与尺寸

- 列表和分类页的 12 个产品图片实例均有非空 alt 与 `width="700" height="700"`；浏览器 natural size 也为 `700×700`。
- 六个产品详情页的主图均完成解码，alt 与语言对应，未出现 fallback。
- Header Logo 使用空 alt，属于重复品牌链接中的装饰图，不计为缺失产品 alt。
- 没有读取或公开图 5，也没有修改媒体文件、哈希、ID、水印、alt 或主图关系。

### 5.2 内部链接发现

14/16 个核心页面的面包屑正文中存在正式域名绝对链接。正式 canonical/hreflang 保持绝对地址是当前合同要求；但是这些面包屑在本地保护预览中如果点击会离开 `junhui.test`。本轮没有点击这些链接，也没有访问生产站。生产域名部署后它们会成为同站链接，因此需把“本地预览安全提醒”和“生产缺陷”分开。

另一个实际问题是：中文 P01/P02/P03 的面包屑可见标签为英文 `Home / Products`，需要在后续修复轮次处理。

## 6. 浏览器实际点击与功能页

### 6.1 语言导航

| 场景 | 实际结果 |
|---|---|
| P01 desktop | 中文详情 → `/en/...` → 英文详情 → `/zh-cn/...`；最终回中文；相对 href |
| P02 desktop | 中文详情 → 英文详情 → 中文详情；相对 href |
| P03 desktop | 中文详情 → 英文详情 → 中文详情；相对 href |
| P02 mobile 375×812 | 移动菜单实际点击中文 → 英文；无横向溢出；相对 href |
| 外站请求 | 0 |
| Console/page errors | 0 / 0 |

### 6.2 RFQ

- 中英文 RFQ 页面均实际返回 200，并保持页面级 `noindex,follow` 与外层 `noindex,nofollow`。
- 从 P01/P02/P03 的中英文详情读取到 6 个带 `source_type=product` 和正确 `source_slug` 的来源链接。
- 实际打开这 6 个 RFQ URL 后，来源提示、首个询价项类型 `product` 和对应 slug 均被保留。
- 未填写联系信息、未提交、未选择或上传附件、未发送邮件。
- **阻塞发现：中英文 RFQ 的必选隐私同意链接分别指向 `/zh-cn/privacy/` 和 `/en/privacy/`，两页均实际 404。**

### 6.3 Search

| 语言与查询 | HTTP | 实际结果 |
|---|---:|---|
| 中文 `nitrided` | 200 | 无结果 |
| 中文 `氮化` | 200 | P01/P02 均未返回 |
| 英文 `nitrided` | 200 | 返回 Junhui Nitrided Screw 与 Junhui Nitrided Barrel |

中文 Search 的 CJK 检索覆盖不足属于实际首发问题。若本轮之后未修复，应在首发时后置或隐藏 Search，而不是让用户进入可用但找不到已展示产品的入口。

### 6.4 页脚、根路由和负面路径

- `/` 实际落到中文首页；最终正文为真实首页，不是认证页。
- 页脚实际存在 Company、Products、Solutions、Knowledge、RFQ、Privacy、Sitemap 和语言链接。
- Privacy 中英文均 404，属于缺陷。
- `/sitemap.xml` 为 404，属于当前隔离保护预期；不能因此判为业务 SEO 缺陷。
- 未发现独立 Terms 或 Contact 页面链接；Contact 栏当前使用 RFQ 入口。
- 旧试点中英文详情均 404；随机不存在路径也为 404。

## 7. 空栏目盘点与首发后置建议

以下栏目都从真实本地页面读取，双语共 12 页均返回 200，但正文明确显示“暂无已发布内容 / No published content”：

- Solutions
- Materials
- Applications
- Manufacturing Capabilities
- Case Studies
- Knowledge

这些页面当前还被主导航或页脚暴露。建议首发时后置，并在没有真实内容前从主导航移除或关闭入口；不要通过虚构案例、参数、专家、证书或技术结论填充空白。

## 8. SEO / GEO 技术审查

### 8.1 Head 与结构化数据

- Title：16/16 有值；但 Products/分类标题过短且通用。
- Meta description：12/16 有值；About 与 Products 双语共 4 页缺失。
- H1：16/16 恰好一个。
- `lang`：16/16 与页面语言一致。
- Canonical：16/16 正式自规范。
- hreflang：16/16 包含 `zh-CN/en/x-default` 并互惠。
- JSON-LD：16/16 至少一段，全部可解析；抽查实体名称、描述和 URL 与可见页面一致，未发现额外价格、评分、证书或技术承诺。

三款产品的 Product JSON-LD 没有 `review`、`aggregateRating` 或 `offers`。Google Product snippet 指南要求至少包含其中之一才能满足产品摘要最低组合。[Google Product snippet 文档](https://developers.google.com/search/docs/appearance/structured-data/product-snippet) 本项目没有真实价格/评分，且本轮明确禁止伪造，所以报告仅记录“不具备产品富结果资格”，不建议为了通过验证而添加虚假数据。

### 8.2 Sitemap 候选规则（无副作用检查）

本地端点没有开启。只读代码审查确认：生产开关开启时，`/sitemap.xml` 调用 `list_indexable_routes`，只序列化同时满足 published、translation published、canonical、active、indexable、语言启用、SEO 可索引和业务实体 enabled 的结构化 owner 路由。

当前生命周期快照能进入该候选源的是 12 条：Company 2、分类 4、P01/P02/P03 6。双语首页与产品总列表共 4 个聚合页虽在 SSR 中呈现 `index,follow`，但不属于该 owner route 集合。生产启用 Sitemap 前，需要决定是否把这 4 个核心聚合页纳入候选规则。

### 8.3 GEO / AI Search 解释

没有把保护站内容发送给外部 AI，也没有生成引用率、推荐率或排名数据。Google 当前说明 AI Overviews/AI Mode 没有独立的特殊技术要求，基础 SEO、可索引、可发现内部链接、文本内容和与可见内容一致的结构化数据仍然适用。[Google AI features 文档](https://developers.google.com/search/docs/appearance/ai-features) 因此本轮只审查可见问题覆盖、技术可抓取条件和事实一致性，不虚构“AI 已收录”。

## 9. 20 条双语问题池覆盖

汇总：`ANSWERABLE 14`、`PARTIAL 0`、`NOT_STATED_INTENTIONAL 6`、`NOT_STATED_NEEDS_DECISION 0`。

| ID | 结果 | 实际页面 | 可见证据摘要 |
|---|---|---|---|
| Q01-zh-CN | ANSWERABLE | `/zh-cn/about/` | 位于中国浙江舟山 |
| Q01-en | ANSWERABLE | `/en/about/` | Based in Zhoushan, Zhejiang, China |
| Q02-zh-CN | ANSWERABLE | `/zh-cn/products/` | 当前列表可见三款产品及询价入口 |
| Q02-en | ANSWERABLE | `/en/products/` | Three visible products with RFQ links |
| Q03-zh-CN | ANSWERABLE | `/zh-cn/about/` | 设计、研发、测绘、生产、热处理、工艺、销售、售后 |
| Q03-en | ANSWERABLE | `/en/about/` | Design through after-sales service |
| Q04-zh-CN | ANSWERABLE | P01 中文 | 设备名称/型号、数量、图纸或需求说明 |
| Q04-en | ANSWERABLE | P01 英文 | Machine/model, quantity, drawing or requirements |
| Q05-zh-CN | ANSWERABLE | P02 中文 | 可注明螺杆等部件，具体配套另行确认 |
| Q05-en | ANSWERABLE | P02 英文 | Other components may be mentioned; matching confirmed separately |
| Q06-zh-CN | ANSWERABLE | P01/P02/P03 中文 | 图纸可作为私密 RFQ 附件，不在产品页公开 |
| Q06-en | ANSWERABLE | P01/P02/P03 英文 | Private RFQ attachments are not displayed on product pages |
| Q07-zh-CN | NOT_STATED_INTENTIONAL | P01 中文 | 直径/长度参数为 0，尺寸需沟通确认 |
| Q07-en | NOT_STATED_INTENTIONAL | P01 英文 | No exact dimensions published |
| Q08-zh-CN | NOT_STATED_INTENTIONAL | P02 中文 | 未声明硬度值 |
| Q08-en | NOT_STATED_INTENTIONAL | P02 英文 | No hardness value stated |
| Q09-zh-CN | ANSWERABLE | P03 中文 | 没有确认是铬；具体镀层需沟通确认 |
| Q09-en | ANSWERABLE | P03 英文 | Chromium is not confirmed; plating must be confirmed individually |
| Q10-zh-CN | NOT_STATED_INTENTIONAL | P03 中文 | 未发布寿命比较或量化数据 |
| Q10-en | NOT_STATED_INTENTIONAL | P03 英文 | No comparative service-life claim published |

“未声明且有意留空”没有被自动升级为首发阻塞，也没有从行业常识、图 5 或字段定义推导数值。Google 的 people-first 指南强调内容应对实际受众有用、体现真实经验并让用户获得足够信息；本轮用它作为后续真实内容建设原则，而不是补写未经确认的事实。[Google helpful content 文档](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

## 10. 本地性能基线

### 10.1 工具与配置

- 浏览器：Microsoft Edge `152.0.4191.66`
- 驱动：Playwright `1.63.0-alpha-2026-08-31`
- 方法：Edge DevTools Protocol + 浏览器 PerformanceObserver
- 每次使用新 incognito context；CDP 清浏览器缓存和 Cookie；阻止 Service Worker；没有清服务器缓存
- Mobile：375×812、DPR 2、CPU 4× slowdown、150ms latency、下载 200000 B/s、上传 93750 B/s
- Desktop：1365×900、DPR 1、CPU 1×、40ms latency、下载/上传 1250000 B/s
- Lighthouse：本机无现成可执行包，`BLOCKED`；没有安装
- INP：短时无交互实验室加载无法取得，`NOT_AVAILABLE`
- TBT：仅作为实验室响应性信号，**不替代 INP**

Chrome 官方说明 Lighthouse 可从 DevTools、CLI 或 Node 运行，并可审计需要认证的页面；但本轮遵守“不安装、不改依赖”的冻结条件。[Chrome Lighthouse 概览](https://developer.chrome.com/docs/lighthouse/overview) Web Vitals 指南也明确指出无用户输入的 Lighthouse 不能测量 INP，TBT 只是实验室代理，实验室测量不能替代现场数据。[web.dev Web Vitals](https://web.dev/articles/vitals)

### 10.2 三次中位数

| 页面 | 配置 | 有效次数 | FCP ms | LCP ms | CLS | TBT ms | TTFB ms | Load ms | LCP 元素 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| home-zh-cn | Mobile | 3/3 | 1112 | 1112 | 0 | 0 | 240.4 | 5883.2 | 简介段落 |
| home-zh-cn | Desktop | 3/3 | 360 | 360 | 0 | 0 | 118.0 | 1150.1 | H1 |
| home-en | Mobile | 3/3 | 1056 | 1056 | 0 | 0 | 241.7 | 5883.3 | 简介段落 |
| home-en | Desktop | 3/3 | 360 | 360 | 0 | 0 | 127.7 | 1188.2 | H1 |
| P02-zh-cn | Mobile | 3/3 | 1020 | 2180 | 0 | 1 | 257.5 | 5955.5 | 产品主图 |
| P02-zh-cn | Desktop | 3/3 | 308 | 308 | 0 | 0 | 129.3 | 1171.8 | 简介段落 |
| P03-en | Mobile | 3/3 | 944 | 944 | 0 | 16 | 243.2 | 5991.1 | 简介段落 |
| P03-en | Desktop | 3/3 | 300 | 300 | 0 | 0 | 123.7 | 1182.9 | H1 |

24/24 样本均满足：HTTP 200、最终 URL 为预期本地 URL、H1 精确命中、正文长度大于 150、无横向溢出、无 console/page error。结果对本地合成条件而言是积极基线，但不能声称全球访问、真实用户 Core Web Vitals 或生产 Lighthouse 分数达标。

性能后续建议：生产候选环境可用时，安装与项目隔离的受控 Lighthouse 工具或使用已认证 DevTools，再按同一页面和固定配置复测；上线后用真实用户数据验证 LCP/CLS/INP。当前 P02 Mobile 的 LCP 是产品主图，应优先保留其尺寸、预加载/优先级和压缩策略，不要为了提高分数关闭 Basic Auth 或 noindex。

## 11. Findings

| ID | 优先级 | 发现 | 首发处置建议 |
|---|---|---|---|
| F-R1-001 | P0 / blocker | 中英文 Privacy 均 404，RFQ 必选隐私同意与页脚均引用 | RFQ 上线前必须提供真实政策页或负责人批准的合法替代 |
| F-R1-002 | P1 | 中文“氮化”搜索找不到 P01/P02，英文正常 | 修复 CJK 检索；否则首发后置 Search |
| F-R1-003 | P1 | 6 类栏目双语共 12 页以 200 暴露空内容 | 有真实内容前从首发导航后置 |
| F-R1-004 | P1 | About/Products 双语 4 页缺 meta description；列表/分类 metadata 通用 | 后续 SEO 内容轮次补齐，不改 COPY-V1 16 字段 |
| F-R1-005 | P1 | Sitemap 候选源缺双语首页/产品总列表 4 个聚合页 | 生产启用前决定是否纳入 |
| F-R1-006 | P2 | Product JSON-LD 不满足 Google Product snippet 最低组合 | 不伪造价格/评分；接受无富结果或等真实数据 |
| F-R1-007 | P2 | 中文产品面包屑为英文；本地预览正文面包屑会指向正式域名 | 修复中文标签；本地复验时避免点击正式域名链接 |
| L-R1-001 | limitation | Lighthouse 不可用，分类分数未测 | 生产候选轮次使用受控工具复测 |

## 12. 首发候选与待决策清单

### 12.1 有条件首发核心候选

双语首页、About、产品总列表、screws/barrels 分类、P01/P02/P03 详情，共 16 页。它们在当前隔离实例中具备真实正文、正确语言路由、基本 Head、互惠 hreflang、结构化数据和本地可用图片。RFQ 可作为功能候选，但受 F-R1-001 阻塞。

### 12.2 建议后置

- Solutions、Materials、Applications、Capabilities、Case Studies、Knowledge：当前均为空；
- 中文 Search：当前中文产品关键词无结果；
- 可后补的参数、关系、案例、证书和专家内容：继续保留空缺，不自动转为阻塞或虚构填充。

### 12.3 上线前需要负责人决定

1. 中英文隐私政策的真实内容与责任人；
2. 中文 Search 是修复后首发，还是暂时隐藏；
3. 6 类空栏目是否从首发导航移除；
4. Sitemap 是否纳入双语首页和产品总列表；
5. Product JSON-LD 是仅保留语义用途，还是等待真实 offers/review 数据后追求富结果；
6. About/Products 元描述与列表/分类 SEO metadata 的后续内容来源；
7. 可用 Lighthouse 与生产候选/真实用户性能复测安排。

## 13. 实际命令与未执行项

| 操作 | 结果 |
|---|---|
| Git HEAD/branch/upstream/status 与逐文件 SHA-256 | EXECUTED |
| Docker ps/inspect 与选定容器内文件 SHA-256 | EXECUTED |
| `check_boundary.ps1` | PASS（真实 `boundary_verified`） |
| `run_protected_preview.ps1 -Mode Verify` | PASS（16 字段、冻结哈希、生命周期均真实验证） |
| `node audit_pages.js` | PASS（31 个 SSR/候选页面，3 个产品双语往返，1 个移动点击） |
| `node functional_checks.js` | EXECUTED_WITH_FINDINGS（搜索、6 个 RFQ 来源、12 个后置栏目） |
| `node performance_baseline.js` | PASS（24/24 有效样本） |
| Lighthouse 分类评分 | BLOCKED（工具不存在） |
| 无关全量测试 | NOT_RUN |
| 外部 AI 引用/排名评测 | NOT_RUN |
| Review/Publish、RFQ POST、上传、部署 | NOT_RUN / 未调用 |

本轮是内容和运行状态的只读采集，没有业务代码修改，所以没有重跑无关 pytest、Vitest、类型检查或全量构建；未执行项没有标记为 PASS。

## 14. 证据与保留状态

公开报告：本文件。

私有原始目录：`data/phase3-7/readonly-audit/20260907T112635+0800/`，包含首次 SSR HTML、可见正文、逐次性能数据和采集脚本；该目录不提交 Git。

脱敏证据包包含：

- `page-matrix.json`
- `seo-geo-checks.json`
- `question-review.json`
- `performance-summary.json`
- `functional-checks.json`
- `protection-and-freeze.json`
- `environment-baseline.json`
- `execution-record.json`
- `findings.md`
- `launch-recommendations.md`
- 本报告副本
- 8 张真实桌面/移动截图
- `MANIFEST.json` 与 `SHA256SUMS.txt`

证据包不含密码、Cookie、Token、数据库连接串、对象存储密钥、私有签名 URL 或原始内部媒体 UUID。原始性能文件因为包含内部媒体路径和完整运行细节，仅保留本地；分享的是一致别名化摘要。

审计结束时原受保护预览继续运行，没有重启、撤回或清理已批准内容。下一步应由负责人先处理/决策 Findings，再单独授权修复或生产准备；本轮不宣布 Phase 3.7 完成。
