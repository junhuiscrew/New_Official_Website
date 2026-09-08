# Privacy P1 正文、版本与 RFQ 关联实施报告

> Run ID：`20260908T155947+0800`  
> 状态：`IMPLEMENTED_FOR_ACCEPTANCE / MAIN_DRAFT_ONLY`  
> 代码基线：分支 `phase-3.7`，HEAD `995d1ce162964adbffd64bde18e5c58e47099086`，工作区含本轮及此前保留的未提交文件  
> 运行目标：`junhui-phase37-pilot / phase37-local-https`

## 1. 范围与结论

Privacy P1 的最低必要工程能力已经实现并完成本地验收：固定 Privacy 页面身份、双语正文后台、不可变政策版本、唯一 current 指针、公开资格门禁，以及 RFQ 对实际版本/语言/正文哈希的服务端关联。

验证严格分开两个环境：

- 主预览只应用迁移并保存公司既有工作稿为私有 draft；没有 Review、Publish、测试 RFQ 或附件。
- 独立 `TEST ONLY` 应用与 PostgreSQL 验证发布、A→B 版本切换、虚构 RFQ、陈旧上下文拒绝和重新确认。

因此本轮可以提交 P1 技术验收，但不代表正式政策获批。`F-R1-001` 和 Phase 3.7 整体继续保持开放，也没有生产上线许可。

## 2. 基线与安全边界

| 项目 | 实际值 |
| --- | --- |
| 开始时主库迁移 | `20260907_0011` |
| 完成后主库迁移 | `20260908_0013` |
| 本地域名 | `https://junhuiscrewbarrel.com/` |
| Admin | `https://admin.junhuiscrewbarrel.com/` |
| HTTPS 监听 | 仅 `127.0.0.1:443` |
| Nginx Basic | 前台无挑战；Admin 自身登录保留 |
| 外层 robots | `X-Robots-Tag: noindex, nofollow` |
| 常驻 Sitemap | `404` |
| 输入 ZIP SHA-256 | `9B6282AC984103B6008CECCE27A4D63DDAEAA0061EB6D62A1D78CA4549547EBC` |

迁移前生成私有 PostgreSQL custom-format 快照，归档目录校验成功；0012 前快照 SHA-256 为 `B0552790FA8253C7EC85F5AC39D46C3F15BEB66D32E2C20B84BB55C1AFA44ACB`。独立审查加固后又在应用 0013 前生成第二份快照，大小 540245 bytes，SHA-256 为 `BCC248D68120628E3187BAE1D2831546F73E6ECB5DB035A073F5D8F280D888A4`，`pg_restore --list` 成功。备份、凭据和数据库连接信息未进入 Git 或脱敏证据包。

## 3. 实际实现

### 3.1 固定页面与不可变版本

- 复用现有 `SitePage`，建立唯一固定 `system_key=privacy`，不借用 Company、Product，也没有创建第二套 CMS。
- 新增 `PrivacyPageState`，只保存一个 `current_version_id` 和一个 `draft_version_id`。
- 新增 `PrivacyNoticeVersion` 与双语 `PrivacyNoticeVersionTranslation`；版本号和版本标签由服务端生成。
- 继续复用现有 `TranslationStatus`、`ContentPublication`、`ContentRoute`、`ContentRevision` 和 `AuditLog`。
- 任一语言进入人工审核、版本已发布/current 或被 RFQ 引用后，服务层与 PostgreSQL trigger 都拒绝原地修改；后续编辑必须克隆为新 draft。
- current 切换在稳定页面与状态行锁内完成；旧版本和历史 RFQ 外键使用限制删除语义保留。
- 审核必须回传管理员实际看到的版本标签、revision 和目标语言正文 hash；发布必须回传同一版本标签、revision 及双语精确 hash。服务端在行锁内重新读取并比对，任一观察值陈旧即返回 409，不接受“按钮点击时换版”的静默覆盖。

正文哈希算法为 `sha256-nfc-json-v1`：Unicode NFC、统一 LF、去每行尾随空白及首尾空行，再对键排序的 `{body_markdown,title}` UTF-8 JSON 计算 SHA-256。服务端在审核、发布、公开读取和 RFQ 提交时重算并比对。

### 3.2 API 与权限

新增固定 Privacy 管理和公开 API：

- 管理：状态读取、初始化、创建/克隆 draft、保存、分语言审核、双语发布、历史读取、页面状态。
- 公开：按语言读取 current 政策；为指定 current 版本签发短时 RFQ policy context。

