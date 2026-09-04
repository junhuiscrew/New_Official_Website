# Junhui Global Website — Codex 正式交接文件（Phase 3.2）

版本：V1.0  
日期：2026-09-04  
项目：Junhui Global Website  
正式主域名：`https://junhuiscrewbarrel.com`  
GitHub：`junhuiscrew/New_Official_Website`

---

# 0. 本文件用途

本文件用于把已经通过源码级验收的 Phase 3.1 项目，正式交接给 Codex 执行 **Phase 3.2**。

本阶段主题：

> **Authentication + RBAC + Localization + Publication Foundation**

本阶段目标不是做最终 CMS UI，也不是开始产品、材料、案例、知识库等大规模业务功能，而是把后续 CMS 所依赖的“身份、权限、语言、发布、路由、审计和安全边界”先做扎实。

---

# 1. Phase 3.1 验收结论

Phase 3.1 已通过：

- 架构验收
- 运行验收
- 源码级 Code Review

已经确认：

- Monorepo 结构成立
- Nuxt Website/Admin 可运行
- FastAPI 基础成立
- PostgreSQL / Redis / MinIO / Nginx Docker 本地环境成立
- SQLAlchemy 2.x 基础模型成立
- Alembic 首版 migration 成立
- 基础 RBAC 表成立
- Locale 基础表成立
- Seed 幂等
- Website SSR 成立
- `/` → `/zh-cn/` 308 成立
- canonical / hreflang / visible direct answer 基线成立
- Admin noindex 基线成立
- public-media / private-rfq 存储边界成立
- `.env` / `.gitignore` 基础 Secret 隔离成立

Phase 3.1 不需要推倒重来。

---

# 2. 当前冻结的业务约束

## 2.1 主域名

唯一正式主域名：

`https://junhuiscrewbarrel.com`

Canonical Host：

`junhuiscrewbarrel.com`

不使用：

- `www`
- HTTP
- 其他镜像域名

---

## 2.2 多语言

V1：

- `zh-CN` → `/zh-cn/`
- `en` → `/en/`

根目录：

`/` → 308 → `/zh-cn/`

未来：

- `/vi/`
- `/ru/`
- `/ja/`
- `/ar/`

原则：

- Master Entity + Translation tables
- 不复制整套业务数据
- 已发布翻译才进入 hreflang
- 每种语言 self-canonical
- 不使用 IP 强制跳转语言

---

## 2.3 SEO / GEO

本项目需继续遵循用户已安装的：

- `$seo-rank`
- `$geo-rank`

核心原则：

- 重要正文 SSR 输出
- H1/H2 SSR 输出
- canonical SSR 输出
- hreflang SSR 输出
- GEO direct answer 必须对用户可见
- 禁止 AI-only hidden text
- 禁止白字/隐藏关键词
- 禁止 doorway page
- 禁止 fake review / fake author / fake freshness
- Schema 必须与可见内容一致

---

# 3. Phase 3.2 强制修正项

这些问题不阻塞 Phase 3.1，但必须在 Phase 3.2 中一起修正。

---

## 3.1 Nuxt SSR 内部 API 地址与浏览器 API 地址分离

当前问题：

浏览器和 Nuxt SSR 不能都使用：

`http://localhost:8010/api/v1`

因为 Nuxt SSR 在 Docker `website` 容器中运行时，`localhost` 指向 website 容器自身，而不是 FastAPI。

必须改成两套配置：

### Browser Public API

推荐：

```text
NUXT_PUBLIC_API_BASE=/api/v1
```

浏览器访问：

```text
https://junhuiscrewbarrel.com/api/v1
```

本地通过 Nginx：

```text
http://localhost:8080/api/v1
```

### Nuxt SSR Internal API

新增：

```text
NUXT_API_INTERNAL_BASE=http://api:8000/api/v1
```

Nuxt 服务端请求使用 internal base。

要求：

- 浏览器绝不使用 Docker service hostname
- SSR 不使用 `localhost:8010`
- API helper 必须根据 server/client 环境选择正确 base
- 添加测试覆盖

---

## 3.2 CORS / Same-Origin 策略

Phase 3.2 开始做 Admin Authentication，必须正式定义 API Origin。

开发环境至少允许：

- `http://localhost:3000`
- `http://localhost:3001`
- `http://localhost:8080`

生产环境：

仅允许明确配置的正式 Origin。

禁止：

```text
allow_origins=["*"]
+
allow_credentials=True
```

建议：

