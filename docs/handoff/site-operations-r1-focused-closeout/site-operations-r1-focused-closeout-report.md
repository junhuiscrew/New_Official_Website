# 站点运营设置 R1 有限收尾报告

运行标识：`20260914T232127+0800`  
工作区：`phase-3.7`（目录仍为 `.worktrees/phase-3.6`）  
基线 HEAD：`13baa264e6fb6dfad707e05ea5f303c9729ac58b`  
结论：`SITE_OPERATIONS_R1_FOCUSED_CLOSEOUT_READY_FOR_REVIEW`

本结论只关闭复验包指定的 Logo、可读性、页脚操作链和手册打包问题，不代表全站、SEO/GEO 或生产上线通过。本轮未 stage、commit、push、merge、部署生产，也未修改原 phase37 数据。

## 1. QA 移动菜单新 Logo

根因定位为旧 QA 证据中的数据库媒体引用与对应对象存储生命周期不一致：克隆数据库保留了媒体记录，但新建的独立 QA MinIO 起始为空，旧引用请求返回 404，因此浏览器不能解码。组件本身并不需要 fallback；使用同一 QA 后台真实上传并保存的新对象可以正常返回和解码。

本轮使用现有批准静态 Logo 的副本，文件名明确标为 `TEST-ONLY-real-public-ready-logo.png`，只上传到独立 QA：

- 后台上传接口返回 201，媒体为公开、就绪、`image/png`。
- 公共媒体经 QA API、Website 和 Web Gateway 均返回 200，长度 681151 bytes。
- 后台媒体库、品牌认证预览、前台桌面头部和 375px 移动菜单均解码为 `2078 × 757`。
- 品牌链：初始 revision `0/0` → 保存并刷新回读 `1/0` → 认证预览 → 确认应用 `1/1` → 前台移动菜单正常解码。
- 恢复时，命令行工具第一次不能传递空选项，产生了内容不变的 revision 2；该次未当作恢复成功。随后在同一浏览器直接选择“使用现有批准静态素材”，保存为 revision 3 并确认应用。最终 QA 品牌为 `3/3`，桌面与移动 Logo 的草稿/应用媒体引用均为空，即回到原静态 Logo。

旧静态 Logo 正常未被用来替代新媒体验证；新媒体验证过程中没有增加 fallback。

## 2. 导航与重定向可读性

后台导航语言按钮增加明确的未选中深色正文、选中蓝底白字、hover、键盘 focus-visible 样式，并使用 `aria-pressed` 表达状态。实际在 1440×900 与 1366×900、100% 缩放下切换过中文和英语：未选中按钮颜色为 `rgb(23, 50, 74)`，选中按钮为蓝底白字；英文数据未被中文页脚操作覆盖。

重定向规则列表的来源主机/路径使用深色正文并允许安全换行，实际颜色为 `rgb(23, 50, 74)`、字重 900。历史动作主文案改为“新建草稿、更新草稿、完成检查、确认启用、停用规则”，原 `redirect.*` 技术代码与 revision 继续显示在详情行。

独立 QA 的 TEST ONLY 规则：

- 来源：`junhuiscrew.com/siteops-focused-r1-test-only/`
- 目标：`https://junhuiscrewbarrel.com/en/products/`
- 状态：308
- 保存草稿 → 本地冲突检查 → 确认启用 → 不跟随请求得到真实 308/Location → 停用 → 再请求为 404。
- 最终规则为 `enabled=false`、`workflow_status=draft`、revision 1，不留下启用试验跳转。

脱敏原始响应头见证据包 `checks/redirect-response-headers-sanitized.txt`。

## 3. 页脚专属操作链

只在独立 QA 修改中文页脚，具体前后值如下：

