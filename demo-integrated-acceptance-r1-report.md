# Demo 整体验收与版本整理 R1 报告

运行编号：`20260911T112621+0800`  
目标环境：`junhui-demo-r2`  
工作区：实际 `phase-3.7` 工作区（目录名仍为 `.worktrees/phase-3.6`）  
结论：`DEMO_BASELINE_READY_FOR_OWNER_REVIEW`

## 1. 结论与边界

本轮在同一份最终代码、同一组最终镜像和同一套常驻 Demo 数据上完成了主前台、后台只读、隔离写链、回归测试、安全保护及仅 Demo 的 Stop/Start。核心流程有当前证据，没有发现 Demo 级阻断；版本可定位，剩余真实资料、政策与生产事项已单独列出，因此可进入所有者集中复验。

这个结论只表示“当前 Demo 基线可供所有者复验”，不表示 Phase 3.7 完成、不表示正式视觉认可、不表示全站 SEO/GEO 获得事实认证，也不表示生产环境可以上线。

## 2. 统一验收版本

- Git 分支：`phase-3.7`
- HEAD：`d86f524f0d973b70c4fef6d76c7a58bd6cfd18f0`
- 迁移 head：`20260910_0016`
- 工作树：13 个 tracked dirty 文件；staged 为 0
- 本轮没有执行 reset、stash、切分支、fetch、stage、commit、tag、push、merge或历史清理
- HEAD 不能代表全部运行实现；最终运行代码由 HEAD、tracked diff、依赖锁与逐文件 SHA-256 共同定位
- 完整文件哈希、镜像摘要和启动配置见 `demo-baseline-manifest.json`

最终 Demo 镜像摘要：

| 服务 | 镜像摘要 |
|---|---|
| API | `sha256:631f22f9363336fdfd3ef68c9e4f9a79afcefd29fd39128370f229b4eb387f4e` |
| Worker | `sha256:ee20ba75673d22f255325b0910cbca4d7303c9c24206d5f2078a0b6bdf7d4f8c` |
| Website | `sha256:a8ff2c42cb516475c53f5f31f9194b4b7b69361683b67ff4fc00cd1dcbc34b9b` |
| Admin | `sha256:096ebd2ff7268bc817d7c94addc52fe79775da7c812613a347957a64d7ea54d4` |

## 3. 本轮有限修复

只处理了当前可复现的限定问题与验收中发现的数据正确性缺陷：

1. 搜索页中文“搜索/清除”按钮禁止换行；英文单条结果改为 `1 result`，多条继续使用 `results`。
2. FAQ 的 GEO 可见来源支持已发布、同语言、启用的真实公开问题和答案；不读取后台备注或私有字段。最终镜像对既有已发布 FAQ 回读为 200。
3. 下载资料创建、更新、归档在事务提交后显式刷新实体，再进行序列化，修复真实 PostgreSQL 下 `updated_at` 过期触发的 `MissingGreenlet` 500。
4. 真实 MinIO 测试模式保留容器提供的 secret，避免测试夹具错误覆盖后产生 `SignatureDoesNotMatch`。
5. 两处迁移测试从旧 head `0015` 更新为当前 `0016`；媒体 API 的导入顺序按 Ruff 修正。

没有重做官网设计、没有扩大搜索类型、没有修改六页新 SEO、没有为搜索改产品名称或演示业务内容，也没有新增模型或业务迁移。

## 4. 主 Demo 前台只读串联

桌面使用 1440×900，手机使用 375×812。所有主链路均由正常浏览器点击执行，没有网络 mock，也没有用直接跳转代替应验的点击。

- 首页返回 200，14 个首页模块存在；19/19 张首页图片完成解码。
- 产品列表从 9 条按机筒类别筛到 2 条，清除后恢复 9 条。
- 真实关系链：产品详情 → PA66 材料 → 知识文章 → 返回产品 → 磨损方案 → RFQ。
- 产品详情显示 5 行规格，2/2 张图片解码。
- Gallery 能打开；打开后焦点进入弹层；Escape 关闭后焦点恢复到触发按钮。
- RFQ 页面可到达，但提交按钮继续禁用；没有创建询盘或上传客户附件。
- 两个既有 WebM 均真实进入播放态约 1.3 秒，`readyState=4`。
- 公开 PDF 正常点击并回读：HTTP 200、`application/pdf`、68,291 字节、文件签名 `%PDF-`。
- 手机导航、产品详情和 RFQ 均可达，375 宽度没有页面横向溢出。
- 最终主链无页面异常、无控制台错误、无失败响应。

