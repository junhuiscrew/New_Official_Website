# Phase 3.7 Batch01 受保护预览展示修复报告

- Run ID：`20260907T103809+0800`
- 执行日期：2026-09-07（Asia/Shanghai）
- 实际目标：`phase37-local-https`
- 本地入口：`https://junhui.test/`
- 分支：`phase-3.7`
- 基线 HEAD：`0fd6edabfc6d4efa8666cf49c54765b099b24300`
- 工作区状态：保留已有后续提交及未提交工作；本轮改动未提交、未 push、未 merge
- 结论：本轮限定的三个展示问题已修复并在最终重建的本地隔离实例上完成真实回读和浏览器验收；等待前台复验，不代表 Phase 3.7 整体完成。

## 1. 范围与边界

本轮只处理以下内容：

1. IMG-02/03/04 现有对象的真实图片尺寸元数据；
2. 语言导航在保留正式 canonical/hreflang 的同时，以经本站来源校验的相对路径跳转；
3. 首页 Hero 主标题与简介绑定。

未修改 COPY-V1 的 16 个字段，未重新导入产品，未调用 CMS Review/Publish，未提交 RFQ，未上传附件，未发送邮件，未修改 DNS，未连接或部署生产环境，也未创建公网隧道。

## 2. 实际修复

### 2.1 媒体尺寸与复用路径

- API 在接收公开图片时使用 Pillow 完整解码像素，并按 EXIF 方向得到真实宽高；不再只依赖扩展名、MIME 和文件头。
- Pillow 从测试依赖调整为 API 运行时依赖，保证实际上传路径可执行解码。
- 新增受 `media.update` 权限和 CSRF 保护的幂等元数据刷新端点。端点只读取现有 public-media 对象，先校验对象长度及 SHA-256 与数据库记录一致，再更新宽高；客户端不能提交或猜测尺寸。
- Batch01 的既有映射复用路径不再直接跳过媒体：复用时调用上述端点；尺寸相同则 no-op，不重新上传、不创建重复媒体。
- 容错边界：对象不存在、对象完整性不匹配、非 ready 的公开图片或无法完整解码时停止，不绕过 PublicImage 条件。

### 2.2 语言导航

- 正式 canonical 和 hreflang 保持绝对正式地址，Head 生成逻辑未改。
- 语言菜单读取 alternate 后，以正式站 `SITE_URL` 为受信 origin 解析并校验；仅 HTTPS 同源地址可转换为 `pathname + search + hash` 相对路径。
- 外站、协议相对地址、反斜杠网络路径、`javascript:` 和格式错误地址均回退到目标语言首页。

### 2.3 首页 Hero

- H1 绑定已确认的 `company_name`。
- `short_intro` 原文绑定为 Hero 中的普通简介段落。
- 仅在 `short_intro` 缺失时沿用既有 mission/界面兜底；没有更改或新增营销事实。

## 3. 媒体实际回读

更新前已保存私有快照，更新后从 Admin DTO、对象存储和只读数据库回读交叉核对。私有快照保留在本地忽略目录，不进入验收 ZIP。

| 别名 | 更新前 | 真实解码/更新后 | changed | 本次 Audit |
| --- | --- | --- | --- | --- |
| IMG-02 | width/height 均为空 | 700 × 700 | true | 1 |
| IMG-03 | width/height 均为空 | 700 × 700 | true | 1 |
| IMG-04 | width/height 均为空 | 700 × 700 | true | 1 |

核对结果：

- 更新 3 项，no-op 0 项；
- 三个媒体 ID 均未变化；
- 对象字节数和对象 SHA-256 均未变化；
- 存储位置、原始/安全文件名、MIME、扩展名、文件大小、上传者、校验及扫描状态均未变化；
- 产品主图关联、嵌入水印、翻译与 alt 均未变化；
- 仅宽高元数据发生预期变化；内容 Revision 未新增，新增 3 条真实 `media.metadata_refresh` Audit，每个别名 1 条。

## 4. 内容与生命周期不变量

- COPY-V1：实际 Admin/API 回读 16/16 字段匹配。
- 冻结状态：未变化；SHA-256 为 `eb3604a43247931034745a6d3494f31c954ab9ba1b304a9d7cc7de075ec2d93b`。
- Company、必要分类和 P01/P02/P03：12 组 Translation/Publication/Route 仍为此前批准的 published/active 状态。
- 旧试点：仍关闭且为 draft，未发布。
- P01/P02/P03 参数值：分别为 0/0/0。
- F05 英文：仍空缺。
- 型号与关系：仍为空；七个规格字段定义未改。

