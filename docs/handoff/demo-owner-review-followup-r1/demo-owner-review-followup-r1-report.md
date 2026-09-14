# Demo Owner Review Follow-up R1 实施报告

Run ID：`20260914T141327+0800`  
项目：`junhuiscrew/New_Official_Website`  
工作区：实际 `phase-3.7` 工作树  
目标环境：`junhui-demo-r2`  
结果：**DEMO_OWNER_REVIEW_FOLLOWUP_R1_COMPLETE**

本结论只覆盖本轮首页轮播、后台中文手册和后台不可直改审计，不代表 Phase 3.7、全站 SEO/GEO、视觉定稿或生产上线通过。

## 1. 版本与边界

- HEAD：`d86f524f0d973b70c4fef6d76c7a58bd6cfd18f0`
- 分支：`phase-3.7`
- 保留了进入本轮前已有的全部提交、tracked diff 和未跟踪交付物。
- 本轮没有 reset、stash、切分支、stage、commit、push、merge、tag 或生产部署。
- 只更新 `junhui-demo-r2` 的 API、Worker、Website、Admin 镜像和 Demo 首页配置。
- 未运行迁移、Restore 或默认 Seed；未修改原 `phase37` 数据。
- 未连接云、NAS、Gmail，未发邮件，未改公共 DNS、Analytics、Privacy 或 RFQ 开关。

## 2. 设计方案

先完成并展示了桌面高保真概念图：深蓝科技背景、金属螺杆主视觉、左侧主文案、明确 CTA、底部编号进度、前后箭头与暂停按钮。实现沿用当前品牌导航，不替换整站风格，也不改变首页其余 13 个模块。

设计图：`artifacts/demo-owner-review-followup-r1-design/hero-slider-concept-desktop-demo.png`  
SHA256：`34E8CB6D0663459C75EEEB05497BBD647FB5AB6F75C3FEA61796BEEB86FB724F`

最终前台特点：

- 全宽深蓝工业 Hero，图片覆盖并带网格和渐变遮罩。
- 桌面与 375px 手机响应式布局。
- 每 6 秒自动播放；鼠标悬停、焦点进入、页面隐藏或系统“减少动态”时暂停。
- 支持上一张、下一张、编号圆点和显式暂停/播放。
- 活跃轮播只渲染一个 H1。
- 图片与文案明确显示 `DEMO 素材 / DEMO ASSET`。
- 无第三方轮播库。

## 3. 轮播后台与 API 实施

后台入口：`首页编排` → `Hero 首页主视觉` → `Banner Slider 轮播图`。

实现能力：

- 中文与英文分别维护。
- 新增、修改、删除、上移、下移。
- 选择公开、已就绪、`public-media` 桶中的图片。
- 编辑主标题、副标题、按钮文案和本站内部链接。
- 启用/停用单个轮播项。
- 最多 5 张；列表顺序即播放顺序。
- 保存草稿、认证预览、应用布局继续使用现有 revision 乐观锁和权限体系。
- 未输入轮播时继续显示原 Hero，不影响其他模块。

服务端门禁：

- 输入字段使用严格白名单，拒绝额外字段、重复 key、超过 5 项和非 Hero slides。
- CTA 文案和链接必须成对；链接只允许以 `/` 开头的本站路径。
- 保存时一次查询核对媒体；不存在、私有、未就绪、非图片或非公开桶媒体返回 409。
- 公开读取时再次核对当前媒体状态；已撤回媒体即时从结果排除。
- 公开 DTO 不输出内部 slide id、media_id、enabled、bucket 或 storage key。
- 公开列表只包含启用项，首图 eager，其余 lazy。

## 4. 本轮 Demo 轮播内容

写入前先核对草稿与应用版一致，避免夹带旧草稿。中文从 revision 6 更新到 7；英文从 revision 1 更新到 2。两种语言仍保持 14 个首页模块，Hero 原有 `demo-s01/demo-s02/demo-s03` 产品关联未变。

| 顺序 | Demo 图片 | 中文 | English | 链接 |
|---:|---|---|---|---|
| 1 | `generated-01.jpg` | 螺杆与机筒精密制造 | Precision Screw & Barrel Manufacturing | Products |
| 2 | `generated-14.jpg` | 表面工程与工艺技术 | Surface Engineering & Process Technology | Technologies |
| 3 | `generated-31.jpg` | 制造能力与质量控制 | Manufacturing Capability & Quality Control | Capabilities |
| 4 | `generated-23.jpg` | 面向应用的解决方案 | Application-led Solutions | Solutions |

四项均启用。所有图片来自现有 Demo 媒体库，只用于演示，不代表正式工厂、客户、设备、证书或能力事实。

## 5. 真实浏览器验收

在最终 Demo Website 运行版完成正常浏览器操作，没有网络 mock，也没有用直接 goto 替代要求的 CTA 点击。

### 桌面 1440×1000