另从首页逐一正常点击了产品、解决方案、材料、应用、制造能力、案例、知识、关于、搜索、RFQ、联系和下载 12 个公开入口，全部保持 `demo.junhuiscrewbarrel.com` 同源并显示非空 H1。技术工艺当前不在一级主导航内，氮化工艺已通过搜索结果清单及首次 HTML/详情证据覆盖；本轮没有为了凑入口而改导航。

## 5. 八类搜索

中文查询“演示”返回 46 个唯一“类型+路径”组合，跨 4 页，覆盖：

- 产品
- 材料
- 应用
- 解决方案
- 案例研究
- 技术知识
- 工艺技术
- 制造能力

四页总数均为 46，未发现跨页重复；清除后恢复“输入至少两个字符开始搜索”。英文 `Nitriding` 返回 `1 result`，类型为 `Technologies`，验证了本轮单复数修复。特殊字符、同语言限制、草稿/停用/撤回/noindex/私有字段排除由独立真实 PostgreSQL 回归覆盖。

## 6. 后台只读验收

本轮进入了 20 个主要侧栏页面：网站总览、首页编排、工作台、演示素材、内容目录、客户案例、知识文章、FAQ、作者与专家、企业资料与制造能力、下载、媒体、询盘、语言、用户、角色、产品页 SEO、联系页 SEO、询价页 SEO、隐私版本。

不是只检查列表：产品、案例、知识、FAQ、专家、制造能力、下载、媒体和角色均选择了既有记录并读取实际编辑器。询盘中心只读取数量，不创建或修改记录。1366×768、1440×900、DPR 1 下代表长页无文档横向溢出。

Contact 和 RFQ 后台状态已经分层显示：

- 内容发布状态
- 页面访问状态
- 页面搜索引擎规则
- 环境保护

两页实际仍为 `noindex`：Contact 为 `noindex, nofollow`，RFQ 为 `noindex, follow`；外层 Demo 环境继续全站 `noindex, nofollow`。只修正了显示逻辑和中文词表复用，没有改变页面 SEO 值、robots、发布状态、权限或英文正文。

证据 ZIP 中只放脱敏后台截图：登录账号卡片已遮盖，询盘原始截图、账号、Cookie、Token 和私有数据不在包内。

## 7. 六页 SEO 与代表页

以附件内独立前基线 `20260910T234537+0800` 为准，中英文 About、Contact、RFQ 六页的 title、description、canonical、hreflang 与 robots 逐项一致，没有变化。六页在 Demo 外层响应中均继续返回 `X-Robots-Tag: noindex, nofollow` 与 `Cache-Control: no-store`。

产品、氮化工艺、制造能力、知识文章和案例代表页的首次 HTML 均为 200，正式 canonical 未被 Demo 域替换，适用 JSON-LD 均可解析。知识页的可见 GEO 同时显示“演示编辑部原创样例；无外部研究背书”。

边界：制造能力详情当前首次 HTML 缺少 meta description。本轮是限定整体验收，不扩大为新一轮 SEO 重写，因此登记为后续元数据缺口。JSON-LD 可解析仅表示结构正确，不代表专家身份、技术事实、项目结果或业务承诺已经获得认证。

## 8. 隔离 TEST ONLY 写链

写操作只在 `junhui-integrated-acceptance-r1-test-only` 中进行，使用独立 PostgreSQL 17.6、Redis、MinIO、媒体空间、缓存和端口。QA 后台与 QA 前台属于同一个隔离环境；没有把 QA 后台操作与常驻 Demo 前台拼成一条证据链。

| 写链 | 实际结果 |
|---|---|
| 产品正文、规格、关系 | 保存正文和 TEST ONLY 规格；材料/工艺/应用/方案关系回读；双语审核发布；fresh GET、刷新重开和 QA 前台一致 |
| 文章、FAQ、SEO/GEO | 文章正文、关系、SEO/GEO 与双语生命周期通过；FAQ 答案、关系、SEO/GEO 回读，并由正常展开 FAQ 在 QA 前台看到标记 |
| 媒体、换图、下载 | 媒体 alt/title/caption 回读；产品主图指定位置换图并发布；下载首次暴露真实 500，修复后保存、fresh GET、重开和公开下载页均通过 |
| 首页 | 从 14 模块基线完成草稿、受保护弹窗预览、内建恢复、临时应用、最终恢复；最终回到 14/14 模块 |
| 非系统角色 | 对无用户绑定的 TEST ONLY 角色添加 `media.read`、回读重开，再恢复原权限；没有改系统角色或真实员工 |

每组的前值、操作、保存状态、fresh GET、重开、生命周期和 QA 前台结果都在 `demo-acceptance-matrix.json` 引用的 JSON 证据中。

