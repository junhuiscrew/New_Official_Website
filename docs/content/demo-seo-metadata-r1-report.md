# Demo 前台 SEO 元数据收尾 R1 实施报告

## 1. 结论

本轮已在唯一业务写入目标 `junhui-demo-r2` 完成 About、Contact、RFQ 中英文共 6 页的限定 SEO 收尾。6 页的 title、description、canonical、双语 reciprocal hreflang 与 x-default 均已通过后台/管理 API 回读、公开 API、首次 SSR HTML 和真实浏览器复验。

本轮只关闭上述 Demo 元数据缺口，不代表全站 SEO/GEO、Phase 3.7 或生产上线通过。未执行 Git commit、push、merge、生产部署、公共 DNS 修改、Privacy 发布、RFQ 提交、附件上传或邮件发送。

## 2. 实际目标与版本

- Run ID：`20260910T234537+0800`
- 工作区：`phase-3.7`
- 基线 HEAD：`2fbcc7d84865d9e98092c3e6e78751f2337e5f0d`
- `origin/phase-3.7`：`2fbcc7d84865d9e98092c3e6e78751f2337e5f0d`
- 工作树：保留既有未提交文件；本轮代码和报告仍未提交
- Demo 网站：`https://demo.junhuiscrewbarrel.com/`
- Demo 后台：`https://admin-demo.junhuiscrewbarrel.com/`
- 数据库迁移：`20260910_0016`
- 最终本地镜像：
  - API：`sha256:6acfee40ae898006dbb5ee5f46ab7d86a5c1cbead6f519b9b9407230a7888cd3`
  - Admin：`sha256:3f4aa281a681f6919fb88a9213dcccb2a5953213631929b0d980c563dbd9e8a7`
  - Website：`sha256:ca959b3b2a8124b54879bdfa5c2257e346bbb9ca59323486d5067e644e8f1a44`

## 3. 实施内容

### 3.1 About

About 继续使用现有 Company Profile 的真实页面身份、正文和 SEO owner。本轮只为 Company SeoDocument 的 `zh-CN`、`en` 补充 description；title、canonical、hreflang、robots、公司正文和发布状态未被重存或改变。

后台公司资料页新增按语言维护 About SEO 摘要的中文入口。保存时沿用 `seo.read/update`、认证、CSRF、Revision/Audit，完整保留 SeoDocument 的其他字段；保存后立即 fresh GET 比对。权限区使用客户端安全会话边界，避免 SSR 匿名态与已登录态产生 hydration 结构不一致。

### 3.2 Contact 与 RFQ

在既有 SitePage/SeoDocument/Translation/Publication/ContentRoute 体系中增加两个严格固定身份：

- `contact`：`/zh-cn/contact/`、`/en/contact/`
- `request-a-quote`：`/zh-cn/request-a-quote/`、`/en/request-a-quote/`

新增迁移只扩展 `site_pages.system_key` 约束与中文字段注释，不插入业务内容；页面身份由带权限、CSRF 和 Audit 的幂等初始化接口创建。Admin 通过固定 key 打开中文表单，用户不填写 UUID 或 JSON。

公开元数据 API 仅允许 Contact/RFQ 严格白名单；只有页面启用、双语已发布、Route active、SEO 完整且 robots/规范 URL 符合固定策略时才返回。canonical 与 hreflang 由服务端正式源站和固定 Route 生成，不读取请求 Host 或查询参数。

### 3.3 前端接线

Contact 和 RFQ 的 Nuxt 首次 SSR 现在从固定 SitePage 公开 API 读取 SEO。页面正文、RFQ 来源参数和 Privacy 上下文仍沿用原逻辑。RFQ 的 `source_type`、`source_slug`、`privacy_context_token` 经实测均未进入 canonical 或 hreflang。

## 4. 实际内容保存与生命周期

- 初次更新：6 项；初次 no-op：0 项
- SitePage 初始化：2 个
- 双语审核：4 次
- 双语发布到受保护 Demo 预览：4 次
- 后台 UI 相同值复验：4 次 no-op；Revision/Audit 未增加
- 新增 ContentRevision：6 条，均为 `seo_document`，revision_no 均为 1
- 新增 Audit：29 条
  - Company SEO upsert：2
  - SitePage initialize：2
  - SitePage SEO upsert：4
  - Translation review：4
  - Publication status change：8
  - Route change：8
  - 正常管理员登录：1

未重新审核或发布 Company、产品、分类、Privacy 或旧试点。Contact/RFQ 的内部 Route 已达到页面发布资格；其业务 SEO robots 仍分别为 `noindex, nofollow` 与 `noindex, follow`，外层网关继续统一返回 `X-Robots-Tag: noindex, nofollow`。

## 5. 六页实际回读

完整修改前/后值见 `demo-seo-six-pages-readback.json`。摘要如下：

