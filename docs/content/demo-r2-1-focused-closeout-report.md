# Demo R2.1 定向收尾报告

## 1. 结论

本轮仅在持久本地 Demo 环境 `junhui-demo-r2` 中完成前后台视觉与可维护性收尾。五项 `DR2-UI` 发现均已按限定范围处理并完成真实浏览器回读；没有清库、重新导入、切换到 Privacy、连接生产、提交 RFQ、发送邮件、修改公共 DNS，亦未执行 commit、push 或 merge。

可直接验收：

- 中文站：`https://demo.junhuiscrewbarrel.com/zh-cn/`
- 英文站：`https://demo.junhuiscrewbarrel.com/en/`
- Demo 后台：`https://admin-demo.junhuiscrewbarrel.com/`
- 后台目录中心：`https://admin-demo.junhuiscrewbarrel.com/catalog`
- 后台首页编排：`https://admin-demo.junhuiscrewbarrel.com/homepage`

## 2. 实际目标与版本

| 项目 | 实际值 |
| --- | --- |
| 工作区 | `D:\Python_Project\New_Official_Website\junhui-global-website\.worktrees\phase-3.6` |
| 分支 | `phase-3.7` |
| 基线 HEAD | `c07a32355ee937badd67140ade4b844c7798d759` |
| 数据库迁移 head | `20260909_0015` |
| Demo API 镜像 | `sha256:1a4626bdfd0e46eb9821f96fa345a6b6b73d0d5df4ae3d062c81d958e0a41eb8` |
| Demo Admin 镜像 | `sha256:cdacdf9bd8e2248c7798852ac8080f446699d46974f46a52b3b4cb2d9f0bfd19` |
| Demo Website 镜像 | `sha256:391ce3ab785e124359941eb22f3175b924e4628391f63dce9ed1584b33ab1156` |
| 03 指令 SHA-256 | `C63D0B145E406982BC3599E5A89FE37004438B2EFE2736AB2D7A768FB8EBF33F` |
| Demo 内容源 SHA-256 | `E0108BA4B9A57C428EA90B2455BAE2156C0BF1C9CB305BC28F6607EBF3632260` |
| 私有更新前数据库快照 | `data/demo-r2/private/backups/demo-r2-before-r21-20260909T152500.dump` |
| 快照 SHA-256 | `6D651FC765E4C855638675A6C16273D7386FDA8870DEFAC51E43BD491D41373C` |

快照保留在私有目录，未放入脱敏证据包或 Git。开始时仅有用户原有的未跟踪文件 `交接文档-新对话.md`，本轮未修改该文件。

## 3. 五项发现状态

| Finding | 状态 | 实际处理与证据 |
| --- | --- | --- |
| DR2-UI-01 `/catalog` 仍为 Phase 3.3 占位入口 | **FIXED** | 改为中文结构化内容中心；显示 7 个模块、真实数量、搜索和维护入口。实际截图 `admin-catalog-1440.png`。 |
| DR2-UI-02 产品参数缺少名称、单位和类型 | **FIXED** | 产品编辑器回读规格组、双语名称、代码、类型、单位和当前值，并按 number/range/enum/boolean/text 使用对应控件。代表记录 `DEMO-S02` 的 5 项值均由真实定义和值组装。截图 `admin-product-s02-specifications.png`。 |
| DR2-UI-03 已有知识文章选中后正文为空 | **FIXED** | 先复现后确认数据库、详情 API 和正文均未丢失；原截图属于选中记录与异步详情回填之间的时机。增加显式加载态、请求防串线和禁用态；真实修改文章、保存、刷新、重开及首次 SSR 均成功。 |
| DR2-UI-04 后台 Hero/编辑器过长，首页/About 设计不足 | **FIXED（R2.1 范围）** | 压缩工作台 Hero；首页编排改为紧凑模块列表、属性面板、受认证预览与操作栏；首页 Materials、Applications、Technologies、Why Junhui 使用差异化布局；About 增加公司概览、产品视觉轨道、市场目录、工作原则和联系面板。 |
| DR2-UI-05 Demo 产品图片与对象不符 | **FIXED** | 仅调整 5 个 Demo 产品主图引用，并完善 4 张生成图的双语 Alt/标题/图注；所有受影响产品恢复正常 Demo 生命周期，列表、详情与 Gallery 使用一致资源。 |

“FIXED”只表示本轮五项定向发现已处理，不表示 Phase 3.7、Privacy 或生产上线完成。

## 4. 工程修改

### 4.1 Admin

- `catalog/index.vue`：替换工程占位文案，提供 7 个真实模块、数量、筛选和入口。
- `catalog/products.vue`：规格定义/分组水合，五种数据类型专用输入，清晰呈现名称、类型、单位、当前值；编辑区增加基础信息、正文、媒体、规格、关系和生命周期分组导航。
- `AuthorityCrud.vue`：记录点击后立即进入明确加载态；使用请求标识防止快速切换时旧响应覆盖新记录；详情未完成前禁用表单。
- `media.vue`：增加媒体详情读取、双语 Alt/标题/图注的稳定回填、保存、fresh GET 与重新打开。
- `index.vue`：缩小宣传 Hero，让统计、流程和常用操作进入 1440×1000 首屏。
- `homepage.vue`：改为紧凑三栏工作区，复用既有 API 与认证预览，不建立第二套 CMS。

