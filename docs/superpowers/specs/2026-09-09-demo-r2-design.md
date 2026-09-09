# Demo R2 完整官网与后台设计规格

## 1. 目标与边界

Demo R2 在现有 Nuxt/Vue/FastAPI/CMS 代码基础上交付一套可长期保留的本机演示环境。它必须使用独立数据库、Redis、MinIO、会话密钥和本地域名，不读取或覆盖原 phase37-local-https 的公司、产品、SEO、Privacy、RFQ 和媒体数据。

演示内容统一标记批次 `JH-DEMO-R2-V1`，外层与业务层均保持 noindex，Sitemap、llms.txt、Analytics、邮件发送和外部提交关闭。演示环境可以走真实 CMS 生命周期、发布虚构演示政策并提交虚构询盘，但所有内容必须持续显示简洁的 DEMO 标识。

## 2. 视觉方向

采用用户确认的 A 方案“工业内容编辑型”。

- 主色：深海军蓝 `#061b33`、技术蓝 `#0878e8`、白色和冰蓝灰；品牌绿色仅用于少量状态或强调。
- 字体：中文优先使用系统无衬线字体，英文与数字采用清晰紧凑的技术字体栈。
- 形态：1px 细分隔线、方正或 4px 小圆角、非对称编辑式构图；避免大面积渐变、巨型标题、重复 SaaS 卡片和无意义空白。
- 节奏：首页以深浅区带、横向数据轨道、产品图、结构化文本和媒体交替组成，14 个模块各有明确视觉角色。
- 后台：固定深色左侧导航、紧凑顶栏、工作区工具栏、结构化表单和可读状态系统；不暴露 UUID、原始 JSON 或开发者字段作为最终操作界面。

设计候选：

- `docs/design/demo-r2/concepts/demo-r2-website-new-concept.png`
- `docs/design/demo-r2/concepts/demo-r2-admin-new-concept.png`

原始设计画布未在交接包或工作区找到，因此上述文件标记为 Demo R2 新候选。

## 3. 环境与安全架构

### 3.1 本地域名

- Website：`https://demo.junhuiscrewbarrel.com/zh-cn/`、`/en/`
- Admin：`https://admin-demo.junhuiscrewbarrel.com/`
- API/媒体：`https://api-demo.junhuiscrewbarrel.com/`

hosts 仅追加精确域名到 `127.0.0.1`。Nginx 宿主端口仅绑定 loopback，前台不启用 Nginx Basic Auth，后台继续使用应用登录、RBAC、CSRF、Secure Cookie。证书由现有本地 CA 签发并包含三个 Demo 域名。

### 3.2 数据隔离

Demo Compose 使用独立项目名和命名卷，包含 PostgreSQL、Redis、MinIO、API、Website、Admin、Worker 和 Nginx。Demo 不复用主实例卷，不复制主库会话、Privacy、RFQ、凭据或私有媒体。

真实 Logo 与三款产品图只从已批准公开接口或公开对象做只读导出，复制到 Demo 的独立 public-media 桶，并形成新的 Demo 媒体记录；不存在跨库外键。

### 3.3 初始化

普通启动不自动导入 Demo。显式 `demo setup` 执行：基础 seed → 解析受控内容包 → 生成媒体映射 → 调用领域服务创建/更新本批记录 → 走 Translation/Publication/Route/Revision/Audit → 建立关系和首页引用 → 生成校验清单。

初始化通过 manifest 保存别名、实体类型、实体 ID、内容指纹、来源与替换状态。重复执行只补缺项；已人工修改且指纹不一致时跳过并报告冲突。

## 4. 数据模型与 API

优先复用既有 Product、Material、Technology、Application、Solution、CaseStudy、KnowledgeArticle、FAQ、ManufacturingCapability、Equipment、Exhibition、DownloadResource、SEO、GEO、Media、Publication 和 ContentRoute。

最小新增结构：

1. `demo_content_records`：记录批次、别名、实体类型、实体 ID、初始指纹、当前替换状态和来源元数据。
2. `content_media_links`：为各内容实体提供有类型的主图、图库、视频、封面与下载引用，包含排序和用途；媒体本身仍由 MediaAsset 管理。
3. 必要时扩展首页模块配置的媒体引用与选择数量，但不复制业务正文。

新增 Demo 状态/统计 API 必须只在配置明确启用的 Demo 环境工作；生产与主预览默认关闭。后台业务 CRUD 仍使用既有权限、Revision、Audit 和生命周期接口。

