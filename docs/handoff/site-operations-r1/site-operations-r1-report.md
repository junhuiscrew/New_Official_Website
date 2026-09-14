# 站点运营设置 R1 实施报告

状态：`SITE_OPERATIONS_R1_READY_FOR_REVIEW`
运行标识：`20260914T204639+0800`
目标环境：`junhui-demo-r2 / phase-3.7`
代码基线 HEAD：`245075f6eac8093adf9605785f8c67c76fa4a8de`（本轮实现仍包含未提交文件，HEAD 不代表完整运行版本）

本报告只关闭品牌设置、导航与页脚、受控重定向三个运营编辑缺口，不代表全站、SEO/GEO 或生产上线通过。

## 1. 结论

本轮三个中文后台入口均已实现并运行在 Demo R2：

1. `站点运营 → 站点与品牌`：`/site-operations/brand`
2. `站点运营 → 导航与页脚`：`/site-operations/navigation`
3. `站点运营 → 重定向管理`：`/site-operations/redirects`

品牌与导航均采用“草稿 → 认证预览 → 确认应用 → 生成新修订恢复”的版本链；普通前台只读取应用版。重定向复用已有 `RedirectRule` 与 resolver，并增加草稿、检查、确认、停用和不可删除的历史记录。未新增权限类型，也没有建立第二套 CMS。

常驻 Demo 最终等值保留原品牌、菜单、四张双语轮播和每语言 14 个首页模块；没有留下 `TEST ONLY` 文案或启用的试验重定向。Privacy 仍未发布，RFQ 仍禁用，全站 `noindex/no-store` 与 Sitemap 404 保持不变。

## 2. 实施内容

### 2.1 站点与品牌

- 可编辑简体中文、英文展示名称与简称。
- Logo、移动 Logo、favicon 通过现有媒体库选择；服务端只接受公开、就绪且类型合格的图片。
- 初始化只在不存在配置时等值读取现有 `CompanyProfile` 和批准 Logo；已有草稿不会被覆盖。
- 品牌显示名只用于站点展示，不修改法定公司资料。
- 保存只更新草稿；应用要求 `content.publish` 权限、CSRF、版本一致及用户确认。
- 恢复从当前应用版生成新的草稿修订，不删除历史。
- 媒体引用已接入使用位置和删除保护，原图不会被覆盖。

### 2.2 导航与页脚

- 可分别维护中英文顶部/移动菜单、页脚分组、标签、顺序和启停。
- 所有目标来自服务端认可的站内目标枚举，不允许员工填写 UUID、JSON、脚本、协议相对链接、后台/API/私有文件地址或任意 HTML/CSS。
- 新增/移除只改变菜单项，不删除内容实体。
- 初始值与原导航等值，没有自行把工艺技术提升为一级菜单。
- Contact/RFQ 虽为 `noindex`，仍可作为允许访问的菜单目标。
- Privacy/Sitemap 在编辑器中保留原选择并标明“当前不可公开”，公开输出会按实时资格过滤；没有生成占位 200，也没有发布 Privacy。
- 中文保存不会清空英文；语言切换和搜索继续使用原系统逻辑。

### 2.3 受控重定向

- 提供搜索、受控新增/修改、保存草稿、离线规则检查、确认启用、停用和变更历史。
- 复用既有 `redirect.read` / `redirect.manage` 权限、CSRF、`RedirectRule` 模型和真实 resolver。
- 检查覆盖：重复来源、自跳、循环、跳转链、受保护路径、非法协议、查询泄露、来源/目标主机白名单及版本冲突。
- “检查跳转”只检查本地规则与路由，不访问外网，不抓取员工输入 URL。
- 正式目标仍受批准 HTTPS 主域约束；没有为 Demo 放宽白名单。
- 常驻 Demo 最终重定向总数为 0，没有启用测试规则，也没有执行旧站迁移。

## 3. 数据、迁移与权限

- 新增迁移 head：`20260914_0017_site_operations_r1`。
- 新增 `site_brand_settings`、`site_navigation_settings`，并为现有 `redirect_rules` 追加工作流、版本和审计字段；未修改历史迁移。
- 字段名为英文，新增数据库字段均带中文注释。
- 复用已有 `Media`、Audit、RBAC、CSRF 和内容发布权限：读取 `content.read`，草稿 `content.update`，应用 `content.publish`；重定向继续使用 `redirect.read` / `redirect.manage`。
- 没有扩大系统或员工角色权限，没有运行默认 Seed，没有重导产品或清库。
- 迁移前创建 Demo 私有快照，保留在非证据目录：`data/demo-r2/private/site-operations-r1-20260914T204639+0800/demo-r2-before.dump`；该文件未加入证据包。

## 4. 独立 TEST ONLY 真实操作链

独立环境使用一次性 PostgreSQL、Redis、MinIO、API、Admin、Website，写操作没有连接常驻 Demo 或原 phase37。

### 4.1 品牌链

- 前值：草稿 revision 2，应用版 revision 1。
- 实际修改中文展示名并选择图片，保存后 fresh GET、刷新和重新打开均读回成功；英文名称保持不变。
- 认证预览读取服务端草稿；确认应用后 revision 为 `4/4`，QA 前台读到应用版名称。
- 再保存 revision 5 的临时草稿并执行恢复，生成 revision 6；应用版仍为 revision 4，审计历史未删除。

### 4.2 导航与页脚链

