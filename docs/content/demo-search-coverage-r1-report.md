# Demo 站内搜索覆盖补齐 R1＋后台状态文案小修实施报告

## 1. 结论

- 实施范围：仅 `junhui-demo-r2`，实际分支 `phase-3.7`。
- 运行编号：`20260911T100118+0800`。
- Git 基线：`d3e4435da63c583a3c46b395d3875ca573801ea1`，本地上游基线一致；本轮未执行远端 fetch。
- 站内搜索覆盖问题：已关闭。搜索白名单由六类补齐为八类，新增当前代码枚举中的 `technology` 与 `manufacturing_capability`。
- Contact/RFQ 后台状态文案问题：已关闭。内容发布、页面访问、页面搜索引擎规则、环境保护已分开显示。
- 六页 SEO：未重写，最终逐页复核与既有验收基线完全一致。
- 数据与部署边界：未迁移、未运行 Seed、未 Review/Publish、未修改 Demo 业务内容或发布状态、未连接云/NAS/Gmail、未改 DNS/Analytics、未部署、未 commit/push/merge。
- Demo 状态：`junhui-demo-r2` 全部服务健康并保持运行；唯一宿主监听仍为 `127.0.0.1:443`。
- 本报告只关闭本轮“搜索覆盖＋后台状态文案”问题，不代表全站 SEO/GEO 或生产环境通过。

## 2. 输入材料与现状读取

实施前已读取附件中的：

- `01-Search-Coverage-Handoff.md`
- `03-Search-Coverage-and-QA.json`
- `SOURCE-NOTES.md`
- `sources/` 下与本轮搜索、六页 SEO 和前台定向复核有关的材料

同时读取了实际工作树、当前搜索白名单、公开 technology/capability 集合和主 Demo 查询结果。附件中的说明仅作为交接资料，没有覆盖真实代码或当前运行态。

覆盖前真实状态：

| 项目 | 覆盖前结果 |
| --- | --- |
| 搜索类型白名单 | `product`、`material`、`application`、`solution`、`knowledge_article`、`case_study` |
| 中文“螺杆” | 6 条产品结果 |
| 中文“氮化” | 0 条 |
| 中文“需求评审” | 0 条 |
| 显式 `types=technology` | HTTP 422，类型不受支持 |
| 已发布公开工艺 | 实际存在 6 条中文 technology |
| 已发布公开制造能力 | 实际存在 4 条中文 manufacturing capability |

根因是公开集合配置已经存在工艺技术与制造能力，但搜索 API、字段白名单、前台类型及分页合同仍停留在六类版本。

## 3. 实施内容

### 3.1 后端搜索

搜索白名单现在按当前实体枚举覆盖八类：

1. `product`
2. `material`
3. `technology`
4. `application`
5. `solution`
6. `manufacturing_capability`
7. `case_study`
8. `knowledge_article`

新增真实可见字段：

- 工艺技术：标题、`definition`、`process_description`、`benefits`、`limitations`。
- 制造能力：标题、`summary`、`description`。

既有字段与查询方式保持不变：PostgreSQL `FTS + pg_trgm + strpos` 中文安全字面子串查询；没有引入外部搜索引擎、AI、自动翻译或第二套内容库。SQLite 隔离测试分支也改为转义 `%`、`_` 和转义符的字面包含查询。

每个结果仍先经过原公开集合资格链：

- 实体状态为启用；
- 目标语言启用；
- 同语言翻译为已发布；
- Publication 为已发布；
- Route 为启用、可索引、自规范路由；
- 业务 SEO 未设置 `robots_index=false`；
- canonical override 不得指向非当前自规范 URL。

Demo 网关的全站 `X-Robots-Tag: noindex, nofollow` 只承担环境保护，不会把站内搜索归零；单个内容自己的 noindex 与公开资格规则仍会排除该内容。

查询结果改为先构造一份合格集合，再按 `(type, slug)` 去重，并在同一集合上完成相关性排序、总数、分页和当前页分组。API 返回 `items/page/page_size/total/pages`，保留 `groups` 作为兼容字段。旧 `limit` 参数保留为已弃用兼容入口，不再用于每类独立截断。

### 3.2 前台搜索交互

- 显示当前语言的类型、标题、公开摘要和详情路径。
- 结果链接继续使用相对路径，点击后保持 `demo.junhuiscrewbarrel.com` 同源；正式 canonical 没有修改。
- 分页由服务端统一执行，查询词与页码保留在 URL 参数中。
- 空输入、加载、无结果、错误、清除、返回与分页状态继续存在。
- 新请求采用可取消去重策略，加载期间不显示旧结果，避免旧响应覆盖新查询。
- 没有更换整套前台设计，也没有新增搜索管理平台。

### 3.3 Contact/RFQ 后台显示

状态区域现在分别展示：

- 翻译状态；
- 内容发布状态；
- 页面访问状态；
- 页面搜索引擎规则；
- 环境保护；
- 固定路径。

`Route.active/indexable` 只保留在折叠的技术状态中，不再把 `Route.is_indexable` 直接翻译为“业务可索引”。页面状态、翻译状态、发布状态和语言操作标签复用中文词表；`English` 显示为“英语（en）”。这次只修改显示，没有改变 SEO 值、robots、发布状态、权限或英语正文。

