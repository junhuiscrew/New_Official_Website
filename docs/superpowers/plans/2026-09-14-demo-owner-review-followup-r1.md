# Demo Owner Review Follow-up R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有双语首页草稿/预览/应用体系中增加安全可编辑的 4 项 Demo Hero 轮播，并交付中文手册、不可编辑内容审计和最终脱敏证据。

**Architecture:** 不建新表；把 `slides` 作为 Hero 模块的白名单 JSONB 配置，保存时核验公开就绪图片，公开聚合时解析为不含媒体 ID/存储字段的 DTO。前台用独立 Vue 组件实现自动/手动/无障碍轮播，旧配置无轮播时继续走现有静态 Hero。后台复用当前双语标签、媒体 API、草稿/预览/应用/恢复链路。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy async、PostgreSQL/SQLite 测试、Nuxt 4、Vue 3、TypeScript、Vitest、Playwright CLI、Docker Compose、Markdown/JSON。

**Execution note:** 用户明确要求继续现有 `phase-3.7` 工作区并禁止 commit/push/merge，因此本计划在当前 worktree 内执行；所有“提交”节点改为记录 `git diff`、HEAD 和校验结果。

---

## File structure

- Modify `apps/api/app/modules/presentation/schemas.py`: 定义轮播输入、链接与唯一性校验。
- Modify `apps/api/app/modules/presentation/registry.py`: 默认 Hero 增加空 `slides`，保持十四模块固定。
- Modify `apps/api/app/modules/presentation/services.py`: 序列化轮播、校验媒体引用、生成安全公开轮播 DTO。
- Modify `apps/api/app/modules/discovery/public_collections.py`: 等待异步轮播 DTO 附加。
- Modify `apps/api/tests/test_homepage_presentation_r1.py`: API 红绿测试。
- Create `apps/website/app/components/HeroBannerSlider.vue`: 独立轮播渲染与交互。
- Modify `apps/website/app/components/HomepagePresentation.vue`: Hero 有轮播时使用新组件，无轮播时保持旧实现。
- Modify `apps/website/app/components/HomePage.vue`: SSR 预加载第一张合格轮播图。
- Modify `apps/website/app/types/public.ts`: 增加轮播 DTO 类型。
- Create `apps/website/tests/hero-banner-slider.test.ts`: 自动/手动/暂停/回退测试。
- Modify `apps/website/tests/phase36-homepage.test.ts`: 将“禁止轮播”旧冻结断言替换为“禁止第三方轮播和硬编码事实”。
- Modify `apps/website/tests/website-presentation-r1.test.ts`: 锁定十四模块不变与新 Hero 分支。
- Modify `apps/admin/app/pages/homepage.vue`: 轮播 CRUD、排序、启停、媒体选择和预览提示。
- Modify `apps/admin/tests/homepage-presentation-r1-contract.test.ts`: 锁定后台入口、字段和权限边界。
- Create `docs/handoff/demo-admin-chinese-user-manual.md`: 12 章员工操作手册。
- Create `docs/handoff/admin-non-editable-content-audit-r1.md`: 不可编辑项审计和 P0/P1/P2。
- Create `demo-owner-review-followup-r1-report.md`: 实施和验收报告。
- Create `demo-owner-review-followup-r1-readback.json`: 结构化 readback。
- Create `artifacts/demo-owner-review-followup-r1-<run-id>/...`: 截图、命令输出、清单和脱敏证据。

### Task 1: API 输入合同与媒体门禁

- [ ] **Step 1: 写失败测试**

在 `apps/api/tests/test_homepage_presentation_r1.py` 增加：创建一张 `public/ready/public-media/image` 和不合格媒体；保存含两项轮播的 Hero；断言顺序和字段 fresh GET 保留；断言重复 ID、6 项、外部/脚本链接、CTA 单边填写、非 Hero `slides`、私有/未就绪/非图片媒体被拒绝。

核心测试输入：

```python
slides = [
    {
        "id": "precision-manufacturing",
        "media_id": str(public_image.id),
        "title": "螺杆与机筒精密制造",
        "subtitle": "Demo 说明",
        "cta_label": "探索产品",
        "cta_href": "/zh-cn/products/",
        "enabled": True,
    },
    {
        "id": "surface-engineering",
        "media_id": str(second_public_image.id),
        "title": "表面工程与工艺技术",
        "subtitle": "Demo 说明",
        "cta_label": None,
        "cta_href": None,
        "enabled": False,
    },
]
```

- [ ] **Step 2: 运行并确认 RED**

Run: `uv run --project apps/api pytest apps/api/tests/test_homepage_presentation_r1.py -q`

Expected: 新测试因 `slides` 为额外字段或公开 DTO 无轮播而失败。

