# 官网呈现 V1.0 · R1 设计规范

## 目标与边界

本轮在现有 Nuxt/Vue、FastAPI、PostgreSQL 与 Admin CMS 中交付中英文完整首页、首页模块编辑器、认证完整布局预览和全站模块总览。普通首页只展示已通过现有公开门禁的内容；作者预览仍只使用公开内容，但会显示全部十四个模块的位置、缺件原因和管理入口。

不得新增或暗示厂房、客户、证书、专利、产能、出口市场、价格、参数或技术结论。设计概念图只作为布局参考；其中生成的机器、厂房、地图、资质图形和营销句全部禁用。生产页面媒体仅允许复用当前已批准的产品图片和 Logo。

## 数据模型

- 扩展固定 `SitePage` 白名单，增加唯一 `system_key=home` 页面身份。
- 每个启用语言对应一条 `HomepageLayout`，保存 `draft_config_jsonb`、`applied_config_jsonb`、草稿/应用修订号及真实操作者。
- 配置只保存十四个固定模块的顺序、显示状态、有限样式变体，以及产品 slug 引用；不保存正文副本、任意 UUID、HTML、CSS 或 API 地址。
- 保存草稿使用 `content.update`，查看和作者预览使用 `content.read`，应用布局使用 `content.publish`。所有写入继续使用 Cookie 认证、CSRF、`ContentRevision` 和 `AuditLog`。
- 写接口携带期望修订号并在数据库中锁行，冲突返回 409，不覆盖并发人工修改。
- 恢复操作把当前已应用配置复制回草稿，不修改已应用页面；再次应用才影响普通首页。

## 十四模块注册表

固定键和数据源如下，配置中必须恰好出现一次：

1. `hero`：CompanyProfile、首个已选公开产品媒体。
2. `core_product_families`：公开产品分类、后台选择的公开产品引用。
3. `materials`：公开 Material。
4. `special_applications`：公开 Application。
5. `technologies`：公开 Technology。
6. `manufacturing_capability`：公开 ManufacturingCapability。
7. `why_junhui`：已批准 CompanyProfile 正文。
8. `factory_equipment`：公开 Equipment 与公司工厂媒体。
9. `solutions`：公开 Solution。
10. `case_studies`：公开 CaseStudy。
11. `technical_knowledge`：公开 KnowledgeArticle。
12. `certificates_patents`：公开 Certificate 与 Patent。
13. `global_markets`：CompanyProfile 中已批准的 export_markets。
14. `rfq_cta`：现有 RFQ 页面入口；不改变 Privacy 未发布时的正式提交禁用状态。

## 普通首页与完整布局预览

- 普通首页读取 `applied_config_jsonb`。模块被关闭或没有合格公开数据时不渲染，不用默认文案假装有内容。
- 作者预览读取 `draft_config_jsonb`，由受保护 API 校验登录与 `content.read`。它显示全部十四个位置：有内容时使用同一 renderer；无内容时显示结构化缺件原因和真实 Admin 管理链接。
- 作者预览通过 `admin.junhuiscrewbarrel.com/preview/{locale}/` 进入。Nginx 仅把该精确前缀代理到 Website SSR，使 Admin 的 host-only 登录 Cookie 可由服务端校验。
- 预览响应和 API 都返回 `Cache-Control: private, no-store` 与 noindex；匿名请求返回 401/403，查询参数、localStorage 和前端变量均不能解锁。
- 预览内语言切换留在 Admin 预览域；正文链接明确指向本机裸域的公开 canonical 路径。

## 视觉系统

- 背景：真实白色 `#ffffff` 与浅蓝 `#f3f8ff`；主色深海军蓝 `#071d3b`、钴蓝 `#1268e8`、浅青蓝 `#62c7ff`。
- 字体：沿用支持中英文的系统无衬线字体；桌面 H1 约 56–64px，移动端控制在 36–42px。
- 容器：最大 1200px；桌面约 32px 横向留白，375px 约 20px。
- 形态：8px 小圆角、细钢蓝边、克制阴影；不用胶囊、霓虹、彩色光球、虚构图标证据或层层卡片。
- 首屏：深蓝底、左文右图，右侧由三款真实产品图形成有秩序的制造构图；无工厂图时不伪造背景。
- 长页：开放分区、横向轨道、编辑式分栏和浅蓝色带交替；普通首页当前重点呈现 Hero、Core Product Families、Why Junhui、RFQ CTA。
- 产品卡：三款真实方形主图，保持原 alt、尺寸和 canonical 链接。
- 空态：仅作者预览出现，使用文本、状态边线和管理入口，不生成示意厂房、证书、地图或人物。

## Admin 交互

- 双语标签页；每个模块显示名称、来源状态、可见开关、样式选择、上移/下移。
- 产品引用使用带名称和主图缩略图的复选框，只列出当前语言严格公开的产品；后台不显示或要求 UUID。
- “保存草稿”后重新回读并核对修订号；“应用布局”单独受发布权限控制；“恢复到当前应用版”只重置草稿。
- 模块总览列出前台地址、后台地址、实体数量、公开数量、导航状态、实际实现层级和隐藏原因。Technologies 与 Contact 单独列出。

## 响应式与无障碍

- 375px 下首屏单列、产品图不裁断、模块控制可键盘操作。
- 排序按钮有明确 aria-label；开关使用原生 checkbox；状态不只依赖颜色。
- 页面保持唯一 H1、语义 section/headings、图片尺寸与 alt；焦点样式清晰。

## 验收不变量

8组 SEO、COPY-V1、产品参数 0/0/0、七个定义、F05 英文空缺、名称、slug、分类、图片/图注、型号、关系、旧试点、Privacy draft/current 空与 RFQ=0 均不得改变。外层保持 127.0.0.1:443、无前台 Basic 弹窗、后台应用登录、全站 noindex、Sitemap 404。