公开政策 JSON 与 context API 的成功和失败响应都显式带 `X-Robots-Tag: noindex, follow`；政策读取为 `no-cache, must-revalidate`，context 为 `no-store`。该应用层约束不依赖外层 Nginx 的全站 noindex。

新增原子权限 `privacy.read/edit/review/publish/history`，并继续要求既有内容权限组合。所有写请求沿用登录 Cookie、CSRF、真实用户、Revision 和 Audit；没有免登录管理员、owner UUID 输入或权限扩大。

### 3.3 Admin 与安全 Markdown

- Admin 新增 `/privacy`，支持双语 draft 编辑、安全预览、保存后 fresh GET、刷新/重开、分语言审核、独立发布和历史列表。
- Admin 审核/发布按钮发送当前回读的版本、revision 与 hash；409 时自动刷新实际状态，并要求操作者重新核对后再次确认。
- 已审核/已发布内容在界面只读，创建下一版必须显式克隆。
- Markdown 不使用 `v-html`；后端拒绝原始 HTML、所有 Markdown 图片、危险协议、协议相对地址、含查询/多地址的 `mailto:` 和无法可靠解析的复杂链接，前后台使用相同限制并用受限 AST 渲染。

### 3.4 Website 与 RFQ

- 新增双语 `/privacy/` SSR 页面。只有 current、双语完整、已人工审核并发布、已生效、页面启用且 Route active 的版本才返回 200。
- Privacy 业务 robots 固定 `noindex,follow`，且不进入 Sitemap、Search、GEO 或营销集合。
- RFQ 页面先取得短时 policy context；没有合格政策时显示“等待发布”，同意框和提交按钮禁用。
- context JWT 绑定版本标签、语言、正文哈希、canonical、签发和过期时间，不暴露内部 UUID。
- RFQ 创建在写入前校验签名、有效期、语言、hash、current 指针和全部公开门禁；成功后保存版本引用、版本标签、语言、hash、canonical 及服务端确认时间。
- 新 RFQ 的 `preferred_language` 必须显式为 `zh-CN` 或 `en`，不能通过省略语言绕过 policy context 的语言一致性校验；数据库 nullable 只用于兼容历史 legacy 记录。
- policy context 的服务端 TTL 配置限制为 1–60 分钟；默认 10 分钟，0、负数或超过 60 的配置均无法启动。
- 缺失、过期、伪造、错语言或 A→B stale context 均不创建 RFQ。前端保留已填字段和待上传文件，清除旧勾选并要求查看当前政策后主动重新确认。
- 首次 SSR 后若政策已由 A 切换到 B，前端在第一次 context 请求失败时只执行一次受控恢复：读取最新政策、撤销旧勾选并重试；不会要求整页刷新，也不会无限重试。
- 旧 RFQ 的版本证据字段允许全部为 null，不回填或伪造历史同意。

## 4. 迁移、约束与主预览操作

迁移 `20260908_0012_privacy_p1.py` 追加在真实最新 head `20260907_0011` 后，没有修改此前已存在的历史 migration。独立审查发现数据库 trigger 还应直接约束审核人和发布时间后，继续追加 `20260908_0013_privacy_p1_hardening.py`。0013 只替换 Privacy TranslationStatus 防篡改 trigger：INSERT 只能是无审核人的 draft；`draft→human_reviewed` 必须有审核人且没有发布时间；`human_reviewed→published` 必须保留审核身份并写入发布时间；其他越级或回退转换被拒绝。

最终复核又发现：0012 初版 downgrade 在已经初始化 Privacy 后不能恢复 products-only 的 SitePage 约束。由于 0012 本身仍是本轮新增且未提交的迁移，本轮保持 upgrade 路径不变，只补齐其 downgrade 清理顺序：先删除 Privacy 版本的 Revision、TranslationStatus、Publication 和 Audit，再删除 Privacy SitePage 的 Route、Revision、Publication、TranslationStatus、翻译及页面，最后恢复原约束。

该降级不只做字符串检查。独立真实 PostgreSQL 在已有 Privacy 页面、版本、生命周期、Revision/Audit、测试 RFQ 及原 Products SitePage 的状态下实际完成 `0013 → 0012 → 0011`：Privacy 表被删除、Privacy SitePage/多态 Revision/Audit 均为 0、RFQ 的 Privacy 证据列被移除、Products SitePage 仍为 1，products-only CHECK 可恢复；随后同一库实际重新升级 `0011 → 0012 → 0013` 成功，Privacy 表、固定权限和约束重新建立，Products 页面仍保留。所有上述数据均来自 TEST ONLY 隔离库，主预览未执行降级。