- [ ] **Step 3: 实现 Pydantic 白名单**

在 `schemas.py` 增加 `HomepageHeroSlideInput`，字段限制：`id` 1–64、`title` 1–120、`subtitle` 1–300、CTA 0–40/0–240、`media_id: UUID`、`enabled: bool`；模型校验 CTA 成对与 `cta_href` 必须以单 `/` 开头且不含 `://`、`//`、控制字符。`HomepageModuleInput.slides` 最多 5 项，仅 Hero 允许，Hero 内 ID 唯一。

- [ ] **Step 4: 实现媒体引用门禁与序列化**

在 `registry.py` 默认每个模块都稳定包含 `slides: []`（仅 Hero 可非空）。在 `services.py` 的 `_config_from_payload` 保留新字段；增加 `_validate_hero_slide_references(session, locale, config)`，一次查询所需媒体并核验 `visibility == public`、`upload_status == ready`、`storage_bucket == public-media`、`media_type == image`；不合格返回 `homepage_hero_media_unavailable`。

- [ ] **Step 5: 运行 API 测试并确认 GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/test_homepage_presentation_r1.py -q`

Expected: 全部通过，原 revision/apply/restore 权限断言不变。

### Task 2: 安全公开轮播 DTO

- [ ] **Step 1: 写失败测试**

在同一 API 测试中保存并应用两项轮播，调用 `/api/v1/public/home/zh-cn` 与认证预览，断言：普通首页只返回启用项；数组顺序一致；首图 `loading=eager`、后续 `lazy`；DTO 不含 `media_id/storage_bucket/storage_key/uploaded_by`；禁用/后来变为不合格的图片不进入公开结果；旧空轮播仍返回现有 `hero_media` 回退。

- [ ] **Step 2: 运行并确认 RED**

Run: `uv run --project apps/api pytest apps/api/tests/test_homepage_presentation_r1.py -q`

Expected: `presentation.modules[hero].slides` 尚未解析为公开媒体 DTO。

- [ ] **Step 3: 实现异步公开附加**

将 `attach_homepage_presentation` 改为异步并接收 `session`、`locale_id`；对 Hero 的启用项调用现有 `_public_media(..., fallback_alt=title)`，只在成功解析后输出：

```python
{
    "id": slide["id"],
    "title": slide["title"],
    "subtitle": slide["subtitle"],
    "cta_label": slide["cta_label"],
    "cta_href": slide["cta_href"],
    "media": media.model_dump(),
}
```

普通模块不输出私有 `media_id`。更新 `public_collections.py` 为 `return await attach_homepage_presentation(...)`。

- [ ] **Step 4: 运行 API 测试并确认 GREEN**

Run: `uv run --project apps/api pytest apps/api/tests/test_homepage_presentation_r1.py -q`

Expected: 公开与预览安全断言通过。

### Task 3: 前台轮播组件

- [ ] **Step 1: 写失败组件测试**

新建 `apps/website/tests/hero-banner-slider.test.ts`，挂载 3 张真实 DTO，使用 fake timers 断言：初始只显示第一项；6 秒切换；点击下一项/圆点切换；暂停键停止；hover/focus 暂停；`visibilitychange` 暂停；CTA 使用服务端站内路径；只有一项时无 autoplay；组件卸载清理 timer。测试 DOM 使用 `data-testid="hero-slider"`、`hero-slide`、`hero-next`、`hero-previous`、`hero-pause`、`hero-dot`。

- [ ] **Step 2: 运行并确认 RED**

Run: `pnpm --filter @junhui/website test -- hero-banner-slider.test.ts`

Expected: 组件文件不存在或行为断言失败。

- [ ] **Step 3: 实现最小 Vue 组件**

创建 `HeroBannerSlider.vue`：`activeIndex`、`pausedByUser`、hover/focus/visibility 状态；`setInterval(6000)`；`onMounted/onBeforeUnmount`；`aria-live=polite`；箭头、圆点、暂停/播放；使用 `PublicImage`，第一项 eager，其余 lazy；标题只在当前项中作为唯一 H1。

- [ ] **Step 4: 实现视觉与响应式**

CSS 按设计图实现全宽图片、深蓝渐变、网格/金属线、文字安全区和底部控件；`@media (max-width: 48rem)`、`@media (max-width: 30rem)`、`@media (prefers-reduced-motion: reduce)`；375px 按钮不溢出，控件不遮挡正文。

- [ ] **Step 5: 运行组件测试并确认 GREEN**

Run: `pnpm --filter @junhui/website test -- hero-banner-slider.test.ts`

Expected: 全部通过且无未处理 timer/console error。

### Task 4: 接入首页与 SSR 预加载

- [ ] **Step 1: 写失败集成测试**

更新 `website-presentation-r1.test.ts` fixture，为 Hero 增加 `slides`；断言轮播分支有 1 个 H1、标题/CTA 来自 DTO、十四模块键与顺序不变；清空 slides 后断言旧 Hero 回退仍存在。更新 `phase36-homepage.test.ts`：允许内部 `HeroBannerSlider`，仍禁止 Swiper/Splide/第三方 carousel 和硬编码制造事实。增加 `HomePage` head 断言优先预加载第一张启用轮播图。

- [ ] **Step 2: 运行并确认 RED**

Run: `pnpm --filter @junhui/website test -- website-presentation-r1.test.ts phase36-homepage.test.ts`

Expected: 新 DTO/轮播/预加载断言失败。

- [ ] **Step 3: 接入类型与渲染**

在 `public.ts` 增加 `HomepageHeroSlideDto`，在 `HomepageModuleDto.slides?: HomepageHeroSlideDto[]`。`HomepagePresentation.vue` Hero 分支在 `module.slides?.length` 时渲染新组件，否则保持原静态结构不变。`HomePage.vue` 的 `heroPreload` 先取 Hero 第一张 slide media，再回退 `home.hero_media`。

- [ ] **Step 4: 运行集成测试并确认 GREEN**

Run: `pnpm --filter @junhui/website test -- website-presentation-r1.test.ts phase36-homepage.test.ts hero-banner-slider.test.ts`

Expected: 全部通过。

### Task 5: 后台轮播 CRUD

- [ ] **Step 1: 写失败后台合同测试**

更新 `homepage-presentation-r1-contract.test.ts`，断言页面读取 `/media`，存在 `data-testid="homepage-hero-slides"`、新增/删除/上移/下移、启用、主标题、副标题、按钮文案、站内链接和媒体选择；仍不出现手工 UUID/JSON 输入；保存 payload 继续使用 `expected_revision` 和整个 `modules`。

- [ ] **Step 2: 运行并确认 RED**

Run: `pnpm --filter @junhui/admin test -- homepage-presentation-r1-contract.test.ts`

Expected: 新轮播编辑器断言失败。

- [ ] **Step 3: 实现后台状态与操作**

在 `homepage.vue` 增加 `HeroSlideConfig`、`MediaItem`，`cloneModules` 深拷贝 `slides`；`loadHomepage` 同时读取 `/media` 并只保留 `type=image && visibility=public && upload_status=ready && url`。实现：

```ts
function addHeroSlide(module: ModuleConfig): void
function removeHeroSlide(module: ModuleConfig, index: number): void
function moveHeroSlide(module: ModuleConfig, index: number, direction: -1 | 1): void
```

ID 在浏览器中生成 `slide-${Date.now()}-${sequence}`，不要求员工输入。`hasUnappliedChanges` 使用稳定深比较，覆盖轮播字段。

- [ ] **Step 4: 实现编辑 UI**

仅在当前模块为 Hero 时显示轮播区域；卡片内提供顺序、启用、图片、标题、副标题、CTA 和站内路径；显示“当前编辑：中文/English”和“保存草稿后预览”；5 项时禁用新增；删除前使用浏览器确认；CSS 保持当前后台风格和 1366px 可读性。

- [ ] **Step 5: 运行后台测试并确认 GREEN**

Run: `pnpm --filter @junhui/admin test -- homepage-presentation-r1-contract.test.ts admin-cn-ux-r1.test.ts`

Expected: 全部通过。

### Task 6: 静态审计与员工手册

- [ ] **Step 1: 审计代码与配置**

优先用 codebase-memory 搜索公开路由、首页/导航/页脚、SEO/GEO、RFQ/Privacy、媒体、下载、配置和初始化函数；仅在字符串/配置/脚本场景用 `rg`。对每项记录证据文件与后台入口缺口，排除普通 UI 标签、错误消息与测试文本。

- [ ] **Step 2: 编写不可编辑内容清单**

创建 `docs/handoff/admin-non-editable-content-audit-r1.md`，按六类列出稳定编号、位置、当前表现、原因、改造建议、P0/P1/P2、是否需真实资料；汇总总数和各优先级数量，明确 Logo 与已批准三款产品图不重复索要。

- [ ] **Step 3: 编写中文手册**

创建 `docs/handoff/demo-admin-chinese-user-manual.md`，覆盖 12 个指定章节，每章包含入口、建议顺序、保存/回读/预览/发布注意点；补充轮播操作、Demo 保护、不要上传客户资料、常见错误。

- [ ] **Step 4: 交叉核对文档**

逐条对照真实后台菜单、字段和状态词；用 `rg` 检查文档无密码、Token、Cookie、私有路径和测试账号。

### Task 7: 独立 TEST ONLY 实际验证

- [ ] **Step 1: 记录并检查测试配置**

记录 HEAD、tracked/untracked diff、lockfile hash、Alembic head、镜像/Compose 文件；确认 TEST 数据库 URL 与常驻 Demo 不同，媒体/缓存独立；不运行 Seed/迁移到主 Demo。

- [ ] **Step 2: 运行真实 PostgreSQL 轮播链**

在独立 PostgreSQL 环境执行：初值 → 后台新增/编辑/排序/停用 → 保存 → fresh GET → 预览 → 应用 → 公开 GET → 恢复；验证错误链接、私有/草稿/未就绪/非图片媒体不能进入保存或公开 DTO。

- [ ] **Step 3: 保存 TEST ONLY 证据并停止测试服务**

证据显式标 `TEST ONLY`，记录容器/数据库名称，停止测试应用但保留所需卷；不把 QA 数据与主 Demo 截图混合。

### Task 8: 主 Demo 配置四项并浏览器验收

- [ ] **Step 1: 安全快照与目标核对**

核对 `junhui-demo-r2` 服务、数据库和共享网关，保存脱敏首页布局快照及数据库备份校验；确认原 `phase37` 容器与卷未改变。

- [ ] **Step 2: 更新受影响 Demo 镜像并安全重开**

只构建/更新 API、Website、Admin 受影响服务；使用现有安全启动链，保留卷，不 Restore、不 Seed、不迁移原 phase37。

- [ ] **Step 3: 通过后台正常操作配置中英文四项**

选择现有 Demo 图片，分别在中文与 English 标签中新增 4 项、保存、fresh GET、预览、应用。文案不写真实参数，图片/文案显式为 Demo。记录每项标题、类型、路径、媒体文件名和 revision。

- [ ] **Step 4: 桌面 1440 真实验收**

流程：打开首页 → 观察首项 → 等待自动切换 → 点击箭头和圆点 → 暂停/播放 → CTA 正常点击 → 核对同源 Demo 域名与目标 H1 → 切英文重复。记录页面 URL、标题、DOM、console、网络和截图。

- [ ] **Step 5: 手机 375 真实验收**

重复主流程，检查标题/副标题/按钮/控件不换行溢出、不遮挡、图片解码和触控按钮可用。

- [ ] **Step 6: 后台 1366/1440 真实验收**

进入首页编辑器，选择 Hero，验证语言切换、图片选择、增改删排启停、保存后预览；截图中脱敏账号和任何浏览器隐私数据。

### Task 9: 统一回归、报告和证据包

- [ ] **Step 1: 运行受影响与组合测试**

Run:

```text
uv run --project apps/api pytest apps/api/tests/test_homepage_presentation_r1.py -q
pnpm --filter @junhui/website test
pnpm --filter @junhui/admin test
pnpm --filter @junhui/website typecheck
pnpm --filter @junhui/admin typecheck
uv run --project apps/api ruff check apps/api/app apps/api/tests
uv run --project apps/api ruff format --check apps/api/app apps/api/tests
pnpm exec prettier --check apps/website apps/admin
pnpm --filter @junhui/website build
pnpm --filter @junhui/admin build
```

逐项记录 exit code、通过/失败/跳过/警告；Ruff format 历史债务与本轮新增问题分开。

- [ ] **Step 2: 生成报告与 readback**

创建根目录 `demo-owner-review-followup-r1-report.md` 和 `demo-owner-review-followup-r1-readback.json`，至少包含四项轮播、后台入口、手册路径、不可编辑总数、P0/P1/P2、必须由 Owner 提供的真实资料、测试结果和未覆盖风险。

- [ ] **Step 3: 生成脱敏证据包**

整理设计稿、前台桌面/手机、后台编辑、公开 DTO 摘要、实际操作链、测试输出、文件校验；排除密码、Token、Cookie、备份、私有 RFQ/客户资料。生成 `Junhui-Demo-Owner-Review-Follow-up-R1-Evidence-<run-id>.zip` 与 SHA256 清单。

- [ ] **Step 4: 最终安全核对**

核对 Demo HTTPS、前台无 Basic 弹窗、后台登录/RBAC/CSRF、noindex/no-store、sitemap 404、Privacy 未发布、RFQ 禁用、原 phase37 未变；保持 Demo 健康运行。

- [ ] **Step 5: 最终 diff 与交付**

运行 `git status --short`、`git diff --stat`、关键文件 SHA256；确认没有 stage/commit/push/merge/deploy；用当前证据如实给出完成、PARTIAL 或 BLOCKED，不宣布全站或生产通过。

