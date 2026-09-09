# Demo R2 实施计划

> 执行方式：在当前 phase-3.7 工作区内分批实施并逐批验证；遵守用户“不自动 commit/push/merge”的要求。

## Task 1：冻结基线与建立 Demo 环境契约

- 新增 Demo 专用环境示例、Compose/Nginx/TLS/hosts/快捷方式工具。
- 编写配置测试，证明宿主只绑定 `127.0.0.1`、域名精确、数据卷独立、普通启动不自动 Demo seed。
- 记录主实例关键冻结项快照与代码/容器基线。

## Task 2：Demo 来源与媒体关联模型

- 先新增失败的模型、约束和迁移测试。
- 追加线性 Alembic 迁移，新增 `demo_content_records`、`content_media_links`。
- 增加服务与 API DTO，验证权限、冲突保护、引用完整性和生产默认关闭。

## Task 3：显式幂等 Demo 初始化器

- 将 `03-Demo-Content-V1.json` 作为输入数据映射，而非 API payload。
- 复用基础 seed 与领域服务创建 90 条样例、双语翻译、关系、SEO/GEO、生命周期和首页配置。
- 保存 alias→UUID manifest、初始指纹；验证重复运行 no-op、人工修改冲突跳过。

## Task 4：媒体生产与入库

- 生成至少 18 张有区分度的演示图像和两个 MP4 视频及 poster。
- 制作 3 个有效示例下载文件。
- 通过 Demo Media API 入库并写入双语 alt/caption、尺寸、时长、来源与关系。

## Task 5：后台应用壳与工作台

- 修复根路由/登录恢复/SSR 资源白屏。
- 先写 Admin 组件测试，再实现左侧导航、顶栏、Demo 标识、工作台统计和最近活动。
- 统一 tokens、列表、表单、状态、错误和响应式壳。

## Task 6：后台业务列表与编辑器

- 完善产品/内容列表、编辑器、媒体库、关系选择、规格/型号、SEO/GEO、发布历史和 RFQ 页面。
- 确保所有按钮调用真实 API，处理 403/409/500，不暴露 UUID/JSON。
- 真实执行保存→刷新→重开。

## Task 7：完整前台与 14 模块首页

- 先为各模块和页面族补 SSR/组件测试。
- 重构共享视觉 tokens、Header/Footer、卡片、过滤器、媒体组件和详情布局。
- 使用 API 内容渲染 14 模块及产品/材料/工艺/应用/方案/案例/知识/About/Contact/下载视频/RFQ。

## Task 8：生命周期传播场景

- 在 Demo 环境依次验证产品改文换图、规格/关系、SEO/GEO、视频替换、文章发布撤回、首页排序和虚构 RFQ。
- 每个场景保留 API 前后回读、首次 SSR 和浏览器截图。

## Task 9：专项回归与安全检查

- 运行 Ruff、后端专项、真实 PostgreSQL 迁移/约束/并发测试。
- 运行 Admin/Website 测试、typecheck、format check 和 build。
- 检查 noindex、Sitemap 关闭、匿名 Admin/私有附件拒绝、loopback 监听和主实例冻结项。

## Task 10：视觉验收与交付

- 在 1440/1920/375/430 前台和 1366/1440 后台截取完整页面。
- 使用设计候选逐项对比并修正明显差异。
- 生成快捷方式、日常维护说明、`demo-r2-report.md`、manifest/SHA256SUMS 和脱敏证据 ZIP。
- 完成后保持 Demo 服务和数据运行，不自动清理、提交或推送。
