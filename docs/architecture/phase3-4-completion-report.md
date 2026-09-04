# Phase 3.4 完成报告

生成日期：2026-09-04
正式主域名：`https://junhuiscrewbarrel.com`

## 1. Branch / Base SHA / Final SHA

- Branch：`phase-3.4`
- Base SHA：`6a605d9cbc4e46117e4e9bd64fb3546ce823d1f5`
- Phase 3.4 实现 SHA：`3ff2d5979d486d14a816af421be350b8ccdbc070`
- 本报告作为实现后的独立文档提交；分支最新 SHA 以远端 `phase-3.4` 为准。
- 范围仅为 Authority Content + SEO/GEO Delivery Layer，未进入 Phase 3.5、最终 UI、RFQ、Page Builder 或生产部署。

## 2. Migrations

- `20260904_0006_authority_content.py`：新增 Case、Knowledge、FAQ、Author/Expert、translations 与全部显式关系表。
- `20260904_0007_discovery_delivery.py`：新增统一 SEO/GEO 文档、来源引用与 Redirect Manager。
- Alembic 保持 `0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007` 单线历史，当前 head 为 `20260904_0007`。
- 已验证空数据库升级至 latest，以及 `0001 → latest`。

## 3. Case Model

`case_studies` 保存稳定 slug、启停状态、行业/设备/材料等结构化事实及内部客户身份字段；`case_study_translations` 保存 title、summary、problem、analysis、solution、result、engineer comment 等语言正文。客户名称、地址和 Logo 各自具有独立公开许可开关。

## 4. Knowledge Model

新增 `knowledge_categories`、`knowledge_category_translations`、`knowledge_articles`、`knowledge_article_translations`。文章必须引用已核验真实 Author，Reviewer 如存在也必须是真实人物。Seed 幂等创建 `technical-guides`、`material-guides`、`selection-guides`、`troubleshooting`、`comparisons`、`faq`、`industry-knowledge`、`company-news`、`exhibitions` 及中英文名称。

## 5. FAQ

新增 `faqs` 与 `faq_translations`。FAQ 复用 TranslationStatus、Revision、Audit，但按冻结决策不建立独立 ContentPublication 或 ContentRoute；FAQ 只有翻译审核发布后才可作为已发布页面的可见关联内容。

## 6. AuthorExpert

新增 `author_experts` 与 `author_expert_translations`。公开人物资料和 Person/Article Schema 强制 `is_real_person_verified=true`；项目未 Seed 任何虚构专家、默认作者或 AI 人物。

## 7. Relations

建立 17 张显式关系表：Case ↔ Product/Material/Technology/Application/Solution；Article ↔ Product/Material/Technology/Application/Solution/Case/FAQ；FAQ ↔ Product/Material/Solution/Article/Case。关系修改写入包含实际前后值的 Revision 与 Audit，不把事实关系塞回 Rich Text。

## 8. SEO Document

统一 `seo_documents(owner_type, owner_id, locale_id)`，支持 title、description、canonical override、robots、Open Graph 与受控 Schema override。Canonical override 仅允许正式主域 HTTPS；Schema override 递归拒绝 Offer、价格、Review、Rating 等当前事实模型无法证明的字段。

## 9. GEO Document

统一 `geo_documents(owner_type, owner_id, locale_id)`，支持 direct answer、target questions、key facts、evidence、related questions、真实 Reviewer 与复核日期。保存时逐项验证 direct answer/key facts/evidence 必须能在 `visible_source_text` 中找到，杜绝 AI-only 隐藏声明。

## 10. Sources

`source_citations` 可关联 GEO Document 或 Knowledge Article，记录标题、真实 URL、Publisher、发布日期、访问日期、类型与排序。服务拒绝缺少 owner、非 HTTP(S) 以及 example/localhost 等占位来源。

## 11. Redirect

`redirect_rules` 使用精确 `source_host + source_path` 唯一键，支持 301/302/307/308、启停、命中数与最近命中时间。创建前检查 self、loop、chain、duplicate、unsafe target；已支持 `junhuiscrew.com` 旧路径直接迁移到 `junhuiscrewbarrel.com` 最终 canonical。公开 resolver 只做精确匹配并更新命中统计。

