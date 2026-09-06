# Phase 3.7.1 资料盘点与只读预检报告

## 1. 结论与状态

- 子阶段：Phase 3.7.1 — 资料盘点与只读预检
- 执行日期：2026-09-06（Asia/Shanghai）
- 状态：`PREPARATION_COMPLETE`
- 输入状态：`WAITING_FOR_INPUT`
- Phase 3.7 总状态：**未完成，不是 Phase 3.7 PASS**
- 数据写入：未写真实内容数据库，未上传真实素材，未修改 Publication/Route，未发布，未部署
- 下一停止点：等待用户确认具体首批内容、真实来源、公开许可和非生产目标后，才能进入 3.7.2

本轮完成了源码级 CMS 能力核对、指定资料盘点、旧站只读比对、候选产品链规划、重复/slug/Route/来源/许可预检，以及环境和后续验收准备。现有资料可证明“有可整理的图片和旧站参考”，但不足以证明产品参数、经营事实、媒体公开权利或双语内容已经获批。

## 2. 实际基线与工作区

| 项目 | 实际结果 |
|---|---|
| 仓库 | `junhuiscrew/New_Official_Website` |
| 验收基线分支 | `phase-3.6-fix` |
| 核对基线 SHA | `c16385cc57ec4ce1aa66164928be2a2cc30d4473` |
| 本地工作分支 | `phase-3.7` |
| 分支创建点 | 与 `origin/phase-3.6-fix` 同一 SHA |
| 开始时工作区 | clean |
| 远端操作 | 未 push、未 merge、未部署 |
| 历史 migration | 未修改 `0001–0010`；当前数据库版本 `20260905_0010` |

仓库中未找到实体 `AGENTS.md` 文件；本轮仍遵循当前任务上下文注入的 AGENTS 代码、数据库、前端注释和 codebase-memory 规则。通过 codebase-memory 索引与源码交叉核对，当前图谱包含 2,136 个节点、139 条 Route 节点；未依靠旧报告猜测 API。

## 3. 本轮输入边界与资料清单

为避免把本机其他资料误纳入项目，本轮只读取用户明确上传、指定目录或指定网址。真实原件、完整文件清单和审批信息均未复制进公共 Git。

### 3.1 已收到或可读取

| 来源编号 | 来源 | 只读盘点结果 | 当前用途 | 状态 |
|---|---|---|---|---|
| `SRC-INTAKE-PACK-01` | Phase 3.7 交接包 | Handoff、README、空模板、SHA256SUMS 完整；校验和匹配 | 规范与空登记模板 | 可用，但无真实经营资料 |
| `SRC-INTAKE-XLSX-01` | 内容登记工作簿 | 6 个 Sheet；用户字段均为空或默认“待确认/待资料” | 后续私有登记 | `WAITING_FOR_INPUT` |
| `SRC-BRAND-ICON-01` | 用户上传 Logo 图标 | PNG，314×302，RGB，无 Alpha，49,593 bytes | 品牌图参考 | 公开权利与原始透明稿待确认 |
| `SRC-FACTORY-01` | 用户上传工厂图 | JPEG，570×552，RGB，有 EXIF、无 GPS，252,626 bytes | 工厂视觉参考 | 公开权利、拍摄主体和 EXIF 处理待确认 |
| `SRC-BRAND-WORDMARK-01` | 用户上传公司名称 + Logo 图 | PNG，2170×725，RGB，无 Alpha，1,085,182 bytes | 横版品牌图参考 | 棋盘格已烘焙，并非透明图 |
| `SRC-PRODUCT-IMAGES-01` | 用户明确指定的产品图片目录 | 186 个文件，共 31,839,683 bytes；185 JPEG + 1 PNG | 产品图候选池 | 可预检，未获批上传 |
| `SRC-LEGACY-WEB-01` | 用户指定旧官网 | 首页、公司介绍与一个产品详情页可只读访问 | 分类/旧 URL/旧文案线索 | 仅参考，不能作为唯一权威事实源 |

### 3.2 产品图片技术盘点

- 185 张 JPEG 均为 700×700 RGB；另有 1 张 750×322 PNG。
- 186 个文件均可正常解码，无空文件。
- 185 张 JPEG 含 EXIF，未发现 GPS；面向网站的派生副本应移除 EXIF。
- 共 184 个唯一 SHA-256，存在 2 组完全重复内容（4 个文件）。正式登记前要指定保留件，避免重复上传和误建多个产品。
- 与当前开发媒体库 11 条记录进行 SHA-256 只读比对，匹配数为 0。
- 目录和文件名可提供分类线索，但不能证明图片属于一个产品、一个型号或多个角度，也不能证明规格和工艺。
- 抽样图片带有品牌水印；其中包含宣传性文字，进入正式页面前需要确认水印是否保留及其文字是否获准公开。

