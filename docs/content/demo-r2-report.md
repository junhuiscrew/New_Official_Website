# Demo R2 完整官网与后台实施报告

## 1. 结论

Demo R2 已在独立、持久、仅本机可见的环境中完成。它提供完整中英文官网、14 个有内容的首页模块、可操作后台、真实媒体库、两段可播放视频、产品/材料/工艺/应用/方案/案例/知识/About/Contact/下载/RFQ 页面，以及数据库持久化的内容、关系、SEO/GEO、Revision/Audit 和发布生命周期。

本报告不构成生产上线许可。全部新增业务事实均为 Demo；原 phase37 已批准 Company/Product/SEO/Privacy 数据没有被演示数据覆盖。未执行 commit、push、merge、公共 DNS 修改、云部署、Analytics、真实 RFQ、附件上传或邮件发送。

## 2. 实际目标与版本

| 项目 | 实际值 |
|---|---|
| 工作区 | `D:\Python_Project\New_Official_Website\junhui-global-website\.worktrees\phase-3.6` |
| Git 分支 | `phase-3.7` |
| 实施基线 HEAD | `86f7defb911e3fcd422e935f7c7d959d882898d5` |
| 自动提交/推送/合并 | 未执行 |
| Demo Compose 项目 | `junhui-demo-r2` |
| 共享本机入口 | `junhui-phase37-pilot` Nginx |
| Demo batch | `JH-DEMO-R2-V1` |
| 迁移 head | `20260909_0015` |
| API 运行版本 | `0.5.0-demo-r2` |
| Docker / Compose | 29.7.2 / v5.3.1 |
| 证据 run id | `20260909T162617+0800` |

## 3. 实际地址

- 中文完整官网：<https://demo.junhuiscrewbarrel.com/zh-cn/>
- 英文完整官网：<https://demo.junhuiscrewbarrel.com/en/>
- 后台：<https://admin-demo.junhuiscrewbarrel.com/>
- 首页模块编辑器：<https://admin-demo.junhuiscrewbarrel.com/homepage>
- 演示媒体管理：<https://admin-demo.junhuiscrewbarrel.com/demo-media>
- 产品编辑器：<https://admin-demo.junhuiscrewbarrel.com/catalog/products>
- 媒体库：<https://admin-demo.junhuiscrewbarrel.com/media>
- SEO/GEO 可在对应产品、分类、案例、文章及固定页面编辑流程中维护。
- 认证完整布局预览：<https://admin-demo.junhuiscrewbarrel.com/preview/zh-cn/>

桌面快捷方式：`C:\Users\pc\Desktop\打开骏辉完整演示站.lnk`。

## 4. 环境隔离与安全

- Demo 使用独立 `postgres_demo_r2_data`、`minio_demo_r2_data`、`redis_demo_r2_data` 数据卷。
- Demo Admin/API/Website/数据库/对象存储没有宿主直出端口；共享 Nginx 是唯一的 `127.0.0.1:443` 入口。
- `demo`、`admin-demo`、`api-demo` 三个域名均解析到 `127.0.0.1`，代理使用精确 DIRECT/本地解析规则；VPN 验收期间保持开启。
- 证书由已有受信本地 CA 签发，SAN 校验通过，没有关闭 TLS 验证。
- 前台无 HTTP Basic 弹窗；后台保留应用登录、RBAC、CSRF、Secure Cookie。
- 前台、后台、API 均返回 `X-Robots-Tag: noindex, nofollow`；Sitemap 实测 404。
- 响应带 `X-Junhui-Local-Preview: demo-r2-loopback-only`，证明进入本机 Demo 网关。
- 匿名 `/api/v1/auth/me`、作者完整布局预览、媒体 API 和私有附件 URL 签发均实测 401。
- 已执行一次 `Stop`/`Start`：数据卷保留，原 phase37 预览继续运行，最终 Demo 七个常驻服务均 healthy。

## 5. 数据与媒体结果