- 用 Settings 管理 allowlist
- production 无显式 allowlist 时拒绝启动或安全默认
- 为 cookie authentication 设置正确 credentials 行为

如果 Admin/API 最终通过同域 Nginx 路由，则优先采用 same-origin，减少 CORS 复杂度。

---

## 3.3 Email 唯一性必须大小写不敏感

当前 `users.email` 为普通 `VARCHAR UNIQUE`。

问题：

理论上：

```text
Sales@example.com
sales@example.com
```

可能被数据库视为不同值。

Phase 3.2 必须在认证上线前修复。

推荐方案之一：

### 方案 A（推荐）

PostgreSQL `CITEXT`

- 启用 `citext` extension
- users.email 使用 CITEXT
- unique index

### 方案 B

保存：

- email
- normalized_email

`normalized_email = lower(trim(email))`

并对 normalized_email unique。

必须：

- API 入参统一 normalize
- 登录查询统一 normalize
- 测试覆盖不同大小写重复注册

---

## 3.4 Locale 只能存在一个默认语言

当前 `locales.is_default` 只是 bool。

必须增加数据库级约束：

> 全库最多一个 `is_default = true`

PostgreSQL 推荐：

```sql
CREATE UNIQUE INDEX ...
ON locales ((is_default))
WHERE is_default = true;
```

或等价 partial unique constraint/index。

要求：

- zh-CN 继续作为默认
- 修改默认语言操作必须事务化
- 测试两个默认语言写入失败

---

## 3.5 Admin noindex 改成应用级 / Header 级

当前 Admin 首页已有 meta robots。

Phase 3.2 必须升级成全局策略。

至少：

### Admin App

所有 Admin 页面默认：

```text
noindex, nofollow
```

### Nginx / Server Layer

对 Admin 响应增加：

```text
X-Robots-Tag: noindex, nofollow
```

不要依赖每个页面自己手写 meta。

---

## 3.6 Production Secret 必须 fail-fast

当前开发默认值可以保留。

但：

当：

```text
APP_ENV != development
```

时，以下关键 Secret 若：

- 缺失
- 仍为示例值
- 仍为默认值

应用必须拒绝启动。

至少包括：

- DATABASE credentials / DATABASE_URL
- MINIO / S3 secret
- JWT signing secret
- session / refresh secret
- any admin/bootstrap secret

不得在 production 默默使用：

```text
change-me-...
junhui-local-dev
```

---

# 4. Phase 3.2 正式范围

## EPIC A — Authentication

实现：

- 用户登录
- 用户退出
- Refresh
- Current User
- Password Hash
- Password Verify
- Account active check
- Failed login handling
- Basic login audit

推荐密码哈希：

- Argon2id

不要使用：

- SHA256(password)
- MD5
- 自研密码算法

---

## EPIC B — Session / Token Strategy

推荐：

> **HttpOnly Secure Cookie based session / refresh architecture**

原则：

- refresh credential 不存 localStorage
- production Cookie 使用 `Secure`
- `HttpOnly`
- 合理 `SameSite`
- 明确 CSRF 策略

如果使用 access token + refresh token：

- access token 短生命周期
- refresh token 轮换
- 服务端可撤销
- refresh token 只放 HttpOnly Cookie

不要仅实现一个长期 JWT 然后永久有效。

---

# 5. RBAC

## 5.1 角色

保留现有 8 个角色：

- super_admin
- content_admin
- editor
- translator
- reviewer
- seo_manager
- sales
- media_manager

---

## 5.2 Permission 命名规范

采用：

```text
resource.action
```

例如：

```text
user.read
user.create
user.update
user.disable

role.read
role.manage

locale.read
locale.manage

content.read
content.create
content.update
content.review
content.publish
content.archive

translation.read
translation.create
translation.update
translation.review
translation.publish

seo.read
seo.update

geo.read
geo.update

redirect.read
redirect.manage

media.read
media.upload
media.update
media.delete

rfq.read
rfq.assign
rfq.update
rfq.download_private_file

settings.read
settings.update

audit.read
```

Phase 3.2 不需要把未来所有 Product 权限全部细化到最终版本，但必须建立可扩展权限体系。

---

## 5.3 权限要求

禁止：

```text
if user.is_admin:
```

作为主要权限系统。

FastAPI 应提供：

- `get_current_user`
- `require_permission(...)`
- `require_any_permission(...)`
- `require_role(...)`（仅少量系统级场景）

Admin 前端 Route Guard 只是 UX。

**真正权限必须由 API 服务端执行。**