### 3.3 当前未收到

- 已填写并经负责人核对的 Company / Product / 参数证据 / 素材许可 / 批次与环境登记表；
- 公司成立年份、从业年限、员工范围、厂房面积、产能、出口市场和公开联系方式的现行权威来源；
- 候选产品的正式产品名、型号边界、适用机型、材料、工艺、尺寸、硬度、粗糙度、公差、单位和适用条件的最新版证据；
- Logo 矢量或真正透明的原稿；
- 每张工厂图和产品图的所有权/授权、公开范围、可裁切/转码/去 EXIF/去背景/保留水印决定；
- 可公开证书、专利、荣誉、设备、展会、客户案例和客户许可；
- 真实 Author/Expert 身份、本人公开许可和审核责任；
- 经技术审核的中文内容和经语言审核的英文内容；
- 用户确认的非生产目标环境、数据库、对象存储实例和允许操作范围。

## 4. 旧官网只读预检

旧官网仅作为线索源，不自动继承为新站事实。首页可读取现有产品分类树、公司介绍和旧 URL；旧英文入口指向另一个域名，该域不在本轮迁移范围。

一个旧产品详情页同时出现互相不一致的参数，例如：

- 螺杆直线度出现 `0.02 mm` 与 `0.015 mm`；
- 镀铬硬度出现 `≥950 HV` 与 `≥900 HV`；
- 镀层厚度出现 `0.03–0.05 mm` 与 `0.05–0.10 mm`；
- 双合金硬度出现 `HRC55–62` 与 `HRC56–65`。

因此旧站产品参数 dry-run 判定为 `CONFLICT`。这些值在最新版技术表、适用产品/型号与审核人明确前，不能写入 ProductSpecValue、正文、SEO、GEO 或 Schema。旧站“近 20 年/20 年以上”等动态经营文案同样不得直接迁移。

只读参考页：

- <https://www.junhuiscrew.com/>
- <https://www.junhuiscrew.com/about/company-profile.html>
- <https://www.junhuiscrew.com/product/zhusujiliaotongxilie/danhualiaotong/04-junhuiluogan-danhuajitong-5.html>

`robots.txt` 未被当前读取工具安全解析，`sitemap.xml` 因 XML 读取限制未完成内容核对，均记为 `NOT RUN`，没有据此推断旧站索引状态。

## 5. 当前开发数据与 QA fixture 隔离

当前本地 Compose 数据库不是可直接承接真实试点的干净内容库：

- 29 个 Product 中 28 个 slug 为 `qa36-*`，另 1 个为 `pg-*` 集成样本；
- ProductCategory 2 个，其中 1 个 `qa36-*`、1 个 `pg-*`；
- Material 3 个，其中 2 个 `qa36-*`、1 个 `pg-*`；
- Application、Technology、Solution、Capability、Equipment、Case、Expert 和 Download 的现有记录均为 QA36 样本；
- 2 个 KnowledgeArticle 均为 QA36；9 个非 QA KnowledgeCategory 为 seed 分类；
- MediaAsset 共 11 条：2 条 public QA 媒体、9 条 private RFQ QA 文件；
- CompanyProfile 有 1 条，但缺成立年份、年限、电话、邮箱、地址与 Logo，且没有可追溯到本次 intake 的来源批准；不得把它当成已验收真实公司档案；
- 语言中 `zh-CN` 与 `en` 已启用，另有 1 个禁用的测试语言记录。

本轮没有删除、修复或覆盖这些记录。3.7.2 必须使用显式隔离、可恢复的非生产数据库和 MinIO 实例；不能仅以“localhost”或数据库名相同证明隔离。

## 6. 源码核对后的 CMS 能力地图

### 6.1 Company / Trust