| 页面 | 本轮缺口 | 结果 |
| --- | --- | --- |
| About zh-CN | description | 已补充；原 title/canonical/hreflang/robots 保持 |
| About en | description | 已补充；原 title/canonical/hreflang/robots 保持 |
| Contact zh-CN | canonical、hreflang | 已通过 SitePage 接通；原 title/description 保持 |
| Contact en | canonical、hreflang | 已通过 SitePage 接通；原 title/description 保持 |
| RFQ zh-CN | description、canonical、hreflang | 已通过 SitePage 接通；原 title/robots 保持 |
| RFQ en | description、canonical、hreflang | 已通过 SitePage 接通；原 title/robots 保持 |

每页首次 SSR 均只有 1 个 title、1 个 description、1 个 robots、1 个 canonical，以及各 1 个 `zh-CN`、`en`、`x-default` alternate。6 个 SSR 响应均为 200，HTML `lang` 与页面语言一致。

## 6. 真实浏览器验收

使用 Playwright CLI 0.1.14 与本机 Edge：

- 新建不注入 HTTP Basic 凭据的前台会话，1440×900 打开三类双语页面；About、Contact、RFQ 均实际完成 `zh → en → zh`。
- 375×812 打开三类页面，均从移动菜单实际完成 `zh → en`；3 页均无横向溢出。
- 所有切换后的浏览器 origin 均为 `https://demo.junhuiscrewbarrel.com`，未访问 canonical 正式源站。
- 首页、Products、演示产品详情只读回归均为 200；正文、图片与原有 Head 正常。
- RFQ 提交按钮仍禁用，页面显示暂不可提交；RFQ 记录数始终为 12。
- 前台 console error 0、page error 0；后台最终复验 console error 0、page error 0。
- 后台 Contact/RFQ 完成中文和英语相同值保存、fresh GET、刷新重开；About 双语完成刷新重开，英语切换未清空中文。

## 7. 安全与冻结核对

保存前后数据库冻结值：

- RFQ：12 → 12
- Privacy current：0 → 0
- Product：9 → 9
- Product spec values：45 → 45
- Company SeoDocument：0 → 2（仅本轮 About 双语 description）
- SitePage keys：`home, products` → `contact, home, products, request-a-quote`

运行保护：

- HTTPS 有效，未跳过 TLS 校验
- 宿主 443 仅监听 `127.0.0.1:443`
- API/Admin/Website/PostgreSQL/Redis/MinIO 均无新增宿主直出端口
- 前台无 Nginx Basic 弹窗；匿名后台 API 实测 401
- 全站网关 `noindex, nofollow` 与 `no-store` 保持
- `/sitemap.xml` 实测 404
- Privacy current 仍为空；RFQ 政策门禁与提交禁用保持

本轮迁移前私有数据库快照保存在 `artifacts/demo-seo-metadata-r1-20260910T234537+0800/private-demo-db-before.dump`，SHA256 为 `b6bd72083bbc11cb2490059da297949bc12b3e5f2f8c5d336bec2c282d8fb026`。该快照不进入 Git 或分享证据包。

## 8. 测试与构建

| 检查 | 实际结果 |
| --- | --- |
| API 固定页、公开读取、权限、迁移链及 Sitemap 专项 | PASS，34 tests |
| 独立真实 PostgreSQL 并发初始化 | PASS，1 test |
| 独立 PostgreSQL 全迁移至 0016 | PASS |
| 独立 PostgreSQL 0016 → 0015 → 0016 | PASS |
| Website Vitest | PASS，16 files / 155 tests |
| Admin Vitest | PASS，14 files / 88 tests |
| Website typecheck | PASS |
| Admin typecheck | PASS |
| Ruff 0.12.11（本轮 Python 文件） | PASS |
| Prettier（本轮项目前端文件） | PASS |
| API/Admin/Website Docker build | PASS |
| 真实浏览器 1440/375 | PASS |

补充说明：首次直接在常驻 runtime API 容器执行 pytest 时发现生产镜像不包含 pytest，随后改用项目既有、锁定依赖的测试镜像并只读挂载当前源码，34 项通过。两端 typecheck 首次受沙箱对 `.nuxt` 的写权限限制，使用同一项目环境授权写入生成类型后通过。未运行与本轮无关的 API 全量套件或 Lighthouse，状态为 `NOT_RUN`，未写成 PASS。

## 9. 交付与后续状态

- 报告：`docs/content/demo-seo-metadata-r1-report.md`
- 六页完整回读：`docs/content/demo-seo-six-pages-readback.json`
- 脱敏证据包：`Junhui-Demo-SEO-Metadata-R1-Evidence-20260910T234537+0800.zip`

Demo 继续运行，等待复验。本轮未执行 Git commit/push/merge，也未将任何敏感账号、Cookie、Token、数据库凭据或私有备份加入证据包。
