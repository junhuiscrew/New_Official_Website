# Phase 3.5 Remediation Completion Report

## 1. Branch / Base / Final SHA

- 项目：`junhuiscrew/New_Official_Website`
- 分支：`phase-3.5-fix`
- 基线分支：远端 `phase-3.5`
- Base SHA：`7597ac3c05c825dd21249051e9dfdd7080a380e9`
- Final implementation SHA：`f0c9550e0132ad4ce17f899786f8e069710b7862`
- 正式主域名：`https://junhuiscrewbarrel.com`
- 范围：仅 Phase 3.5 Remediation；没有进入 Phase 3.6、最终首页、最终 Design System、Page Builder 或生产部署。

## 2. Object Storage Adapter

新增 `app/modules/media/storage.py`，使用 MinIO 官方 Python SDK 实现异步友好的 `put_object`、`get_object`、`delete_object`、`object_exists` 与 `presigned_get`。阻塞 SDK 调用通过 `asyncio.to_thread` 移出事件循环；内部读写端点与浏览器可访问签名端点分离，并显式配置 S3 region，避免签名阶段探测公网端点。

## 3. Public Media real upload

`POST /api/v1/media/assets` 现在完成文件校验后真实写入 `public-media`，数据库失败时删除已写对象。公共文件通过 API 同源代理读取；返回给浏览器的 URL 不包含 `minio:9000`。`MediaAssetTranslation` 提供按 Locale 的 alt/title/caption/description 元数据编辑与审计。

## 4. RFQ Private real upload

后台和匿名 RFQ 附件都真实写入 `private-rfq`。对象键由 RFQ、随机 UUID 和清洗后的文件名组成；数据库 flush/commit 失败时回滚对象。公共媒体与 RFQ 私有文件继续受 visibility/bucket 数据库约束和服务层校验双重隔离。

## 5. Presigned Download

移除自定义 HMAC 拼接 URL。私有下载使用官方 S3 Presigned GET，TTL 固定受 60–900 秒边界约束。签发前必须同时满足：已认证、`rfq.download_private_file`、文件属于目标 RFQ、asset 为 private、bucket 为 `private-rfq`、`malware_scan_status=clean`、`upload_status=ready`。签发动作写入 Audit Log。

## 6. Public RFQ Attachment

采用两阶段匿名上传：创建 RFQ 后返回公开 reference 和 30 分钟短期 submission token；上传端点使用公开 reference 定位，token 只允许对应 RFQ 的附件上传，不使用或暴露数据库 UUID。支持 JPG、PNG、WEBP、PDF、DWG、DXF、STEP/STP、IGES/IGS，Website 表单支持多 Item、多附件和可选 Item 绑定。

## 7. Malware worker

新增 ClamAV INSTREAM scanner adapter、扫描结果状态机和 Celery `scan_private_asset` 任务。Worker 从 MinIO 读取私有对象，扫描后在数据库事务中写入结果和审计；同时保留 retention candidate 任务骨架，不自动删除真实生产数据。

## 8. Scanner production behavior

只有 `clean` 才会进入 `ready`。`infected` 记录为 infected，`failed` 记录为 failed，两者的 `upload_status` 均为 `quarantined`；没有向 `malware_scan_status` 写入数据库 CHECK 不允许的 `quarantined` 值。Staging/Production 未启用或无法使用扫描器时 fail-closed，文件不可下载；开发/测试可以显式关闭外部扫描器。

## 9. CAD signature validation

除 extension、MIME、大小、文件名和 SHA256 外，增加 DWG `ACxxxx`、DXF section/header、STEP `ISO-10303-21`、IGES 固定列 section marker 的实际 header/signature 校验。仅伪造扩展名或 `application/octet-stream` 不能通过。

## 10. Trust lifecycle

Manufacturing Capability 与 Exhibition 继续复用既有 TranslationStatus、ContentPublication、ContentRoute、ContentRevision 和 Audit。编辑已发布翻译会把 TranslationStatus 退回 draft、Publication 退回 review，并令 Route inactive + noindex。Published slug 直接修改返回 409；Draft slug 修改同步 canonical Route。disabled/retired 会 archive publication 并关闭 route，重新 enabled 不会自动发布。