| 阶段 | 分组名称 | 组内顺序 | revision |
| --- | --- | --- | --- |
| 前值 | 联系我们 | 联系我们 → 提交询价 → 下载资料 | 草稿 0 / 应用 0 |
| TEST ONLY 草稿 | TEST ONLY 服务入口 | 提交询价 → TEST ONLY 联系入口 → 下载资料 | 草稿 1 / 应用 0 |
| TEST ONLY 应用 | TEST ONLY 服务入口 | 提交询价 → TEST ONLY 联系入口 → 下载资料 | 草稿 1 / 应用 1 |
| 恢复应用 | 联系我们 | 联系我们 → 提交询价 → 下载资料 | 草稿 2 / 应用 2 |
| 系统恢复草稿 | 联系我们 | 联系我们 → 提交询价 → 下载资料 | 草稿 3 / 应用 2 |

revision 1 保存后执行了页面刷新重开与 fresh GET 回读，并经过认证预览。应用后，QA 前台显示具体测试值；正常点击“TEST ONLY 联系入口”到达同源 `/zh-cn/contact/`，页面 H1 为“从需求开始沟通”。随后保存并应用原值，再执行系统“从应用版恢复”生成新草稿。英文始终为草稿 0 / 应用 0。

## 4. 手册修订与离线包

后台中文使用手册已修订为 1→15 连续章节；第 12 章“常见错误与排查建议”已回到第 13～15 章之前。品牌、导航、重定向三张图片均替换为本轮实际界面截图，仓库内相对路径逐一验证存在。

离线包保留 `docs/handoff/...` 与 `artifacts/...` 的相同相对层级，因此解压后直接打开 Markdown 即可显示图片。包内不含密码、Token、Cookie、数据库快照、私有媒体或客户资料。

## 5. 测试与独立运行环境

- Admin Vitest：15 个文件、97 项测试全部通过。
- Admin typecheck：宿主机首次因 `.nuxt/schema/nuxt.schema.json` 文件占用返回 EPERM；在本轮同码、锁定依赖的 QA Admin 镜像内重跑通过。宿主失败保留记录，没有伪装为通过。
- Prettier 3.6.2：本轮 3 个受影响代码/测试文件全部通过。
- Admin build：锁定 `pnpm@11.19.0` 的 Docker 构建通过。
- API/Python 本轮未改；未运行会 `drop_all/create_all` 并调用默认 Seed 的旧 PostgreSQL 集成测试，以遵守“不清库、不默认 Seed”。真实 PostgreSQL/MinIO 验证由本轮浏览器操作链和只读运行摘要提供。

独立 QA 运行在 `junhui-siteops-focused-r1-qa`：PostgreSQL 17.6，数据库 `junhui_siteops_qa`，迁移头 `20260914_0017`；MinIO 公共桶存在且有 1 个本轮 TEST ONLY 对象，私有 RFQ 桶为空。存储均为 QA 临时空间，不指向常驻 Demo 或 phase37。

## 6. 常驻 Demo 最终状态

- 前台：`https://demo.junhuiscrewbarrel.com/`
- 后台：`https://admin-demo.junhuiscrewbarrel.com/`
- Demo Admin 已仅重建受影响容器并恢复 healthy；实际镜像 `sha256:3ee9ae69c3891f7b5ae0ede439341ded853c8e3d5b32bf0bb9a0591b347dfbd8`。
- 品牌：草稿/应用 revision `0/0`，桌面和移动 Logo 继续使用原静态素材。
- 导航：中文、英文均为 `0/0`；没有 TEST ONLY 页脚值。
- 重定向：总数 0、启用 0。
- 首页：中文 revision 7、英文 revision 2；两种语言均为 14 模块、4 张轮播。
- 首页 HTTPS 200，`X-Robots-Tag: noindex, nofollow`，`Cache-Control: no-store`；Sitemap 404、Privacy 404；RFQ 仍禁用。

Demo 和原 phase37 服务均保持运行。本轮没有连接云/NAS/Gmail，没有改 DNS/Analytics，没有发送邮件或询盘。

## 7. 交付索引

- 结构化回读：`site-operations-r1-focused-closeout-readback.json`
- 中文手册：`../demo-owner-review-followup-r1/后台中文使用手册.md`
- 本轮截图：`artifacts/site-operations-r1-focused-closeout-20260914T232127+0800/screenshots/`
- 脱敏证据包与校验清单：见同一 artifacts 目录及项目根目录的最终 ZIP。
