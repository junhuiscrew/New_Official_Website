# Phase 3.7.2 首个产品 Draft Import 试点报告

## 1. 结论与停止点

- 执行日期：2026-09-06（Asia/Shanghai）
- 仓库：`junhuiscrew/New_Official_Website`
- 分支：`phase-3.7`
- 验收基线：`c16385cc57ec4ce1aa66164928be2a2cc30d4473`
- 本轮实现 SHA：`87b44d4a5c6c0d7f3dce01a1514f84ca55afaf90`
- 试点状态：`DRAFT_IMPORT_COMPLETE_AWAITING_USER_REVIEW`
- 发布状态：未 Review、未 Publish、Route inactive/noindex、未进入 Sitemap
- 远端状态：未 push、未 merge、未部署

本轮在独立 PostgreSQL、Redis、MinIO 和 HTTPS Compose project 中完成“注塑机氮化料筒”双语 draft 试点。导入仅包含用户确认的中英文产品名称、保守的 draft 描述和 4 张获批图片派生件；旧站存在冲突或无法确定适用范围的参数、型号与结构化关系均保持缺失。下一步必须由用户在 Admin 中审核并修改内容，不能把本轮结果视为正式发布批准。

## 2. 用户确认与批次范围

| 项目 | 本轮采用的确认 |
|---|---|
| 试点产品 | `注塑机氮化料筒` |
| 英文 draft 名称 | `Nitrided Barrel for Injection Molding Machines`，仍由用户终审 |
| 产品 slug | `nitrided-barrel` |
| 分类 | `注塑机料筒` / `Injection Molding Machine Barrels` |
| 分类 slug | `injection-molding-machine-barrels` |
| 图片归属 | 文件名含“骏辉螺杆 氮化机筒”的前 4 张属于同一产品图库 |
| 排除图片 | `05-骏辉螺杆 氮化机筒日精.jpg` 属于另一个产品，未复制、未处理、未上传 |
| 媒体权利 | 公司确认可用于新官网，并允许裁切、缩放、压缩、WebP、去 EXIF、缩略图、去背景和水印处理 |
| 审核责任 | 中文与英文均由用户本人审核 |
| 目标环境 | 独立本地 HTTPS、Basic Auth、全站 noindex，不连接生产 |
| 授权范围 | 仅允许 draft import；不允许受保护预览发布或生产发布 |

## 3. 来源与事实处理

旧站来源页：

- 中文：<https://www.junhuiscrew.com/product/zhusujiliaotongxilie/danhualiaotong/04-junhuiluogan-danhuajitong-5.html>
- 英文产品目录线索：<https://www.china-barrelscrew.com/product/>

旧站只用于确认产品语境和整理 draft 文案。由于旧站同页存在直线度、硬度、镀层厚度等互相冲突的数值，并且缺少最新版参数表与明确适用型号，本轮未创建 ProductModel、ProductSpecValue、Material/Technology/Application/Solution 关系，也未将这些数值写入正文、SEO、GEO 或 Schema。

私有可执行 manifest、原图、派生图、数据库备份和运行证据保存在忽略目录 `data/phase3-7/pilot-001/`，不进入公共 Git。仓库内的 manifest 文件只是脱敏结构示例，不含真实源文件哈希、凭据或目标实例信息。

## 4. 媒体处理与对象存储

4 张已批准源图均以 SHA-256 锁定，转换为 700×700 WebP，并移除 EXIF。没有对排除的第 5 张图片执行处理或上传。

| 图序 | 派生 SHA-256 | 尺寸 | 大小 |
|---|---|---:|---:|
| 1 | `acfdea942b353e2a88654f9b3a7779a310b737054f4aa5dedcb69dab8c08343e` | 700×700 | 17,390 bytes |
| 2 | `c26309d9b2aa4bb42792f3929b5d9fa6bf9913c85d7ff004d9b683812c690606` | 700×700 | 32,788 bytes |
| 3 | `92937ee11cfcbd5c42ea4c308afcfbc9ef901af84986d52addfcdd4e681b28ca` | 700×700 | 10,492 bytes |
| 4 | `8fa9c16958dd0f08fbabe00958a0e2aec82fbd608723829f8c32ad032d976ef3` | 700×700 | 13,738 bytes |

