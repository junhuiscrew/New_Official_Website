# Phase 3.7.3 Products SitePage SEO 实施报告

## 1. 结论

- 执行结果：`IMPLEMENTED_VERIFIED_PENDING_REVIEW`。
- F-R1-004：在本地受保护预览范围内已具备关闭证据；Products 两组与原有六组 SEO 已完成 `8/8` 实际保存、API 回读和首次 SSR 核验。
- F-R1-001：`OPEN`。本轮未发布 Privacy，也未实施 NAS 备份、保留或删除制度。
- 本轮不是 Phase 3.7 整体完成声明，也不是生产上线许可。
- 未执行 Git commit、push、merge、部署、DNS、搜索平台或 Analytics 操作。

## 2. 实际目标与代码状态

- 项目：`junhuiscrew/New_Official_Website`
- 工作区：`D:\Python_Project\New_Official_Website\junhui-global-website\.worktrees\phase-3.6`
- 分支：`phase-3.7`
- 实际 HEAD：`91cea435fcf4f5fb9faeb82106e9ad8b3c9b64be`
- 实施时工作区：dirty；保留了此前提交和全部未提交工作。
- tracked diff 哈希：`428fc34d162d08179e8c092f1e9f650b6ab8d6df`。新增未跟踪实现文件另由证据包 SHA256 清单覆盖。
- 目标实例：`phase37-local-https`，Docker Compose project `junhui-phase37-pilot`。
- 迁移前版本：`20260905_0010`；迁移后版本：`20260907_0011`。
- 更新后 API 镜像：`sha256:c28f232791c7e0f39dc156b4f2762bfb9ac19055fe09e305e81dfcbcd37a21b8`。
- 更新后 Admin 镜像：`sha256:d35c3a6639b06f120575e977e72d558ecad6c32ecac63843d65e5b61d570f89c`。
- API 实际启动命令：`uvicorn app.main:app --host 0.0.0.0 --port 8000`；没有执行 Seed。

## 3. 目标与保护核验

- Nginx 是唯一映射宿主机端口的服务：`443:443`。
- API、Admin、Website、PostgreSQL、Redis、MinIO 和 Worker 仅暴露容器内部端口。
- Website、Admin、API 未认证访问均返回 `401`。
- 认证后的中文 Products 页面返回 `200`。
- Products 首次 SSR 响应头保留 `X-Robots-Tag: noindex, nofollow`。
- 常驻预览 `/sitemap.xml` 返回 `404`。
- HTTPS、Basic Auth、全站 noindex、Sitemap 关闭和端口隔离均保持。

## 4. 私有备份与冲突检查

在迁移和业务写入前保存了两组私有安全快照。最新即时备份如下：

- 数据库转储：489,564 bytes。
- 数据库转储 SHA-256：`D6181E89FFB2708B20D198B73B8FF0BC13A67A763FD1A0C9232A0E1F8E6CA4E3`。
- 迁移前状态 SHA-256：`55A42558E071EAC831FCA9441786A2654B2B975AA44A3EA8C9EB39B6063DD7A1`。
- 迁移前 Products 目标路由占用数：`0`。
- 迁移前原 SEO 记录：`6` 组。
- 迁移前 Batch01 产品：`3` 款；规格定义：`7` 个。

未发现错误目标、目标路由冲突或人工修改冲突，因此继续实施。原始转储、原始状态和凭据保留在本地私有目录，不进入共享证据包或 Git。

## 5. 工程实施

### 5.1 SitePage 数据模型与迁移

- 新增固定页面 `SitePage` 与 `SitePageTranslation`，固定 `system_key=products`。
- 使用真实 UUID、现有 Locale、TranslationStatus、ContentPublication、ContentRoute、SeoDocument、Revision 和 Audit 体系。
- 迁移 `20260907_0011_site_pages.py` 只创建/删除新表，不夹带业务数据。
- 迁移在独立真实 PostgreSQL 完成空库升级、降级到 `0010`、再次升级到 `0011` 和并发初始化/失败重试验证。
- 原隔离库升级后、初始化前，新表计数为 `0/0`。

### 5.2 固定键 CMS/API

新增固定键接口：

- `POST /api/v1/discovery/site-pages/products/initialize`
- `GET /api/v1/discovery/site-pages/products`
- `PUT/PATCH /api/v1/discovery/site-pages/products/seo/{locale_code}`
- `POST /api/v1/discovery/site-pages/products/translations/{locale_code}/review`
- `POST /api/v1/discovery/site-pages/products/publications/{locale_code}/publish`

