# Demo R2.1 DR2-UI-04 定向收尾报告

## 1. 范围与结论

本轮只处理 Demo R2.1 复验包中仍开放的 DR2-UI-04：产品卡片截图来源核对、Why Junhui/About 优势内容、特殊应用首屏空白感、375px 长截图复核，以及后台产品规格锚点遮挡问题。

DR2-UI-01、DR2-UI-02、DR2-UI-03、DR2-UI-05 按用户要求接受并保持，不在本轮重做。没有清库、重导、添加首页模块、修改 Privacy 或生产数据。

结论：DR2-UI-04 的本轮定向项目已完成。产品卡片问题判定为旧截图，不修改产品引用、查询或渲染数据；Why Junhui/About 和特殊应用已完成实际内容/布局收尾；375px 重复判定为长图采集拼接伪影；后台规格锚点已修复并实测。

## 2. 实际目标、代码版本与运行状态

- 项目工作区：`junhui-global-website/.worktrees/phase-3.6`
- 分支：`phase-3.7`
- 实际 HEAD：`56891e01f5d6c7d217ef8ee6f9c5be382291e51e`
- 运行目标：`junhui-demo-r2` Demo 环境
- 前台：`https://demo.junhuiscrewbarrel.com/zh-cn/`、`https://demo.junhuiscrewbarrel.com/en/`
- 后台：`https://admin-demo.junhuiscrewbarrel.com/`
- Docker Client/Server：`29.7.2 / 29.7.2`
- Website 镜像更新后容器：healthy；Admin 镜像更新后容器：healthy；API、PostgreSQL、Worker、Redis、MinIO 未因本轮代码需要重启。
- 未执行迁移、Seed、产品重导、生产部署、Review/Publish 操作。
- 工作区原有未提交内容保留；本轮没有自动 commit、push 或 merge。

本轮源码改动集中在：

- `apps/website/app/components/HomepagePresentation.vue`：从后台 `company.advantages` 渲染 Why Junhui 优势；当应用卡片没有媒体时使用紧凑文字状态。
- `apps/website/tests/website-presentation-r1.test.ts`：覆盖后台优势字段和无媒体特殊应用状态。
- `apps/admin/app/pages/catalog/products.vue`：分区导航置于固定页头下方，并为编辑区增加锚点滚动预留。
- `apps/admin/tests/catalog-contract.test.ts`：覆盖固定页头下的规格导航约束。

## 3. 四项收尾结果

### 3.1 产品卡片：旧截图，不是不同发布状态造成的查询问题

复验包中的桌面截图只显示一张卡片，而本轮使用真实 Demo 前台重新打开并在桌面 1440px、中文移动 375px、英文移动 430px 读取 DOM 和公开 API，三种视口均返回同一组：

1. `demo-s01` / `通用注塑螺杆（演示）`，媒体 700×700；
2. `demo-s02` / `耐磨选型螺杆（演示）`，媒体 1200×900；
3. 中文为 `demo-c01` / `配套止逆组件（DEMO R2）`，英文为既有对应英文内容，媒体 1200×900（中文）或既有英文 `demo-s03` 700×700，取决于当前语言的既有首页配置。

后台详情核对结果：`demo-s01`、`demo-s02`、`demo-c01` 均为 enabled；各自中英文 Translation 和 Publication 均为 `published`，对应路由均 active。由此确认桌面一张卡片来自旧采集截图，不是当前发布状态分裂，也没有证据表明产品引用、查询或渲染存在实际缺陷。

本轮仅重新采集最终截图和回读，不修改 Product、首页产品选择、图片对象、媒体内容或发布状态。移动端将每张卡片滚入真实视口后，三张图片的 `naturalWidth/naturalHeight` 均有有效值。

### 3.2 Why Junhui 与 About 优势：改为真实后台 DEMO 内容

通过现有 Admin 的 Company Profile 编辑入口保存，随后按 Demo 原有生命周期重新审核/发布中英文翻译；前台不硬编码这些优势。公开 API 返回 200，并在首页 SSR 中实际出现以下内容。

中文三项：

- 定制需求沟通：围绕材料、设备接口与使用场景整理输入，形成可继续确认的需求记录。
- 加工与检测衔接：把加工节点、检查项目与交付资料放在同一演示流程中，便于复核。
- 配套件协同：将螺杆、机筒与止逆组件等配套关系集中展示，支持方案对照与维护。

英文三项：

- Requirement review: Organize material, interface, and use-case inputs into a record ready for further confirmation.
- Processing-to-inspection handoff: Keep processing steps, inspection items, and delivery records together for review.
- Component coordination: Present screw, barrel, and non-return component relationships together for side-by-side planning.

