# Phase 3.6 Remediation 浏览器 QA

此流程只允许用于本地开发/测试环境。它使用真实 PostgreSQL、Redis、MinIO、FastAPI、Nuxt SSR 和 Chromium，不使用手工 DTO 或整套 API mock。

## 安全门禁

- 仅允许 `APP_ENV=development/test`；staging/production 均直接拒绝。
- 必须显式设置 `PHASE36_QA_CONFIRM=LOCAL_QA_ONLY`。
- 必须另设 `PHASE36_QA_ISOLATION=LOCAL_COMPOSE_ONLY`，且程序会解析并拒绝非 localhost/Compose 的 PostgreSQL、Redis、MinIO 目标或错误桶名。
- 每次运行必须提供 3–40 位小写 `run-id`；本轮验收固定为 `remediation-20260905`。
- 样本 slug 和 MinIO key 全部带运行前缀；不会清空数据库或对象存储。
- 输出 manifest 会逐类列出 Company marker、所有资源 slug 与两个 public-media object key；清理只能依据这份清单精确执行，禁止全库或整桶删除。
- `artifacts/phase3-6-remediation/` 已忽略，不提交 RFQ 编号、提交 token、私有 URL 或请求正文。

## 数据准备

```powershell
docker compose exec -T `
  -e PHASE36_QA_CONFIRM=LOCAL_QA_ONLY `
  -e PHASE36_QA_ISOLATION=LOCAL_COMPOSE_ONLY `
  -e PHASE36_QA_RUN_ID=remediation-20260905 `
  api python -m app.cli phase36-qa-setup
```

命令通过既有 Catalog/Authority/Company Trust 服务创建双语 Company、Category、26 条公开 Product、Material、Technology、Application、Solution、Capability+Equipment、匿名 Case、真实人物标记的 QA Expert、Knowledge、draft/noindex 负向样本及公开 PDF。代表公开内容通过统一 `transition_publication()` 完成 review→publish；PNG/PDF 经 `MinioStorageAdapter` 真正写入 `public-media`。所有内容均带 `QA ONLY` 标记且命令幂等。

## 浏览器执行

```powershell
$env:NODE_PATH = 'C:\path\to\the\installed\playwright\node_modules'
node scripts/phase36-browser-qa.js
```

Windows 的 `playwright-cli run-code` 会经 `.cmd` 转发参数；长脚本可能被 shell 截断。因此验收脚本直接复用同一 Playwright 安装中的 Chromium，并在页面级收集 console/network 结果。

脚本覆盖 Home→Product→RFQ→private-rfq 附件、Search→Knowledge→Product、双语/缺翻译回退、Knowledge/匿名 Case→RFQ 来源、有效/无效/零结果/越界分页及恢复、移动菜单和 Gallery。Home 与 Product 会在 320/375/430/768/1024/1280/1440/1920 八个宽度检查 HTTP、单一 main/H1/main-content 与文档级横向溢出；脚本还验证图片 `naturalWidth`、pageerror、console 和关键网络状态，并保存桌面/移动截图。
