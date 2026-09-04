# Migration Runtime Strategy

## 目标

数据库结构升级必须先于 API 新版本接收流量，系统 Seed 必须在 migration 成功后执行。多个 API 副本不得各自在启动命令中竞争执行 DDL。

## 本地开发

本地 Compose 为开发效率保留串行入口：

```text
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

该模式只适用于单个本地 API 容器。

## Staging / Production

部署编排必须采用一次性 job 和应用启动门禁：

```text
Migration job: alembic upgrade head
        ↓ 成功
System-data job: python -m app.cli seed
        ↓ 成功
Application: uvicorn app.main:app --host 0.0.0.0 --port 8000
        ↓
Readiness: GET /api/v1/health/ready
```

任一步失败都必须停止发布；禁止跳过失败 migration 启动新 API。Seed 只补充冻结的系统 Locale、Role、Permission 与缺失的基线 role-permission mapping，不删除管理员自定义映射。

## 并发、回退与可观察性

- 同一环境同一时间只运行一个 migration job。
- 每次发布记录 Alembic 当前 revision、目标 revision、job 日志和耗时。
- migration 前执行数据库备份并验证可恢复性。
- 应用回退不自动执行 Alembic downgrade；先判断新 schema 是否向后兼容。
- 破坏性 schema 变更采用 expand/migrate/contract，多次发布完成。
- `/health/live` 只判断进程；流量门禁只使用 `/health/ready`。

## Secret 与环境安全

Staging/Production 必须显式提供数据库、MinIO、JWT、refresh 和非本地 HTTPS CORS allowlist；数据库 URL 必须包含用户名和密码。所有非 development 环境只要仍含 `change-me`、`local-dev` 或本地示例地址，Settings 就拒绝启动。Bootstrap 管理员不属于 Seed，必须通过一次性安全命令执行。