首页 Why Junhui 同时读取后台双语 `full_intro`；About 页继续读取同一 Company 数据的 `advantages`，没有建立第二套内容库。内容均明确为 DEMO 示例，不构成真实客户、产能或技术承诺。

### 3.3 特殊应用：无媒体字段时使用完整紧凑文字布局

实际公开 Application 卡片没有可用的 `media` 关联字段；本轮没有猜图、错配产品图或新增媒体。首个 Featured Application 改为浅色、有边框、按内容自适应高度的文字布局，保留真实标题、摘要和其他应用列表。

实测结果：

- 桌面 Featured 区高度约 186px，移除了原先大面积深色空面板；
- 375px 视口中标题、摘要和列表均可见，无大片未完成空区域；
- DOM 存在 `.presentation-applications__feature--text-only`，且内容来自公开 API 的 Application 数据。

### 3.4 375px 长截图与固定页头遮挡

重新以普通 375×812 视口实际滚动：首页 `scrollHeight=22914`、`h1Count=1`、`bodyWidth=375`，14 个首页模块按唯一顺序出现，没有第二个首页，也没有横向溢出。复验包中约 16384px 位置再次出现导航/Hero 的长图来自采集工具的拼接/平铺伪影，不能据此修改页面结构。

后台规格锚点的最终浏览器测量（1088×900）：

| 区域 | 最终位置 |
| --- | ---: |
| 全局固定页头 | 0–80px |
| 产品分区导航 | 80–134.16px |
| 规格区 | 143.67px 起 |
| “产品规格与参数”标题 | 176.86–207.86px |
| 首个参数标题“样例直径” | 357.22–378.22px |

规格导航现在紧跟全局页头，点击“规格”后标题和首行参数均不再被遮挡。截图为实际点击 `a[href="#product-specifications"]` 后保存，没有执行保存操作。

## 4. 最终回读摘要

- 公开 API：`/api/v1/public/company-profile/zh-cn`、`/en` 和 `/api/v1/public/home/zh-cn`、`/en` 均返回 200。
- Company 中英文 `short_intro`、`full_intro`、`advantages` 与 Admin 保存内容一致；原有公司名、联系方式、演示状态未被本轮意外覆盖。
- 首页中英文均为单一 H1；桌面 1440px、中文 375px、英文 430px 产品卡片均为三张同组公开卡片。
- 三张移动卡片逐一滚入真实视口后，图片均完成浏览器解码；公开媒体路径、alt 与 API 返回的尺寸一致。
- 中文/英文首页均存在文字优势列表；特殊应用均保留，Featured 应用使用 text-only 布局。
- 固定页头、前台运行入口和 Demo 既有保护配置未在本轮改动；未修改原 phase37 数据。

## 5. 当前检查结果

以下结果均为本轮实际命令或本轮重新采集结果，不沿用复验包里的旧数量：

| 检查 | 结果 |
| --- | --- |
| Website 专项 Vitest：`tests/website-presentation-r1.test.ts` | PASS，1 file / 5 tests |
| Admin 专项 Vitest：`tests/catalog-contract.test.ts` | PASS，1 file / 15 tests |
| Website Nuxt typecheck | PASS，exit code 0 |
| Admin Nuxt typecheck | PASS，exit code 0 |
| 受影响文件 Prettier check | PASS |
| Website Docker production build | PASS，容器健康 |
| Admin Docker production build/recreate | PASS，容器健康 |
| 桌面/375px/430px真实浏览器 DOM、图片解码、滚动与溢出 | PASS |
| 全仓库全量测试 | NOT_RUN，本轮未重复无关全量测试 |
| API/数据库专项回归 | NOT_RUN，本轮没有后端模型/API改动 |
| 真实 RFQ 提交、附件上传、邮件 | NOT_RUN，按范围禁止 |

## 6. 证据与限制

本轮只整理聚焦证据，不重复打包旧素材。脱敏 JSON 和最终截图位于同一证据目录；ZIP 只包含本报告、精简回读 JSON、最终桌面/移动截图、后台锚点截图和校验清单，不包含账号、Cookie、Token、密码或数据库凭据。

特殊应用没有新增图片，是因为当前 Application 公开卡片没有可复用的媒体字段；本轮采用了用户允许的完整紧凑文字方案。产品卡片没有修改引用，因为当前实际 API、发布状态和多视口页面已经一致。

本报告完成 DR2-UI-04 定向收尾记录，不代表 Demo R2.1 全部视觉问题、Phase 3.7 或生产上线已完成。