本轮没有调用 Review/Publish，也没有撤回已批准的受保护预览。

## 5. 真实浏览器验收

浏览器插件在当前环境不可用，因此按既有回退策略使用 Playwright 驱动电脑上已安装的 Microsoft Edge。浏览器网络守卫只允许 `junhui.test`、`api.junhui.test` 和 `admin.junhui.test`；最终执行没有外站请求，也没有生产站导航尝试。

### 首页与 SEO

- 中英文首页均返回 200，并带 `X-Robots-Tag: noindex`。
- 两种语言的 H1 均逐字等于对应 `company_name`，简介段落均逐字等于对应 `short_intro`。
- 正式 canonical 和 zh-CN/en/x-default hreflang 均保持正式绝对地址。

### 图片与 Gallery

- 中文产品列表显示 3 张真实图片，均为 HTML `700×700`，浏览器 natural size 也为 `700×700`；fallback 数量为 0。
- P01、P02、P03 详情分别显示对应真实图片，均完成加载；fallback 数量为 0。
- 三款产品的空规格区继续隐藏。
- P03 Gallery 实际点击打开；dialog 内图片加载成功；关闭按钮获得焦点；Esc 关闭后焦点返回原触发按钮。

### 语言与响应式

- 桌面：实际点击 `/zh-cn/` 的语言菜单，链接属性为 `/en/`，最终到达 `https://junhui.test/en/`。
- 移动：在 375px 实际打开移动菜单，从 `/en/` 点击 `/zh-cn/`，最终到达 `https://junhui.test/zh-cn/`。
- 375×812 中英文首页及 320×720 的 P02 详情均无横向溢出；320px 下真实图片继续加载。
- 浏览器 pageerror/console error：0。

## 6. 外层保护复验

- HTTPS 入口正常，主入口仅发布宿主机 443 端口。
- Website/Admin/API/Worker/PostgreSQL/Redis/MinIO 均未直接发布宿主机端口。
- 匿名业务请求返回 401；认证后业务请求返回 200。
- 网关 `X-Robots-Tag: noindex, nofollow` 保持；Sitemap 返回 404 且未启用。
- Basic Auth 保持；direct origin bypass 为 false。
- 环境仍为 staging；Analytics、营销邮件和公网隧道均未启用。

## 7. 本轮回归结果

| 检查 | 实际结果 |
| --- | --- |
| API 目标回归：`test_phase35_foundation.py`、`test_phase35_remediation.py`、`test_phase37_batch01.py` | 37 passed，2 skipped，0 failed；跳过项是需要显式启用真实 MinIO/Redis 的既有集成测试，未写为 PASS |
| API Ruff 0.12.11 | All checks passed |
| Website Vitest | 11 files、118 tests passed |
| Website TypeScript/Nuxt typecheck | 通过 |
| Website Nuxt production build | 通过；仅有依赖包既有 deprecation warning |
| 本轮前端文件 Prettier | 通过 |
| 最终本地 Edge 验收 | 12 张真实截图；0 浏览器错误；0 外站请求 |

测试过程中的非产品前置问题如实记录：首次浏览器工具脚本曾分别因模块相对路径、既有认证变量名和 Playwright 自带 Chromium 未安装而在页面启动前停止；改用正确路径、既有变量名及电脑上已安装的 Edge 后，最终完整执行通过。首次 Ruff 容器缺少 dev optional 中的可执行文件，随后在一次性容器安装项目锁定的 Ruff 0.12.11 并实际通过。以上失败运行未计入 PASS。

## 8. 证据与后续状态

- 脱敏检查 JSON：`docs/content/phase3-7-batch01-preview-display-fix-checks.json`
- 最终截图：12 张，覆盖中英文首页、产品列表、P01/P02/P03、Gallery、桌面语言菜单、375px 与 320px。
- 分享 ZIP：在仓库外生成，包含本报告、脱敏 JSON 和上述 12 张截图；不包含账号、密码、Cookie、Token、数据库连接、对象存储键、内部 UUID 或私有签名 URL。

受保护预览继续保留，等待前台复验。
