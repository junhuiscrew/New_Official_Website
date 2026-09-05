# Phase 3.5 Final Patch v3 完成报告

## 1. Branch 与提交基线

- Branch：`phase-3.5-final-patch-v3`
- Base branch：`phase-3.5-final-patch-v2`
- Base SHA：`310bf1348cd9661348bc14a56b0f91f4efb163f2`
- Final implementation SHA：`fba48ea30f84b5f61b2d7ba5105af6f12517916e`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 数据库 migration：无新增 migration；本轮只修正 Authority 服务权限映射与既有 Permission/Role Seed。

> 本报告单独作为文档提交，因此 Final implementation SHA 指功能代码与回归测试提交，不使用无法自引用的报告提交 SHA。

## 2. Authority Publication 双重权限校验

`transition_authority_publication()` 的实体权限映射已修正为：

| 目标状态 | Authority 实体权限 | 统一 Publication 权限 |
| --- | --- | --- |
| `REVIEW` | `{entity}.review` | `content.review` |
| `SCHEDULED` | `{entity}.publish` | `content.publish` |
| `PUBLISHED` | `{entity}.publish` | `content.publish` |
| `ARCHIVED` | `{entity}.archive` | `content.archive` |
| `DRAFT` | `{entity}.update` | `content.update` |

- Authority API 外层按 Case、Knowledge、Expert 的实体职责执行第一层校验。
- 既有 `transition_publication()` 继续执行全局 Content 权限校验，没有建立旁路或第二套发布逻辑。
- Reviewer 不再需要 `case.update`、`knowledge.update` 或 `expert.update` 即可完成审核。
- Editor 只有实体 `update` 与 `content.update` 时，Review 和 Publish 均返回 `403 permission_denied`。
- Translator 只有 Translation 权限时不能发布 ContentPublication。

## 3. `expert.review` 与 Reviewer RBAC

- `expert.review` 已加入 `PERMISSION_CODES`，Seed 会幂等创建缺失权限。
- Reviewer Role Matrix 已加入 `expert.review`，并继续保留 `expert.read`、`expert.publish`。
- Reviewer 没有获得 `expert.create` 或 `expert.update`。
- Content Admin 与 Super Admin 通过既有 Authority Permission 集合自动包含新增权限，没有改变其他角色边界。
- 本轮没有修改 Media、RFQ、MinIO、Malware、Trust 或 Company Profile 权限和生命周期实现。

## 4. Expert Translation Review

`POST /api/v1/authority/experts/{id}/translations/{locale}/review` 已完成以下回归验证：

- `draft` 与 `machine_translated` 可以转换为 `human_reviewed`。
- `reviewed_by` 写入当前 Reviewer 用户 ID。
- 审核动作写入 `AuditLog`，action 为 `translation.review`。
- 已为 `published` 的 Translation 重复 Review 返回 `409`。
- 缺少 `expert.review` 时返回 `403`。
- Reviewer 无需 `expert.update` 即可审核 Expert Translation。

## 5. Case / Knowledge / Expert 发布回归

新增回归测试分别验证 Case、Knowledge 与真实人物 Expert：

1. Translation 从 `draft` 进入 `human_reviewed`；
2. Publication 从 `draft` 进入 `review`；
3. Publication 从 `review` 进入 `published`；
4. 发布后 canonical Route 为 `active=true` 且 `indexable=true`。

同时验证了实体权限与全局内容权限缺一不可：仅有 `{entity}.review` 不能替代 `content.review`，仅有 Translation 权限也不能替代 Content Publication 权限。

## 6. Trust / Company Final Patch v2 无回归

- Full backend suite 包含 Phase 3.5 remediation、Final Patch、Final Patch v2 以及 Phase 3.4 相关测试，全部通过。
- Trust / Company Review 继续使用 `translation.review` 与 `content.review`。
- Trust / Company Publish 继续使用 `translation.publish` 与 `content.publish`。
- Non-route Trust 继续使用既有 Translation Review/Publish 生命周期，不产生独立 ContentPublication 或 ContentRoute。
- 本轮未改动上述已验收模块的服务、DTO、Admin 或公开输出。

## 7. Seed 幂等性

- 本机完整套件中的基础 Seed、Permission Matrix 与 Phase 3.4 Seed 幂等测试通过。
- Docker API test profile 在真实 PostgreSQL 上执行 migration 和 Seed 后运行完整测试，全部通过。
- 重复 Seed 不会重复创建 `expert.review` Permission 或 RolePermission；Reviewer 仍不包含 `expert.update` / `expert.create`。

## 8. 测试与构建结果

| 验证项 | 实际结果 |
| --- | --- |
| Ruff | 通过，`All checks passed!` |
| v3 聚焦回归测试 | `7 passed` |
| Backend pytest（本机完整套件） | `190 passed, 9 skipped`；跳过项为需要真实 PostgreSQL/Redis/MinIO 的集成用例 |
| Docker API test profile | `199 passed`，使用真实 PostgreSQL、Redis 与 MinIO |
| PostgreSQL integration | 通过；Docker profile 覆盖真实 PostgreSQL、空数据库 migration 与 `0001 -> latest` 回归 |
| Seed idempotency | 通过；基础 Seed、RBAC Seed、Phase 3.4 Seed 幂等测试均在完整套件内执行 |
| Website Vitest | `15 passed` |
| Admin Vitest | `23 passed` |
| Typecheck | Website/Admin 均通过 |
| Prettier | 通过，所有匹配文件符合格式 |
| Production Build | Website/Admin Nuxt production build 均通过 |

新增 `test_phase35_final_patch_v3.py` 覆盖交接文件要求的 Reviewer 正向、Editor/Translator 负向、Expert Translation 状态与审计、实体与全局双层权限以及三类 Authority Review → Publish 闭环。

## 9. Docker Compose 健康状态

- 最终镜像已重新构建：`api`、`worker`、`website`、`admin`。
- Docker Compose 最终状态：
  - `api`：healthy
  - `worker`：healthy
  - `postgres`：healthy
  - `redis`：healthy
  - `minio`：healthy
  - `website`：healthy
  - `admin`：healthy
  - `nginx`：healthy
- Docker test profile 中 `postgres-test` 与 `redis-test` 也为 healthy。
- API `live`、`ready`、Nginx 代理、Website 与 Admin 实际 HTTP 请求均返回 `200`。

## 10. Known issues

- Starlette TestClient 仍产生一条来自上游依赖的 `anyio.abc.BlockingPortal` deprecation warning，不影响测试或运行结果。
- Nuxt/Nitro production build 有一条 Node package exports 尾斜杠弃用提示，不影响构建产物。
- 本轮没有数据库结构变化，因此没有新增 migration。
- 本报告记录的是技术完成状态；最终源码验收仍由项目负责人确认。

## 11. Phase 3.5 FINAL PASS 结论

- Authority 的 REVIEW、SCHEDULED/PUBLISHED、ARCHIVED、DRAFT 权限映射已全部符合冻结规范。
- `expert.review` 已进入 Permission Seed 与 Reviewer，且没有扩大 Reviewer 的 Expert 创建/编辑权限。
- Case、Knowledge、Expert 的 Review → Publish 与 Trust / Company v2 回归全部通过。
- Backend、真实 PostgreSQL/Redis/MinIO、Seed、Website/Admin、Typecheck、Prettier、Production Build 与 Docker Health 均通过。
- 从实现与自动化验证结果看，已达到 **Phase 3.5 FINAL PASS 技术门槛**，当前状态为等待最终源码验收。
- 未进入 Phase 3.6，未扩展 Homepage、Design System、Page Builder 或 Production Deployment。
