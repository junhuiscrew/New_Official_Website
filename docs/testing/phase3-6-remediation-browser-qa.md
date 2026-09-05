# Phase 3.6 Remediation 浏览器 QA

此流程只允许用于本地开发/测试环境。它使用真实 PostgreSQL、Redis、MinIO、FastAPI、Nuxt SSR 和 Chromium，不使用手工 DTO 或整套 API mock。

## 安全门禁

- `APP_ENV=production` 时数据准备命令直接拒绝。
- 必须显式设置 `PHASE36_QA_CONFIRM=LOCAL_QA_ONLY`。
- 每次运行必须提供 3–40 位小写 `run-id`；本轮验收固定为 `remediation-20260905`。
- 样本 slug 和 MinIO key 全部带运行前缀；不会清空数据库或对象存储。
- `artifacts/phase3-6-remediation/` 已忽略，不提交 RFQ 编号、提交 token、私有 URL 或请求正文。

## 数据准备

```powershell
docker compose exec -T `
  -e PHASE36_QA_CONFIRM=LOCAL_QA_ONLY `
  -e PHASE36_QA_RUN_ID=remediation-20260905 `
  api python -m app.cli phase36-qa-setup
```

命令通过既有 Catalog/Authority 服务创建内容，通过统一 `transition_publication()` 完成 review→publish，并经 `MinioStorageAdapter` 将校验后的公开 PNG 写入 `public-media`。

## 浏览器执行

```powershell
$env:NODE_PATH = 'C:\path\to\the\installed\playwright\node_modules'
node scripts/phase36-browser-qa.js
```

Windows 的 `playwright-cli run-code` 会经 `.cmd` 转发参数；长脚本可能被 shell 截断。因此验收脚本直接复用同一 Playwright 安装中的 Chromium，并在页面级收集 console/network 结果。

脚本覆盖 Home→Product→RFQ→附件、Search→Knowledge→Product、双语/缺翻译回退、Knowledge→RFQ 来源、分页 404 恢复、移动菜单和 Gallery，并保存桌面/移动截图。
