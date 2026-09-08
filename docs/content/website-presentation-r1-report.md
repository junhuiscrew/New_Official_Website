# 官网呈现 V1.0 · R1 实施报告

- 执行批次：`20260908T204522+0800`
- 项目：`junhuiscrew/New_Official_Website`
- 工作区：`phase-3.7`（既有 `phase-3.6` worktree）
- 基线 HEAD：`995d1ce162964adbffd64bde18e5c58e47099086`
- 代码状态：基线 HEAD 加本地未提交工作；本轮未 commit、push、merge
- 唯一运行目标：`junhui-phase37-pilot` / `phase37-local-https`
- 结果：本地实现、迁移、配置应用、可视预览和验收均已完成；没有生产上线或 Privacy 发布

## 1. 最终结果

本轮已交付新的双语首页、十四模块共享渲染器、双语首页模块编辑器、认证“完整布局预览”和全站模块总览。普通首页只显示已批准且符合公开门禁的内容；认证预览显示全部十四个位置，并对缺件给出真实原因和管理入口。

三个数字必须分开理解：

- 组件已完成：`14/14`
- 普通首页实际有内容并可见：`4/14`
- 仍缺已发布资料：`10/14`

没有用“14/14”掩盖空内容，也没有创建厂房、客户、资质、产能、出口市场或其他新业务事实。

## 2. 实施前盘点与实施后状态

| 原定模块 | 实施前实际状态 | R1 后组件/配置 | 普通首页真实内容 | 缺件或数据源 |
| --- | --- | --- | ---: | --- |
| Hero | 有公司与产品内容，旧首页呈现偏空 | 已完成 | 1 | CompanyProfile + 三款已发布产品图 |
| Core Product Families | 有分类/产品，缺完整呈现节奏 | 已完成 | 1 | screws、barrels、P01/P02/P03 |
| Materials | 有模型/路由/后台模板，无公开记录 | 已完成 | 0 | 缺已发布材料记录 |
| Special Applications | 有模型/路由/后台模板，无公开记录 | 已完成 | 0 | 缺已发布应用记录 |
| Technologies | 有独立模型、API、后台与前台路由，无公开记录；并非单纯“被隐藏” | 已完成 | 0 | 缺已发布技术记录 |
| Manufacturing Capability | 有模型/API/后台/路由，无公开记录 | 已完成 | 0 | 缺已发布制造能力记录 |
| Why Junhui | 有已批准 Company full_intro | 已完成 | 1 | CompanyProfile |
| Factory & Equipment | 有独立设备模型/后台，无公开记录 | 已完成 | 0 | 缺已发布设备记录 |
| Solutions | 有模型/路由/后台模板，无公开记录 | 已完成 | 0 | 缺已发布解决方案记录 |
| Case Studies | 有模型/API/后台，无公开记录 | 已完成 | 0 | 缺已发布案例记录 |
| Technical Knowledge | 有模型/API/后台，无公开记录 | 已完成 | 0 | 缺已发布知识内容 |
| Certificates / Patents | 有独立模型/API/后台，无公开记录 | 已完成 | 0 | 缺已发布证书/专利记录 |
| Global Markets | Company 实体存在，但 export_markets 为空 | 已完成 | 0 | 缺已批准市场事实 |
| RFQ CTA | 有真实入口 | 已完成 | 1 | 入口可用；正式提交因无当前已发布 Privacy 版本而禁用 |

额外栏目：

- `Technologies`：单独列示为“能力存在、公开内容为 0、未进入主导航注册表”，没有笼统归为隐藏。
- `Contact`：没有独立 Contact 正文页；当前只有 RFQ/页脚入口，公开 Company 联系字段为空。全站总览单独列示为 `contact_entry_only`。

## 3. 工程实现

### 3.1 数据与 API