## 9. 回归与构建

所有通过数字均来自本轮实际运行，不复制历史结果：

| 检查 | 最终结果 |
|---|---|
| API + 独立真实 PostgreSQL 17.6 | 387 passed，0 failed，0 skipped，1 warning，169.40 秒 |
| Website | 16 个文件、157 tests passed |
| Admin | 14 个文件、89 tests passed |
| Typecheck | Website PASS；Admin PASS |
| Prettier format check | PASS |
| Ruff lint | PASS（锁定版本 0.12.11） |
| Build | Website PASS；Admin PASS |
| `git diff --check` | PASS；只有工作副本 LF→CRLF 警告 |
| Ruff format check | **CURRENT_FAIL**：102 个历史文件会被重排，其中 8 个触及文件也继承该格式债务 |

API 首次全量运行是 384 passed、3 failed、1 warning。三个失败分别是两处旧迁移 head 断言和测试夹具覆盖真实 MinIO secret；修复后从头执行得到最终 387 passed。Ruff format 的 102 文件属于既有全库格式债务；为遵守本轮限定范围，没有自动重写全库。

## 10. 数据与安全边界

主 Demo 前快照使用 PostgreSQL 17.6 custom archive 创建并验证，但位于私有目录，不进入证据 ZIP。为避免普通 dump 文件排序导致的伪差异，本轮把前快照还原到隔离 PostgreSQL，并对 93 个非认证、非审计、非 RFQ 业务表逐表计算“计数 + 规范 JSONB 排序哈希”。前后聚合 SHA-256 均为：

`2be287a92c017273fd7fb79d99cbac51e3f0ea5fff610666d70eef4cbdc0532d`

93 个表的计数与哈希全部一致，证明本轮没有修改主 Demo 业务内容。后台登录可能产生认证会话、最后登录时间和审计记录，这是已声明的必要安全副作用；RFQ 私有表没有参与公开内容证据或业务哈希判定。

持续保护最终复核：

- HTTPS 与 TLS SAN/CA：PASS
- 唯一宿主监听：`127.0.0.1:443`
- 前台无 Basic Auth 弹窗
- 后台登录、RBAC、CSRF 保持
- 全站 `noindex, nofollow` 与 `no-store`
- Sitemap：404
- Privacy：404（未批准、不发布）
- RFQ：页面可预览、提交禁用

## 11. 安全重开与最终运行状态

只对 `junhui-demo-r2` 执行了一次 Stop/Start，保留数据卷和共享网关；没有运行迁移、Restore 或默认 Seed。原 `junhui-phase37-pilot` 业务服务没有重建、停止或修改，其启动时间早于本轮运行。

最终 `junhui-demo-r2` 的 PostgreSQL、Redis、MinIO、API、Worker、Website、Admin 均健康；`minio-init` 按一次性任务正常退出 0。中英文首页、后台登录页和 API health 返回 200；Sitemap 与 Privacy 返回预期 404。Demo 已保持运行，等待所有者复验。

## 12. 剩余事项

不会阻断本轮 Demo 所有者复验，但会阻断生产或正式接单的事项：

1. Privacy 正式政策、版本批准、公开指针、留存与 DSAR 流程。
2. RFQ 正式启用、附件生命周期、恶意文件扫描、真实邮件链和业务责任人。
3. 演示文字、虚构案例、生成式素材、示例 PDF、设备/能力/市场等事实替换与批准。
4. 制造能力详情 meta description 缺口。
5. 全库 Ruff format 的 102 文件历史格式债务。
6. 生产 DNS、基础设施、备份恢复演练、监控、Analytics、外网性能和部署。
7. Safari/Firefox、Lighthouse 和真实 Core Web Vitals 本轮未测。

详细对象/字段替换地图和上线阻塞见 `project-status-and-launch-blockers.md`；所有者复验步骤见 `demo-owner-walkthrough.md`。

## 13. 交付与证据

- `demo-integrated-acceptance-r1-report.md`
- `demo-baseline-manifest.json`
- `demo-acceptance-matrix.json`
- `project-status-and-launch-blockers.md`
- `demo-owner-walkthrough.md`
- `Junhui-Demo-Integrated-Acceptance-R1-Evidence-20260911T112621+0800.zip`
- `Junhui-Demo-Integrated-Acceptance-R1-Evidence-20260911T112621+0800.sha256`

证据包含当前运行清单、实际查询结果、正常点击结果、脱敏后台状态截图、隔离写链、回归与构建结果、文件清单及 SHA-256；不含密码、Token、Cookie、私有数据库快照、私有备份、未脱敏询盘截图或附件输入包。
