# Demo Owner Review Follow-up R1｜有限收尾报告

运行编号：`20260914T172540+0800`

项目基线：`junhui-demo-r2 / phase-3.7`

Git 定位：`ba80be35b05ea9d9888172183d1e5e7229cb7f88`，本轮改动保留在未提交工作区，未 stage、commit、push 或 merge。
结果：**本轮 5 项限定收尾均已完成。** 这不是全站重新审计，也不代表生产发布或全站 SEO/GEO 通过。

## 1. 两处布局修复

### 官网 Hero 留白

问题根因是 Hero 内容层把全站 `.public-container` 的响应式宽度覆盖为 `100%`，导致正文、按钮在桌面和手机都从视口 `x=0` 开始。

本轮仅让文字内容重新使用全站统一内容线，背景仍然全宽铺满；同时允许中文标题按短语安全换行。最终浏览器测量如下：

| 视口 | 内容/标题/按钮左边距 | 横向溢出 | 轮播项 |
|---|---:|---|---:|
| 1440 × 1000 | 80 px | 无 | 4 |
| 375 × 812 | 16 px | 无 | 4 |

未改变自动播放、箭头、编号、暂停、CTA、安全站内链接或 14 个首页模块结构。

### 后台轮播缩略图

问题根因是原图片自身带 `width`/`height` 属性，图片只限制了宽度与 `aspect-ratio`，仍可能按源图比例把左侧网格撑高。

本轮给缩略图增加独立的 `16:9` 裁切框，并限制左栏最大宽度。1366 视口实测：缩略图 `256 × 144 px`、比例 `1.778`、`object-fit: cover`；源图虽为 `1200 × 900`，已不会被拉成纵向长条。首张编辑卡片高度为 `569.11 px`。

## 2. 独立 TEST ONLY 真实操作链

写操作只发生在 `junhui-integrated-acceptance-r1-test-only`，使用它自己的真实 PostgreSQL、Redis、MinIO 和 Compose 数据卷。所有修改通过真实后台界面完成，GET 仅用于脱敏回读；常驻 Demo 和原 phase37 数据未写入。

1. 通过后台表单建立四张中英文 TEST ONLY 基线并应用，两个语言均保持 14 个模块。
2. 中文首项标题改为 `TEST ONLY｜螺杆与机筒精密制造（保存回读）`，第二项上移，第四项停用。
3. 保存草稿返回 HTTP `200`，revision `18`；刷新重开后真实顺序、标题和停用状态仍在。
4. 认证预览显示 3 个启用项，H1 为保存后排在第一的“表面工程与工艺技术”。
5. 应用返回 HTTP `200`，应用版 revision `10`；独立 QA 普通前台显示 3 个启用项。
6. 新增第五项并保存后回读 5 项；通过确认框删除并再保存后回读 4 项。
7. 另存一条仅草稿差异，再点击“从应用版恢复草稿”；返回 HTTP `200`、草稿 revision `22`，恢复后的草稿与应用版逐项一致。
8. 最后用后台恢复四张中文基线并重新应用：中文草稿 revision `23`、应用版 revision `11`；英文仍为 4 项。非 Hero 13 模块哈希、Hero 产品引用和 14 模块数量均未变化。

完整标题、状态、路径、revision 和断言见 `checks/qa-carousel-operation-chain.json`。证据没有密码、Cookie、Token、客户资料或私有附件。

## 3. 手册勘误

已修订《后台中文使用手册》：

- 首页轮播必须“编辑 → 保存草稿 → 认证预览 → 应用布局”后才改变普通首页；只保存草稿不生效。
- 产品、案例、知识、FAQ、SEO 和媒体分别遵循自己的保存/审核/发布规则，不能把首页规则套到所有对象。
- 当前 RFQ 关闭的是新的前台提交；后台仍可能显示历史或既有 Demo 询盘，应先核对权限、筛选、分页和真实计数。
- 媒体扫描及处理状态由系统产生；员工不能手工标记“处理完成/扫描通过”，也不能绕过失败状态。

## 4. 50 条清单重分类

50 个可追溯 ID 和原 P0/P1/P2 均保留，已从“看起来都是后台缺陷”改为按实际处理性质分类：

| 新分类 | 数量 | 含义 |
|---|---:|---|
| A 日常运营编辑缺口 | 6 | 员工高频需要，但当前没有直接入口 |
| B 受控技术配置 | 19 | 安全、发布、结构或基础设施边界，不应开放给普通内容人员 |
| C 待真实资料/授权 | 15 | 多数已有后台入口，缺的是已批准事实、素材或政策决定 |
| D 可选增强 | 10 | 不阻断当前 Demo，可按真实需求再做 |

原优先级合计仍为 P0 `21`、P1 `20`、P2 `9`。品牌、导航/页脚、轮播高级配置、RFQ/Privacy、重定向、搜索、首页结构、媒体/视频/下载等重叠项已按 8 个问题组合并，避免重复立项。

资料要求已纠正：不要求公开客户图纸，不要求 9 款 Demo 产品全部正式化；只需后续确认拟正式上架的产品。现有 4 张轮播图属于 40 张生成式 Demo 媒体的复用引用，不重复计算为 44 张。已有批准 Logo、三款产品图和 COPY-V1 不再索取。

## 5. 验证与运行状态

- Website Vitest：17 个文件、161 项通过。
- Admin Vitest：14 个文件、91 项通过。
- API 首页回归：挂载当前源码后以 `python -m pytest` 运行，5 项通过。
- Website/Admin typecheck：通过。
- 本轮 4 个受影响前端文件 Prettier：通过。全仓检查另有两份既有根目录 JSON 未格式化，本轮未越界修改。
- `pnpm build`：Website/Admin 通过；最终 Demo Website/Admin Docker 镜像构建通过。
- Ruff：锁定的本机与 API 测试环境未包含 Ruff，本轮未另装第二套依赖环境，记录为未运行。
- 浏览器：优先浏览器插件未安装，按测试技能说明回退到本机 Chrome + Playwright；桌面、手机与后台截图和尺寸断言均通过。
- 首次 typecheck/build 因沙箱无法写 `.nuxt` 缓存而 EPERM；授权重跑后通过。直接调用容器 `pytest` 控制台入口曾加载镜像内旧安装包并产生 2 个假 422，改用 `python -m pytest` 明确加载挂载的当前源码后 5 项全部通过。

常驻 Demo 最终 7 个服务均健康：API、worker、Website、Admin、PostgreSQL、Redis、MinIO。网站 HTTP `200`，后台登录页 HTTP `200`，`X-Robots-Tag: noindex, nofollow`、`Cache-Control: no-store` 保持。

未发布 Privacy，未开启 RFQ，未发送邮件，未连接云/NAS/Gmail，未修改 DNS、Analytics 或生产部署。最终 Demo 保持运行，供本轮复验。

## 6. 限定交付

- 本报告：`docs/handoff/demo-owner-review-followup-r1/demo-owner-followup-r1-focused-closeout-report.md`
- 修订手册：`docs/handoff/demo-owner-review-followup-r1/后台中文使用手册.md`
- 重分类清单：`docs/handoff/demo-owner-review-followup-r1/后台不能直接修改的内容清单.md`
- 结构化回读：`docs/handoff/demo-owner-review-followup-r1/demo-owner-review-followup-r1-readback.json`
- 最终截图与脱敏检查：`artifacts/demo-owner-followup-r1-focused-closeout-20260914T172540+0800/`