实现约束：

- 初始化使用 PostgreSQL advisory transaction lock、页面行锁和双语生命周期行锁，重复调用保持幂等。
- 路由已被占用、语言缺失、固定名称/路径/生命周期不一致时停止，不覆盖现有记录。
- 通用 SEO 写接口拒绝 `owner_type=site_page`，防止绕过固定 key。
- 专用 SitePage schema 拒绝未知字段，仅允许本轮 SEO 字段。
- 权限复用 `seo.read/update`；Review/Publish 继续要求既有双权限组合，未扩大 SEO 编辑者发布权限。
- 相同 SEO 内容返回成功但不新增 Revision/Audit。

### 5.3 Admin 入口

- 后台入口：`https://admin.junhui.test/site-pages/products`
- 导航仅对拥有 `seo.read` 的用户显示 `Products SEO`。
- 页面固定使用 `products` key，不要求用户填写 UUID。
- 双语表单仅编辑 SEO title 与 meta description；生命周期只读显示。
- 保存后会再次 GET 实际值并逐字比较，只有一致时才显示成功。
- 已实际完成中文保存、英文保存、刷新、重新打开并回读。
- `seo.read` 但无 `seo.update` 的账号只能查看，保存控件禁用。

观察项：Admin 首次加载记录一条 Vue hydration mismatch。该模式来自既有 `currentUser` 客户端恢复式导航壳；本轮保存、刷新和重新打开均正常，不影响本次验收。该项未在本轮扩大范围修复，也未记为 PASS。

### 5.4 公开 Products 与 Sitemap

- Products 总列表公开 API 只在 SitePage enabled、翻译/发布/路由/SEO 全部合格时读取新 SeoDocument。
- 已登记 SitePage 若处于 disabled、draft、noindex、缺翻译、非 canonical 或不活动，旧合成分支不会使相同 URL 重新进入公开候选。
- 查询第二阶段再次校验 SitePage key/status，避免并发禁用时泄漏 SEO。
- SitePage 尚不存在时保留旧合成聚合页兼容；存在后由真实 Route 接管。
- Sitemap 对 URL 去重；独立测试配置验证候选与 XML，常驻预览端点仍关闭。
- 分类 SEO、产品详情、分页和筛选逻辑保持不变；Website 未硬编码批准文案。

## 6. 已批准 Products SEO 实际应用

批准引用：`SEO-CANDIDATE-R1-V1`，授权 `JH-P37-PRODUCTS-SITEPAGE-20260907`。

| 页面 | 语言 | title | description | 结果 |
| --- | --- | --- | --- | --- |
| Products | zh-CN | 骏辉螺杆与机筒产品 | 查看骏辉氮化螺杆、骏辉氮化机筒和骏辉电镀螺杆，并通过询价入口提交设备信息、图纸或需求说明。 | MATCH |
| Products | en | Junhui Screw and Barrel Products | Explore Junhui Nitrided Screw, Junhui Nitrided Barrel and Junhui Electroplated Screw, then use the RFQ entry point to share machine information, drawings or requirements. | MATCH |

批准内容哈希：

- zh-CN title：`7cb6468bf8bf2935f8c8ec3cf5c7d115eb8151af09b3103c3d7c32f58c5b73b6`
- zh-CN description：`de68a6352ea3c51ef3e863ae9e12d21830a7c20ed843c57461b2de91a5fc03b2`
- en title：`55f40ceaa8bfb08b6f7358e21e4c8fb18414400bb965684236b9caebe3bf744f`
- en description：`fde33d70bcbdb6dda23989777cb4ff035d79298d632dcd2ffd0e04285dcf0242`

两次相同值重放前后计数均为：SEO Revision `2`（每语言 revision 1），SitePage Audit `3`，证明第二次保存为 no-op。

## 7. 生命周期与 Audit

仅对新 Products SitePage 执行了授权范围内的正常 CMS 生命周期：

- zh-CN Review：`200`
- en Review：`200`
- zh-CN Publish：`200`
- en Publish：`200`

最终状态：

| 语言 | TranslationStatus | Publication | Route | active | indexable |
| --- | --- | --- | --- | --- | --- |
| zh-CN | published | published | `/zh-cn/products/` | true | true |
| en | published | published | `/en/products/` | true | true |

Audit 摘要：

- `site_page.initialize`：1
- `seo.upsert`：2
- `translation.review`：2
- `publication.status_change`：4

没有重新审核或发布 Company、分类、三款产品、旧试点或 Privacy。

## 8. 8/8 SEO 回读