## 11. Trust Revision

Trust create/update/translation 修改写入真实 snapshot revision；Translation revision 包含实际 Locale 和变更后的字段，不保存空壳 revision。生命周期变化继续由统一 Content 模块维护。

## 12. RFQ Origin

Origin/Referer 使用 URL parser 后对 scheme、hostname 和显式 port 做完整 tuple 精确匹配。恶意前后缀域名、userinfo、错误 scheme 或端口均拒绝；Production 缺失 Origin/Referer 也拒绝。

## 13. Client IP trust model

只有直连 peer 命中 `TRUSTED_PROXY_CIDRS` 时才读取 `X-Forwarded-For`。解析时从右向左剥离可信代理并取第一个不可信地址，非可信 peer 的自报头完全忽略。Nginx 改为覆盖 `X-Forwarded-For` 为 `$remote_addr`，同一可信 IP 用于 Redis rate limit 和 `submitted_ip`。

## 14. RFQ item ownership

附件带 `item_id` 时必须查询到 `RFQItem.id + rfq_id` 同时匹配，否则 422。ProductModel 必须存在并属于当前 Product；跨 RFQ Item 和跨 Product Model UUID 注入均有回归测试。

## 15. Reference collision handling

公开 reference 使用高熵随机后缀，并在落库前有限重试 5 次；数据库 unique constraint 仍是最终一致性防线。连续无法获得候选值时返回 503，不静默覆盖或泄露内部 ID。

## 16. Admin Trust

`/trust/company`、`/trust/capabilities`、`/trust/equipment`、`/trust/certificates`、`/trust/patents`、`/trust/honors`、`/trust/exhibitions` 已由占位页升级为连接真实 API 的最小 CRUD。公共 Company Profile 仍只读取真实录入数据，没有 Seed 虚假设备、证书、专利或荣誉。

## 17. Admin Media

`/media` 支持真实文件选择、multipart 上传、public-media 列表和多语言 metadata 编辑。FormData 请求不会错误设置 JSON Content-Type，由浏览器生成 multipart boundary。

## 18. Admin Downloads

新增 Downloads Admin API；`/downloads` 支持选择 ready public media、创建、编辑 translations、状态切换和 archive。私有 RFQ asset 无法被选择为公开下载。

## 19. Admin RFQ Detail

`/rfqs/{id}` 展示真实 RFQ、Items、Files、Assignment、Status、Scan/Upload 状态和 Audit；提供状态更新、销售分配、后台私有附件上传及通过权限 API 获取 Signed Download 的操作。

## 20. Trust SEO/GEO

Capability/Exhibition 已接入后端真实可见正文构造、统一 Publication/Route/Translation 门槛、SEO canonical/robots/hreflang 和 GEO 可见内容 DTO。GEO direct answer/key facts/evidence 只能从用户可见的翻译和结构化字段构造，不接受客户端自报隐藏来源。

## 21. Trust index pages

Capability、Certificate、Patent、Honor、Exhibition 索引页均通过 SSR Public API 读取真实可公开数据。空数据使用中性提示，不再静态声称“Verified certificates”等未配置事实；disabled/retired、未发布或不可索引内容不会出现。

## 22. Storage/public URL architecture

服务端通过 `MINIO_ENDPOINT=minio:9000` 读写对象；浏览器只访问同源 API public media proxy，或由 `MINIO_PUBLIC_ENDPOINT` 参与生成官方签名的短期私有 URL。Production 会拒绝 localhost、Docker 内部 host 或示例 Secret，防止内部地址与不安全配置进入公开响应。

## 23. Retention

已提供 orphan/quarantined/RFQ retention candidate 查询任务骨架，并明确不在本阶段自动删除生产数据。后续启用清理前必须增加保留期配置、dry-run、审计和人工恢复窗口。

## 24. Audit

已覆盖 media upload/translation update、download create/update/archive、RFQ submit/file upload/assignment/status/private download、Trust create/update/translation/lifecycle 等关键动作。公开响应不返回 Audit、内部路径、assigned user 或内部工作流字段。

