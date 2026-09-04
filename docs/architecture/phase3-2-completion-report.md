# Junhui Global Website Phase 3.2 完成报告

- 日期：2026-09-04
- 仓库：`junhuiscrew/New_Official_Website`
- 分支：`phase-3.2`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 范围：Authentication + RBAC + Localization + Publication Foundation
- 结论：Phase 3.2 规定的基础能力已实现，并通过本机、Docker 与真实 PostgreSQL 验证；未实现本阶段禁止的完整 CMS、产品、RFQ、最终首页或生产部署。

## 1. 实际修改文件树

以下为本阶段实际新增或重点修改的交付树；未改动的 Phase 3.1 基础文件省略。

```text
junhui-global-website/
├─ Junhui-Codex-Handoff-Phase3.2.md
├─ .env.example
├─ .gitignore
├─ docker-compose.yml
├─ docker-compose.staging.yml
├─ README.md
├─ packages/config/
│  ├─ package.json
│  └─ src/api-base.ts
├─ apps/
│  ├─ website/
│  │  ├─ Dockerfile
│  │  ├─ nuxt.config.ts
│  │  ├─ app/composables/useApi.ts
│  │  └─ tests/api-base.test.ts
│  ├─ admin/
│  │  ├─ Dockerfile
│  │  ├─ nuxt.config.ts
│  │  ├─ app/
│  │  │  ├─ app.vue
│  │  │  ├─ auth-policy.ts
│  │  │  ├─ composables/useAuth.ts
│  │  │  ├─ middleware/auth.global.ts
│  │  │  └─ pages/{index,login,forbidden,users,roles,locales}.vue
│  │  └─ tests/{admin-contract,api-base,auth-guard}.test.ts
│  └─ api/
│     ├─ Dockerfile
│     ├─ pyproject.toml
│     ├─ alembic/
│     │  ├─ env.py
│     │  └─ versions/{20260904_0002_phase32_foundation,20260904_0003_content_integrity}.py
│     ├─ app/
│     │  ├─ api/v1/{auth,health,locales,rbac,users}.py
│     │  ├─ core/config/settings.py
│     │  ├─ core/request_context.py
│     │  ├─ core/security/{csrf,passwords,tokens}.py
│     │  ├─ modules/auth/{dependencies,models,schemas,service}.py
│     │  ├─ modules/audit/{models,service}.py
│     │  ├─ modules/content/{enums,models}.py
│     │  ├─ modules/content/services/{publication,revisions,routes}.py
│     │  ├─ modules/localization/{models,schemas,service}.py
│     │  ├─ modules/users/{bootstrap,models,schemas,service}.py
│     │  ├─ cli.py
│     │  └─ seed.py
│     └─ tests/
│        ├─ test_authentication.py
│        ├─ test_rbac.py
│        ├─ test_locales.py
│        ├─ test_publication.py
│        ├─ test_content_routes.py
│        ├─ test_revisions.py
│        ├─ test_postgresql_integration.py
│        ├─ test_request_context.py
│        └─ 其余 migration/seed/security/API contract 测试
├─ infra/
│  ├─ nginx/nginx.staging.conf
│  └─ scripts/verify-local.ps1
└─ docs/architecture/
   ├─ adr-content-route-publication.md
   ├─ migration-runtime-strategy.md
   └─ phase3-2-completion-report.md
```

核心版本：Python 3.12、FastAPI 0.116.1、SQLAlchemy 2.0.43、Alembic 1.16.5、Argon2 25.1.0、PyJWT 2.10.1、Nuxt 4.5.2、Vue 3.5.42、TypeScript 5.9.2、Node 24、pnpm 11.19.0、PostgreSQL 17.6、Redis 8.2、Nginx 1.28、MinIO `RELEASE.2025-09-07T16-13-09Z`。

## 2. 新 migrations

新增两版顺序 migration：`20260904_0002_phase32_foundation.py` 与 `20260904_0003_content_integrity.py`：