## 12. URL Migration Transaction

已发布 URL 变更通过单事务服务执行：锁定现有 canonical、校验新路径、旧 Route 退役、创建新 canonical、创建旧路径 301、写 Revision 与 Audit。任何校验失败由同一数据库事务回滚，不允许 Admin 分步修改。

## 13. Sitemap

`/sitemap.xml` 直接消费统一 `list_indexable_routes()`。只有 Business Entity enabled、Locale enabled、Translation published、Publication published、canonical、active、indexable 且 SEO `robots_index=true` 的路由进入；使用真实 `ContentRoute.updated_at` 作为稳定 lastmod，并输出正式主域绝对 URL。

## 14. Robots

`/robots.txt` 在 development/test/staging 拒绝全站抓取；production 允许公开站点并屏蔽 Admin、Preview、RFQ API，同时声明正式 Sitemap。响应带 `X-Robots-Tag: noindex`，Nginx 已将根级文件正确转发到 API。

## 15. llms.txt

实现可选 `/llms.txt`，由 `LLMS_TXT_ENABLED` 控制，只列出统一索引源中的公开 canonical URL，不输出隐藏事实；响应自身为 noindex。

## 16. Schema

统一生成 Organization、WebSite、Product、Article、Person、BreadcrumbList、WebPage、VideoObject，以及 feature flag 控制的 FAQPage。Schema 只使用 Public DTO 的可见事实；未实现或缺少事实的数据不会被推断，禁止 fake offers、price、review、rating、author。FAQPage 默认关闭且不承诺 Rich Result。

## 17. SEO/GEO Health

新增可解释问题代码，不输出虚假排名分数。SEO 检查 title、description、canonical、noindex/sitemap 冲突与 orphan；GEO 检查 direct answer、key facts、evidence、真实 reviewer、来源、第一方证据和复核时效，并提供受 RBAC 保护的统一 health API。

## 18. RBAC

- Editor：Case/Knowledge/FAQ read/create/update 与 Expert read，不拥有 publish、source manage 或真实人物创建权限。
- Reviewer：Case/Knowledge/FAQ review/publish，并复用 `content.publish` 与 Translation 权限。
- SEO Manager：SEO/GEO update、Source manage、Redirect manage，以及所需 Authority read。
- Sales/Media Manager 不获得 Authority 编辑权限；所有权限由 FastAPI 服务端校验，前端 Guard 不作为安全边界。

## 19. Admin

新增 `/cases`、`/knowledge`、`/faqs`、`/experts` 最小真实 CRUD；包括 translations、显式 relations、客户隐私许可、真实人物核验、Translation/Publication/Route 状态与审核发布动作。通用 `SeoEditor`、`GeoEditor`、`SourceCitationEditor` 复用于四类编辑页，写请求统一使用 Cookie + CSRF。

## 20. Public API

- `GET /api/v1/public/products/{locale}/{category}/{slug}`
- `GET /api/v1/public/case-studies/{locale}/{slug}`
- `GET /api/v1/public/knowledge/{locale}/{category}/{slug}`
- `GET /api/v1/public/redirects/resolve?host=...&path=...`

Product DTO 包含 translation、models、公开 specifications、核心 relations、已发布 Case/FAQ/Knowledge、SEO/GEO、breadcrumb、Schema 与 hreflang。Case DTO 使用隐私白名单。Knowledge DTO 包含真实 author/reviewer、sources、relations、FAQ、SEO/GEO 与 Article Schema。Draft、noindex 或任一发布门槛失败均返回公开 404，且不生成公开 Schema。

## 21. SSR

新增最小 Nuxt SSR 模板：`/{lang}/products/{category}/{slug}`、`/{lang}/case-studies/{slug}`、`/{lang}/knowledge/{category}/{slug}`。模板输出 canonical、reciprocal hreflang/x-default、robots、可见面包屑、可见 GEO/FAQ/来源和安全 JSON-LD；Markdown 暂以纯文本展示，不使用不受控 `v-html`。本阶段未制作最终视觉。