---

# 6. Permission Seed

Phase 3.2 必须 Seed：

- permissions
- role_permissions

Seed 必须：

- 幂等
- 可重复执行
- 不删除管理员自定义权限映射，除非明确设计为系统权限同步

建议：

## super_admin
全部权限。

## content_admin
内容、发布、Page Builder、Navigation 等内容权限。

## editor
创建/编辑，不能最终发布关键内容。

## translator
翻译相关。

## reviewer
review / approval。

## seo_manager
SEO / GEO / Redirect。

## sales
RFQ。

## media_manager
公开媒体管理，不允许 RFQ 私有附件权限。

---

# 7. Bootstrap Super Admin

Phase 3.1 没有默认管理员，这是正确的。

Phase 3.2 必须提供安全 bootstrap 流程。

推荐：

```bash
python -m app.cli create-super-admin
```

从交互输入或环境变量读取：

- email
- password
- display name

禁止：

- 仓库硬编码默认管理员
- README 明文固定密码
- Seed 自动创建固定 admin/admin

要求：

- email normalize
- 密码强度校验
- 已存在时安全退出
- Audit log

---

# 8. Audit Log 基础

Phase 3.2 实现 `audit_logs` 基础表。

至少记录：

- user_id
- action
- target_type
- target_id
- ip
- user_agent
- metadata_json
- created_at

本阶段记录：

- login.success
- login.failed
- logout
- user.create
- user.update
- user.disable
- role.assign
- permission.change
- locale.change
- publication.status_change（基础）
- route.change（基础）

后期 RFQ 文件下载也使用该系统。

---

# 9. Localization 完整基础

## 9.1 Locales CRUD

Admin/API 支持：

- list
- create
- update
- enable/disable
- change sort
- set default

但：

- zh-CN / en 系统语言不能轻易物理删除
- 禁用默认语言前必须先切换默认语言

---

## 9.2 Translation Status

实现统一：

`translation_statuses`

状态：

- missing
- draft
- machine_translated
- human_reviewed
- published

字段至少：

- owner_type
- owner_id
- locale_id
- status
- source_locale_id
- translated_by
- reviewed_by
- published_at
- updated_at

---

# 10. Publication Foundation

Phase 3.2 需要冻结统一内容状态体系：

```text
draft
review
scheduled
published
archived
```

本阶段不必把 Product 全实现，但必须建立可复用 Contract。

建议创建：

- shared enum / domain type
- publication service contract
- DB model pattern / mixin strategy

必须明确：

- 谁可以 draft → review
- 谁可以 review → published
- translator 不能绕过 reviewer
- archived 不进入 public route
- published 才允许 indexable

---

# 11. Route / Slug / Publication Transaction Boundary

这是 Phase 3.2 的重点之一。

请编写 ADR：

`docs/architecture/adr-content-route-publication.md`

必须冻结：

## 11.1 Slug

- lower case
- kebab-case
- language route prefix
- published URL 改变必须产生 redirect

## 11.2 Transaction

发布动作必须作为一个一致事务：

```text
Content status
+
Translation published
+
Route active
+
SEO indexable state
```

不能出现：

```text
内容已 published
但 route 不存在
```

或：

```text
route 已公开
但 translation 仍 draft
```

## 11.3 Route Registry

Phase 3.2 可以先实现基础 `content_routes` 表：

- id
- owner_type
- owner_id
- locale_id
- path
- is_canonical
- indexable
- active
- created_at
- updated_at

Unique：

`path`

后续 Product / Material 等直接复用。

---

# 12. Revision 基础

Phase 3.2 建立：

`content_revisions`

至少：

- owner_type
- owner_id
- locale_id
- revision_no
- snapshot_jsonb
- changed_by
- created_at

本阶段不要求完整可视化 Diff UI。

但需要：

- revision storage service
- rollback contract
- 单元测试

---

# 13. Staging 安全策略

新增环境：

```text
APP_ENV=staging
```

Staging：

- Basic Auth
- 全站 `X-Robots-Tag: noindex, nofollow`
- 不生成公开 sitemap
- 不发送正式 Analytics
- 不发送正式营销邮件

这些必须由环境级策略控制。

---

# 14. Health Endpoint

升级成：

```text
/api/v1/health/live
/api/v1/health/ready
```

## live

只检查 API 进程存活。

## ready

至少检查：

- PostgreSQL
- Redis

MinIO 可以：

- 作为 optional dependency
- 或一起检查

Docker health 推荐切到 ready。