- PostgreSQL 启用 `citext`，将 `users.email` 转为 `CITEXT` 并保持唯一索引。
- 为 `locales.is_default = true` 增加 partial unique index `ux_locales_single_default`。
- 新建 `auth_sessions`、`translation_statuses`、`content_publications`、`content_routes`、`content_revisions`、`audit_logs`。
- `0003` 增加 `ux_content_routes_one_canonical` partial unique index，保证同一 owner/locale 最多一个 canonical route。
- 每个字段使用英文名称并附中文数据库 comment；状态字段有数据库 Check Constraint。
- 提供逆依赖顺序 downgrade；生产回滚不建议自动 downgrade。

实际在空 PostgreSQL 17 测试库执行 `0001 → 0002 → 0003` 成功；常驻开发库 `alembic current` 为 `20260904_0003 (head)`。

## 3. Authentication 设计

实现 `/api/v1/auth/login`、`/refresh`、`/logout`、`/me`。登录加载启用用户及完整角色权限；未知邮箱仍执行哑元 Argon2id 校验并统一返回 401，降低账号枚举计时差。Refresh 使用服务端 `auth_sessions`，支持轮换、撤销、过期和 replay 拒绝；旧凭据重放会撤销该用户仍有效的后继 refresh session。登录成功、失败及退出写入审计日志。

`get_current_user` 只接受有效短期 access JWT 并重新读取用户启用状态；真正授权在 FastAPI 服务端完成，Admin Guard 不作为安全边界。

## 4. Cookie / Token 设计

- `junhui_access`：HS256 短期 JWT，默认 15 分钟，HttpOnly、SameSite=Lax、Path=/。
- `junhui_refresh`：256-bit 高熵随机凭据，默认 14 天，HttpOnly、SameSite=Lax、Path=/api/v1/auth。
- 数据库仅保存 refresh 的 HMAC-SHA256 摘要，不保存明文。
- `junhui_csrf`：非 HttpOnly 双提交 Cookie；refresh、logout 与业务写接口要求 `X-CSRF-Token` 匹配。
- Staging/Production 强制 Secure Cookie；Refresh 不出现在 JSON、`localStorage` 或客户端持久状态。
- Logout 会撤销 refresh session 并删除 Cookie；已泄露的 access JWT 最长仍可能在其 15 分钟 TTL 内有效。
- Admin 客户端在 `/me` 返回 401 时自动调用一次 `/refresh`，不在 SSR 内刷新，避免内部响应 Cookie 无法安全透传。

## 5. Password hash

使用 `argon2-cffi` 的 Argon2id；创建用户和 Bootstrap 都先执行密码强度校验，仅保存编码后的 Argon2id 哈希。代码和 Seed 不包含默认管理员密码。

## 6. Permission matrix

Seed 冻结 36 个 `resource.action` 原子权限：

| 域 | 权限 |
| --- | --- |
| User | `read/create/update/disable` |
| Role | `read/manage` |
| Locale | `read/manage` |
| Content | `read/create/update/review/publish/archive` |
| Translation | `read/create/update/review/publish` |
| SEO | `read/update` |
| GEO | `read/update` |
| Redirect | `read/manage` |
| Media | `read/upload/update/delete` |
| RFQ | `read/assign/update/download_private_file` |
| Settings | `read/update` |
| Audit | `read` |

FastAPI 提供 `require_permission(...)`、`require_any_permission(...)` 和少量系统场景使用的 `require_role(...)`。缺失权限返回 403。

## 7. Role matrix

| Role | 权限数 | 冻结范围 |
| --- | ---: | --- |
| `super_admin` | 36 | 全部权限 |
| `content_admin` | 27 | Content、Translation、Media、Locale 管理及 SEO/GEO/Redirect 等内容运营权限 |
| `editor` | 6 | 内容读/建/改、翻译读、媒体读/上传 |
| `translator` | 5 | 内容读、Locale 读、翻译读/建/改 |
| `reviewer` | 7 | 内容审核/发布、翻译审核/发布、审计读 |
| `seo_manager` | 10 | 内容/翻译/Locale 读，SEO/GEO/Redirect 管理，审计读 |
| `sales` | 4 | RFQ 全部原子权限 |
| `media_manager` | 4 | Media 全部原子权限 |