| 资源 | 实际字段摘要 | Admin / API | 生命周期 |
|---|---|---|---|
| CompanyProfile | status、founded_year、years_experience、employee_count_range、factory_area_sqm、annual_capacity_text、export_markets_json、公开联系信息、坐标、Logo/工厂媒体；翻译含 company_name、short_intro、full_intro、mission、advantages_json | Admin `/trust/company` 为 JSON 编辑；GET/PUT `/api/v1/trust/company-profile` | TranslationStatus + Publication + `/[locale]/about/` Route + Revision + Audit；Review/Publish/Archive API 已存在 |
| ManufacturingCapability | slug、capability_type、status、sort_order、primary_media_id；翻译含 name、summary、description、key_facts_json | Admin `/trust/capabilities`；通用 Trust CRUD | 独立 Translation/Publication/Route；Review/Publish/Archive 已存在 |
| Equipment | slug、type、manufacturer、model、quantity、commissioning_year、precision/capacity、featured、media；翻译含 name、summary、description、public_specs_json | Admin `/trust/equipment`；通用 JSON 字段 CRUD | 只有 TranslationStatus；发布翻译后才可进入聚合内容，不建独立 Route/Publication |
| Certificate | slug、type/number、issuer、issue/expiry date、verification_url、公开文件媒体 | Admin `/trust/certificates` | 只有 TranslationStatus；无独立 Route/Publication |
| Patent | slug、专利号/类型/申请号、日期、辖区、发明人描述、验证 URL、公开文件媒体 | Admin `/trust/patents` | 只有 TranslationStatus；无独立 Route/Publication |
| Honor | slug、issuing_organization、award_date、media | Admin `/trust/honors` | 只有 TranslationStatus；无独立 Route/Publication |
| Exhibition | slug、event_name、country/city/date/booth、media；翻译含 title/summary/description | Admin `/trust/exhibitions` | 独立 Translation/Publication/Route；Review/Publish/Archive 已存在 |

Trust 通用端点为 `/api/v1/trust/{resource}` 与 `/{entity_id}`，Review、Translation Publish 或 Publication Transition 均走现有服务和权限。编辑已审核/已发布翻译会回到 draft；disabled/retired 会退出公开结果。

### 6.2 Catalog

| 资源 | 实际字段摘要 | Admin / API | 预检结论 |
|---|---|---|---|
| ProductCategory | parent_id、slug、status、sort_order、cover_media_id；翻译含 name、short_description、description | `/catalog/categories` + `/catalog/categories/tree`；Admin `/catalog/categories` | 支持树、循环检测和双语翻译；Admin 未暴露 cover_media_id 与 short_description |
| Product | category_id、code、slug、status、featured、sort_order、primary_media_id；翻译含 name、short_description、description、highlights_jsonb | `/catalog/products`；Admin `/catalog/products` | Detail API 含翻译、型号、规格、关系、Publication/Route 状态；写入 Schema/Admin 未暴露 primary_media_id、short_description、highlights_jsonb |
| ProductModel | product_id、model_code、status、sort_order；翻译含 name、description | Product 子资源 API；Admin Product 页 | 支持创建/退役，V1 无独立索引页 |
| Specification | Group、Definition、Value；value_type 为 text/number/range/boolean/enum；支持 unit、filterable、product/model owner | `/catalog/specifications/*`；Admin `/catalog/specifications` | 独立规格页支持 5 种值；Product 页的快捷规格区仍偏数值型 |
| Material | slug、abbreviation、status、featured、sort_order；翻译含 definition、processing_characteristics、screw_impact、recommendations、limitations | `/catalog/materials`；Admin `/catalog/materials` | API 可接收完整字段；Admin 只显示 name + definition，不能维护其余字段 |
| Technology | slug、status、featured、sort_order；翻译含 definition、process_description、benefits、limitations | `/catalog/technologies` | Admin 只显示 name + definition |
| Application | slug、status、featured、sort_order；翻译含 description、technical_requirements、common_problems | `/catalog/applications` | Admin 只显示 name + description |
| Solution | slug、status、featured、sort_order；翻译含 definition、symptoms、causes、diagnosis、solution、limitations | `/catalog/solutions` | Admin 只显示 name + definition |

Product 可整体替换 Material/Technology/Application/Solution 关系，服务会生成 Revision/Audit。Catalog 创建与翻译修改会建立或撤回生命周期，但当前 OpenAPI 和 Admin **没有 Catalog Translation Review / Publication Transition 入口**。这意味着不能通过普通 Admin 完成“产品送审并发布”的 3.7.2 维护验收。

### 6.3 Authority

| 资源 | 实际字段摘要 | Admin / API | 生命周期/隐私 |
|---|---|---|---|
| CaseStudy | slug、国家/行业/机型/直径/材料/填充、客户私有身份及三个公开许可布尔值、featured、media；翻译含问题/分析/方案/结果 | Admin `/cases`；`/authority/cases` | 独立生命周期；未授权客户名/地址/Logo 不进入 Public DTO、SEO/GEO/Schema |
| KnowledgeArticle | category、slug、真实 author/reviewer、featured、last_reviewed_at、media；翻译含 title、summary、body_markdown | Admin `/knowledge` | 独立生命周期；关系和 SourceCitation 可用 |
| FAQ | status、sort_order；翻译含 question/answer | Admin `/faqs` | 只有 TranslationStatus，无独立 Route/Publication |
| AuthorExpert | slug、role_type、真实人物核验、公开资料开关、头像/邮箱/年限/LinkedIn；翻译含 name/job_title/bio/expertise | Admin `/experts` | 独立生命周期；未核验真实人物不得公开 |