## 5. 前台信息架构

### 5.1 首页 14 模块

1. Hero：双语主标题、摘要、双 CTA、主产品媒体或静音可暂停视频。
2. Core Product Families：三类与代表性产品轨道。
3. Materials：材料卡和快速过滤入口。
4. Special Applications：应用场景与产品关系。
5. Technologies：工艺列表与媒体。
6. Manufacturing Capability：能力流程带、设备和质量节点。
7. Why Junhui：演示优势卡，明确示例性质。
8. Factory & Equipment：设备媒体轨道，标注示意。
9. Solutions：问题到方案的入口。
10. Case Studies：虚构案例卡，明确 SAMPLE。
11. Technical Knowledge：文章、FAQ 与下载关联。
12. Certificates/Patents：仅使用设计占位型证明卡，不仿造证书。
13. Global Markets：演示区域图，不声称实际出口记录。
14. RFQ CTA：保留来源参数并进入演示询价流程。

### 5.2 页面族

完整实现产品、分类、材料、工艺、应用、方案、案例、知识、FAQ、About、Contact、下载/视频和 RFQ。列表支持搜索、过滤、分页和空态；详情支持媒体、结构化规格、型号、关系、SEO/GEO 可见内容、下载/视频和相关 CTA。

所有业务正文和媒体来自 Demo API 首次 SSR。固定导航、按钮与错误提示可使用 i18n。页面保持 canonical 指向 Demo origin，并由网关和 HTML 双重 noindex。

## 6. 后台信息架构

### 6.1 应用壳

深色左侧导航按“工作台、内容、媒体与页面、客户、系统”分组。顶栏包含全局搜索、Demo 环境标识、通知占位、用户菜单和会话操作。根路由在登录恢复后必须稳定渲染工作台，不出现空白。

### 6.2 工作台与列表

工作台统计从 Demo 数据库计算：总内容、草稿、待审核、已发布、媒体、询盘和翻译缺口。最近活动来自 Audit。列表包含缩略图、语言、状态、分类、负责人、更新时间、搜索、过滤、分页和真实操作。

### 6.3 编辑器

产品编辑器使用分区导航：基础信息、双语正文、图库/视频、规格、型号、材料/工艺/应用/方案关系、下载、SEO/GEO、发布、历史/Audit。其他内容实体复用统一编辑器框架和对应字段。字段通过选择器关联，不要求手填 UUID。

媒体库支持图片、视频、文件筛选，显示缩略图、尺寸、时长、来源、许可/生成标识和引用位置；支持上传、替换、alt/caption 与 poster 设置。

首页编排器使用模块列表、桌面/移动预览、内容选择和属性面板；保存、刷新、重开、应用和恢复均连接现有 HomepageLayout。

RFQ 列表和详情只展示明确标记的虚构联系人与项目，不启用外部通知。

## 7. 媒体策略

至少创建 18 个互不重复的演示视觉资产，覆盖产品、材料、工艺、应用、设备、案例、知识与地图。所有生成素材保留生成来源、用途、尺寸、hash 和替换状态，并在图片或相邻说明中标注“演示素材/Illustrative”。

至少制作两段 8–15 秒真实 MP4：产品结构展示动效、制造流程示意。视频包含真实帧变化、poster、时长元数据、播放/暂停/拖动控件；不使用外部跟踪服务。首屏媒体尊重 `prefers-reduced-motion`。

## 8. 验收与证据

- 环境：三个域名均进入本机 loopback；无前台 Basic 弹窗；后台匿名受拒；全站 noindex；Sitemap 关闭。
- 数据：90 条内容起始集及关系按实际成功数统计，Demo 与只读真实副本分列；主实例关键冻结项回读不变。
- CMS：至少真实演示改文换图、规格/关系、SEO/GEO、视频、文章发布撤回、首页排序和虚构 RFQ 状态。
- 浏览器：前台 1440/1920/375/430，后台 1366/1440；完整滚动、菜单、筛选、保存、视频和关系链接可操作。
- 视觉：设计候选与浏览器截图按布局、字体、颜色、间距、媒体和状态逐项对照。
- 交付：快捷方式、维护说明、内容/媒体 manifest、报告、截图/录屏或步骤证据、SHA256SUMS 和脱敏 ZIP。

未实际执行的检查标记 `NOT_RUN`，受阻项标记 `BLOCKED`；不把构建通过等同视觉验收。