## 4. 主 Demo 实际查询结果

以下均为 `junhui-demo-r2` 的真实已发布公开内容，不是为了验收新写入的数据：

| 语言 | 查询 | 总数 | 代表结果 | 类型 | 安全路径 |
| --- | --- | ---: | --- | --- | --- |
| zh-CN | 螺杆 | 6 | 通用注塑螺杆（演示） | 产品 | `/zh-cn/products/demo-cat-screws/demo-s01/` |
| zh-CN | 氮化 | 1 | 氮化流程演示 | 工艺技术 | `/zh-cn/technologies/demo-tec-nitriding/` |
| zh-CN | 需求评审 | 1 | 需求评审（演示流程） | 制造能力 | `/zh-cn/capabilities/demo-cap-01/` |
| en | Nitriding | 1 | Nitriding workflow demo | Technologies | `/en/technologies/demo-tec-nitriding/` |
| en | Requirements review，限制造能力 | 1 | Requirements review — demo workflow | Manufacturing Capabilities | `/en/capabilities/demo-cap-01/` |
| zh-CN | Nitriding | 0 | 无跨语言结果 | — | — |
| en | 氮化 | 0 | 无跨语言结果 | — | — |
| zh-CN | `%_` | 0 | 按字面处理 | — | — |
| zh-CN | `' OR 1=1 --` | 0 | 参数化处理 | — | — |

中文“演示”的跨类型实查结果为 46 条，`page_size=5` 时共 10 页；逐页合计 46 条、唯一 `(type, slug)` 也是 46 条。八类分布如下：

| 类型 | 数量 |
| --- | ---: |
| product | 9 |
| material | 8 |
| technology | 6 |
| application | 6 |
| solution | 1 |
| manufacturing_capability | 4 |
| case_study | 4 |
| knowledge_article | 8 |

前台浏览器使用页面默认 `page_size=12`，第 1 页与第 2 页都显示 12 张卡片，总数始终为 46，第二页 URL 保留 `q=演示&page=2`。

## 5. 公开与隐私边界验证

独立 PostgreSQL 验证中的样本均明确为 **TEST ONLY**，没有写入常驻 Demo。测试数据库从空库迁移到 `20260910_0016`，由用例建立最小语言与内容数据，没有运行默认 Seed。

正向验证：八个类型各 1 条，共 8 条；`page_size=3` 时分页为 `3/3/2`，总数始终为 8，八类全部出现，且 8 个 `(type, slug)` 唯一。类型收窄到工艺技术＋制造能力时总数为 2。

反向验证全部为 0 条：

- 翻译草稿；
- 实体停用；
- Publication 归档/撤回；
- Route 关闭；
- Route noindex；
- 非自规范 Route；
- SEO `robots_index=false`；
- canonical override 指向其他 URL；
- 禁用语言；
- 跨语言查询；
- `%_` 特殊字符；
- Case Study 私有 `client_name/client_address` 字段。

随后把正向 technology Publication 撤回、把正向 manufacturing capability 停用，结果总数由 8 变为 6，这两类立即从同一计数和分页集合中消失。

本轮没有新增数据库索引：当前实现继续复用已有 FTS/trigram 能力，真实 Demo 规模为 6 条工艺、4 条制造能力，查询与分页验证均正常；没有证据支持为本轮追加迁移或索引。

## 6. 浏览器验收

浏览器工具采用本机 Playwright CLI 0.1.14＋Microsoft Edge。Codex 浏览器插件在本地不可用，因此按附件允许的等价浏览器路径执行。

桌面 1440×900 实际完成：

- “螺杆” → 显示产品类型与标题 → 点击“通用注塑螺杆（演示）” → H1 相同 → Demo 同源；
- “氮化” → 显示工艺技术类型与标题 → 点击“氮化流程演示” → H1 相同 → Demo 同源；
- “需求评审” → 显示制造能力类型与标题 → 点击“需求评审（演示流程）” → H1 相同 → Demo 同源；
- 英文 “Nitriding” → 显示 Technologies 与英文标题 → 点击详情 → H1 相同 → Demo 同源；
- “演示”第一页 → 点击下一页 → 查询词、总数和页码正确；
- 点击清除 → 返回“输入至少两个字符开始搜索”。

手机 375×812 实际完成“需求评审”搜索与详情点击；搜索页和详情页均无水平溢出。最终镜像替换后又完整重跑一次上述公开流程；浏览器 console error 与 page error 均为 0。

后台用中文界面实际查看 Contact 与 RFQ 的中英文状态：

| 页面 | 翻译 | 内容发布 | 页面访问 | 页面搜索引擎规则 | 环境保护 |
| --- | --- | --- | --- | --- | --- |
| Contact zh/en | 已发布 | 已发布至本地演示环境 | 已启用 | 禁止索引 | 全站禁止索引 |
| RFQ zh/en | 已发布 | 已发布至本地演示环境 | 已启用 | 禁止索引 | 全站禁止索引 |

