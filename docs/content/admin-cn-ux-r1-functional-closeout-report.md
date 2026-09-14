# 中文后台 R1 功能收尾报告

- Run ID：`20260910T181356+0800`
- 工作区：`phase-3.7`（`phase-3.6` worktree）
- 基线 HEAD：`51061795a6cf54d50867769a4c23f342da671c11`
- 目标：`junhui-demo-r2`，经 `junhui-phase37-pilot` 本机 HTTPS 边缘入口访问
- 前台：`https://demo.junhuiscrewbarrel.com/`
- 后台：`https://admin-demo.junhuiscrewbarrel.com/`
- Git：本轮未 commit、push、merge 或改写历史

## 结果摘要

本轮两个剩余功能均已接通并完成真实操作验证：

1. 媒体使用位置不再只显示泛化的“产品 · 主图”。API 现在从白名单实体和真实关系读取中文优先的具体内容名称、使用角色及有权访问的维护入口；不同 owner 的同类引用分别保留，只对 `owner_type + owner_id + role` 完全相同的引用去重。私有媒体、私有 RFQ、对象存储键和无对应读取权限的 owner 均不返回。
2. 角色权限页已成为真实中文编辑器。系统角色只读；只有具备 `role.manage` 的当前账号可编辑非系统角色；保存前显示新增/移除对比，确认后调用既有 PUT API、CSRF、服务端权限上限检查和 Audit，并立即 fresh GET 校验。

下载、媒体和网站总览中的英语操作标签已显示为“英语”，接口中的 `en` 值及英语业务正文未改变。

## 实现范围

### 媒体使用位置

- 后端只识别显式白名单 owner；没有动态模型名或任意 owner 解析。
- 支持 Company、分类、产品、材料、工艺、应用、方案、案例、知识、FAQ、作者、制造能力、设备、证书、专利、荣誉、展会和下载资料等现有实体。
- 从主图等直接外键和 `ContentMediaLink` 两条真实关系链汇总。
- 只列出 `visibility=public` 的媒体；私有资产返回 404。
- 先检查媒体读取权限，再按 owner 的 `*.read` 权限过滤使用位置。
- 实体停用或作者公开资料关闭时不显示。
- 返回 DTO 仅含 `location`、`content_name`、`role`、`admin_url`，不含内部 owner ID、存储键或签名 URL。
- 无可见引用时前端明确显示“当前没有可查看的公开使用位置。”

### 角色权限管理

- API 角色 DTO 增加真实 `is_system` 标志；前端不再靠角色名猜测系统角色。
- 权限编辑按中文资源和动作分组；原权限代码只保留在技术详情和变更对比中。
- 保存前计算新增、移除和未变化项，忽略输入顺序和重复项。
- 保存成功后再次 GET `/api/v1/rbac/roles`，只有精确匹配才显示成功。
- Audit 的 `permission.change` 记录包含 `before_permission_codes` 和 `after_permission_codes`。
- 当前后端没有“新建角色”和“删除角色”接口；页面明确说明并不提供空按钮或假成功提示。本轮没有扩展这两个动作。

## 真实操作链

### 1. 媒体 → 具体使用对象 → 维护位置

- 视口：1440 × 900，浏览器 100% 缩放。
- 媒体：`approved-product-01.webp`。
- 实际 Admin/API 回读：`产品 / 通用注塑螺杆（演示） / primary / /catalog/products`。
- 页面显示为“通用注塑螺杆（演示）／产品 · 主图”。
- 实际点击“打开维护位置”后，浏览器进入 `https://admin-demo.junhuiscrewbarrel.com/catalog/products`，页面标题为“产品与型号”。
- Demo 主库当前没有同一媒体同时被多个产品引用的自然样本；不同产品同角色不被误去重、直接外键与关系表真重复只保留一次，已在隔离测试数据库的专项测试中验证。

### 2. TEST ONLY 角色 → 对比 → 保存 → fresh GET → 重开

