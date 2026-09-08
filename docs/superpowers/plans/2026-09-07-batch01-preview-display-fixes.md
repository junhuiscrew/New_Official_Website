# Batch01 Protected Preview Display Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `phase37-local-https` 内修复 Batch01 图片尺寸、同站语言点击和首页 Hero 字段绑定，同时保持 COPY-V1、发布状态及外层保护不变。

**Architecture:** 媒体层使用 Pillow 对实际对象字节完成解码，以同一服务同时覆盖新上传与受权限/CSRF保护的既有资产元数据刷新；Batch01 幂等复用路径调用该刷新端点。前端仅在语言导航 helper 中把可信正式站来源转换为相对路径，`useHead` 继续消费原 canonical/hreflang；HomePage 直接把公司名和 short_intro 分别绑定为 H1 与摘要。

**Tech Stack:** FastAPI、SQLAlchemy、MinIO、Pillow、pytest；Nuxt 4、Vue 3、TypeScript、Vitest、Playwright；Docker Compose 本地 HTTPS 隔离实例。

---

### Task 1: 媒体真实尺寸与幂等刷新

**Files:**
- Modify: `apps/api/app/modules/media/services.py`
- Modify: `apps/api/app/api/v1/media.py`
- Modify: `apps/api/app/phase37_batch01.py`
- Modify: `apps/api/pyproject.toml`
- Test: `apps/api/tests/test_phase35_foundation.py`
- Test: `apps/api/tests/test_phase35_remediation.py`
- Test: `apps/api/tests/test_phase37_batch01.py`

- [ ] **Step 1: 写真实图片尺寸、损坏图片拒绝、刷新保持不变量及映射复用刷新测试**

```python
metadata = validate_upload_bytes("real.webp", "image/webp", encoded_image)
assert (metadata["width"], metadata["height"]) == (expected_width, expected_height)
```

- [ ] **Step 2: 运行定向 pytest，确认新断言因尺寸缺失/刷新端点缺失而失败**

Run: `pytest tests/test_phase35_foundation.py tests/test_phase35_remediation.py tests/test_phase37_batch01.py -q`

Expected: FAIL，且失败原因指向 `width/height` 或元数据刷新行为不存在。

- [ ] **Step 3: 实现最小真实解码与受保护刷新**

```python
def decode_image_dimensions(content: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(content)) as image:
        image.load()
        return ImageOps.exif_transpose(image).size
```

刷新端点必须核验 public image、对象存在、字节长度和 SHA256；只更新 `width/height`，同值 no-op，变更时写入 `media.metadata_refresh` Audit。

- [ ] **Step 4: 运行定向 pytest 与 Ruff**

Run: `pytest tests/test_phase35_foundation.py tests/test_phase35_remediation.py tests/test_phase37_batch01.py -q`

Run: `ruff check app/modules/media/services.py app/api/v1/media.py app/phase37_batch01.py tests/test_phase35_foundation.py tests/test_phase35_remediation.py tests/test_phase37_batch01.py`

Expected: 全部通过，且没有错误或警告。

### Task 2: 同站语言导航

**Files:**
- Modify: `apps/website/app/composables/useLocalePath.ts`
- Test: `apps/website/tests/phase36-foundation.test.ts`
- Test: `apps/website/tests/phase36-navigation.test.ts`

- [ ] **Step 1: 把正式站 absolute alternate 应转相对路径、外站/非法 scheme 应回退的断言写入测试**

```ts
expect(alternateTarget('en', { en: 'https://junhuiscrewbarrel.com/en/about/' })).toBe('/en/about/')
expect(alternateTarget('en', { en: 'https://example.com/en/about/' })).toBe('/en/')
```

- [ ] **Step 2: 运行定向 Vitest 并确认旧实现失败**

Run: `pnpm --filter @junhui/website test -- tests/phase36-foundation.test.ts tests/phase36-navigation.test.ts`

Expected: FAIL，旧实现仍返回正式站 absolute URL。

- [ ] **Step 3: 在共享 helper 中校验 `SITE_URL` origin 并只返回 path/search/hash**

```ts
const parsed = new URL(candidate, SITE_URL)
return parsed.origin === new URL(SITE_URL).origin ? `${parsed.pathname}${parsed.search}${parsed.hash}` : fallback
```

- [ ] **Step 4: 重跑定向 Vitest、website typecheck 和 build**

Run: `pnpm --filter @junhui/website test -- tests/phase36-foundation.test.ts tests/phase36-navigation.test.ts`

Run: `pnpm --filter @junhui/website typecheck`

Run: `pnpm --filter @junhui/website build`

Expected: 全部退出码 0。

### Task 3: 首页 Hero 字段绑定

**Files:**
- Modify: `apps/website/app/components/HomePage.vue`
- Test: `apps/website/tests/phase36-homepage.test.ts`

- [ ] **Step 1: 先把测试改为公司名 H1、short_intro 摘要**

```ts
expect(wrapper.get('h1').text()).toBe('API Company Name')
expect(wrapper.get('.page-hero__content > p').text()).toBe('API supplied introduction.')
```

- [ ] **Step 2: 运行定向 Vitest 并确认旧绑定失败**

Run: `pnpm --filter @junhui/website test -- tests/phase36-homepage.test.ts`

Expected: FAIL，旧 H1 为 short_intro。

- [ ] **Step 3: 最小调整 HomePage computed 绑定**

```ts
const heroTitle = computed(() => props.home.company?.company_name?.trim() || fallbackTitle)
const heroSummary = computed(() => props.home.company?.short_intro?.trim() || mission || fallbackSummary)
```

- [ ] **Step 4: 重跑首页测试及 Task 2 的 website typecheck/build**

Expected: 全部退出码 0，16 个 COPY-V1 字段没有数据写入。

### Task 4: 隔离实例回填与真实浏览器验收

**Files:**
- Create: `docs/content/phase3-7-batch01-preview-display-fix-report.md`
- Create: `docs/content/phase3-7-batch01-preview-display-fix-checks.json`
- Create outside Git evidence folder: `Junhui-Batch01-Preview-Display-Fix-Evidence-<run_id>/screenshots/*`

- [ ] **Step 1: 保存 IMG-02/03/04 私有前快照并重建受影响的 API/worker/website 容器**

Run: `docker compose --env-file .env.phase37 -p junhui-phase37-pilot -f docker-compose.yml -f docker-compose.phase37.yml up -d --build api worker website nginx`

- [ ] **Step 2: 通过真实账号、权限和 CSRF 调用尺寸刷新端点，并回读不变量/Audit**

只允许 IMG-02/03/04；尺寸由各自对象字节解码，不接收客户端尺寸。

- [ ] **Step 3: 用 Playwright 实际验证桌面、375px、320px、Gallery、焦点及双语点击**

网络请求必须拦截并拒绝任何非 `*.junhui.test` 导航；不触发 RFQ 提交、上传或邮件。

- [ ] **Step 4: 复核 HTTPS、Basic Auth、noindex、Sitemap、旧试点与参数/字段不变量**

Run: existing protected-preview read-only verification and boundary scripts.

- [ ] **Step 5: 生成脱敏报告、JSON、截图 ZIP 并验证哈希、条目及敏感字段扫描**

Expected: ZIP 仅含报告、脱敏 JSON 和真实截图；不含凭据、Cookie、Token、数据库连接、内部 ID 或私有签名 URL。

本计划按用户明确要求在当前会话内执行；不自动 commit、push、merge、部署或清理工作区。
