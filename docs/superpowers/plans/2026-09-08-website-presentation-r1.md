# 官网呈现 V1.0 · R1 实施计划

> 用户明确禁止本轮 commit、push、merge；因此每个任务完成后保留工作树修改，不执行计划模板中的提交步骤。

## 1. 锁定基线与失败测试

- 保存 HEAD、工作树、运行容器、数据库版本、14模块数据量和冻结字段快照到私有证据目录。
- 新增后端模型/服务/API测试：固定模块白名单、默认配置、并发修订冲突、权限、CSRF、Revision/Audit、应用/恢复、公开/预览 DTO、匿名预览拒绝、no-store。
- 新增 PostgreSQL 迁移测试：升级/降级/再升级、约束、唯一性、并发。
- 新增 Admin 合同与组件测试：首页编辑器、产品选择、应用权限、模块总览。
- 新增 Website 测试：十四 renderer、普通空内容隐藏、预览空态、真实产品图、移动结构、noindex/no-store 路由。
- 先运行上述专项并记录预期失败。

## 2. 后端与迁移

- 新增 `presentation` 模块模型、Schema、服务及受保护 API。
- 在 `20260908_0013` 后追加 `20260908_0014_homepage_presentation_r1.py`，扩展 SitePage home 白名单并创建首页布局表；不修改历史迁移。
- 首页初始化只建立固定页面和双语安全默认配置，不导入业务正文。
- 扩展 Public Home 聚合：读取应用布局、按 slug 解析严格公开产品、补齐 Technology/Equipment/Certificate/Patent 数据源。
- 新增认证作者预览 DTO 和模块总览 DTO；返回安全缺件状态，不返回草稿正文、私有附件、Privacy 或 RFQ 内容。

## 3. Admin

- 新增 `/homepage` 模块编辑器与 `/site-overview` 模块总览。
- 更新 Admin 导航和 CSS，提供双语、排序、显隐、有限变体、三产品引用、保存、应用、恢复与预览入口。
- 所有写操作使用现有认证、CSRF 和回读确认；前端不接受 UUID/JSON/HTML。

## 4. Website 与本机预览入口

- 把 HomePage 重构为配置驱动的十四模块共享 renderer。
- 实现蓝白完整首页、三款产品真实主图、分类、公司介绍和 RFQ CTA；空内容不在普通首页出现。
- 新增 `/preview/[lang]/` SSR 页面，只请求受保护预览 API并转发 Cookie；设置 no-store/noindex。
- 在本机域名 Nginx 的 Admin 虚拟主机中加入精确 `/preview/` Website 代理；默认 staging/production 配置不改变。

## 5. 验证与主实例更新

- 在独立真实 PostgreSQL 中执行迁移升级/降级/再升级和并发测试。
- 为主实例保存私有数据库安全快照，应用迁移，使用正确 Compose 覆盖仅重建受影响服务，不 Seed、不清卷。
- 后台实际执行排序、保存、刷新重开、隐藏/恢复、三产品选择、应用布局；最终恢复批准的展示状态。
- 浏览器验证中英文桌面/375px完整滚动、产品/分类/语言/移动菜单/RFQ点击、匿名预览拒绝和 no-store/noindex。
- 运行 Ruff、后端专项、PostgreSQL专项、Admin/Website测试、typecheck、lint、format check、build；只记录实际结果。

## 6. 交付

- 生成 `docs/content/website-presentation-r1-report.md`。
- 生成 `docs/content/website-presentation-r1-admin-guide.md` 与内容缺口/模块对照附件。
- 私有证据目录保存截图、API回读、命令结果、manifest、SHA256SUMS；制作脱敏 ZIP。
- 最终保持本地域名模式运行，报告真实 URL、剩余资料缺口及不变量核对。