- 前值：中文 `2/1`，英文 `0/0`。
- 实际完成中文标签修改、排序、添加后移除一项、停用一项、保存、重新打开和认证预览；英文仍为 `Products / Solutions / Materials`。
- 中文应用为 revision 3；桌面与 375px 手机通过正常点击进入 `/zh-cn/contact/`，保持同源并显示 H1“从需求开始沟通”。
- 再保存一版草稿并恢复，生成中文草稿 revision 5，应用版保持 revision 3。

### 4.3 重定向链

- TEST ONLY 规则：`junhuiscrew.com/site-operations-r1-ui-test-only/` → `https://junhuiscrewbarrel.com/en/products/`，状态码 308。
- 完成保存、fresh GET、离线检查、确认启用；实际 resolver 返回 308，`Location` 精确一致且测试未自动跟随外域。
- 停用后 resolver 返回 404。
- 历史包含 `redirect.draft.create`、`redirect.check`、`redirect.confirm`、`redirect.disable`。
- 自动化拒绝了重复、自跳、循环、跳转链、保护路径、查询泄露、非法协议以及缺权限/CSRF 请求。

完整结构化链见证据中的 `operation-chains.json`。

## 5. 常驻 Demo 最终回读

| 项目 | 最终值 |
|---|---|
| 数据库迁移 | `20260914_0017_site_operations_r1` |
| 品牌草稿/应用版 | `0/0`，等值初始配置，无 TEST ONLY |
| 中文导航草稿/应用版 | `0/0`，等值初始配置，无 TEST ONLY |
| 英文导航草稿/应用版 | `0/0`，等值初始配置，无 TEST ONLY |
| 重定向 | 总数 0、启用 0 |
| 首页 | 每语言 14 模块、4 张轮播 |
| 搜索“演示” | 总数 46；产品 9、材料 8、工艺 6、应用 6、方案 1、制造能力 4、案例 4、知识 8 |

前台 1440px 与 375px 已实际检查头部、页脚、移动菜单和同源点击；后台 1440px 截图覆盖三个入口，1366px/100% 下再次读取完整表单和操作区。最后一次 1366px 只读复核使用的旧会话在导航后发生 `/auth/me` 401，原因是验收会话到期；此前已认证保存、预览、应用和恢复链不受影响，该 401 不计作功能通过证据。

六页 SEO 的 title、description、canonical、hreflang 与既有基线一致；About 保持 `index,follow`，Contact 保持 `noindex,nofollow`，RFQ 保持 `noindex,follow`。

## 6. 测试与构建

| 检查 | 结果 | 说明 |
|---|---:|---|
| API 全量 pytest | 380 通过、19 跳过、0 失败、0 错误 | 399 收集；跳过项主要为未选择的通用外部 PostgreSQL profile，本轮独立 PostgreSQL 测试另行执行 |
| Site Operations API 定向 | 9 通过 | 最终正确环境执行；早先两次环境接线错误未作为业务通过 |
| 独立真实 PostgreSQL + MinIO | 1 通过 | 真实数据库、媒体资格、工作流及 3xx resolver |
| Website 单元测试 | 17 文件、161 通过 | 无失败 |
| Admin 单元测试 | 15 文件、95 通过 | 无失败 |
| Website / Admin typecheck | 通过 | 沙箱内 `.nuxt/schema` EPERM 后在相同锁定环境重跑通过 |
| Ruff lint | 通过 | `app`、`tests`、`alembic` |
| 受影响 Python 格式检查 | 17 文件通过 | 未全仓格式化 |
| 受影响前端 Prettier | 通过 | 本轮文件通过 |
| Website / Admin build | 通过 | Nuxt/Nitro 完整构建；有插件耗时与依赖 trailing-slash deprecation 警告，无构建失败 |

非本轮阻断但如实保留：根级全量 Prettier 仅在两个既有、无关 JSON（`demo-acceptance-matrix.json`、`demo-baseline-manifest.json`）失败；全量 Ruff format 报告 96 个历史 Python 文件会被重排。本轮没有为消除历史格式差异而全仓改写。

## 7. 运行与保护

- Demo R2 的 API、worker、website、admin 已更新；PostgreSQL、Redis、MinIO 数据卷保留。
- 最终镜像 SHA256：API `9a9bd738…ae18`、worker `3af5c1b5…815f`、website `57675981…466`、admin `d826868c…9557d`；完整值写入结构化回读。
- Demo R2 最终所有服务健康运行。
- 原 phase37 的 API、worker、website、admin、PostgreSQL、Redis、MinIO 和共享 Nginx 均健康；其业务服务未重建。
- 共享网关只监听 `127.0.0.1:443`。
- 前台 HTTPS 无 Basic 弹窗；后台继续使用登录、RBAC、CSRF。
- 前台与后台继续返回 `noindex,nofollow`、`no-store` 和 Demo 标识；Sitemap 404；Privacy 404；RFQ 提交禁用。
- 未连接云、NAS、Gmail，未发送邮件或询盘，未修改公共 DNS 或 Analytics，未部署生产。
- 未执行 stage、commit、tag、push 或 merge。

## 8. 交付文件

- 本报告：`docs/handoff/site-operations-r1/site-operations-r1-report.md`
- 结构化回读：`docs/handoff/site-operations-r1/site-operations-r1-readback.json`
- 更新手册：`docs/handoff/demo-owner-review-followup-r1/后台中文使用手册.md`
- 更新清单：`docs/handoff/demo-owner-review-followup-r1/后台不能直接修改的内容清单.md`
- 截图与操作链：`artifacts/site-operations-r1-20260914T204639+0800/`
- 精简脱敏证据包：仓库根目录 `Junhui-Site-Operations-R1-Evidence-20260914T204639+0800.zip`

证据包不包含密码、Token、Cookie、数据库快照、客户资料或附件原包。