通用 Authority API 支持 CRUD、关系替换、Translation Review、FAQ Translation Publish，以及 Case/Knowledge/Expert Publication Transition。Admin 嵌入 SEO、GEO 和 SourceCitation 编辑，但媒体 ID 主字段没有在通用表单中完整暴露。

### 6.4 Media / Downloads / SEO-GEO

- MediaAsset 记录 visibility、media_type、bucket/key、原始/清洗文件名、MIME、扩展名、大小、SHA-256、尺寸/时长、校验、扫描与上传状态；MediaTranslation 包含 alt/title/caption。
- Admin `/media` 可以把 JPG/PNG/WEBP/PDF/MP4/WEBM 上传到 `public-media` 并编辑双语元数据。私有 RFQ 文件不会通过 `media.read` 暴露。
- public-media 上传完成后即可通过代理 URL 访问，不是内容 draft；因此只有已获公开许可的派生副本才允许上传，即使目标是受保护环境。
- DownloadResource 有 slug/type/status/media/version/date/requires_form/sort/translations；Admin `/downloads` 有 CRUD 与 broken-media 提示。它没有 ContentPublication，`enabled + public ready object + enabled locale` 即可进入公开下载列表，试点时默认必须以 `disabled` 创建并单独确认。
- 统一 SeoDocument 支持 title/description/canonical/robots/OG/schema override；GeoDocument 支持 direct answer、问题、事实、证据、真实 reviewer 和复核时间；SourceCitation 支持 official/standard/paper/manufacturer/first-party/case 等来源。
- GEO visible source 由后端从 Product/Case/Knowledge/Expert/Capability/Exhibition/Company 可见内容生成并校验，不能由客户端自报。
- 当前 Admin 的通用 SEO/GEO 编辑组件只嵌入 Authority CRUD；Product、Company 和 Trust 页面没有完整对应入口，3.7.2 如需要普通管理员维护这些字段，需做小范围 Admin 接线，不得绕过 API 或直接 SQL。

## 7. 3.7.2 前必须关闭的维护闭环缺口

这些是现有 UI/API 接线缺口，不代表需要第二套 CMS：

1. ProductCreate/ProductUpdate 与 Product Admin 均不能设置 `primary_media_id`，无法通过普通后台更换产品主图。
2. Product Admin 不能维护 `short_description`、`highlights_jsonb`；Category 不能维护 `short_description` 和 `cover_media_id`。
3. Product Admin 没有 Catalog Translation Review / Publication Publish / Archive，OpenAPI 也没有对应 Catalog 端点。
4. Material/Technology/Application/Solution Admin 只暴露一个正文列，不能维护模型已有的完整结构化翻译字段。
5. Product/Company/Trust 缺通用 SEO/GEO/Source 的 Admin 接线；直接调用 API 虽可写，但不能满足“普通用户可维护”的验收。
6. Authority API 支持 primary/profile media 字段，但通用 Admin 表单没有完整提供媒体选择。

建议在 3.7.2 先做一个严格限定的“CMS 维护闭环补线”小批修改：只暴露已有字段与既有生命周期服务，不加表、不改 migration、不建立第二套发布体系。未完成前，不能用脚本或 SQL 假装后台维护已经通过。

## 8. 首个真实产品候选链

### 8.1 候选范围

候选产品：**注塑机氮化料筒**。原因是指定图片目录内有 5 张名称相符的候选图，旧站也有对应分类和产品页，适合暴露来源冲突并验证完整链。该选择仍需用户确认：5 张图片究竟是一个产品的图库、多个型号，还是多个独立产品。

建议的外部登记键和 slug 仅用于 dry-run：

| 对象 | external_key | 建议 slug | 建议 Route |
|---|---|---|---|
| ProductCategory | `junhui:product-category:injection-molding-machine-barrels` | `injection-molding-machine-barrels` | `/zh-cn/products/injection-molding-machine-barrels/`、`/en/products/injection-molding-machine-barrels/` |
| Product | `junhui:product:nitrided-barrel` | `nitrided-barrel` | `/zh-cn/products/injection-molding-machine-barrels/nitrided-barrel/`、`/en/products/injection-molding-machine-barrels/nitrided-barrel/` |

