# Docker

容器构建文件按应用保存在 `apps/*/Dockerfile`，根目录 `docker-compose.yml` 负责本地编排。

## Phase 3.7 隔离 HTTPS 试点

该环境使用独立 Compose 项目名与独立 PostgreSQL、Redis、MinIO volumes，仅开放本机 `443`。三个入口均受 Basic Auth 和 `X-Robots-Tag: noindex, nofollow` 保护：

- `https://junhui.test`
- `https://admin.junhui.test`
- `https://api.junhui.test`

先在仓库根目录运行 `powershell -File scripts/phase37-local-https.ps1`。默认只在已忽略的 `data/phase3-7/` 和 `.env.phase37` 中生成随机凭据、CA、SAN 证书与 htpasswd，不修改系统信任库或 hosts。只有明确需要时才以管理员 PowerShell 运行 `-InstallTrustAndHosts`。

校验并启动：

```powershell
docker compose -f docker-compose.yml -f docker-compose.phase37.yml --env-file .env.phase37 config --quiet
docker compose -f docker-compose.yml -f docker-compose.phase37.yml --env-file .env.phase37 up -d --build
```

Bootstrap 管理员密码只从 `.env.phase37` 载入到当前进程，不写入命令、报告或 Git。停止时使用 `stop`；未经备份和单独确认不要执行 `down -v`。数据库 dump、MinIO inventory、私有 manifest、派生图与证据统一保存在 `data/phase3-7/pilot-001/`。

未安装 hosts 时可用 `curl --resolve junhui.test:443:127.0.0.1 --cacert data/phase3-7/tls/ca.crt https://junhui.test/` 做隔离检查。正式 canonical 仍为 `https://junhuiscrewbarrel.com`，本机 `.test` 域名不会进入内容路由、Sitemap 或 Git。
