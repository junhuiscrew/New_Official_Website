# ADR: Content Route 与 Publication 事务边界

- 状态：Accepted
- 日期：2026-09-04
- 适用阶段：Phase 3.2 及后续 Structured Core CMS

## 决策

所有公开内容采用 Master Entity + Translation 状态记录，不复制整套业务数据。V1 URL 固定使用 `/zh-cn/` 与 `/en/` 语言前缀；路径必须小写、kebab-case、首尾带斜杠。正式 canonical host 固定为 `https://junhuiscrewbarrel.com`，每种已发布语言 self-canonical，只有已发布翻译才允许生成 hreflang。

发布动作必须在一个数据库事务中同步变更：

1. `content_publications.status`
2. `translation_statuses.status` 与 `published_at`
3. `content_routes.active`
4. `content_routes.indexable`
5. `audit_logs`

只有 `published` 内容可令 route 同时 `active=true`、`indexable=true`。`draft`、`review`、`scheduled` 和 `archived` 均不得进入公开索引。GEO direct answer 必须来自同一公开 SSR 正文；不得建立 AI-only 隐藏内容或绕过发布状态的机器专用路由。

服务在任何状态变更前校验 Publication、Translation、Route 的 `(owner_type, owner_id, locale_id)` 完全一致，并拒绝向禁用 Locale 发布。发布只接受唯一 canonical Route，不能通过非 canonical Route 绕过 URL 规则。事务按 Locale → Publication → Translation → Route 的固定顺序获取行锁，Locale 停用与发布、同一内容的竞争状态转换因此被串行化。数据库 partial unique index 保证每个 owner/locale 最多一个 canonical route，避免并发请求绕过服务层检查。

## 权限与状态转换

- `draft → review`：要求 `content.update`。
- `review → scheduled/published`：要求 `content.publish`。
- `scheduled → published`：要求 `content.publish`。
- `published → archived`：要求 `content.archive`。
- `archived → draft`：要求 `content.update`。
- 只有达到 `human_reviewed` 的翻译才能随内容发布；translator 角色不具备 `content.publish`，不能绕过 reviewer。

## Slug 变更与 Redirect

已发布 canonical path 视为不可原地改写。后续 Slug 变更 API 必须在同一事务中创建旧路径到新路径的永久 Redirect、注册新 canonical route、停用旧 route，并更新 sitemap/internal links。Phase 3.2 不开放已发布路径修改 API，因此不会产生“改 URL 但没有 Redirect”的中间状态。

## Revision 与回滚

`content_revisions` 保存不可变 JSONB 快照和 owner/locale 内递增修订号。PostgreSQL 使用以 owner/type/locale 为键的事务级 advisory lock 串行化 `max(revision_no)+1` 分配；唯一约束作为最终防线。回滚读取只返回快照副本；未来具体内容模块应用该副本时必须创建一个新的 revision，禁止覆写历史记录。

## 结果

该边界保证 Content、Translation、Route 与 SEO indexable 状态不会部分提交。Schema、canonical、hreflang、sitemap 和用户可见内容必须从已发布状态派生，避免搜索引擎和 AI answer systems 读取草稿或不一致实体。