只读数据库检查显示上述 category/product slug 及双语详情 Route 均为 0 个冲突。`external_key` 是私有 intake/import manifest 的稳定键，不写入 CMS UUID，也不要求新增数据库列。

### 8.2 完整内容链计划

1. 用户确认产品粒度、中文正式名、英文正式名与 slug。
2. 为 5 张图片逐张建立私有 Media rights 记录，确认图库/型号/独立产品归属；生成去 EXIF 的发布副本并补双语 alt。
3. 由最新版技术表建立 ProductSpec Definition/Value；每个值必须记录来源定位、单位、适用型号/条件和技术审核人。
4. 只建立经确认的 Material、Technology、Application 关系；Solution、Case、FAQ、Knowledge、Expert 缺资料时保持空。
5. 先在隔离目标创建 category/product 的 `zh-CN` 与 `en` draft；不设置 published，不激活 Route。
6. 普通管理员通过 Admin 更换主图、修改摘要/参数/关系；完成中文技术审核与英文语言审核。
7. 通过已有 Translation → Publication → Route 事务送审和发布；再录入 SEO/GEO，所有 GEO 事实必须可在公开正文或规格中找到。
8. 在受保护 HTTPS 环境验证 Public DTO、SSR、canonical/hreflang、Schema、Sitemap、语言切换、RFQ attribution 和响应式图片。
9. 该产品链签收后，再由用户选择 3–5 个产品扩展；其余产品继续由用户后续在后台录入。

## 9. 首批内容地图

| 内容 | 来源状态 | 目标模型 | 本轮状态 |
|---|---|---|---|
| 公司名称/简介/联系信息 | 旧站有线索，本次无现行权威表 | CompanyProfile + translations | `BLOCKED` |
| Logo / 横版名称图 | 有参考图，但无透明原稿与公开许可记录 | MediaAsset + MediaTranslation；CompanyProfile.logo_media_id | `BLOCKED` |
| 工厂图片 | 有 1 张参考图 | MediaAsset；CompanyProfile.primary_factory_media_id 或 Capability media | `BLOCKED` |
| 注塑机料筒分类 | 图片目录和旧站均有线索 | ProductCategory + translations | `CREATE` 候选，待确认 |
| 注塑机氮化料筒 | 5 张候选图和旧网页；参数冲突 | Product + translations | `CREATE` 候选，事实 `CONFLICT` |
| 产品型号 | 图片文件名不足以证明型号 | ProductModel | `BLOCKED` |
| 技术参数 | 旧页内部矛盾，无最新版表 | SpecificationGroup/Definition/Value | `CONFLICT` |
| 材料/工艺/应用关系 | 旧页仅有泛化文字 | Material/Technology/Application + relations | `BLOCKED` |
| Solution / Case / FAQ / Knowledge / Expert | 未收到真实资料 | 对应 Structured Core / Authority | `BLOCKED`，不补假内容 |
| Certificate / Patent / Honor / Equipment / Exhibition | 未收到真实原件与公开许可 | Trust models | `BLOCKED`，不 seed 假记录 |
| Downloads | 未收到公开版目录/PDF | MediaAsset + DownloadResource | `BLOCKED` |

## 10. 中英文术语表（提案，全部待审核）

| 中文 | 英文候选 | 状态/注意事项 |
|---|---|---|
| 螺杆 | screw | `PENDING_TECH_REVIEW`；需要按塑机部件语境使用 |
| 料筒 / 机筒 | barrel | `PENDING_TECH_REVIEW`；统一是否保留两个中文同义词 |
| 螺杆料筒 | screw and barrel / screw barrel | `PENDING_LANGUAGE_REVIEW`；正文、导航与 SEO 需统一 |
| 注塑机螺杆 | injection molding machine screw | `PENDING_LANGUAGE_REVIEW` |
| 注塑机料筒 | injection molding machine barrel | `PENDING_LANGUAGE_REVIEW` |
| 挤出机螺杆 | extruder screw | `PENDING_LANGUAGE_REVIEW` |
| 平行双螺杆 | parallel twin screw | `PENDING_TECH_REVIEW` |
| 锥形双螺杆 | conical twin screw | `PENDING_TECH_REVIEW` |
| 哥林柱 | tie bar | `PENDING_TECH_REVIEW`；不要自动采用机翻 |
| 过胶头 / 过胶圈 / 过胶介子 | screw tip / check ring / thrust washer | `PENDING_TECH_REVIEW`；需确认企业内部叫法和零件边界 |
| 氮化 | nitrided / nitriding | 分别用于产品状态与工艺，`PENDING_LANGUAGE_REVIEW` |
| 电镀 | electroplated | 未确认具体镀层时不要写 hard chrome |
| PTA | PTA | 全称、工艺范围与牙顶处理需技术确认 |
| 烧结 / 双合金 | sintered / bimetallic | 旧资料语义混用风险，`PENDING_TECH_REVIEW` |

