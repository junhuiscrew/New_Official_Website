# Phase 3.7.3 SEO 有限应用与隐私准备报告

运行 ID：`20260907T154820+0800`
执行日期：2026-09-07（Asia/Shanghai）
唯一目标：`phase37-local-https`
候选版本：`SEO-CANDIDATE-R1-V1`
结论：`PARTIAL — 6/8 OWNER-BACKED GROUPS APPLIED AND VERIFIED; PRODUCTS 2/8 BLOCKED`

## 1. 执行结论

本轮在原有本地隔离实例中完成了可使用现有真实 owner 保存的 6 组 SEO：About、screws、barrels 的中英文 `title` 与 `description`。6 组均通过现有 Admin API、真实登录权限和 CSRF 写入；最终 Admin/API 回读、公开 API 和首次 SSR 均与审批内容逐字一致。

Products 聚合页中英文 2 组没有写入。实际代码和数据库中不存在可代表 `/products/` 的真实页面 owner、ContentRoute、站点页面注册表或设置实体；当前后端 `_product_listing_seo` 对无分类列表使用通用硬编码标题。按用户明确边界，建立可维护保存位置需要扩模型和迁移，因此本轮暂停这两组，未伪造 UUID、未借用其他 owner、未创建假产品，也未在 Vue 中硬编码审批文案。

因此：

- `F-R1-004`：`PARTIAL / OPEN — PRODUCTS STORAGE MODEL DECISION REQUIRED`，不能关闭。
- `F-R1-001`：`OPEN — POLICY AND OPERATIONS PENDING`，不能因主体和地址已确认而关闭。
- 本报告不代表 Phase 3.7 完成，不构成生产上线许可。

## 2. 实际目标与代码版本

| 项目 | 实际值 |
|---|---|
| Git 分支 | `phase-3.7` |
| HEAD | `0fd6edabfc6d4efa8666cf49c54765b099b24300` |
| 开始时未提交路径数 | 37 |
| 报告生成前未提交路径数 | 43；原有后续提交和未提交工作均保留 |
| 审批 JSON SHA-256 | `d6be4ee3647b7be0d93851bcd16702c56f0f6a8918c8013b4e534638fa5d2b3d` |
| 输入 ZIP SHA-256 | `5e04958e65e5aa4387e461c483aaafd72c929f35bbaa439f09ea6fdf0d0e1ae0` |
| 运行 API 容器镜像 ID | `sha256:08596df0fe9958c03ee1d389830bd71c0c88e7ace178dec88e325c19b6f94b3c` |
| 运行 API 启动时间 | `2026-09-07T08:12:29.547022306Z`，健康状态 `healthy` |
| 工作区/运行容器/最终构建内 `services.py` SHA-256 | 均为 `35304e1e535f9793e27842ada10be53ba2dc31aeb1bc2447dbcb3e3c530dc288` |

输入包 13 条 manifest 哈希全部核对成功。包中 JSON 只作为审批内容记录读取，没有直接作为完整 API 请求体提交。

## 3. 冲突门与保存方式

写入前从实际 Admin/API 读取现值和 owner，并保存私有前快照。结果：

- 计划更新 6 组；已有相同值 0 组；冲突 0 组。
- Products 2 组在 owner 解析阶段标记 `blocked_missing_owner`。
- 只构造现有 `SeoDocumentUpsert` 允许的完整字段，保留 canonical override、robots、Open Graph 和 Schema override 现值。
- 共执行 6 次 `PUT /api/v1/discovery/seo/...`；更新 6、no-op 0、冲突 0。
- 保存后重新运行同一规划器：6 组均变为 no-op，Products 仍为受阻。
- Review 调用 0，Publish 调用 0。现有已发布正文 owner 的公开查询直接消费独立 SEO 文档，因此本轮不需要重发正文。

为满足 Revision/Audit 要求，本轮给既有 `upsert_seo_document` 增加了以真实 `seo_document.id` 为 owner 的独立不可变 Revision 快照，并保留原有 `seo.upsert` Audit。没有修改历史 migration。

实际隔离 PostgreSQL 聚合回读：

| 对象 | 数量 / 摘要 |
|---|---|
| `seo_documents` | 6 |
| `content_revisions`（`owner_type=seo_document`） | 6；revision 号均为 1 |
| `audit_logs`（`action=seo.upsert`） | 6 |
| Audit 时间范围（UTC） | `2026-09-07T08:12:58.941996Z` 至 `2026-09-07T08:12:59.138818Z` |
| 执行身份 | 脱敏别名 `SEO-EDITOR-01`；未伪造审核人 |