## 25. Tests

| 检查项 | 实际结果 |
| --- | --- |
| Ruff | PASS：`All checks passed!` |
| Backend pytest（本地 SQLite） | PASS：170 passed，9 skipped，1 warning |
| Backend pytest（Docker 全集成） | PASS：179 passed，1 warning |
| Media/RFQ/CAD/Malware/Trust/RBAC/Security | PASS，包含新增专项回归 |
| Website Vitest | PASS：13 tests |
| Admin Vitest | PASS：22 tests |
| Typecheck | PASS：Website + Admin |
| Prettier | PASS：All matched files use Prettier code style |
| Production Build | PASS：Website + Admin Nuxt SSR/Nitro |

唯一 pytest warning 是 Starlette TestClient 的 AnyIO alias deprecation；Nuxt plugin timing 与 Node trailing-slash deprecation 不影响构建产物。

## 26. PostgreSQL

真实 PostgreSQL 17.6 集成用例已包含在 179 tests 中并通过。另用两个隔离临时数据库实际验证：Empty DB → `20260904_0009 (head)` 通过；`20260904_0001` → head 通过。主开发库 `alembic current` 为 `20260904_0009 (head)`。Seed 连续执行两次均成功且幂等。

## 27. MinIO integration

真实 MinIO 用例完成 private bucket 的 put、exists/stat、get、官方 presigned URL 和 delete 闭环；签名 URL 不包含 `minio:9000`。Redis 真实双窗口 rate-limit 用例也在同一 Docker 套件中通过。

## 28. Build

宿主机和 Docker 镜像均完成 Website/Admin Production Build。Nuxt 4.5.2、Vue 3.5.42、Vite 8.2.2、Python 3.12、FastAPI 0.116.1、SQLAlchemy 2.0.43、Alembic 1.16.5、Celery 5.5.3、MinIO SDK 7.2.15。

## 29. Docker

`docker compose up -d --build` 已实际完成。`postgres`、`redis`、`minio`、`api`、`worker`、`website`、`admin`、`nginx` 全部 healthy；`minio-init` 正常完成后退出。HTTP smoke：API live 200、API ready 200、Website `/zh-cn/` 200、Admin `/` 200、Nginx ready 200。

## 30. Known issues

1. ClamAV adapter 与 Celery worker 已实现，但本地 Compose 默认未内置重型 ClamAV daemon；开发环境默认关闭，Staging/Production 必须配置实际 scanner host 并启用，否则 fail-closed。
2. Public media 当前采用应用代理确保同源和不泄露内部 MinIO 地址；生产可在保持 bucket 隔离的前提下切换到受控 CDN/custom domain。
3. Retention 仅提供候选查询/任务骨架，不会自动删除真实数据。
4. 仍存在上游 Starlette/Nuxt deprecation warning，不影响测试和构建。

## 31. Phase 3.5 final acceptance status

本轮 20 项 Remediation 已形成可工作的存储、RFQ、扫描、Trust、Admin、SEO/GEO 闭环；P0/P1 回归、真实基础设施集成、迁移、Seed、Build 与 Docker 健康均通过。验收结论：**Phase 3.5 Remediation implementation complete，等待项目方最终复验；未进入 Phase 3.6。**

## 32. `$seo-rank` / `$geo-rank` conflict review

- `$seo-rank`：canonical、hreflang、robots、Locale、Publication、Route 与 indexability 继续使用唯一既有体系；disabled/retired 和正文变更后不会继续作为可索引权威内容。未发现与冻结交接规范冲突。
- `$geo-rank`：Capability/Exhibition 的 visible-source 由服务器从真实可见正文/结构化事实构造；私有 RFQ、未授权信息、隐藏 AI-only 事实不会进入 Public DTO、Schema 或索引来源。未发现与冻结交接规范冲突。
- 冲突裁决：如通用 Skill 建议与冻结业务决策不同，始终以本项目交接文件与既有 `Master Entity + Translation + Publication + Route + Revision + Audit + RBAC + SEO/GEO` 架构为准。