此表不是已批准翻译，正式值应填入私有 terminology register，再由技术与英语审核人分别确认。

## 11. 只读 dry-run

| 目标 | 预期动作 | dry-run 结果 | 原因 |
|---|---|---|---|
| `zh-CN`、`en` Locale | `no-op` | `NO-OP` | 已启用，`zh-CN` 为默认语言 |
| QA36/PG fixture | `no-op` | `NO-OP` | 明确排除；本轮不清理、不覆盖 |
| 9 个 KnowledgeCategory seed | `no-op` | `NO-OP` | 已存在，但不等于已批准真实文章 |
| 候选 ProductCategory | `create` | `CREATE`（未执行） | slug/Route 无冲突；名称和层级仍待用户确认 |
| 候选 Product | `create` | `BLOCKED` | 产品粒度、真实参数、双语名、主图与许可未批准 |
| 候选 ProductModel | `create` 或 `no-op` | `CONFLICT` | 5 张图不能确定是型号还是图库 |
| ProductSpecValue | `create` | `CONFLICT` | 旧站同页参数矛盾，缺最新版来源 |
| 186 个媒体候选 | `create` | `BLOCKED` | 当前媒体库 SHA 无重复，但目录内有重复且公开许可未确认 |
| CompanyProfile | `update` | `CONFLICT` | 开发库记录来源不可追溯，不能与真实公司档案合并 |
| Trust / Authority 内容 | `create` | `BLOCKED` | 无真实原件、许可或审核人 |
| Production/Redirect/Search Console/Analytics | 无动作 | `BLOCKED` | 不在 3.7.1 授权范围 |

本轮没有生成写数据库的导入脚本。dry-run 仅使用文件读取、OpenAPI、HTTP GET、SQL `SELECT`、MinIO `list_objects` 与哈希比对。

## 12. 媒体授权、脱敏与性能预案

每个拟公开媒体必须在私有台账记录：来源、原文件 SHA-256、权利依据、对应 owner、是否允许公开/裁切/转码/去背景、客户或第三方标识、人物肖像、设备铭牌、联系方式、图纸/尺寸、GPS/EXIF、需遮挡区域、双语 alt 和批准人。

本轮发现：

- 两份 Logo PNG 都不是透明图；横版图的棋盘格是像素内容。若要透明版，应由用户提供矢量/Alpha 原稿，或另行批准背景移除派生稿。
- 工厂 JPEG 含 EXIF，虽无 GPS，仍建议网站副本统一去元数据。
- 产品图均为 700×700，技术上可作卡片/图库候选，但应生成明确尺寸与质量的 WebP 派生副本并保留原稿私有。
- 抽样产品图带水印和宣传文字；不能在未核对时把图中文字当结构化事实或 alt 文本。
- Public Media 和 RFQ Private File 必须继续使用 `public-media` / `private-rfq` 隔离；任何 RFQ/CAD 私图均不得进入本台账的公开候选。

## 13. SEO / GEO 只读准备检查

本轮使用 `$seo-rank` 与 `$geo-rank` 核对，未发现与交接文件冲突；交接文件更严格的来源、可见内容和审批规则优先。

后续每个获批页面必须满足：

- enabled entity + enabled locale + published translation + published publication + canonical + active + indexable；
- SeoDocument `robots_index=true`，canonical、Sitemap、内部链接和 hreflang 一致；
- 中英文各自 self-canonical、互返 hreflang，正文而非仅导航完成本地化；
- GEO direct_answer/key_facts/evidence 均能在 SSR 可见正文、规格或经许可案例中找到；
- 每项关键技术事实有 SourceCitation 或私有事实登记来源，不以旧站重复文字代替证据；
- Schema 只输出页面可见且已审核的 Organization/Product/Article/Person/Breadcrumb，不生成价格、Offer、Review、Rating、虚构专家或证书；
- 图片有准确 alt，关键事实不只存在于图片文字；
- 固定 GEO question pool 在真实内容获批后建立，建议 20–50 条双语问题；当前没有事实基础，未生成假问题结果；
- Search Console、Bing、GA4/GTM 和正式监测均未启用，不把 `llms.txt` 或 Schema 当作收录/引用保证。

## 14. 环境与工具准备

### 14.1 当前只读健康状态