### 4.2 API

- 新增受 `media.read` 权限保护的 `GET /api/v1/media/{asset_id}`。
- 返回公开安全媒体字段和各语言 Alt/标题/图注，不返回对象存储桶、对象键、签名 URL 或凭据。
- 继续拒绝匿名访问；实测匿名请求为 HTTP 401。

### 4.3 Website

- 首页 14 个既有模块全部保留，针对 Materials、Applications、Technologies、Why Junhui 等减少重复卡片表达并增加差异化结构。
- About 使用既有公司 API 与前三个产品 API 数据形成完整滚动页面；没有新增真实经营、客户、资质或产能结论。
- 375px/430px 长页无横向溢出；首页 19 张图片逐张触发惰性加载后 `naturalWidth > 0`。

## 5. 三组可读编辑证据

所有内部 UUID 在分享材料中以一致别名替代。

### 5.1 产品：`P-DEMO-S02`

| 项目 | Before | After |
| --- | --- | --- |
| 业务键 | `DEMO-S02 / demo-s02` | 不变 |
| 主图 | `approved-product-02.webp`，内容为机筒，不符合耐磨螺杆对象 | `generated-01.jpg`，螺杆表面与螺棱近景 |
| 规格编辑显示 | 值和输入框缺乏明确名称/类型/单位上下文 | 5 项均显示组、名称、代码、类型、单位、当前值，并按类型渲染 |
| 保存 | — | Admin PATCH HTTP 200；fresh GET 返回新主图 |
| 重开 | — | 后台重新打开仍为 `generated-01.jpg`，5 项参数值不变 |
| 前台 | 图片语义不匹配 | 中文详情 HTTP 200；图片 1200×900；Alt 为“螺杆表面与螺棱近景（DEMO示意素材）”；Gallery 打开/关闭及焦点返回均通过 |

Fresh GET 的 5 项参数：

| 名称 | 类型 | 单位 | 当前值 |
| --- | --- | --- | --- |
| 样例直径 / Sample diameter | number | mm | 45 |
| 样例长度区间 / Sample length range | range | mm | 850–1050 |
| 图纸状态 / Drawing status | enum | 无 | 示例文件 / Example document |
| 支持定制示例 / Customization sample | boolean | 无 | 是 / true |
| 说明 / Note | text | 无 | 仅用于界面演示，不用于选型或生产 / UI demonstration only; not for selection or production |

保存产品主图会按既有规则使两个语言生命周期失效。本轮通过真实 Admin 流程对 5 个受影响 Demo 产品分别完成双语 review/publish，最终 10 个 TranslationStatus 与 10 个 Publication 均为 `published`，10 条 Route 均恢复 `active=true`。这是 Demo 环境的正常生命周期恢复，没有批量重导。

### 5.2 知识文章：`A-DEMO-ART-01`

| 项目 | Before | After |
| --- | --- | --- |
| 复现 | 选中 `demo-art-01` 后等待详情完成，Slug、双语标题/摘要/正文及关系均有值；数据库内容未丢失 | 显式加载态消除“左侧已高亮、右侧像空新增表单”的截图歧义 |
| 中文正文 | 原正文以“来源说明”结束 | 追加“后台维护验证”段，说明由真实后台保存并回读 |
| 英文正文 | 原正文以 “Source note” 结束 | 追加 “Admin maintenance check” 段 |
| 保存 | — | Admin PATCH HTTP 200；fresh GET 含两段新增内容 |
| 重开 | — | 刷新并重新选择后两种语言正文均完整 |
| 前台 | — | 中英文详情首次 SSR HTML 与最终渲染均包含各自验证段，HTTP 200 |

文章更新后按既有生命周期执行双语 review/publish。最终中英文 TranslationStatus、Publication 均为 `published`，Route 均为 `active=true`；外层仍由 Demo 网关统一返回 `X-Robots-Tag: noindex, nofollow`。

### 5.3 媒体：`M-GENERATED-01`

| 项目 | Before | After |
| --- | --- | --- |
| 文件 | `generated-01.jpg`，1200×900 | 文件、尺寸和媒体对象不变 |
| 中文 Alt | 生成式工业演示视觉，不代表真实工厂、客户、证书或设备型号 | 螺杆表面与螺棱近景（DEMO示意素材） |
| 中文标题/图注 | 无针对性标题/图注 | 螺杆近景演示图；生成式螺杆近景，仅用于演示页面布局和后台替换流程。 |
| 英文 Alt | Generated industrial demo visual; not real factory, customer, certificate or equipment evidence | Screw surface and flight close-up (generated DEMO illustration) |
| 英文标题/图注 | 无针对性标题/图注 | Screw close-up demo image；Generated screw close-up for demonstrating page layout and the admin replacement workflow. |
| 保存与回读 | — | 两语言 PATCH 均 HTTP 200；fresh GET、后台重新打开与产品前台图片一致 |