真实 PostgreSQL 回读得到 8 条，页面别名为 `ABOUT / PRODUCTS / SCREWS / BARRELS`，每页 `zh-CN / en` 两种语言。所有记录均为：

- TranslationStatus：published
- Publication：published
- Route：active=true、indexable=true
- title/description：Products 两组与批准包逐字一致；原 About/screws/barrels 六组与迁移前快照逐字一致。

完整脱敏记录见证据包 `api/seo-eight-readback.json`，内部 UUID 已省略并使用一致别名。

## 9. 首次 SSR、公开 API 与浏览器验证

### 9.1 首次 SSR

| 本地页面 | HTTP | title/description | canonical | hreflang | 外层 robots |
| --- | --- | --- | --- | --- | --- |
| `https://junhui.test/zh-cn/products/` | 200 | MATCH | `https://junhuiscrewbarrel.com/zh-cn/products/` | zh-CN/en/x-default | noindex, nofollow |
| `https://junhui.test/en/products/` | 200 | MATCH | `https://junhuiscrewbarrel.com/en/products/` | zh-CN/en/x-default | noindex, nofollow |

公开 API 两种语言均返回批准 title/description、正式 canonical/hreflang、业务 robots `index, follow` 和 3 款产品。业务索引资格与外层本地保护分别记录，未将本地 noindex 误判为 SEO 缺陷。

### 9.2 真实浏览器

- Edge/Playwright，桌面 `1440×1000`：中文 Products 打开，实际点击语言菜单后到达本地英文 Products。
- Edge/Playwright，移动 `375×812`：英文 Products 打开，实际点击移动菜单和语言菜单后到达本地中文 Products。
- 中英文 title 分别为批准值；每页显示 3 款真实产品。
- 前台浏览器控制台错误检查结果：0 errors、0 warnings。
- 后台完成中文/英文实际保存、刷新和重新打开；截图不包含密码、Cookie、Token 或内部 UUID。

## 10. 冻结项核验

迁移前后私有状态逐段比较：

- `locales`：相同
- `company_copy_v1`：相同
- `approved_seo_six`：相同
- `batch01_products`：相同
- `all_product_lifecycle`：相同
- `specification_definitions`：相同

因此 COPY-V1 的 16 个正文字段、名称、分类、slug、图片/图注、七个规格定义、F05 英文空缺、型号、关系和旧试点状态均未改。三款产品参数值仍为 `0/0/0`。

迁移后私有状态 SHA-256：`73FB38EF863547681E379D7508627D9E7C9121AF2676924C12A5224F581C3F06`。该原始状态含内部标识，仅保留本地，不进入共享包。

## 11. 实际检查与结果

| 检查 | 实际结果 |
| --- | --- |
| API 全量 pytest | PASS：294 passed，12 skipped，1 warning，107.34s |
| 独立真实 PostgreSQL 迁移（空库 upgrade/downgrade/re-upgrade） | PASS |
| 真实 PostgreSQL 并发初始化与失败重试专项 | PASS：1 passed，9 deselected，2.12s |
| 最新代码 Sitemap 候选/XML 专项 | PASS：12 passed，7.08s |
| Ruff `check app tests` | PASS |
| Ruff `format --check app tests` | NOT_PASS：发现 64 个既有文件格式差异；未将其写为 PASS，未做无关全库格式化 |
| Website Vitest | PASS：121 passed，11 files |
| Admin Vitest | PASS：30 passed，7 files |
| 前端 Prettier `format:check` | PASS |
| Website/Admin typecheck | PASS |
| Website build | PASS |
| Admin build / phase37 Admin image build | PASS |
| phase37 API runtime build | PASS |
| `git diff --check` | PASS；仅显示既有 Windows CRLF 转换提示 |
| 最终代码审查 | PASS：未发现高或中严重度问题；审查未修改文件 |

跳过的 API 测试为已有外部服务/标记测试；关键 SitePage PostgreSQL 测试另在真实 PostgreSQL 中执行并通过。未复制旧测试数量。

## 12. 交付与后续

- 本报告：`docs/content/phase3-7-3-products-sitepage-seo-report.md`
- Admin 入口：`https://admin.junhui.test/site-pages/products`
- 中文预览：`https://junhui.test/zh-cn/products/`
- 英文预览：`https://junhui.test/en/products/`
- 证据包：`Junhui-Products-SitePage-SEO-Evidence-20260907T192659+0800.zip`

受保护预览继续运行。下一步仅等待前台/后台复验；不自动提交、推送、合并或生产上线。