实际对象边界：`public-media=4`、`private-rfq=0`。公开媒体由既有代理 API 提供，浏览器端没有暴露 Docker 内部 `minio:9000` 地址；抽查第一张媒体 GET 返回 `image/webp`、17,390 bytes 和 noindex 响应头。RFQ 私有桶未被使用。

## 5. 实现内容

### 5.1 受控导入工具

- 新增 `phase37-pilot-dry-run`、`phase37-pilot-apply`、`phase37-pilot-verify` CLI。
- manifest 使用严格 Pydantic 校验，只接受本批 4 个白名单文件名和 external key。
- 导入前校验源文件 SHA-256；派生 WebP 时移除 EXIF。
- HTTP 客户端显式禁用继承系统代理，使用私有 CA、Basic Auth 和现有 Admin API。
- Apply 可幂等重跑；不直接写 SQL，不绕过 Revision/Audit/Publication/Route 服务。
- verify 强制断言双语翻译为 draft、Publication 为 draft、Route closed、主图已设置，且无型号、规格和关系。

### 5.2 独立 HTTPS 环境

- Compose project：`junhui-phase37-pilot`
- 独立服务：PostgreSQL、Redis、MinIO、API、worker、website、admin、nginx
- 对外仅开放 HTTPS 443；内部服务端口不直接暴露。
- Nginx 对 Website、Admin、API 统一启用 Basic Auth 和 `X-Robots-Tag: noindex, nofollow`。
- Staging 配置启用 secure cookie，禁用 Sitemap 和 Analytics。
- `.env.phase37`、本地 CA/证书与 htpasswd 均为随机生成并被 Git 忽略。

## 6. Dry-run、Apply 与幂等结果

首次 dry-run：

| 对象 | 结果 |
|---|---|
| `zh-CN`、`en` locales | `no-op` |
| ProductCategory | `create` |
| Product | `create` |
| 4 个 MediaAsset | `create` |
| Specifications | `blocked` |
| Relations | `blocked` |
| 总体 | `ready` |

首次 apply 创建 1 个分类、1 个产品和 4 个媒体；第二次 apply 为 `no-op`，创建媒体数为 0。最终 verify 全部通过。

## 7. 数据库与生命周期结果

| 数据 | 实际结果 |
|---|---:|
| ProductCategory | 1 |
| Product | 1 |
| ProductCategoryTranslation | 2 |
| ProductTranslation | 2 |
| MediaAsset | 4 |
| MediaAssetTranslation | 8 |
| ProductModel | 0 |
| ProductSpecValue | 0 |
| Product relations | 0 |

生命周期断言：

- Product 与 Category 的 `zh-CN` / `en` TranslationStatus 均为 `draft`；
- 两类对象的 ContentPublication 均为 `draft`；
- Product 2 条、Category 2 条 canonical Route 均为 `active=false`、`indexable=false`；
- Product 和 Category 各产生 1 条 ContentRevision；
- 全部写入通过现有 API、服务、Revision 和 Audit 路径完成。

## 8. 公开门禁与 SEO/GEO 检查

| 检查 | 结果 |
|---|---|
| 中文 Product Public API | 404 |
| 英文 Product Public API | 404 |
| 中文 Product SSR | 404 |
| 英文 Product SSR | 404 |
| Published listing | 200，未包含试点产品 |
| Sitemap | 环境禁用并返回 404，未包含试点产品 |
| canonical/hreflang/schema | Draft 不生成公开输出 |
| GEO visible source | Draft 不进入公开可见来源 |

本轮与 `$seo-rank` / `$geo-rank` 无冲突：正式主域 canonical 配置未修改；draft 未进入 Public DTO、SSR、Sitemap、hreflang、Schema 或 GEO visible source；没有把不确定参数包装成权威事实。