主预览按以下顺序处理：

1. 核对 Compose 项目、实际迁移、监听和未提交文件；
2. 保存并校验私有数据库快照；
3. 重建 `api/worker/website/admin`；
4. 分别显式执行 `alembic upgrade 20260908_0012` 与审查后的 `alembic upgrade 20260908_0013`，均未运行 Seed；
5. 只更新受影响服务，保留原 PostgreSQL/MinIO 卷；
6. 通过真实 Admin 初始化固定页面并保存既有公司工作稿；
7. 刷新、离开页面后重新打开，再做数据库和公开入口回读。

主预览最终实际状态：

| 项目 | 实际值 |
| --- | --- |
| Privacy 版本 | 1 个，`PRIVACY-000001` |
| current | 空 |
| draft | `PRIVACY-000001`，row version 3 |
| effective_at | 空 |
| zh-CN | Translation `draft`；Publication `draft`；Route inactive/noindex |
| en | Translation `draft`；Publication `draft`；Route inactive/noindex |
| reviewer / published_at | 均为空 |
| Privacy Revision | 6 条（初始化内容骨架及两次双语保存） |
| Privacy Audit | initialize 1、draft_create 1、draft_update 2 |
| 主库 RFQ | 0 |

第一次多行正文经 CLI 普通 `fill` 时只送入首行，真实回读为 32/38 字符。该版本始终是未审核 draft。随后改用 UTF-8 Base64 浏览器输入事件，通过同一 Admin 覆盖为完整既有工作稿，并再次执行 fresh GET、刷新和重开。最终值为：

| 语言 | 标题 | 正文字数 | `sha256-nfc-json-v1` |
| --- | --- | ---: | --- |
| zh-CN | 隐私说明中英文工作稿（内部 V0.2） | 1339 | `381b3cd2cb9aaf88c907b8daf88e1ae2cb75ca83c529c4f05ffbbc7a89cabd62` |
| en | Privacy Notice Working Draft (Internal V0.2) | 2810 | `dde07b4e898601b44ce35ea1a39118fa088841d1c4337e3f6535956ce7d60f9e` |

以上长度和哈希与从仓库既有 `privacy-notice-working-draft-v0-2.zh-en.md` 机械拆分得到的预期值一致；没有重新起草政策事实。

## 5. 公开资格与本机运行核验

- `https://junhuiscrewbarrel.com/zh-cn/`：200，实际远端地址 `127.0.0.1`，TLS 主机名/证书链校验通过。
- `/zh-cn/privacy/` 与 `/en/privacy/`：均 404，因为主预览没有获准 current。
- `/sitemap.xml`：404；Privacy 未进入候选。
- 匿名 `https://api.junhuiscrewbarrel.com/api/v1/privacy`：401。
- 主 RFQ 页面显示政策等待发布；同意框和提交按钮禁用，未上传附件或提交表单。
- 首页响应含 `X-Robots-Tag: noindex, nofollow`，无 `WWW-Authenticate`。
- Windows curl 首次因本地 CA 没有公网吊销端点返回 `CRYPT_E_NO_REVOCATION_CHECK`；复测仅使用 `--ssl-no-revoke`，未使用 `-k/--insecure`，TLS 校验结果为 0。

运行镜像摘要：

| 服务 | 镜像 digest |
| --- | --- |
| API | `sha256:f8ae3f9bc8b2930fd58da3a3afcdc5d2ed8d2959474229803621f218d752a16a` |
| Worker | `sha256:d5f4c8f7c6b783fa9c5b4514c87fcc9e52c6264911330a80581f47da7b801a44` |
| Website | `sha256:14e7ea95ed68b2f208d858591bcd6112b0beed0310208424d99ad89ddf3e1cdd` |
| Admin | `sha256:57e04d858fddc32dc5379593e7a1c1ef5edc314ffd926464f04a9439e28dd857` |

## 6. TEST ONLY 发布与 RFQ 版本闭环

独立测试栈使用独立 Compose project、数据库、Redis 和 MinIO，不共享主预览业务卷；宿主仅临时绑定 loopback 测试端口。实际浏览器与数据库结果：