内容源 `demo-content-v1.json` SHA-256 为 `E0108BA4B9A57C428EA90B2455BAE2156C0BF1C9CB305BC28F6607EBF3632260`。

| 指标 | 实际回读 |
|---|---:|
| Demo 内容记录 | 90 |
| 源关系 | 72 |
| 最终业务关系 | 73 |
| 媒体对象 | 48（43 图、2 视频、3 PDF） |
| checksum verified / ready | 48 / 48 |
| 内容—媒体关联 | 67 |
| 双语发布记录/Route | 112 / 112 |
| Revision | 258，覆盖 170 个 owner identity |
| Audit | 1041 |
| Demo RFQ | 12；四种状态各 3 条 |
| Privacy page/current | 0 / 0 |

源关系 72 条幂等导入后，真实 Admin 的产品关系编辑演示产生 1 条新增关系和较晚的 `relation.change` Audit，故最终为 73；不是重复导入。Demo RFQ 全部标记为虚构，没有真实客户资料、附件或邮件。

媒体包括 3 张已批准产品图的只读副本、40 张生成式演示图片/裁切图、2 段真实 WebM 和 3 个演示 PDF。浏览器实际播放时两段视频的可读时长分别约 12.20 秒和 12.36 秒，时间均推进超过 1.2 秒，`readyState=4`。

## 6. 前台呈现

采用用户选择的 A 方向：深海军蓝工业展厅风，蓝白高对比排版、技术网格、产品大图、紧凑导航与模块化长页面；没有另建 React 站点，继续使用现有 Nuxt/Vue/FastAPI。

原设计画布未在包内找到，因此本轮先制作并明确标识为“新候选”的完整前台/后台概念图，再以同尺寸真实页面截图对照，不冒充用户此前批准的旧画布。

首页 14 项均具备 renderer、配置入口和有意义 Demo 内容：Hero、Core Product Families、Materials、Special Applications、Technologies、Manufacturing Capability、Why Junhui、Factory & Equipment、Solutions、Case Studies、Technical Knowledge、Certificates/Patents、Global Markets、RFQ CTA。

统计分开记录：

- 组件完成：`14/14`；
- Demo 数据真实可见：`14/14`；
- 含至少一项仍待真实资料替换/核准的模块：`14/14`。

这不是用 14/14 掩盖资料缺口。现有真实 Logo 与三张已批准产品图只读复用，其余产品事实、规格、工厂、设备、产能、出口、客户、案例、证书、专利、作者和技术结论均仍是 Demo。

中英文各 13 个核心栏目页面，共 26 个 URL，真实浏览器均返回 200 和 noindex。另验证：

- 产品详情 zh→en→zh 均留在 Demo 域名；
- 中文“通用”搜索返回 DEMO-S01；
- 产品分类筛选从 9 条收敛到 6 条；
- Gallery 打开、Escape 关闭、关闭按钮聚焦和触发器焦点恢复；
- 375px 移动菜单、产品二级菜单、语言切换；
- RFQ 入口可达，但提交按钮禁用，没有发出请求；
- 两段视频均是真实可播放 WebM，不是 poster、假 URL 或伪扩展名。

## 7. 后台呈现与真实编辑

修复并统一了 Admin 登录页、工作台、侧栏、目录、产品、Company/信任、案例、知识、FAQ、媒体、下载、询盘、SEO/GEO 和首页编辑器视觉。产品列表支持分页、中文/英文名称与 slug 搜索、分类/状态过滤、缩略图；关系选择器显示可读名称与 slug，不把 UUID 或 JSON 输入作为日常界面。

已真实完成并回读以下操作：

1. 首页排序→保存草稿→刷新重开→作者预览→应用；另做隐藏/恢复模块和三款产品引用选择。
2. DEMO-C01 修改双语文案、主图、规格值和关系，保存并发布到隔离 Demo，首次 SSR 显示变化。
3. 知识文章完成正文、双语 SEO/GEO、发布/撤回生命周期演示并重新打开回读。
4. 演示媒体槽位替换图片/视频并保存，前台随后播放实际对象。
5. 12 条虚构询盘在后台按 `new`、`in_progress`、`waiting_customer`、`closed` 四组各 3 条展示；没有发送邮件。