## 22. Privacy

Public Case DTO 从空白白名单构造，未授权的客户名称、地址、Logo ID 不会进入 DTO、SSR、Schema。SEO/GEO 保存服务还会拦截未授权身份值；隐私测试使用唯一秘密标记验证完整序列化结果不可检索。

## 23. Tests

- Ruff：通过，`All checks passed!`。
- 本机 Backend pytest：`145 passed, 7 skipped`；跳过项全部是要求真实 PostgreSQL 的专用测试。
- Phase 3.4 专项最终回归：`29 passed`。
- Website Vitest：`9 passed`。
- Admin Vitest：`18 passed`。
- Website/Admin Typecheck：通过。
- Prettier check：通过，全部匹配。
- Redirect、Sitemap、Schema、GEO、Privacy、RBAC、URL Transaction 均有专项回归覆盖。

## 24. PostgreSQL

Docker test profile 使用 PostgreSQL 17.6 + Redis 8.2，从空库执行 Alembic latest、Seed，再运行完整套件：`151 passed`。覆盖数据库约束、并发 Publication、默认 Locale、Phase 3.3 生命周期及 Phase 3.4 migrations/业务回归。Seed 在运行态再次执行成功，证明幂等。

## 25. Build

Nuxt 4.5.2 / Vue 3.5.42 / TypeScript 5.9.2 的 Website 与 Admin production build 均成功。构建只出现 Node 对依赖包 trailing-slash exports 的弃用警告，不影响产物或运行。

## 26. Docker

`docker compose up -d --build` 成功。PostgreSQL、Redis、MinIO、API、Website、Admin、Nginx 全部为 healthy；API Alembic current 为 `20260904_0007 (head)`。实际 HTTP 验证：live/ready、Website、Admin、Sitemap、Robots、llms.txt 均为 200；Sitemap 为 XML，Robots/llms.txt 为纯文本。

本地地址：Website `http://localhost:3000/zh-cn/`，Admin `http://localhost:3001/login`，API `http://localhost:8010`，同源入口 `http://localhost:8080`。

## 27. Known Issues

- 未 Seed 真实 Author/Expert 和业务内容，这是避免虚构人物/批量真实内容并遵守阶段边界的有意行为；需由获授权人员在 Admin 创建并核验。
- SEO orphan 检查的内部链接计数接口已经冻结，但当前最小 Admin health 聚合暂以 0 提示待建立链接；Phase 3.5 媒体/信任内容关系稳定后再接真实内部链接图。
- Nuxt 构建存在上游依赖的 Node `DEP0155` 弃用警告，无失败或运行影响。
- 未执行生产部署，符合 Phase 3.4 禁止事项。

## 28. Phase 3.5 Recommendation

按冻结路线进入 Company Trust Content + Media：设备、证书、专利、荣誉、视频、下载与 RFQ 基础。继续复用 Master Entity + Translation + Publication + Route + Revision + Audit + RBAC，并让媒体/下载的公开性、授权、来源与 Schema 仍受统一发布和隐私门槛控制；最终首页、Design System 和完整 Page Builder 继续后置。

## 29. `$seo-rank` / `$geo-rank` Conflict Review

已使用两项 Skill 检查 URL、canonical、hreflang、robots、Sitemap、Schema、结构化正文、来源与 GEO 可见性。未发现与正式交接文件的冻结架构冲突；发生选择时始终以本交接为最高约束。

- SEO：一个公开事实源、稳定 canonical、严格索引门槛、真实 lastmod、noindex 不进 Sitemap、无虚假商业/评价 Schema。
- GEO：direct answer/key facts/evidence 必须能在用户可见内容中找到，来源可核验，Reviewer 为真实人物，正文修改后失去已发布权威状态。
- Privacy：客户身份许可优先于任何 SEO/GEO 完整性建议，未授权数据不会进入公开交付链。
- 结论：无冲突，无需偏离 `Master Entity + Translation + Publication + ContentRoute + Revision + Audit + RBAC`。