1. Admin 创建、保存、刷新和重开 A；双语人工审核后发布 `PRIVACY-000001`。
2. 桌面英文和 375px 中文 Privacy 均显示真实正文；SSR canonical/hreflang 保持正式规范域名，robots 为 `noindex,follow`。
3. 第一个虚构 RFQ 使用 A 成功；数据库保存 A、`en`、64 位 hash、版本外键和服务端确认时间，附件为 0。
4. 保持第二个表单及 A context 不刷新，在 Admin 克隆、编辑、审核并发布 B `PRIVACY-000002`。
5. 使用旧 A context 提交被拒；页面显示版本变化提示，版本刷新为 B，原字段仍在，同意框被取消；数据库 RFQ 数仍未增加。
6. 主动重新确认 B 后同一份虚构表单成功；最终 TEST ONLY 库恰有 2 条 RFQ，分别关联 A 与 B，0 附件。

审查加固后，在同一独立 TEST ONLY 数据库上追加完成 C `PRIVACY-000003` 的真实浏览器复验：从 B 克隆、双语保存为 revision 2、分语言人工审核、独立发布并切换 current；随后重新打开后台，确认 C 为 current、无工作 draft、A/B/C 均保留且只读。前台实际点击中文语言菜单进入 `/en/privacy/`，英文标题与版本均为 C，并保存 375px 截图。公开政策 API 与 context API 均回读 `X-Robots-Tag: noindex, follow`；context token 只核对存在、长度和过期时间，未写入证据。

最终 TEST ONLY 数据库为：迁移 `20260908_0013`、政策版本 3、current `PRIVACY-000003`、draft 空、Privacy Revision 24、RFQ 2、附件 0。Audit 聚合为 initialize 1、draft_create 3、draft_update 3、translation_review 6、publish_switch 3。RFQ 仍只对应先前虚构 A/B；C 的浏览器复验没有重复提交询盘。

第一次 B 审核点击时，长时间浏览器会话的 access cookie 已过期并真实返回 401；页面刷新通过既有 refresh cookie 恢复会话，重试成功，失败调用没有改变审核状态。

## 7. 验收矩阵

| 编号 | 检查项 | 状态 | 证据摘要 |
| --- | --- | --- | --- |
| P1-01 | 草稿访问边界 | `PASS` | 主 Admin 登录可读写；匿名管理 API 401；主公开页 404 |
| P1-02 | 已发布不可变 | `PASS` | 服务测试、0013 PG trigger 与真实 Admin A/B/C 历史共同验证 |
| P1-03 | 双语原子切换与观察值绑定 | `PASS` | C 仅在双语均人工审核后切换 current；陈旧 revision/hash 返回 409 |
| P1-04 | 可读但不可索引 | `PASS_TEST_ONLY` | TEST ONLY 公开 200 + `noindex,follow`；主预览因未批准保持 404 |
| P1-05 | RFQ 真实版本关联 | `PASS_TEST_ONLY` | A/B 两条虚构 RFQ 均有完整版本证据，主库 RFQ=0 |
| P1-06 | 陈旧、过期、伪造、错语言 | `PASS` | API 专项覆盖全部负向；真实浏览器完成 A→B stale |
| P1-07 | 发布与 RFQ 并发 | `PASS` | 真实 PostgreSQL 行锁/竞态专项通过 |
| P1-08 | 历史 RFQ legacy/null | `PASS` | 迁移兼容与 all-null/check constraint 专项通过，不回填历史 |
| P1-09 | 最小权限与 CSRF | `PASS` | API/Admin 权限专项及匿名 401；没有 owner UUID 或权限扩张 |
| P1-10 | 前台禁用与重新确认 | `PASS` | 主预览禁用；TEST ONLY 保留字段、取消勾选并成功重确认 |
| P1-11 | 安全 Markdown 与首次 SSR | `PASS` | API 安全输入、Website AST、双语 SSR 与桌面/375px实际页面 |
| P1-12 | 本机环境与冻结项回归 | `PASS` | loopback 443、TLS、noindex、Sitemap 404、冻结指纹均核验 |

`PASS_TEST_ONLY` 仅表示独立测试环境通过，不表示主预览或生产已发布政策。

## 8. 实际测试、检查与构建

| 检查 | 实际结果 |
| --- | --- |
| API 全量，独立真实 PostgreSQL/Redis/MinIO（含 Privacy 迁移/约束/并发） | `346 passed, 1 warning in 126.97s` |
| Website Vitest | `143 passed` |
| Admin Vitest | `50 passed` |
| Ruff | `All checks passed!` |
| Prettier（Admin/Website） | PASS |
| Website/Admin typecheck | PASS；在无端口的最终镜像容器内执行 |
| Website/Admin production build | PASS；按主预览安全 Compose 覆盖构建 |
| `git diff --check` | PASS；仅 Git 的 LF→CRLF 工作区提示 |
| 主预览 Admin 保存→fresh GET→刷新→重开 | PASS |
| 独立浏览器桌面/375px、A→B stale/重新确认及加固后 C 生命周期 | PASS |

