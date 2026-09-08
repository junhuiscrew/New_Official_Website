# Privacy P1 后台使用说明

> 状态：`ACCEPTANCE_READY / MAIN_DRAFT_ONLY`  
> 后台入口：`https://admin.junhuiscrewbarrel.com/privacy`  
> 当前主预览只有内部工作稿，没有 current，禁止审核或发布。

## 使用边界

- Privacy 中英文组成同一个政策版本，不能把两种语言分别切换为 current。
- 只有纯 draft 可编辑；任一语言进入人工审核后，该版本正文即不可覆盖。
- 发布只切换唯一 current，不删除旧版本，也不改写已关联 RFQ 的历史证据。
- 后台预览仅供已认证人员查看 draft，不会签发可提交 RFQ 的 policy context。
- 主预览当前版本 `PRIVACY-000001` 标记为 `NOT APPROVED`，双语均为 `draft/draft`，Route inactive/noindex；不要点击审核按钮。

## 权限

| 操作 | Privacy 权限 | 仍需既有权限 |
| --- | --- | --- |
| 查看状态 | `privacy.read` | 无额外写权限 |
| 查看历史 | `privacy.history` | 无额外写权限 |
| 初始化、创建/克隆、保存 | `privacy.edit` | `content.update` 与 `translation.update` |
| 分语言人工审核 | `privacy.review` | `content.review` 与 `translation.review` |
| 发布/切换 current | `privacy.publish` | `content.publish` 与 `translation.publish` |

系统沿用现有角色：super admin/content admin 拥有完整 Privacy 能力；editor/translator 仅可读写 draft；reviewer 可读历史、审核和发布。权限判断始终在服务端执行，Admin 按钮隐藏或禁用不能替代服务端校验。

## 新建和保存 draft

1. 使用 Admin 自身账号登录，打开“Privacy”。
2. 首次使用时点击“初始化 Privacy 页面”。该操作只建立固定页面身份和生命周期骨架，不写正文、不审核、不发布。
3. 点击“创建/克隆草稿”：
   - 没有 current 时创建空白双语版本；
   - 已有 current 时从 current 克隆正文和 hash 到下一编号 draft，但不复制生效时间和审核人。
4. 分别打开“简体中文 · zh-CN”和“English · en”，填写标题及完整 Markdown 正文。
5. 需要拟定生效时间时可填写；未获批准的工作稿应保持为空。
6. 点击“保存双语草稿”。成功提示必须显示“已通过 fresh GET 确认实际值”。
7. 刷新页面，并离开后重新打开 `/privacy`；再次核对标题、正文、revision、双语状态和 Route。

保存使用整版乐观锁。审核必须同时提交当前页面实际显示的版本标签、revision 和目标语言正文 hash；发布还必须提交双语精确 hash。若服务器状态已变化，旧页面的保存、审核或发布都会返回 409；后台随后刷新实际状态，操作者必须重新核对并再次确认，不能沿用旧确认覆盖。

## Markdown 规则

允许普通段落、标题、列表、引用、强调、代码和简单安全链接。以下内容会被服务端拒绝：

- 原始 HTML；
- 任意 Markdown 图片或引用式图片；
- `javascript:` 等危险协议；
- `//host/path` 协议相对链接；
- 带空白、嵌套括号或无法可靠解析的复杂链接。

后台和前台都按不可信 Markdown 处理，不使用 `v-html`。保存后的 hash 由服务端按 `sha256-nfc-json-v1` 计算，不能由浏览器自行声称。

## 审核、发布和新版本

只有获得正文批准和相应权限后才能执行：

1. 先核对双语正文、服务端 hash、拟定生效时间和 Route。
2. 分别点击“人工审核 zh-CN”和“人工审核 en”，每次都确认真实操作者。
3. 两种语言都必须达到 `human_reviewed/review`，发布按钮才可用。
4. 再次独立确认“发布并切换 current”。系统在事务内重算双语 hash、检查生效时间和公开资格，然后切换 current、更新 Route 并写 Revision/Audit。
5. 发布后该版本只读。需要改字时点击“创建/克隆草稿”，编辑新版本并重新走完整审核流程。

不要直接 SQL 改状态，不伪造审核人、发布时间或历史政策同意。已经发布的旧版本仍保留在历史列表中，但公开页面只读取 current。

## 公开页面与 RFQ

- 合格 current 的 `/zh-cn/privacy/` 和 `/en/privacy/` 可返回 200，但业务 robots 始终为 `noindex,follow`，且不会进入 Sitemap、Search 或 GEO。
- 公开政策 JSON 与短时 context API 的成功、失败响应也显式返回 `X-Robots-Tag: noindex, follow`；政策响应强制重验证，context 不得缓存。
- 页面未启用、无 current、双语不完整、未审核、未发布、未生效或 Route inactive 时，公开 Privacy 返回 404。
- RFQ 只有取得当前语言、当前版本的短时 context 后才允许主动勾选和提交。
- 新 RFQ 必须显式提交 `zh-CN` 或 `en`，并与 context 语言一致；数据库允许 null 只用于兼容旧 legacy 记录。
- context TTL 只允许配置为 1–60 分钟，默认 10 分钟。首次 SSR 后若发生 A→B 切换，前端只自动恢复一次并撤销 A 的勾选，用户仍须对 B 再次主动确认。
- 政策切换、context 过期/伪造/错语言时，提交不会创建询盘；页面保留字段和文件选择，取消旧同意，并刷新到最新版本要求重新确认。
- 保存版本关联只能证明用户在提交时主动确认了该版本，不能表述为证明用户读完了全部正文。

## 常见状态和处理

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 公开 Privacy 404 | 没有完整合格 current | 不要造空壳 200；完成正式批准后再审核发布 |
| RFQ 显示等待发布 | 没有合格公开政策 | 保留表单入口，禁止正式提交 |
| 保存返回 409 | revision/current/draft 已变化 | 刷新后人工比较，不强制覆盖 |
| 审核按钮不可用 | 缺正文、权限或版本已锁定 | 核对双语 draft 与服务端权限 |
| 发布按钮不可用 | 双语未全部人工审核或生效信息不合格 | 补齐批准流程，不直接改数据库 |
| 提交提示政策变化 | A context 已过期或 current 已切换到 B | 查看 B、重新主动勾选后提交 |
| 长时间停留后台后写请求 401 | access cookie 到期 | 刷新页面使用既有 refresh cookie 恢复；不要绕过登录 |

## 当前主预览交接状态

- Admin 已实际完成保存、fresh GET、刷新和重新打开。
- current：空。
- draft：`PRIVACY-000001`，revision 3，生效时间为空。
- zh-CN：1339 字符，hash `381b3cd2cb9aaf88c907b8daf88e1ae2cb75ca83c529c4f05ffbbc7a89cabd62`。
- en：2810 字符，hash `dde07b4e898601b44ce35ea1a39118fa088841d1c4337e3f6535956ce7d60f9e`。
- 双语 Translation/Publication 均为 draft，Route 均 inactive/noindex。
- 主库 RFQ 为 0，公开 Privacy 为 404，RFQ 提交禁用。

正式政策和流程获批前，只能继续编辑此私有 draft；不得 Review、Publish 或将其解释为已生效制度。
