# Junhui Global Website Phase 3.1 基础工程设计

## 状态与约束

本设计直接落实《Junhui-Codex-Handoff-Phase3.1.md》中已经冻结并获准执行的决策。正式主域名为 `junhuiscrewbarrel.com`，V1 语言为 `/zh-cn/` 与 `/en/`，根路径仅作为语言入口。Phase 3.1 不实现最终首页、完整 CMS、RFQ、批量产品页、生产部署或微服务。

## 架构

仓库采用 pnpm workspace Monorepo。`apps/website` 与 `apps/admin` 是独立 Nuxt SSR 应用；`apps/api` 是 FastAPI 模块化单体。PostgreSQL、Redis、MinIO 与三个应用通过 Docker Compose 组成一键本地环境。后端以 SQLAlchemy 2.x async session、Alembic 和确定性 Seed 为数据基础。

## 数据模型

本阶段只创建 `users`、`roles`、`permissions`、`user_roles`、`role_permissions`、`locales`。所有字段使用英文名并带中文数据库注释；多对多关系使用显式关联表和联合主键。`locales` 保存标准代码、URL slug、名称、默认/启用状态和排序，保持未来 Master Entity + Translation tables 的扩展方向。

## HTTP 与异常约定

API 前缀为 `/api/v1`。健康检查返回统一 JSON envelope，包含 `success`、`data` 与 `error`。应用级异常由集中处理器转成同一格式；未知异常返回不泄露内部细节的 500。分页模块只提供经过边界约束的基础参数，不引入业务 CRUD。

## SEO / GEO 基线

Website 使用 SSR，根路径执行服务端 308 到 `/zh-cn/`，两个语言 placeholder 各自输出唯一 title、description、canonical、hreflang、可见 H1 和直接说明。内容保持极简，不创建 Schema、Sitemap、批量内容或最终视觉。Admin 输出 `noindex,nofollow`，避免管理壳进入索引。

## 测试与验收

测试覆盖 health、数据库连接、迁移到 head、locale Seed、RBAC Seed，以及两个前端的 build 与 SSR 路由响应。最终通过 Docker Compose 实测所有服务健康、迁移、Seed、API、Website、Admin 和测试命令，并把实际结果写入完成报告。

