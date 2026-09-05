# Phase 3.5 Final Patch v2 完成报告

## 1. Branch 与提交基线

- Branch：`phase-3.5-final-patch-v2`
- Base branch：`phase-3.5-final-patch`
- Base SHA：`09c05dffc778e82afed76a6cc3de43c615f73b1e`
- Final implementation SHA：`ecef0fc407987a1d692e8b753c53c0b2ce5dda74`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 数据库 migration：无新增 migration；本轮复用既有 `translation_statuses`、`content_publications`、`content_routes`、`content_revisions` 与 `audit_logs`。

> 本报告单独作为文档提交，因此 Final implementation SHA 指本轮功能代码与回归测试提交，不使用无法自引用的报告提交 SHA。

## 2. Non-route Trust Translation 生命周期修复

### 2.1 生命周期与公开门禁

- Equipment、Certificate、Patent、Honor 已支持 `draft -> human_reviewed -> published` 的 TranslationStatus 生命周期。
- Review 仅允许 `draft` Translation；Publish 仅允许 `human_reviewed` 且实体状态为 `enabled` 的 Translation。
- Review 与 Publish 都写入 Audit Log，并记录审核人、审核时间或发布时间。
- 已审核或已发布 Translation 编辑后继续复用既有失效逻辑，自动回到 `draft`，清空审核/发布时间并从公开聚合结果消失。
- enabled 的 non-route Trust 被 disabled/retired 后，其 TranslationStatus 会撤回为 `draft`；重新启用不会自动恢复发布。
- Public Trust 聚合查询继续同时要求：Business Entity enabled、Locale enabled、TranslationStatus published。

### 2.2 不建立第二套公开路由

- Equipment、Certificate、Patent、Honor 仍不创建独立 `ContentPublication` 或 `ContentRoute`。
- Admin 列表明确返回这些实体的 TranslationStatus，并为 `publications` / `routes` 返回空数组，避免前端误判。
- Admin Trust CRUD 已增加 non-route Translation Review 与 Publish 操作；Capability / Exhibition 仍使用统一 Publication 工作流。
- 本轮没有修改 `0001~0009` migration，也没有增加数据库表或第二套生命周期。

### 2.3 Capability Equipment 公开结构化内容

- Public Capability DTO 新增真实关联 Equipment 结构化数据。
- 后端仅返回 enabled 且当前 Locale TranslationStatus 为 `published` 的关联 Equipment。
- Nuxt Capability SSR 页面把该 DTO 输出为用户可见 HTML；设备名称、说明、制造商、型号、数量与公开规格不会成为仅供 AI 消费的隐藏内容。
- 已发布 Equipment Translation 再次编辑后，设备会立即从 Capability 公开结构化模块消失，直至重新审核和发布。

## 3. Reviewer RBAC 修复

- Route-based Trust 与 Company Profile 的 Translation Review 显式要求 `translation.review`，统一 Publication 的 `draft -> review` 转换要求 `content.review`。
- Route-based Trust 与 Company Profile Publish 同时要求 `translation.publish` 和 `content.publish`。
- Non-route Trust Review 使用 `translation.review`，Publish 使用 `translation.publish`。
- Reviewer Seed 增加 Company、Capability、Equipment、Certificate、Patent、Honor、Exhibition 的只读权限，以便读取审核对象；没有新增任何对应 `*.update` 权限。
- Reviewer 在没有 `company.update`、`capability.update`、`exhibition.update` 的情况下可以完成 Review；具备两类 Publish 权限时可以发布。
- Editor 仅有实体更新/内容更新权限时，Review 与 Publish 均由服务端返回 `403 permission_denied`。
- Admin Route Guard 仍只是交互层；最终权限判断始终由 FastAPI 服务端执行。

## 4. 回归测试结果

| 验证项 | 实际结果 |
| --- | --- |
| Ruff | 通过，`All checks passed!` |
| Backend pytest（本机完整套件） | `183 passed, 9 skipped`；跳过项为需要真实 PostgreSQL/Redis/MinIO 的集成用例 |
| Docker API test profile | `192 passed`，使用真实 PostgreSQL、Redis 与 MinIO |
| Final Patch v2 聚焦 RBAC 复验 | `3 passed` |
| PostgreSQL integration | 通过；Docker profile 覆盖空数据库 migration、Seed 与 PostgreSQL 专项用例 |
| MinIO integration | 通过；Docker profile 使用真实 MinIO |
| Website Vitest | `15 passed` |
| Admin Vitest | `23 passed` |
| Typecheck | Website/Admin 均通过 |
| Prettier | 通过，所有匹配文件符合格式 |
| Production Build | Website/Admin Nuxt production build 均通过 |

新增或扩展的回归覆盖包括：

- Certificate `draft -> human_reviewed -> published`，发布前不可见、发布后聚合页可见。
- Patent/Honor 已发布 Translation 编辑后回到 draft，并从公开聚合页消失。
- Equipment 只有已发布 Translation 才能进入 Capability 公开 DTO；编辑后立即撤回。
- Reviewer 无实体 update 权限但有 review 权限时可以审核 Trust 与 Company。
- Editor 只有实体/content update 权限时不能 Review 或 Publish。
- Non-route Trust 在 Review/Publish 后仍不存在 ContentPublication / ContentRoute。
- Admin non-route Review/Publish 契约与 Website Capability Equipment SSR 可见内容契约。

## 5. SEO / GEO 一致性检查

- 使用 `$seo-rank` 核对公开门禁与服务器渲染：未发布、被编辑撤回或 disabled/retired 的 non-route Trust 不再进入公开聚合模块，避免搜索引擎继续读取过期权威事实。
- 使用 `$geo-rank` 核对可见内容一致性：Capability Equipment 由后端按真实发布状态构造，并在 Nuxt SSR 中作为用户可见 HTML 输出，不存在 AI-only 隐藏事实。
- Equipment、Certificate、Patent、Honor 不产生独立 URL，因此不会制造孤立页、重复 canonical、错误 hreflang 或 Sitemap 条目。
- 本轮未改变既有 canonical、hreflang、Sitemap、Schema 或 GEO 文档体系，未发现与正式交接文件冻结架构的冲突。

## 6. Production Build 与 Docker

- 根目录执行 `pnpm build` 成功，Website 与 Admin 的 Client/Server production build 均完成。
- Docker 镜像重新构建成功：`api`、`worker`、`website`、`admin`。
- Docker Compose 最终状态：
  - `api`：healthy
  - `worker`：healthy
  - `website`：healthy
  - `admin`：healthy
  - `postgres`：healthy
  - `redis`：healthy
  - `minio`：healthy
  - `nginx`：healthy
- Docker test profile 中 `postgres-test` 与 `redis-test` 也为 healthy。

## 7. Known issues

- 本轮不 Seed 假证书、假专利、假设备或假荣誉；无真实已审核发布数据时，公开聚合模块按设计为空。
- Non-route Trust 没有独立详情 URL、Publication 或 Route；该约束是本阶段冻结设计，不是缺失实现。
- Admin 可以展示 Review/Publish 操作，但服务端 RBAC 才是最终安全边界；无权限操作会返回 403。
- Production 部署、最终首页、最终 Design System、Page Builder 与 Phase 3.6 均未进入本轮范围。

## 8. 范围确认

- 只完成 Phase 3.5 Final Patch v2 的两个修复项与对应回归测试。
- 未修改已冻结主域名、核心技术栈、Translation/Publication/Route 模型或 SEO/GEO 核心原则。
- 未进入 Phase 3.6、Final Homepage、Final Design System、Page Builder 或生产部署。