- 首页 HTTP 200，`Cache-Control: no-store`。
- 第一张标题“螺杆与机筒精密制造”，只有 1 个 H1。
- 4 个轮播编号均可见，图片成功解码，Demo 标识可见。
- 等待一个播放周期后切到“表面工程与工艺技术”。
- 点击暂停后再等待一个周期，标题保持不变。
- 上一张、下一张和编号切换均改变正确标题。
- 点击第一张“探索产品”，正常进入 `https://demo.junhuiscrewbarrel.com/zh-cn/products/`，目标 H1 为“产品中心”，保持 Demo 同源。

### 手机 375×812

- 第三张“制造能力与质量控制”正确显示。
- 只有 1 个 H1，图片成功解码。
- CTA、前后按钮、编号和暂停按钮均在视口内可用。
- 下一模块仍紧接 Hero，未改变原首页结构。

### 英文

- `/en/` 第一张为 `Precision Screw & Barrel Manufacturing`。
- 4 个英文项均由英文配置输出，链接均为 `/en/.../`。

### 后台编辑器

- 1440px 后台“首页编排”显示 4 张中文轮播卡片。
- 每张包含图片、启用开关、图片下拉、主/副标题、CTA、上移/下移、删除。
- 图片下拉来自真实媒体库；截图中 4 张预览均解码。
- 英文标签可切换并显示 4 张英文项。
- 临时新增、删除和调整顺序只在浏览器未保存状态验证；没有点击保存或应用，刷新后保持已应用配置。
- 后台总览截图遮盖了账号区域，证据不含密码、Token 或 Cookie。

## 6. 后台中文使用手册

交付文件：`docs/handoff/demo-owner-review-followup-r1/后台中文使用手册.md`

手册为全中文员工操作版，含建议操作顺序及以下 12 章：

1. 后台登录与入口说明；
2. 页面结构与菜单说明；
3. 首页内容和轮播如何修改；
4. 产品新增/修改；
5. 产品参数修改；
6. 案例、知识文章、FAQ；
7. 媒体上传与复用；
8. 下载资料维护；
9. SEO/GEO 填写；
10. 询盘中心；
11. 草稿、审核、发布、启停、页面和环境状态；
12. 常见错误与排查。

手册明确了 fresh GET、双语分开维护、先预览后发布、客户私有信息排除，以及当前 Privacy/RFQ 保护。

## 7. 后台不能直接修改审计

交付文件：`docs/handoff/demo-owner-review-followup-r1/后台不能直接修改的内容清单.md`

脚本核对结果：共 50 项，无重复编号。

| 分类 | 数量 |
|---|---:|
| P0 | 21 |
| P1 | 20 |
| P2 | 9 |
| 合计 | 50 |

其中 38 项是真正的代码、配置、初始化、组件结构或缺少后台入口；12 项是需要 Owner 提供、审核或授权的真实资料包。后者部分已有后台输入框，但员工不能凭空生成企业事实、客户授权、专家身份或法律批准。

最优先的资料与决策：Privacy/RFQ 政策，公司与品牌主数据，真实产品与规格，技术能力和设备，客户案例授权，专家身份，证书/专利，真实图片/视频/PDF。

## 8. 自动化与构建结果

| 检查 | 最终结果 |
|---|---|
| API 首页 presentation 测试 | 5 passed |
| Website 全量 Vitest | 17 files / 160 passed |
| Admin 全量 Vitest | 14 files / 90 passed |
| Website + Admin typecheck | PASS |
| 本轮前端文件 Prettier check | PASS |
| 本轮 Git diff whitespace check | PASS；仅 Git 行尾转换提示 |
| Demo API/Worker/Website/Admin build | PASS |
| Ruff | 未运行：锁定 `api-test` 镜像和主机均未安装 Ruff；按边界未临时安装第二套依赖环境 |

全量 Website 首次运行曾有 2 个失败：公开 DTO 带内部 slide id，以及旧正则把 CSS `isolation` 误认成 ISO 声明。根因修复后，相关 27/27 和 Website 全量 160/160 均通过。

## 9. 最终 Demo 状态和保护

- `api`、`worker`、`website`、`admin` 四个受影响服务均为 healthy。
- Website 200；Admin 登录页 200。
- `X-Robots-Tag: noindex, nofollow`，`Cache-Control: no-store`。
- `/sitemap.xml` 返回 404。
- Privacy 页面返回 404，保持未发布。
- RFQ 页面返回 200，但明确显示禁用说明，提交按钮 disabled。
- 页面业务 meta 仍可表示正式页面自身规则；Demo 环境由更严格的外层 `X-Robots-Tag` 保护。未改 canonical。

## 10. 交付物与结论

- 实施报告：本文件。
- 后台中文使用手册：`后台中文使用手册.md`。
- 后台不能直接修改清单：`后台不能直接修改的内容清单.md`。
- 结构化 readback：`demo-owner-review-followup-r1-readback.json`。
- 前台桌面、前台手机、后台编辑器和后台总览脱敏截图。
- 设计图、测试/健康说明、校验清单和脱敏证据 ZIP。

本轮三项目标均已完成，Demo 已保持运行，等待 Owner Review。未宣布全站或生产通过。
