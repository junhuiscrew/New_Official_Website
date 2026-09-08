# ADR: Privacy P1 公开状态与 RFQ 版本绑定

- 状态：接受
- 日期：2026-09-08

## 决策

Privacy 使用现有 `SitePage` 作为唯一稳定技术身份。`ContentRoute` 归属该稳定页面，以继续满足全站路径唯一性；Privacy 路由发布后保持 `active=true`、`indexable=false`。

政策正文保存在 `PrivacyNoticeVersion` 与 `PrivacyNoticeVersionTranslation`。每个不可变版本继续复用现有 `TranslationStatus`、`ContentPublication` 和 `ContentRevision`，其 owner 为 `privacy_notice_version`。所有管理端变更继续写入现有 `AuditLog`。因此不新增第二套翻译、发布、修订或审计状态机。

`PrivacyPageState.current_version_id` 是唯一公开指针。公开读取先解析稳定页面和该指针，再同时验证双语正文、人工审核后的发布状态、服务端重算哈希、生效时间及稳定路由。历史版本即使仍为 published，也不能绕过 current 指针公开。

草稿正文可修改；任一语言进入 `human_reviewed` 或版本进入 published/current/RFQ 引用后，服务和 PostgreSQL 触发器共同禁止覆盖。修改这类版本必须创建服务端编号的新草稿，可从当前版本克隆。外键使用 `RESTRICT` 保存历史政策和 RFQ 证据。

审核请求必须携带管理端实际回读的版本标签、整版 revision 和目标语言内容 hash；发布请求还必须携带双语内容 hash。服务端在稳定页面、状态与目标版本行锁内重新比对这些观察值，任一不一致都以 409 拒绝，避免操作者确认 A 后实际审核或发布已变化的 B。数据库触发器进一步约束合法状态转换与审核人/发布时间组合，防止绕过服务层写出伪造生命周期。

## 哈希与内容安全

算法标识为 `sha256-nfc-json-v1`：标题和 Markdown 做 Unicode NFC；标题去首尾空白；正文统一 LF、移除每行尾随空格/制表符和首尾空行；随后以 UTF-8、键排序、无额外空白的 JSON `{body_markdown,title}` 计算 SHA-256 十六进制摘要。

后端只保存并返回规范化 Markdown，不产生或声明可信 HTML。所有 Markdown 图片（包括 inline/reference image）均被拒绝；原始 HTML 标签也被拒绝。普通链接只支持简单的 `http`、`https`、单一邮箱 `mailto` 和同站相对目标；危险协议、协议相对地址、`mailto` 查询参数/多收件人及无法可靠解析的复杂 Markdown 链接一律拒绝。公开 DTO 标记 `content_format=markdown`、`rendering_trust=untrusted`，消费方仍须使用安全 Markdown 渲染器。

Privacy 公开 DTO 固定为 `index=false, follow=true`，公开政策和 context API 的成功/失败响应均显式返回 `X-Robots-Tag: noindex, follow`。在没有可靠 purge 机制前，current 政策响应使用 `Cache-Control: no-cache, max-age=0, must-revalidate`；短期 consent context 继续使用 `no-store`。

## RFQ 一致性

短期 JWT 使用现有服务端签名密钥及专用 audience/type，绑定公开版本标签、语言、内容哈希、规范 URL、签发和过期时间，不包含内部 UUID。RFQ 创建重新验证签名、期限、当前指针和完整公开门禁，并按“稳定页面 → PrivacyPageState → 版本/生命周期”的顺序加 PostgreSQL 行锁；发布切换采用相同顺序。这样 A→B 竞争只会记录已确认的 A，或在 B 先切换时拒绝 A 为 stale。

新 RFQ 的 `preferred_language` 必须为 `zh-CN` 或 `en`，且必须与 token locale 相同；数据库 nullable 只用于历史 legacy 兼容。context TTL 在配置层限制为 1–60 分钟。SSR 后首次申请 context 若遇到 A→B 切换，客户端最多执行一次重新读取和重试，并撤销旧版本勾选。

RFQ 的六项版本证据字段必须全空或全有。既有 RFQ 保持全空 legacy 状态，不回填、不推断同意内容。

当前没有通用幂等键：同一 token 重复请求可能产生多条完整 RFQ。现有事务边界保证失败时不会产生半条 RFQ 或孤立 RFQItem，但不把这一点伪称为请求幂等；通用 RFQ 幂等能力留待后续独立设计。

## 排除项

Privacy 不加入 Sitemap、Search、GEO 或营销集合；也不放宽 Products/Catalog 的固定 allowlist。初始化和迁移不写政策正文、生效日期、审核用户或发布版本。