幂等 Seed 只添加缺失关系，不删除人工新增的权限或角色映射。Admin 可读取矩阵并在 `role.manage` 服务端授权下更新；角色权限更新和用户角色分配都受操作者自身 permission ceiling 限制。创建用户并分配角色同时要求 `user.create` 与 `role.manage`。

## 8. Bootstrap super admin 方法

无默认管理员。安全命令：

```bash
docker compose exec api python -m app.cli create-super-admin
```

交互输入 email/password/display name；自动化可临时传入 `BOOTSTRAP_ADMIN_*` 环境变量。命令验证强密码、大小写不敏感重复邮箱、`super_admin` Role 存在，并记录 `user.create` 与 `role.assign` 审计；不会覆盖已有账户。

实际创建临时管理员完成 login/RBAC/refresh/logout smoke test 后，已从开发数据库删除，仓库和常驻数据库均无默认密码。

## 9. Locale / translation model

Locale API 支持 list、create、update、启停、排序和设置默认；写操作要求 `locale.manage` 与 CSRF。默认语言切换在单事务内完成，当前默认语言不能直接禁用；`zh-CN/zh-cn` 与 `en/en` 的 V1 标识被冻结，已被内容引用的 Locale 不可改写 code/slug，存在公开或计划发布内容时不可停用。数据库 partial unique index 保证即使并发或绕过服务层也只能有一个默认 Locale。

默认语言切换会先按 Locale 主键固定顺序锁定完整集合，再清除旧默认值并设置新默认值，避免两个不同目标的并发请求形成死锁；真实 PostgreSQL 多轮并发测试确认两个事务都能完成且始终只有一个默认语言。Seed：`zh-CN`/`zh-cn` 为默认且启用，`en`/`en` 启用。`translation_statuses` 以 `(owner_type, owner_id, locale_id)` 唯一关联 Master Entity，状态为 `missing/draft/machine_translated/human_reviewed/published`，保存源语言、翻译人、审核人及发布时间。

## 10. Publication model

`content_publications` 以 `(owner_type, owner_id, locale_id)` 唯一关联内容语言版本，统一状态冻结为 `draft/review/scheduled/published/archived`。状态机禁止越级转换，并在任何写入前验证 Publication/Translation/Route 属于同一 owner/locale、Locale 已启用且 Route 为 canonical，再将权限校验、翻译门禁、Route active/indexable 及审计写入放在同一数据库事务中。事务按 Locale → Publication → Translation → Route 的固定顺序获取行锁；真实 PostgreSQL 并发测试覆盖“停用 Locale 与发布竞争”和“同一 Publication 竞争状态转换”。只有 `human_reviewed` 翻译可进入 published。

## 11. Route transaction ADR

ADR 位于 `docs/architecture/adr-content-route-publication.md`。V1 路径固定 `/zh-cn/`、`/en/` 前缀，小写 kebab-case 且首尾 `/`；canonical host 固定 `https://junhuiscrewbarrel.com`。只有 published Route 可同时 `active=true/indexable=true`，只有已发布语言进入 canonical/hreflang/sitemap。

已发布 URL 不允许原地修改；后续 Slug 变更必须在同一事务创建永久 Redirect、切换 canonical、更新索引状态。Phase 3.2 没有提前开放该修改 API。数据库 partial unique index 确保每个 owner/locale 最多一个 canonical route。

## 12. Revision model

`content_revisions` 按 `(owner_type, owner_id, locale_id, revision_no)` 唯一保存不可变 JSON/PostgreSQL JSONB 快照、变更人和创建时间。PostgreSQL 事务级 advisory lock 串行化同一 owner/locale 的修订号分配，并由唯一约束兜底；真实 PostgreSQL 并发测试得到连续的 `1, 2`。回滚服务只读取深拷贝；后续真正应用回滚时必须创建新 revision，禁止覆写历史。