构建存在 Nuxt 依赖弃用/插件耗时提示，但没有构建失败。Ruff 的第一次直接调用因本机无 `uv`，第二次 `python -m ruff` 因全局 Python 未安装模块，第三次使用已有项目 ruff 时默认缓存目录权限不足；最终改用私有可写 cache 后 lint 通过。附加的全 API 树 `ruff format --check` 会要求重排 83 个既有文件，因此未做越界的全量机械改写，也没有把该附加检查写成 PASS。一次 `compileall` 因容器生成的 `__pycache__` 本机 ACL 被阻止，标记为 `BLOCKED`，没有写成 PASS；相关 Python 文件另用 AST 解析且最终 Pytest/Ruff 均通过。

宿主直接执行 Nuxt typecheck 时，Docker 生成的 `.nuxt` ACL 导致 EPERM；改为在无端口、与最终源码一致的 Website/Admin 镜像容器内运行后两端均通过。第一次纳入第二轮修复的 API 全量测试为 `345 passed, 1 failed`，唯一失败是新增静态迁移测试用了错误的容器路径；修正测试自身后，在全新的 r5 隔离依赖栈得到最终 `346 passed`。更早的加固测试曾因 PostgreSQL 用例提交测试事务污染共用 fixture 而得到 `339 passed, 2 failed`；这些失败均未计为 PASS。

API PostgreSQL migration 的早期验证还发现 asyncpg 不接受在单个 prepared statement 中合并 `CREATE FUNCTION` 与 `CREATE TRIGGER`；迁移已拆为独立语句后重新从空库验证通过。两次测试中的错误 MinIO 覆盖分别产生 `InvalidAccessKeyId` 和 `SignatureDoesNotMatch`，均保留为失败历史，不计入最终 346 项 PASS。

第二轮独立只读复核确认六项源码修复均已落入当前工作树，未发现新的 P1 代码缺陷；其唯一 P2 意见是需要可独立核验的 populated downgrade 实际执行证据。上述 r5 PostgreSQL `0013 → 0011 → 0013` 回读、当前代码指纹和命令结果已加入本次脱敏证据包，因此该验证缺口在交付前闭环。

## 9. 冻结项回读

本轮完成后与本地域名预览启动时的私有表指纹比较：

- Company、Company 翻译、产品、产品翻译、分类、媒体、8 条 SEO、型号、关系、规格组、7 个规格定义及其翻译全部 `UNCHANGED`。
- 只有 Privacy 所需的 `site_pages`、`site_page_translations`、`content_publications` 和 `content_routes` 发生预期增量。
- `product_spec_values` 总数仍为 0，P01/P02/P03 分别为 `0/0/0`。
- 旧试点 `nitrided-barrel` 双语仍为 Translation `draft`、Publication `draft`，Route `inactive/noindex`。
- F05 英文空缺、COPY-V1 16 字段、8 组 SEO、名称、slug、分类、主图/图注、型号和关系均未改变。

## 10. 交付、限制与后续门

交付：

- 本报告；
- `docs/content/privacy-p1-admin-guide.md`；
- 脱敏检查 JSON、真实截图、manifest 与 SHA256SUMS；
- `Junhui-Privacy-P1-Content-Version-Evidence-20260908T155947+0800.zip`。

没有执行：生产/腾讯云连接、DNS 修改、Privacy Review/Publish（主预览）、真实 RFQ、附件上传、邮件、数据删除、保留计时器、请求台账、Gmail/SMTP、NAS 备份、Analytics、commit、push 或 merge。

剩余限制和决策：

- 正式政策正文、保留/删除规则、请求流程、生产/备份地域及 Cookie/服务提供方清单仍待负责人集中批准；`F-R1-001` 继续开放。
- 当前 RFQ 没有通用幂等键；同一个仍有效的 context 被重复发送时，可能形成多条完整 RFQ。事务可防止半条记录，但不能宣称请求幂等。
- 长时间停留在 Admin 后 access cookie 过期时，当前通用写请求不会自动重放；刷新页面可使用 refresh cookie 恢复。该现象未影响数据正确性，但可作为后续通用 Admin 会话体验改进。
- 本轮所有隔离测试 Compose 容器均已停止并保留卷，未删除数据卷；主预览保持运行。

下一步必须取得正式隐私正文和流程的单独批准，才能在主预览执行 Review/Publish 与受保护前台复验。