- 新增固定 `SitePage(system_key=home)`，使用真实 UUID；不借用 Company、Product 或假记录。
- 新增 `homepage_layouts`，按语言保存草稿与应用版 JSONB、Revision、操作者和应用时间。
- 追加迁移 `20260908_0014_homepage_presentation_r1.py`，历史迁移未修改。
- 新增首页配置 API：初始化、详情、草稿保存、应用、恢复、认证预览、全站总览。
- 继续使用 `content.read`、`content.update`、`content.publish`、CSRF、`ContentRevision` 和 `AuditLog`。
- 草稿更新使用 `expected_revision` 乐观并发；冲突返回 409，不覆盖其他修改。
- Hero 和 Core Product Families 只允许从公开产品候选中选择最多三款 slug；不改变 `Product.featured` 或产品关系。

### 3.2 Website

- 使用 Nuxt/Vue/FastAPI 原架构完成蓝白现代科技制造风完整首页。
- Hero 使用已批准公司名、short_intro 和三款现有产品图；没有修改 COPY-V1。
- 普通首页按应用版顺序，只渲染 `visible && content_status=available` 的模块。
- 认证预览复用同一 `HomePage` / `HomepagePresentation` 组件，显示全部十四模块和真实空态。
- 修复 Hero 内外嵌套 `figure` 选择器，三张产品图不再被裁成 2px 横线。
- 认证预览最终 meta 为 `noindex, nofollow`，并保留正式 canonical/hreflang 数据规则。

### 3.3 Admin

- 新增 `/homepage` 双语可视编辑器：排序、显隐、有限 variant、现有产品引用、保存草稿、打开预览、应用布局、从应用版恢复。
- 不要求输入 UUID 或 JSON。
- 新增 `/site-overview`：展示真实前台/后台 URL、实际记录数、公开数量、导航状态、实现状态和隐藏原因。
- 权限导航只对 `content.read` 用户显示；写入和应用权限继续由 API 强制。
- 认证导航放入客户端确认区域，直接 `/login`、登录后的 `/homepage` 和认证预览最终控制台均为 0 error。

### 3.4 本机 Nginx

- 认证预览位于 Admin 同源 `/preview/{lang}/`，由 Website SSR 把 Admin Host-only Cookie 转交 API 验证。
- 增加 `/preview-assets/_nuxt/` 与 `/preview-assets/brand/`，只重写预览 HTML 资源路径，避免与 Admin 自身 `/_nuxt` 冲突。
- 预览响应保持 `private, no-store` 与 `X-Robots-Tag: noindex, nofollow`。
- 普通网站、Admin 和 API 规则未放宽；宿主仍只有 `127.0.0.1:443`。

## 4. 迁移、快照与运行版本

- 迁移前主库：`20260908_0013`
- 当前主库：`20260908_0014`
- 迁移前私有备份：`phase37-pre-0014.pg.dump`
- 备份大小：`541354` bytes
- 备份 SHA-256：`AD24DEAC9E5C9ACA358A8038F056EAE3A35D6B8E639C33C961B1F8964BE11F53`
- 备份保存在私有审计目录，未进入 Git 或分享 ZIP。
- 独立 PostgreSQL 16：空库全迁移至 0014、约束和 Seed 验证通过。
- PostgreSQL 16 无法读取 PostgreSQL 17 custom dump（真实记录为工具版本不兼容）；随后使用无宿主端口的临时 PostgreSQL 17 完成备份恢复与对比。
- 主实例只执行 Alembic upgrade；没有运行默认 migration/Seed 组合、清卷或重导业务数据。

当前服务均健康：API、Admin、Website、Nginx、PostgreSQL、Redis、MinIO、Worker；只有 Nginx 暴露 `127.0.0.1:443->443/tcp`。

## 5. 配置 Revision / Audit

| 语言 | 最终草稿 Revision | 应用 Revision | 最终草稿一致 | 模块数 |
| --- | ---: | ---: | --- | ---: |
| zh-CN | 3 | 1 | 是 | 14 |
| en | 1 | 1 | 是 | 14 |