同样完善了 `generated-02.jpg`、`generated-03.jpg`、`generated-05.jpg` 的双语语义元数据；共 8 次 `media.translation_update` Audit。

## 6. Demo 产品配图核验

| 产品 | 最终资源 | 页面结果 |
| --- | --- | --- |
| DEMO-S02 耐磨选型螺杆 | `generated-01.jpg` 螺杆近景，1200×900 | HTTP 200 |
| DEMO-S06 实验型双螺杆组件 | `generated-02.jpg` 双螺杆组件，1200×900 | HTTP 200 |
| DEMO-B01 耐磨机筒 | `approved-product-02.webp` 已批准机筒图，700×700 | HTTP 200 |
| DEMO-B02 模块化挤出机筒 | `generated-03.jpg` 机筒内孔近景，1200×900 | HTTP 200 |
| DEMO-C01 配套止逆组件 | `generated-05.jpg` 金属组件组合，1200×900 | HTTP 200 |

五页均实测 H1、Alt、图片自然尺寸与 `X-Robots-Tag`。没有修改原 phase37 的三款批准产品素材。

## 7. Revision / Audit 摘要

按实际内容写入窗口 `2026-09-09 12:30:00Z` 之后汇总：

- ContentRevision：`product=15`、`knowledge_article=3`。
- 产品：`product.update=5`、`translation.edited=10`、`translation.review=10`、`publication.invalidated_by_translation=10`、`publication.status_change=10`、`route.change=10`。
- 知识文章：`knowledge_article.update=1`、`relations.replace=1`、`translation.review=2`、`publication.invalidated_by_translation=2`、`publication.status_change=2`、`route.change=2`。
- 媒体：`media.translation_update=8`。

汇总不包含账号、用户 ID、IP、Cookie 或 Token。

## 8. 数据与隔离检查

### Demo 数据库

- `demo_content_records=90`
- `media_assets=48`
- `products=9`
- `knowledge_articles=8`
- `rfqs=12`（原有明确标记的 Demo 虚构询盘，本轮未新增询盘）

### 原 phase37 数据库

- `products=4`
- `media_assets=7`
- `product_spec_values=0`
- `rfqs=0`
- 原实例不存在 Demo 专用 `demo_content_records` 表；本轮数据操作全部发生在 `junhui-demo-r2-postgres-1`。

### 入口保护

- 宿主仅监听 `127.0.0.1:443`；Demo API/Admin/Website/PostgreSQL/Redis/MinIO 没有新增宿主直出端口。
- 中文首页 HTTP 200、无 `WWW-Authenticate`，因此不会出现 Nginx Basic 弹窗。
- 页面统一 `X-Robots-Tag: noindex, nofollow`。
- `/sitemap.xml` 实测 HTTP 404。
- 无后台会话访问 `/api/v1/media` 实测 HTTP 401，且不是 HTTP Basic 认证挑战。
- 移动语言菜单由英文首页实际点击到 `https://demo.junhuiscrewbarrel.com/zh-cn/`，主机名保持本地 Demo 域名。

## 9. 真实视觉验收

已查看而不只是生成以下截图：

- Admin 1440：目录中心、工作台、首页编排、知识文章重开、媒体重开。
- 产品规格：名称、类型、单位、当前值与对应输入控件同屏。
- Website 1440：中文完整首页、About、Products、S02/B02/C01、知识文章、Gallery。
- Website 375/430：中文首页、中文 About、英文首页完整滚动。

结果：375px 与 430px 页面 `scrollWidth === viewport width`；中文/英文首页各 19 张图片最终全部真实加载；Gallery 可打开、Esc 关闭并把焦点返回触发按钮。

## 10. 测试与构建

| 检查 | 实际结果 |
| --- | --- |
| Admin Vitest | 10 files / 66 tests passed |
| Website Vitest | 14 files / 148 tests passed |
| API 专项 Pytest | 5 passed（媒体详情权限/回读及公开 DTO） |
| Admin typecheck | PASS |
| Website typecheck | PASS |
| Ruff（2 个受影响 Python 文件） | PASS |
| Prettier（12 个受影响前端/测试文件） | PASS |
| Admin `nuxt build` | PASS |
| Website `nuxt build` | PASS |

构建仍输出 Node 对尾随斜杠 exports 映射的 `DEP0155` 弃用警告；本轮没有把该既有依赖警告误写为无警告。

## 11. 交付与未执行项

- 报告：`docs/content/demo-r2-1-focused-closeout-report.md`
- 脱敏回读与截图：`data/demo-r2/evidence/demo-r2-1-20260909T152500+0800/share/`
- ZIP：`Junhui-Demo-R2.1-Focused-Closeout-Evidence-20260909T152500+0800.zip`

明确未执行：commit、push、merge、生产部署、公共 DNS 修改、Privacy 发布、真实 RFQ、附件上传、邮件、Analytics、数据清理或重新 Seed。