数据库最终回读包含 258 条 Revision 与 1041 条 Audit，覆盖上述编辑、生命周期、关系和媒体动作。匿名无法取得作者预览；认证预览返回 200、14 模块、`no-store` 和 noindex。

## 8. 设计与实际页面对照

| 画布/实际页面 | 尺寸 | 人工检查结果 |
|---|---|---|
| 新前台候选概念图 | 设计候选 | 深海军蓝、技术网格、蓝白工业基调已进入实现 |
| 中文/英文首页 | 1440px 完整滚动 | 模块节奏、Hero、图片、视频与 CTA 正常 |
| 中文/英文首页 | 375px / 430px 完整滚动 | 无阻塞溢出，标题、图片和续屏节奏正常 |
| 后台工作台/媒体/首页 | 1440px | 导航、卡片层级、缩略图和操作入口一致 |
| 后台产品/目录/知识 | 1366px | 编辑字段、筛选、关系和生命周期可操作 |

概念图位于 `docs/design/demo-r2/concepts/`，真实截图位于本轮证据包。完整长图之外还保留 Hero 和移动端上/中/下分段图，避免应用预览对超长 PNG 的缩放影响判断。

## 9. 回归测试

| 检查 | 实际结果 |
|---|---|
| API 全量真实 PostgreSQL/Redis/MinIO | PASS：367 passed，0 failed，0 skipped，1 warning，135.46s |
| Ruff | PASS：`All checks passed!` |
| Website Vitest | PASS：14 files，147 passed |
| Admin Vitest | PASS：10 files，62 passed |
| Website / Admin typecheck | PASS / PASS |
| Website / Admin build | PASS / PASS |
| Prettier `format:check` | PASS |
| Playwright 本地域名验收 | PASS：26 页面、14 模块、2 视频及关键点击 |

API 唯一 warning 是 Starlette/AnyIO 依赖级弃用提示。Nuxt 构建存在依赖/plugin timing 与 deprecated export 提示，但两个构建均成功；这些 warning 未写成失败，也未被隐藏。

初次 API 全量测试曾暴露测试镜像遗漏 Demo fixture 和迁移 head 断言陈旧；修复 Docker build context、Dockerfile fixture 复制及迁移测试后，目标回归和最终 367 项全量均通过。未沿用旧测试数量。

## 10. 未执行与保留边界

- `NOT_RUN`：生产部署、公共 DNS、腾讯云/NAS、Gmail/SMTP、Analytics、搜索引擎提交、真实 RFQ、真实附件和邮件。
- 原 Privacy 仍未发布；Demo `privacy_state=0`，RFQ 正式提交保持禁用。
- 本轮没有把 Demo 资料写回原 phase37 业务库，也没有改变原批准 SEO/COPY-V1。
- Git 保留已有提交和当前未提交工作；未自动 commit、push 或 merge。
- 私有快照、凭据、Cookie、TLS 私钥和数据库连接资料仅留本机，未进入证据 ZIP。

## 11. 交付物

- 本报告：`docs/content/demo-r2-report.md`
- 后台维护说明：`docs/content/demo-r2-maintenance-guide.md`
- 内容/媒体/替换清单：`docs/content/demo-r2-content-media-manifest.md`
- 新候选设计：`docs/design/demo-r2/concepts/`
- 脱敏证据：`data/demo-r2/evidence/20260909T162617+0800/`
- 最终 ZIP：`Junhui-Demo-R2-Evidence-20260909T162617+0800.zip`

Demo R2 当前保持运行，等待用户进行前台与后台视觉复验；本轮不宣布 Phase 3.7 完成或具备生产上线资格。