## 9. 备份与恢复演练

导入前生成 PostgreSQL custom-format dump，并恢复到独立数据库 `junhui_phase37_restore`。

| 项目 | 结果 |
|---|---|
| 备份大小 | 452,379 bytes |
| 备份 SHA-256 | `b8dd700170f50f85cfaa2beec0acd9f4d27660fe65a37d44d03dbf5cc4621008` |
| Source / Restore Alembic | `20260905_0010` / `20260905_0010` |
| Source / Restore roles | 8 / 8 |
| Source / Restore locales | 2 / 2 |
| Source / Restore products | 0 / 0 |
| 导入前 MinIO 对象 | public 0 / private 0 |

备份文件为私有运行产物，未提交 Git。演练验证了内容导入前数据库基线可恢复；没有执行破坏性回滚，也没有清空对象存储。

## 10. 验证结果

| 检查 | 命令/范围 | 结果 |
|---|---|---|
| Phase 3.7 focused tests | `pytest apps/api/tests/test_phase37_pilot.py` | PASS，14 passed |
| Ruff | `python -m ruff check --no-cache apps/api` | PASS，All checks passed |
| Full Backend pytest | API test image + PostgreSQL/Redis/MinIO | PASS，255 passed，1 warning，73.94s |
| Seed idempotency | isolated API 执行 `python -m app.cli seed` 两次 | PASS；roles 8、permissions 114、locales 2，内容计数不变 |
| Website Vitest | `pnpm --filter website test` | PASS，11 files / 118 tests |
| Admin Vitest | `pnpm --filter admin test` | PASS，6 files / 24 tests |
| Website Typecheck | `pnpm --filter website typecheck` | PASS |
| Admin Typecheck | `pnpm --filter admin typecheck` | PASS |
| Website Build | `pnpm --filter website build` | PASS |
| Admin Build | `pnpm --filter admin build` | PASS |
| Prettier | `pnpm format:check` | PASS |
| Compose config | phase37 compose config validation | PASS |
| Nginx | `nginx -t` | PASS |
| HTTPS / Basic Auth | Docker network + private CA | PASS；无认证 401，认证 Website/Admin/API 200 |

Backend warning 为 Starlette TestClient deprecated alias，不是本轮失败。前端构建使用 Nuxt 4.5.2、Nitro 2.13.4、Vite 8.2.2、Vue 3.5.42。

## 11. 已知限制

1. Windows 主机上的 hosts 写入和本地 CA 信任未能被当前会话可靠验证。Docker 网络内 HTTPS、证书、Basic Auth 和 noindex 已验证；用户如需浏览器访问，应在管理员 PowerShell 中运行 `scripts/phase37-local-https.ps1 -InstallTrustAndHosts` 后自行核对。
2. 当前产品没有已核准参数、型号或 Structured Relations；这不是导入遗漏，而是明确的 `BLOCKED` 数据边界。
3. 产品媒体当前以主图与媒体记录验证为主，既有模型没有独立 Product Gallery 关系表，本轮未新增第二套图库结构。
4. 英文名称和两种语言的技术措辞均为 draft，必须由用户终审。
5. 没有执行 Review、Publish 或受保护预览发布；没有生产部署。
6. Lighthouse、真实 Safari/WebKit 与海外网络未运行，状态为 `NOT RUN`。

## 12. 用户审核入口与下一步

完成主机映射和 CA 信任后，可访问：

- Admin：`https://admin.junhui.test/catalog/products`
- Website：`https://junhui.test/`
- API：`https://api.junhui.test/api/v1/health/ready`

隔离管理员用户名和随机密码保存在被 Git 忽略的 `.env.phase37`，本报告不记录凭据。

请用户在 Admin 中重点核对产品中英文名称、摘要、描述、主图与 4 张媒体归属。确认后仍需另行提供或批准最新版参数来源、单位、适用型号以及材料/工艺/应用关系。本轮在 draft import 后停止，等待用户单独授权下一步；不会自行 Review、Publish、扩展到 3–5 个产品或进入生产环境。