| 项目 | 结果 |
|---|---|
| Docker Compose | postgres、postgres-test、redis、redis-test、minio、api、worker、website、admin、nginx 均 `healthy` |
| API | `/health/live` 200；`/health/ready` 200 |
| MinIO | `/minio/health/live` 200 |
| Website | 3000 与 Nginx 8080 的英文首页均 200 |
| Admin | `/login` 200 |
| Alembic | `20260905_0010` |
| 本地 MinIO 对象 | `public-media=2`、`private-rfq=9`，均为现有 QA 环境对象，不是本轮上传 |

### 14.2 可用工具

- Node.js 24.14.0、pnpm 11.19.0、Python 3.12.14；
- Docker 29.7.2、Docker Compose 5.3.1；
- Pillow/openpyxl 可用于只读媒体与登记表预检；
- Vitest 3.2.4、Prettier 3.6.2 已在项目中；
- 现有 Phase 3.6 浏览器 QA 脚本可复用，但 Playwright 不是项目根依赖，运行前需固定可复现的外部依赖路径；
- Lighthouse、ImageMagick、FFmpeg、ExifTool 当前未在项目/系统路径中发现，均记为 `NOT READY`，不能声称性能或全媒体验收已完成；
- 真实 Safari/WebKit 与海外网络仍为 `NOT RUN`。

### 14.3 受保护非生产环境要求

当前栈为本地 HTTP development，不是本地 HTTPS production-like 环境。3.7.2/3.7.3 前建议新建独立 Compose project/volume/bucket namespace，使用本地受信 TLS、Basic Auth + noindex、生产同构环境变量校验、独立测试管理员、空 DB → 0010 migration，以及只允许批准批次的 public-media。不得连接生产数据库、生产桶或真实 RFQ 数据。

## 15. 备份、恢复与发布准备清单

在任何 3.7.2 写入前：

1. 记录 code SHA、batch ID、source manifest SHA-256、目标 DB/MinIO alias 和授权范围。
2. 对目标 PostgreSQL 执行并校验 `pg_dump`；记录恢复到独立库的演练结果。
3. 记录两个 bucket 的对象清单/版本或可恢复备份；DB 与对象存储分别备份。
4. 保存写入前的 entity/revision/publication/route 摘要，不包含凭据或 PII。
5. dry-run 先给出 create/update/no-op/conflict/blocked；update 必须展示字段差异和当前 revision。
6. 上传失败时只补偿本批对象；不得清空桶或回退无关内容。
7. draft import、公开媒体上传、受保护预览发布、生产部署分别授权。
8. 预览发布后验证 Public DTO → SSR → canonical/hreflang/Schema/Sitemap/GEO visible source → RFQ attribution。
9. 生成脱敏 evidence manifest 与校验和；不得包含 Cookie、Token、signed URL、私有图纸、真实客户资料或数据库文件。
10. 生产部署、DNS、旧站下线、线上 Redirect、Search Console/Bing 和 Analytics 继续保持未授权。

## 16. 本轮验证命令与结果

| 检查 | 方式 | 结果 |
|---|---|---|
| Git 基线/分支/远端 | `git status`、`git rev-parse`、`git log` | PASS；基线与远端均为 `c16385c...`，本地分支 `phase-3.7` |
| Handoff 完整性 | `Get-FileHash` 对照 SHA256SUMS | PASS；列出的文件哈希匹配 |
| Intake workbook | openpyxl 只读读取 6 个 Sheet | PASS；确认模板为空，无真实资料 |
| CMS 架构 | codebase-memory architecture/search_graph + 源码/OpenAPI 交叉核对 | PASS；没有按旧文档猜测路由 |
| 指定产品图片 | Pillow 解码、尺寸/EXIF/GPS、SHA-256 去重 | PASS；186/186 可解码，2 组内容重复 |
| 当前媒体重复 | 本地 SHA-256 对 MediaAsset SHA-256，只读比较 | PASS；0 个匹配 |
| 候选 slug/Route | PostgreSQL `SELECT` | PASS；category/product/zh/en route 均 0 冲突 |
| Compose/HTTP | `docker compose ps` + HTTP GET | PASS；见第 14 节 |
| 旧官网 | 只读网页获取 | PARTIAL；首页/公司/单个产品页可读，robots/sitemap 未完整解析 |
| Ruff/Backend/Frontend/Build | 未改业务代码，本轮未运行 | `NOT RUN`；本轮只新增脱敏文档/空模板 |
| Lighthouse/Safari/WebKit | 环境未就绪 | `NOT RUN` |