保留旧：

`/api/v1/health`

可以临时兼容，但应在 README 写清楚。

---

# 15. Migration Strategy

本地开发仍可：

```text
alembic upgrade head
seed
uvicorn
```

但必须开始准备未来正式部署模式：

```text
migration job
↓
seed system data
↓
API start
```

本阶段至少在 docs 写清楚：

`docs/architecture/migration-runtime-strategy.md`

---

# 16. Admin Phase 3.2 UI 范围

只做：

- Login
- Logout
- Current user display
- Forbidden page
- Admin shell
- 基础 Users 页面
- 基础 Roles / Permissions 查看页
- Locale 管理基础页

不要做：

- Products
- Materials
- Page Builder
- Final CMS dashboard
- Final visual system

Admin UI 仍以功能验证为目标。

---

# 17. Phase 3.2 测试要求

必须添加真实 PostgreSQL 集成测试或 Docker integration test。

至少：

## Authentication

- 正确登录
- 错误密码
- inactive user
- email 大小写 normalize
- refresh
- logout/revoke

## RBAC

- 没权限 → 403
- 有权限 → success
- super_admin
- sales 不能修改 SEO
- media_manager 不能下载 private RFQ（当前业务 endpoint 可先用权限 dependency 单测）

## Locale

- 只有一个 default
- zh-CN 默认
- duplicate code
- duplicate slug
- set default transaction

## Seed

- permissions 幂等
- role_permissions 幂等

## Route

- duplicate path 失败
- published route contract

## Security

- production default secret → startup fail
- admin global noindex
- staging noindex

## API Base

- browser base
- SSR internal base

---

# 18. Phase 3.2 验收标准

完成后必须：

- [ ] Authentication 实际可登录
- [ ] Password 使用安全哈希
- [ ] Cookie / Token 策略有测试
- [ ] Refresh / Logout 有效
- [ ] Permission seed 完成
- [ ] 8 个 Role 映射完成
- [ ] API 权限依赖生效
- [ ] Admin route guard 生效
- [ ] email case-insensitive unique
- [ ] Locale 单一 default 数据库级保证
- [ ] Translation status 基础完成
- [ ] Publication contract 完成
- [ ] content_routes 基础表完成
- [ ] revisions 基础完成
- [ ] audit_logs 基础完成
- [ ] Admin 全局 noindex
- [ ] Staging Basic Auth + noindex 策略完成
- [ ] public/internal API base 分离
- [ ] CORS / same-origin 策略完成
- [ ] production default secret fail-fast
- [ ] live / ready health 完成
- [ ] Alembic migration 成功
- [ ] Seed 幂等
- [ ] Backend tests 全通过
- [ ] Frontend tests/typecheck/build 全通过
- [ ] Docker Compose 最终 healthy

---

# 19. Phase 3.2 禁止事项

禁止：

- 开始完整 Product CRUD
- 开始 Materials
- 开始 Technologies
- 开始 Applications
- 开始 Solutions
- 开始最终 Page Builder
- 开始完整 RFQ
- 开始最终网站首页 UI
- 批量产品内容
- 生产服务器部署
- Kubernetes
- Kafka
- Elasticsearch
- 复杂微服务
- 自研加密算法
- 长期 JWT localStorage

---

# 20. Codex 完成后必须交付

生成：

`docs/architecture/phase3-2-completion-report.md`

必须包含：

1. 实际修改文件树
2. 新 migrations
3. Authentication 设计
4. Cookie / Token 设计
5. Password hash
6. Permission matrix
7. Role matrix
8. Bootstrap super admin 方法
9. Locale / translation model
10. Publication model
11. Route transaction ADR
12. Revision model
13. Audit model
14. CORS / Origin 策略
15. Staging security
16. Health live/ready
17. API public/internal base
18. 测试结果
19. Docker 最终状态
20. 已知问题
21. Phase 3.3 建议
22. `$seo-rank` / `$geo-rank` 冲突检查

---

# 21. 执行原则

优先级：

1. Security
2. Authorization correctness
3. Transaction consistency
4. Localization correctness
5. Publication correctness
6. SEO/GEO route consistency
7. Developer experience
8. UI 最后

如遇普通工程细节，Codex 可自行决定。

只有当问题会改变以下内容时才询问用户：

- 主域名
- 技术栈
- 身份认证核心方案
- 数据库核心关系
- 多语言模型
- SEO/GEO 核心原则
- CMS Structured Core 原则

否则继续执行，不频繁中断。