## 13. Audit model

`audit_logs` 保存 user、action、target type/id、IP、User-Agent、结构化 metadata 和时间。已覆盖 login success/failure、logout、用户创建/修改/禁用、角色分配、权限变更、Locale 变更、Publication 状态与 Route 变更；logout 可关联实际用户与 auth session。用户删除时审计事件保留，`user_id` 置空。默认记录应用直连 peer；只有直连 peer 命中显式 `TRUSTED_PROXY_CIDRS` 时才读取单值 `X-Forwarded-For`。Staging Nginx 覆盖而不是拼接外部转发头，防止客户端伪造审计 IP。

## 14. CORS / Origin 策略

浏览器首选同源 `/api/v1`，本地跨端口开发仅允许 `http://localhost:3000`、`:3001`、`:8080`。CORS 开启 credentials，显式声明 allowlist，禁止 `*`；Staging/Production 未配置 allowlist、使用本地/非 HTTPS Origin、`.localhost`、loopback/link-local/unspecified IP 或包含通配符时拒绝启动。`APP_ENV` 只接受 `development/test/staging/production`，`prod` 等别名也会 fail-fast。自动化测试覆盖允许与拒绝 Origin。

## 15. Staging security

`docker-compose.staging.yml` + `nginx.staging.conf` 实现：仅 Nginx 发布宿主端口；PostgreSQL、Redis、MinIO、API、Website、Admin 不可绕过入口；外部 htpasswd、Basic Auth、全站 `X-Robots-Tag: noindex, nofollow`、关闭 sitemap/analytics/marketing email、Secure Cookie 和必填强 Secret。MinIO 根凭据与 API 客户端凭据来自同一组显式变量，Website/Admin 镜像运行 Nuxt production server。

实际启动隔离的完整 Staging Compose 栈验证：8 个服务全部 healthy；未认证 `/admin/` 为 `401`，认证后的 `/admin/`、`/admin/login`、`/zh-cn/`、`/api/v1/health/ready` 均为 `200`，健康端点为 `200`；所有响应均有 `noindex, nofollow`。Admin `/admin/` base path、代理前缀和健康检查保持一致。合并 Compose 配置只发布 Nginx，MinIO 凭据一致。临时容器、网络、数据卷和 htpasswd 已清理。Admin 自身 HTML meta 与响应头也均实测存在 noindex。

## 16. Health live/ready

- `/api/v1/health/live`：只验证应用进程可响应。
- `/api/v1/health/ready`：实际执行 PostgreSQL `SELECT 1` 与 Redis `PING`，任一依赖失败返回 503。
- Docker API healthcheck 和 Nginx 流量门禁使用 ready。
- 旧 `/api/v1/health` 暂时保留兼容，后续可在调用方迁移后移除。

运行态 live、ready、经 Nginx 的 ready 均返回 200。

## 17. API public/internal base

共享 `@junhui/config/api-base` 统一解析：浏览器使用 `/api/v1`；Nuxt SSR 使用 `NUXT_API_INTERNAL_BASE=http://api:8000/api/v1`。Website `useApi` 与 Admin `useAuth` 均使用该规则。Admin SSR 只输出无敏感数据的应用壳，Current User、自动 refresh 与 Route Guard 在客户端执行；Nitro `/api/**` proxy 消除了浏览器访问 Docker 内部主机名的问题。

## 18. 测试结果