数据库前后只读计数完全一致：Product 29、CompanyProfile 1、MediaAsset 11、ContentPublication 85、ContentRoute 85、ContentRevision 145、AuditLog 1664。MinIO 前后对象计数也完全一致：`public-media=2`、`private-rfq=9`。由此确认本轮没有产生内容、媒体、Publication、Route、Revision 或 Audit 写入。

## 17. 合并后的最小待确认清单

请下一次一次性确认或提供以下 5 组内容，不需要逐字段往返：

1. **试点范围：** 是否以“注塑机氮化料筒”为第一个产品；5 张同目录图片是一个产品图库、多个型号，还是多个独立产品；确认中英文正式名和建议 slug。
2. **真实事实包：** 提供该产品最新版参数表/图纸的可公开版本，明确每个数值的单位、适用型号/条件；确认材料、工艺、应用关系。旧站矛盾值不能直接沿用。
3. **媒体许可包：** 确认三张已上传品牌/工厂图及指定产品图片由公司拥有或获授权，可用于新官网和受保护预览；说明是否允许裁切、转 WebP、去 EXIF、去背景、保留/去除水印，并提供真正透明或矢量 Logo（如有）。
4. **审核责任：** 指定中文技术审核人和英文语言审核人；若未来建立公开 Expert，再单独确认真实身份及本人公开许可。本试点不要求虚构 Expert/Case/Certificate。
5. **目标与权限：** 确认一个与当前 QA 数据隔离的本地 HTTPS 非生产目标，并分别授权 `draft import` 与“批准版本的受保护预览发布”；不包含生产部署。

在以上输入齐备前，Company、证书、专利、设备、案例、专家和其余产品保持缺失，不用 QA fixture 或 AI 文案补齐。

## 18. 下一批试点执行计划

用户确认第 17 节后，3.7.2 建议顺序为：

1. 创建私有 batch manifest 与 source/fact/media/terminology/content-map 登记，锁定源文件 hash。
2. 在独立目标做备份基线和 read-only dry-run；由用户确认 create/update/no-op/conflict/blocked。
3. 仅补现有 CMS 的 Admin/API 维护接线缺口，并运行对应 Backend、PostgreSQL、Admin/Website、typecheck/build 回归。
4. 上传已批准的媒体派生副本，建立双语 alt；确认 Product 主图映射。
5. 导入一个 category + 一个 product 的双语 draft、规格和关系；不发布。
6. 普通管理员在 Admin 完成主图、摘要、参数、关系、送审操作，保留 Revision/Audit。
7. 分别取得中文技术、英文语言和受保护预览发布批准，再通过现有 Publication/Route 服务发布。
8. 运行真实素材浏览器、性能、SEO/GEO、隐私、RFQ 和恢复验收；交付 evidence 与 pilot report。
9. 用户签收一个完整链后，再扩展至 3–5 个产品。

## 19. 本轮新增的通用空模板

- `docs/content/templates/phase3-7-source-fact-register.template.csv`
- `docs/content/templates/phase3-7-media-rights-register.template.csv`
- `docs/content/templates/phase3-7-terminology.template.csv`
- `docs/content/templates/phase3-7-content-map.template.csv`
- `docs/content/templates/phase3-7-release-manifest.template.json`

这些模板不含真实资料、审批签名、凭据或目标实例信息。真实填写版本默认保留在私有目录，不自动提交公共 GitHub。

## 20. 3.7.2 首个产品试点后续更正（2026-09-06）

用户已对第 17 节的首个试点所需输入作出合并确认，因此原报告中的下列试点级阻塞已经关闭：

- 前 4 张“骏辉螺杆 氮化机筒”图片确认为“注塑机氮化料筒”的同一产品图库；“日精”图片属于另一产品并排除本批；
- 用户确认公司拥有 Logo、工厂图和产品图的新官网使用权，并授权裁切、缩放、压缩、WebP、去 EXIF、缩略图、去背景和水印处理；
- 中文与英文内容均由用户本人审核，后台需持续允许修改产品名称、参数和技术表述；
- 用户批准建立与既有 QA 数据隔离的本地 HTTPS、独立数据库与 MinIO 环境，并启用 Basic Auth 和全站 noindex；
- 用户仅授权首个产品写入该隔离环境为 draft，不授权 Review、Publish、Sitemap、生产部署或其他产品导入。

试点已按上述授权完成，实际结果记录于 `docs/content/phase3-7-pilot-report.md`。首个产品的最新版参数、型号适用范围和结构化关系仍缺权威证据，因此保持空缺；第 5 张“日精”图片仍在本批范围外；受保护预览发布仍需用户另行授权。此后续不改变第 1 节的结论：3.7.1 准备完成不等于 Phase 3.7 完成。