- 视口：1366 × 900，浏览器 100% 缩放。
- 验收角色：`TEST ONLY 媒体维护角色`，`is_system=false`，用户绑定数为 0。
- 初始权限：`catalog.read`、`media.read`、`role.read`。
- 仅新增：`media.update`。
- 保存 API：PUT `/api/v1/rbac/roles/{test_role_id}/permissions`，实际返回 200。
- 保存后 fresh GET：200，四项权限逐项一致。
- 整页刷新并重新打开角色：200，仍显示四项权限，媒体“编辑”复选框保持选中。
- Audit（北京时间 2026-09-10 18:19:56）：动作 `permission.change`；before 为三项，after 为四项。
- 保存后数据库只读核对：测试角色仍未分配任何用户；系统角色状态指纹为 `da3baa8c4fd8b9a1942f768f44f04b22`。
- 该 TEST ONLY 角色为验收夹具；由于后端没有角色新建 API，最初建立夹具使用了 Demo 库内的受限 SQL，未分配用户。真正被验收的权限修改只通过现有 Admin/API/CSRF/Audit 链完成。

未用受限账号在主 Demo 浏览器登录。无 `role.manage` 的前端只读门禁由 Admin 定向测试覆盖；服务端拒绝保存由隔离测试账号实测为 403，目标角色 fresh GET 权限未变化。

## 1366 / 1440 检查

在 1366 × 900 和 1440 × 900、100% 缩放下分别打开媒体、角色权限、下载资料、网站总览：8 次页面检查均满足 `document.scrollWidth <= viewportWidth`，未发现共享列表横向溢出。

- 媒体编辑语言实际切换到“英语”后回读选中标签为“英语”，未保存内容。
- 下载资料新建表单实际显示“简体中文”和“英语”分组。
- 网站总览语言下拉实际显示“简体中文”和“英语”。

浏览器控制台仍可见一条 Nuxt hydration mismatch 错误；目标操作链、API 回读和页面布局未受影响。本轮未扩大范围处理该控制台问题，也未将其写为 PASS。两条 `/api/v1/roles` 404 是验收脚本首次使用错误诊断路径产生，修正为 `/api/v1/rbac/roles` 后两次真实回读均为 200。

## 验证结果

| 检查 | 实际结果 |
| --- | --- |
| API 专项：`pytest tests/test_admin_foundation_api.py ...` | PASS，12 passed，13.71s |
| 媒体认证、owner 权限、私有媒体排除、多对象保留、真重复去重 | PASS，包含于上述 12 项 |
| 角色保存、Audit、fresh GET、系统角色不变、无 `role.manage` 返回 403 | PASS，包含于上述 12 项 |
| Admin Vitest：`pnpm --filter @junhui/admin test` | PASS，13 files / 85 tests |
| Admin typecheck：`pnpm --filter @junhui/admin typecheck` | PASS |
| Prettier：`pnpm format:check` | PASS，全部匹配 |
| Admin build：`pnpm --filter @junhui/admin build` | PASS，Nuxt 4.5.2 构建完成 |
| Ruff | BLOCKED：宿主未发现 Ruff，现有 `junhui-global-website-api-test` 镜像也未安装；未新增依赖 |
| `git diff --check` | PASS；仅有 Windows LF/CRLF 提示，无空白错误 |

一次中间 API 测试因新建的测试邮箱使用 `.test` 后缀而登录校验返回 422；将纯测试邮箱改为 `example.com` 后重建测试镜像，最终 12 项全部通过。更早的 11 项结果来自未重建镜像，不计作本轮新增测试通过证据。

## 运行与冻结状态

- Demo API、Admin、Website、PostgreSQL、Redis、MinIO 和 Worker 均保持运行且健康。
- 容器业务服务没有宿主直出端口；唯一 HTTPS 入口仍为 `127.0.0.1:443->443/tcp`。
- 前台和后台登录页实际 HTTPS 返回 200；响应保留 `X-Robots-Tag: noindex, nofollow`、`Cache-Control: no-store` 和 `X-Junhui-Local-Preview: demo-r2-loopback-only`。
- 本轮只重建 Demo API/Admin；未运行 migration、Seed、导入、清库或重导。
- 未更改前台风格、原 phase37 业务库、Privacy、RFQ 提交、云服务器、公共 DNS 或 Git 历史。
- 临时测试 PostgreSQL、Redis 和 MinIO 已停止，测试卷保留；Demo 主实例继续运行。

## 证据

脱敏回读、截图、测试摘要和 SHA256 清单位于：

`data/demo-r2/evidence/admin-cn-r1-functional-closeout-20260910T181356+0800/`

证据不包含 Cookie、Token、密码、内部 owner ID、私有 RFQ、对象存储键或签名 URL。