| 验证 | 结果 |
| --- | --- |
| 本机 backend pytest | 79 passed，6 个 PostgreSQL profile 测试按设计 deselected |
| Docker PostgreSQL 17 backend | 85 passed，包含空库 migration/seed/CITEXT/default Locale/auth session/canonical route、并发默认 Locale/publication/locale/revision |
| Website Vitest | 5 passed |
| Admin Vitest | 8 passed |
| Nuxt typecheck | Website、Admin 均通过 |
| Nuxt production build | Website、Admin 均通过 |
| Ruff | 78 个 Python 文件 `All checks passed` 且 format check 通过 |
| Prettier | 所有匹配文件通过 |
| HTTP smoke | live/ready/site/admin/CORS/bootstrap/auth/RBAC/refresh/logout 均通过；临时管理员已删除 |
| Production fail-fast | `APP_ENV=prod` 和使用示例 Secret 的 production API 均按预期非零退出 |
| 完整 Staging smoke | 8 服务 healthy；Basic Auth、`/admin/`、Website、API、noindex 全部通过 |
| `verify-local.ps1` | `Phase 3.2 local verification passed` |

唯一测试警告来自 Starlette 对 AnyIO 旧类型别名的上游 deprecation，不影响结果。

## 19. Docker 最终状态

常驻开发服务 `postgres`、`redis`、`minio`、`api`、`website`、`admin`、`nginx` 均为 running/healthy。端口：5432、6379、9000/9001、8010、3000、3001、8080。隔离的 `api-test/postgres-test/redis-test` 验收后已删除，不占用常驻资源。

常驻数据库实际 Seed 计数：2 Locales（1 default）、8 Roles、36 Permissions、99 role-permission mappings；Alembic head 为 `20260904_0003`。

## 20. 已知问题

1. Logout 撤销 refresh session，但已泄漏的 access JWT 没有独立 denylist，风险窗口由 15 分钟 TTL 限制；未来可根据威胁模型加入 token version/session binding。
2. Admin 当前是安全可运行的 Phase 3.2 管理基础页，不包含最终设计、复杂筛选、批处理或完整 CMS 工作流。
3. 旧 `/api/v1/health` 为 Phase 3.1 兼容端点；应在外部监控全部迁移到 live/ready 后移除。
4. Staging 安全入口已通过独立容器实测，但本阶段没有执行真实云 Staging/Production 部署、证书或备份恢复演练。
5. Starlette 0.47.3 触发一个 AnyIO deprecated alias 警告，等待兼容依赖升级后消除。
6. Staging 已配置受信 Docker 代理网段；真实生产负载均衡/CDN 的直连网段仍需在部署时显式加入 `TRUSTED_PROXY_CIDRS`，未配置时系统会安全退回记录直连 peer。

## 21. Phase 3.3 建议

1. 在本次 Master Entity + Translation/Publication/Route/Revision 基础上定义首批 Structured Core 内容实体及事务 API，避免引入通用自由 Page Builder。
2. 实现发布调度 worker、canonical/hreflang/sitemap 生成与 Redirect 管理 API，并为 URL 变更执行 ADR 规定的原子事务。
3. 增加审计日志只读检索、revision diff/rollback 工作流及 reviewer 审批界面。
4. 扩展 Admin 的权限感知导航、分页、错误态和 E2E 浏览器测试，同时继续以服务端 RBAC 为唯一安全边界。
5. 在真实 Staging 部署 migration job、备份恢复演练、Secret manager、HTTPS、日志与告警，再讨论 Production rollout。

## 22. `$seo-rank` / `$geo-rank` 冲突检查

已按两个已安装 skill 检查 URL、索引、多语言、发布、Admin 与 GEO 可见性，未发现与冻结业务决策冲突：

- SEO：正式 host 唯一；语言路径稳定且 self-canonical；hreflang/sitemap 只包含已发布翻译；草稿、Admin、Staging 全部 noindex；未来 Slug 变化必须永久 Redirect。
- GEO：机器可读取的 direct answer、事实与 provenance 必须来自同一公开 SSR 正文；禁止 AI-only 隐藏内容、隐藏关键词、机器专用路由或用 Schema 替代正文。
- Publication 与 Route indexable 同事务，避免“内容未发布但已索引”的分裂状态。
- 本阶段仅建立基础架构，没有提前生成产品页、批量 SEO/GEO 内容或最终首页。
- 如 skill 通用建议与项目冻结决策冲突，以交接文档、主域名、多语言前缀和 Structured Core 原则为最高约束；本次实现没有改变这些冻结项。
