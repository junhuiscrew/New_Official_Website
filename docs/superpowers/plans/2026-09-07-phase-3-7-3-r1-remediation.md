# Phase 3.7.3 R1 首发准备整改执行计划

> 状态：执行中。唯一运行目标为 `phase37-local-https`；不含生产上线、CMS Review/Publish、commit、push 或 merge。

## 1. 基线与冻结快照

- 记录实际 HEAD、未提交路径及 SHA-256、容器/镜像/配置版本。
- 只读记录 HTTPS、Basic Auth、noindex、Sitemap 404、端口隔离及 Batch01 内容生命周期不变量。
- 私有证据写入 `data/phase3-7/r1-remediation/<run-id>/`，不把凭据或内部 ID 放入分享包。

## 2. 先写失败测试

- API：真实 PostgreSQL CJK 标题/正文包含匹配、公开门禁、去重排序与英文回归。
- API：导航 `primary` 只包含当前语言存在严格公开内容的栏目，同时保留 Products/About。
- API：产品面包屑中英文标签及正式 Schema URL。
- API：统一 Sitemap 候选包含合格双语首页/产品总列表，仍排除不合格 owner 路由。
- Website：桌面、移动和页脚遵守 Navigation API 的 `primary`；Breadcrumb 只把可信正式站 URL 转成相对路径。

## 3. 最小工程修复

- 在既有 PostgreSQL 搜索表达式中加入参数化的字面子串补充匹配，继续复用完整公开查询门禁。
- 由 Navigation API 根据严格公开内容动态返回可显示栏目，三处前端统一消费该字段。
- 本地化产品面包屑标签；复用并加固正式 Origin 到相对导航的 URL 解析函数，不改 canonical/hreflang/Schema item。
- 增加聚合页 Sitemap 候选生成器，使用合格 owner 路由推导首页/产品总列表资格与可证实 lastmod；常驻开关不变。
- 仅修复经测试证实的 SEO DTO→SSR 接线遗漏；未批准的 8 组元数据只写候选文件。

## 4. 内容准备与事实核对

- 从当前已批准可见正文准备 About、Products、screws、barrels 双语候选 title/description，标记待批准且禁止写库。
- 从 RFQ schema、服务、RBAC、对象存储、扫描、日志及配置整理隐私事实；把生产责任、联系渠道、供应商/地区、保留删除与营销用途收敛成最小问题清单。
- 保留 F-R1-006 与 L-R1-001 为接受限制/未测，不造价格评分或 Lighthouse 分数。

## 5. 验证、运行态更新与交付

- 运行 Ruff、后端专项与真实 PostgreSQL、Website Vitest/typecheck/format/build；Admin 未改则不跑 Admin。
- 仅重建 API 与 Website，保留数据库/对象存储卷和 Nginx 保护；核对运行文件/镜像已加载新代码。
- 用真实 Edge/Playwright 完成中文搜索输入→点击、桌面/移动导航、中文面包屑点击、核心页面与保护冒烟，并保存脱敏截图/JSON。
- 复核 COPY-V1、参数 0/0/0、F05 英文空缺、旧试点和生命周期状态；生成报告、候选文件、manifest、SHA256SUMS 与 ZIP。