后台实际页面中没有“业务可索引”误导文案，中文与英文固定路径均正确。登录验收只新增 1 条 `auth_sessions` 和 1 条 `audit_logs` 安全记录；对快照与验收后的 103 张表做行数＋内容摘要比较，除这两张预期登录表外，业务表差异数为 0。

## 7. 冻结项与运行环境

六页 SEO 与既有 `20260910T234537+0800` readback 比较：6/6 unchanged。

- About zh/en：页面 robots 为 `index, follow`；
- Contact zh/en：页面 robots 为 `noindex, nofollow`；
- RFQ zh/en：页面 robots 为 `noindex, follow`；
- 六页 title、description、正式域 canonical、三组 hreflang、canonical 数量和 alternate 数量均不变；
- Demo 网关仍统一返回 `X-Robots-Tag: noindex, nofollow` 与 `Cache-Control: no-store`。

运行保护复核：

- Demo 首页 200，noindex/no-store；
- Admin 登录页 200，noindex/no-store；
- API ready 200；
- Sitemap 404；
- Privacy 页面与公开 API 都是 404，未发布；
- RFQ 页面 200，但提交仍禁用；
- Alembic 版本仍为 `20260910_0016`，迁移差异为空；
- Demo PostgreSQL、Redis、MinIO 原数据卷保留；
- 未写入、未重建原 `phase37` 批准环境。

本轮受影响最终镜像：

- API：`sha256:33db341f4bf93f69f489d1be6947f75c798220104a102f3c42e8713faf2e9850`
- Website：`sha256:ee405d4a17e01e9cd2dd3e7eba1db52b3e729e8845bfab76f6f4f0ee841439cd`
- Admin：`sha256:409673ed519019b8d78f64f72b60b0c2bb9dbe22a0d668bdecad07566e4ac9ef`

## 8. 测试与构建结果

| 检查 | 最终结果 |
| --- | --- |
| API 受影响测试＋真实 PostgreSQL 集成 | 39 passed，29.22s |
| 独立八类 PostgreSQL 用例 | 1 passed |
| Website Vitest | 16 files / 155 tests passed |
| Admin Vitest | 14 files / 89 tests passed |
| Ruff 0.12.11（受影响 Python 文件） | passed |
| 根目录 `pnpm lint`（含 website/admin typecheck） | passed |
| `pnpm format:check` | passed |
| Website production build（格式化后重跑） | passed |
| Admin production build | passed |
| `git diff --check` | passed；只有 Git 的预期 LF→CRLF 提示 |
| 主 Demo 公开浏览器流程 | passed；console/page errors 0 |
| 六页 SEO 冻结复核 | 6/6 unchanged |

开发过程中的两项非最终失败也已保留说明：

1. TDD 红灯阶段按预期分别发现前台缺少 technology、后台缺少分离状态、API 缺少工艺/能力分组，随后实现转绿。
2. PostgreSQL 集成用例初稿让正向和反向样本共用长 UUID，trigram 合法模糊匹配导致反向样本碰撞；改为独立随机检索词后通过。这是测试数据设计问题，不是生产过滤失败。
3. 最终补充复核时，受限 PowerShell/curl 进程一度无法取得本地 TLS 凭据或写证据路径；相同六页脚本和 API 请求在允许本机 HTTPS 的上下文中重跑后成功。失败调用没有被计入业务验收结果。

## 9. 变更文件

- `apps/api/app/modules/discovery/public_collections.py`
- `apps/api/app/api/v1/public.py`
- `apps/api/tests/test_phase36_public_collections.py`
- `apps/api/tests/test_postgresql_integration.py`
- `apps/website/app/types/public.ts`
- `apps/website/app/pages/[lang]/search/index.vue`
- `apps/website/app/i18n/ui.ts`
- `apps/website/tests/phase36-interactions.test.ts`
- `apps/admin/app/pages/site-pages/[systemKey].vue`
- `apps/admin/tests/demo-seo-metadata-r1-contract.test.ts`

工作树在本轮开始前已有的 `README.md` 修改、旧报告、旧证据 ZIP、旧 artifacts 和交接文档均保留，未被本轮覆盖或清理。

## 10. 数据快照与证据边界

实施前已生成 Demo 私有快照：

- 私有路径：`data/demo-r2/private/backups/demo-r2-before-search-coverage-r1-20260911T100118+0800.dump`
- 大小：717,192 bytes
- SHA-256：`f8c58eaea3955770658863936ff5a05921331840aff7140df9b61d1dcce65404`
- `pg_restore --list` 验证：PostgreSQL custom format、gzip、1508 TOC entries。

该快照包含私有数据，只保留在 Git ignore 的本地 private 目录，明确不进入共享证据 ZIP。后台认证状态、凭据、Cookie、环境变量和私有字段原值同样不进入证据包。

## 11. 交付与复验状态

- 结构化 readback：`docs/content/demo-search-coverage-readback.json`
- 本报告：`docs/content/demo-search-coverage-r1-report.md`
- 证据包：`Junhui-Demo-Search-Coverage-R1-Evidence-20260911T100118+0800.zip`

Demo 保持运行，等待本轮复验。