## 4. 8 组实际回读结果

| 页面 | 语言 | Admin/API | 首次 SSR | 实际状态 |
|---|---|---|---|---|
| About | zh-CN | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |
| About | en | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |
| Products | zh-CN | 无真实 owner，未写入 | 实际标题仍为“产品”，description 为空 | `BLOCKED_NOT_APPLIED` |
| Products | en | 无真实 owner，未写入 | 实际标题仍为“Products”，description 为空 | `BLOCKED_NOT_APPLIED` |
| screws | zh-CN | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |
| screws | en | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |
| barrels | zh-CN | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |
| barrels | en | title/description 逐字一致 | 逐字一致 | `APPLIED_VERIFIED` |

首次 SSR 使用禁用 JavaScript 的真实 Microsoft Edge 上下文采集，不是客户端水合后的替代值。8 页和对应公开 API 均返回 200；6 个 owner-backed 页面 title/description 的内容哈希与审批包一致。

正式 canonical、reciprocal hreflang 和 Schema 继续使用 `https://junhuiscrewbarrel.com/...` 规范地址；本地预览入口未被写进正式 SEO 字段。页面业务 robots 规则保持原值，外层隔离网关继续统一返回 `X-Robots-Tag: noindex, nofollow`。

## 5. Products 聚合页最小后续方案（未实施）

建议后续单独审批一个小型可维护页面实体方案：

1. 新增真实 `SitePage`（或同义命名）实体，以稳定 key `products` 表示产品聚合页，而不是伪造产品或复用 CompanyProfile。
2. 通过 migration 建立该实体及中英文 ContentRoute；现有 `SeoDocument` 继续使用其真实 UUID 和 locale 保存 title/description。
3. Admin 增加该页面的 SEO 编辑入口，沿用 `seo.read`、`seo.update`、CSRF、Revision 和 Audit。
4. `_product_listing_seo` 仅在无分类的聚合页读取该 owner；分类筛选继续使用分类 SEO，分页/筛选 noindex 和公开资格过滤不放宽。
5. 增加 API、真实 PostgreSQL、Admin、SSR 和 sitemap 候选回归后，再应用本次已经批准的 Products 两组内容。

该方案涉及新模型、migration、路由接线和 Admin，因此本轮未擅自实施；其余 6 组不因该阻断回退。

## 6. 冻结项复核

写入前后对 Company、P01/P02/P03、规格定义/值和旧试点完整快照做递归稳定序列化。前后 SHA-256 均为：

`8e0530205e7c55600752a7eafd58fa72c885319742e6cd1059267fe241b64f99`

结果：

- COPY-V1 公司/产品 16 个正文字段未变化。
- 公司名称、产品名称、slug、分类、Logo/主图关联、featured、型号和关系未变化。
- P01/P02/P03 规格值仍为 0/0/0，型号和四类关系数量均为 0。
- 七个规格定义未变化；F05 仍只有中文翻译，英文为空缺。
- P01/P02/P03 原有双语 Publication/TranslationStatus 与 Route 保持已批准预览状态。
- 旧试点双语 TranslationStatus/Publication 仍为 `draft`；两条 Route 仍 `active=false`、`indexable=false`，实际页面为 404。
- 新隐私地址和邮箱只出现在内部隐私文档，没有写入 CompanyProfile、销售邮箱、登录邮箱或 Schema。

## 7. 隔离与浏览器验证

现有边界检查结果为 `boundary_verified`：

- `https://junhui.test/` 为唯一网站入口，宿主机 443 正在监听。
- Website、Admin、API 匿名访问均为 401；认证后核心入口为 200。
- 只有 Nginx 映射宿主 443；API 8000、Website 3000、Admin 3001、PostgreSQL、Redis 和 MinIO 均无宿主端口。
- 8 个 SEO 页面响应均含外层 noindex；Sitemap 仍为 404。
- 中英文 Privacy 均为 404，未发布工作稿或占位页。
- 旧试点中英文页面均为 404。
- Analytics 和 marketing email 保持关闭；未建立公网隧道。