中文验收过程：应用版 Revision 1 → 临时隐藏空的 Materials 并保存草稿 Revision 2 → 刷新重开确认 → 完整预览确认仍保留该位置 → 从应用版恢复为草稿 Revision 3。没有应用临时测试布局。

本轮首页配置记录：

- ContentRevision：6 条
- `homepage.initialize`：1
- `homepage.draft.save`：3
- `homepage.layout.apply`：2
- `homepage.draft.restore`：1

## 6. 真实浏览器验收

- 中英文普通首页：200，无证书警告、无 Nginx Basic 弹窗。
- 桌面与 375px：完整首页可见，Hero/卡片/长页节奏正常。
- 桌面 zh→en、移动 en→zh：通过语言菜单实际点击，均留在本地域名。
- Products：三款产品全部显示，三张主图真实解码为 `700×700`。
- P01 Gallery：实际打开、关闭；关闭后焦点回到 `gallery-open`。
- P02/P03：详情页 200，真实主图加载为 `700×700`。
- 中文搜索：从首页点击 Search，输入“氮化”并点击，真实返回 P01/P02。
- RFQ：从页面实际点击进入；只检查入口，表单存在且提交按钮禁用；未提交、未上传。
- 认证完整预览：14 个模块、10 个空态、所有图片加载、20 个样式表、meta noindex；干净登录会话控制台 0 error。
- 匿名完整预览：401；匿名首页配置 API：401；匿名私有附件签名端点：401。
- Sitemap：常驻预览继续 404。

## 7. 数据冻结回读

迁移前备份库与当前主库在 25 张冻结业务表上逐表比较“行数 + 全行规范化 MD5”，25/25 完全一致。覆盖：

- Company/COPY-V1；
- 产品、产品翻译、分类、主图/媒体；
- 8 组 SEO；
- Publication、ContentRoute；
- 规格组、七个规格定义、产品参数；
- 产品与 Materials/Applications/Solutions/Technologies/Models 关系；
- RFQ；
- Privacy 版本和当前状态。

额外回读：

- 三款参数：`0/0/0`
- 规格定义：7
- F05 英文翻译：0
- RFQ：0
- Privacy current：0；未发布
- P01/P02/P03：仍为 published，`featured=false`
- 旧试点 `nitrided-barrel`：Publication draft；中英文 Route 均 `active=false/indexable=false`

## 8. 测试与检查

| 检查 | 实际结果 |
| --- | --- |
| API 受影响测试 | 83 passed |
| Website 全套测试 | 13 files / 146 passed |
| Admin 全套测试 | 10 files / 53 passed |
| Website typecheck | PASS（首次受 Windows `.nuxt/schema` EPERM 阻塞，授权后重跑通过） |
| Admin typecheck | PASS（同上，重跑通过） |
| Ruff 0.12.11 | PASS；首次发现 1 个 import sort，修复后 `All checks passed` |
| Prettier 3.6.2 | 本轮前端文件全部匹配 |
| Website production build | PASS（Docker/Nuxt） |
| Admin production build | PASS（Docker/Nuxt） |
| Nginx `nginx -t` | PASS |
| 独立 PostgreSQL 迁移/约束 | PASS |
| 主库迁移与最终健康检查 | PASS |

没有复制旧测试数量；发生过的 EPERM、PostgreSQL 16 dump 兼容限制和首次 Ruff 失败均如实记录。

## 9. 未执行与边界

- 生产上线、DNS、腾讯云、搜索平台、Analytics：`NOT_RUN`
- Privacy 发布或 P2：`NOT_RUN`
- RFQ 提交、附件上传、邮件发送：`NOT_RUN`
- 新业务内容创建：`NOT_RUN`
- Git commit、push、merge：`NOT_RUN`

R1 已可在本机进行视觉验收，但不代表十个空模块已有真实内容，也不代表 Privacy、Phase 3.7 或生产上线已完成。