真实浏览器还完成了 8 页桌面渲染和 About zh-CN、screws en 的 375px 移动渲染。页面正文不是 401/登录页，无横向溢出；浏览器 page error 为 0，外站请求为 0。控制台中的 5 条 404 仅来自本轮明确执行的 Sitemap、Privacy 和旧试点负向检查，不是核心页面资源错误。

## 8. 隐私准备结果

本轮生成以下内部材料：

- `privacy-facts-confirmed-v1.md`：区分用户确认、代码事实、用户陈述待运行核验和未知事项。
- `privacy-retention-and-request-process-proposal-v1.md`：按未成交询盘、已成交沟通、附件、日志、备份、Gmail 分类的保留表与最小人工请求流程。
- `privacy-notice-working-draft-v0-2.zh-en.md`：中英文工作稿和明确发布门。

关键边界：

- “保留/删除尚未制定”“请求流程尚未制定、通常由用户本人处理”按事实保留。
- `RFQ_RETENTION_DAYS=730` 仅是 closed 询盘候选计数阈值，不是自动删除或已批准期限。
- 腾讯云具体地域与本地备份位置仍未知；MinIO 是自建，不是 COS。
- Gmail 仅为联系邮箱；没有启用 SMTP、Gmail API、自动转发或推广邮件。
- 没有虚构答复天数、数据地区、DPO、合规结论或全备份即时删除能力。
- 隐私正文仍未批准，当前 404 不以空白 200、占位或跳转伪装修复。

## 9. 验证命令与真实结果

| 检查 | 结果 |
|---|---|
| 新增 Revision 测试，修复前单测 | `FAIL`：实际返回 0 条 Revision，证明测试有效 |
| 同一单测修复后 | `1 passed` |
| API 专项回归：`test_phase34_discovery.py`、`test_phase34_authority_services.py`、`test_phase34_api_contract.py` | `28 passed in 6.62s` |
| Ruff 0.12.11 lint（本轮两个 Python 文件） | `PASS — All checks passed` |
| Ruff format check（全文件） | `NOT CLEAN`：两个历史文件含既有未格式化区段；为避免重排无关未提交代码，已撤销全文件格式化，不写 PASS |
| `git diff --check` | `PASS`；仅有 Windows LF/CRLF 提示，无 whitespace error |
| API runtime 构建 | `PASS`，最终镜像已生成 |
| 运行容器与工作区/最终镜像源码哈希 | `PASS`，三者 `services.py` 哈希一致 |
| Admin/API 写入后 no-op 回读 | `PASS`：6 exact，0 conflict，2 blocked |
| 禁用 JS 首次 SSR + 公开 API | `PASS`：6/6 owner-backed exact；Products 2/2 如实受阻 |
| Edge 桌面/375px 浏览器核验 | `PASS`：10 张真实截图，无横向溢出、无 page error、无外站请求 |
| Website test/typecheck/build | `NOT_RUN`：本轮没有修改 Website 代码；未复制旧测试数量 |
| Admin 回归 | `NOT_RUN`：本轮没有修改 Admin 代码或配置 |
| 全量测试 | `NOT_RUN`：纯限定 SEO/Revision 改动不运行无关全量测试 |

初次尝试在仓库根直接运行 `docker build --target test ...` 因根目录没有 Dockerfile 而失败；随后使用实际 `apps/api/Dockerfile` 完成构建。这是命令路径修正，不记为项目测试通过或失败。初次测试镜像未包含 Ruff，故曾返回工具缺失；随后使用固定 `ruff==0.12.11` 的临时容器完成实际 lint/format 检查，没有全局安装或修改项目依赖。

## 10. 未执行和禁止动作

- 未执行 Content Review/Publish，未重发产品、分类或 Company 正文。
- 未发布 Privacy，未提交 RFQ，未上传附件，未发邮件。
- 未导入、Seed、迁移、清理数据或恢复备份。
- 未连接生产、腾讯云账户或生产对象存储；未改 DNS、Analytics 或仓库公开性。
- 未 commit、push、merge 或部署；受保护预览继续保留。

## 11. 下一步等待事项

1. 决定是否单独授权 Products 聚合页真实 `SitePage`/migration/Admin 接线方案；完成并核验两组后才能关闭 `F-R1-004`。
2. 一次性确认腾讯云地域、“本地备份”位置、分类保留规则和人工请求流程。
3. 审阅并批准最终中英文隐私正文；批准前继续保持 Privacy 404。
