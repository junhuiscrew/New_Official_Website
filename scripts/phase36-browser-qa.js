// 脚本用途：在真实 localhost 服务上执行 Phase 3.6 有内容浏览器 QA，不启用任何 API mock。
const { chromium } = require('playwright')
const { mkdirSync, writeFileSync } = require('node:fs')

const RUN_ID = process.env.PHASE36_QA_RUN_ID || 'remediation-20260905'
const BASE_URL = process.env.PHASE36_QA_BASE_URL || 'http://localhost:8080'
const LOCAL_ORIGIN = new URL(BASE_URL).origin
const OFFICIAL_ORIGIN = 'https://junhuiscrewbarrel.com'
const OUTPUT_DIR =
  process.env.PHASE36_QA_OUTPUT_DIR || `artifacts/phase3-6-qa-closeout/${RUN_ID}`
const TESTED_IMPLEMENTATION_SHA = process.env.PHASE36_TESTED_SHA || 'unknown'

function outputPath(filename) {
  mkdirSync(OUTPUT_DIR, { recursive: true })
  return `${OUTPUT_DIR}/${filename}`
}

/** 脱敏证据路径中的媒体和 RFQ 内部标识。 */
function redactPath(pathname) {
  return pathname
    .replace(/\/api\/v1\/public\/rfqs\/[^/]+\/files$/, '/api/v1/public/rfqs/[REDACTED]/files')
    .replace(/\/api\/v1\/public\/media\/[^/]+$/, '/api/v1/public/media/[REDACTED]')
}

function assertQa(condition, message) {
  if (!condition) throw new Error(`QA assertion failed: ${message}`)
}

/**
 * 为本地 QA 安装 exact-origin 请求转发。
 *
 * 正式 alternate/canonical 仍保留正式域名；只有浏览器发出的精确正式
 * origin 请求在测试上下文内转发到已确认的本地 Nginx，不接触生产服务。
 */
async function installLocalOriginForwarding(context) {
  const forwarded = []
  const blocked = []
  await context.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (!['http:', 'https:'].includes(url.protocol)) return route.continue()
    if (url.origin === OFFICIAL_ORIGIN) {
      const localUrl = `${LOCAL_ORIGIN}${url.pathname}${url.search}`
      forwarded.push({ path: redactPath(url.pathname), target: LOCAL_ORIGIN })
      try {
        const requestHeaders = {}
        for (const headerName of ['accept', 'accept-language', 'content-type', 'origin', 'referer']) {
          const value = request.headers()[headerName]
          if (value) requestHeaders[headerName] = value
        }
        const response = await fetch(localUrl, {
          method: request.method(),
          headers: requestHeaders,
          body: ['GET', 'HEAD'].includes(request.method()) ? undefined : request.postDataBuffer(),
        })
        const responseHeaders = Object.fromEntries(
          [...response.headers.entries()].filter(
            ([name]) => !['content-length', 'content-encoding', 'transfer-encoding'].includes(name),
          ),
        )
        await route.fulfill({
          status: response.status,
          headers: responseHeaders,
          body: Buffer.from(await response.arrayBuffer()),
        })
      } catch (error) {
        blocked.push({ url: url.pathname, error: String(error) })
        await route.abort()
      }
      return
    }
    if (url.origin === LOCAL_ORIGIN) return route.continue()
    blocked.push({ url: url.origin, error: 'non-allowlisted-origin' })
    await route.abort()
  })
  return { forwarded, blocked }
}

/** 读取完整文档的正式 metadata，证明语言点击后的真实页面状态。 */
async function readLanguageDocument(page) {
  return page.evaluate(() => ({
    url: window.location.href,
    language: document.documentElement.lang,
    heading: document.querySelector('h1')?.textContent?.trim() ?? '',
    canonical: document.querySelector('link[rel="canonical"]')?.getAttribute('href') ?? '',
    hreflang: Object.fromEntries(
      [...document.querySelectorAll('link[rel="alternate"][hreflang]')].map((link) => [
        link.getAttribute('hreflang'),
        link.getAttribute('href'),
      ]),
    ),
  }))
}

/** 通过用户可见语言菜单点击切换语言，不以读取 href 后 goto 代替。 */
async function clickLanguage(page, expectedPath) {
  const toggle = page.locator('.language-switcher > button:visible')
  assertQa((await toggle.count()) === 1, 'visible language toggle exists exactly once')
  await toggle.click()
  const option = page.locator('[data-testid="language-options"] a:visible')
  assertQa((await option.count()) === 1, 'visible language option exists exactly once')
  const href = await option.getAttribute('href')
  const target = new URL(href, page.url())
  assertQa(
    target.origin === OFFICIAL_ORIGIN || target.origin === LOCAL_ORIGIN,
    'language option uses official or isolated local origin',
  )
  assertQa(target.pathname === expectedPath, 'language option points to expected path')
  await Promise.all([
    page.waitForURL(
      (url) =>
        (url.origin === OFFICIAL_ORIGIN || url.origin === LOCAL_ORIGIN) &&
        url.pathname === expectedPath,
    ),
    option.click(),
  ])
  await page.waitForLoadState('networkidle')
  return readLanguageDocument(page)
}

/** 强制执行 Gallery 打开、焦点、Escape 和可见关闭按钮路径。 */
async function exerciseGallery(page, screenshotName, viewport) {
  const opener = page.getByTestId('gallery-open')
  assertQa((await opener.count()) === 1, `${viewport} gallery-open exists exactly once`)
  assertQa(await opener.isVisible(), `${viewport} gallery-open is visible`)
  assertQa(await opener.isEnabled(), `${viewport} gallery-open is enabled`)
  const sourceImage = page.locator('main img').first()
  const sourceDimensions = await sourceImage.evaluate((image) => ({
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
    displayedWidth: image.getBoundingClientRect().width,
    displayedHeight: image.getBoundingClientRect().height,
  }))
  assertQa(sourceDimensions.naturalWidth === 1200, `${viewport} source image width`)
  assertQa(sourceDimensions.naturalHeight === 800, `${viewport} source image height`)

  await opener.click()
  const dialog = page.locator('dialog[role="dialog"]')
  await dialog.waitFor({ state: 'visible' })
  const opened = await dialog.evaluate((element) => ({
    open: (element instanceof HTMLDialogElement && element.open) || element.hasAttribute('open'),
    focusedInside: element.contains(document.activeElement),
  }))
  const dialogImage = dialog.locator('img').first()
  const dialogImageState = await dialogImage.evaluate((image) => ({
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
    displayedWidth: image.getBoundingClientRect().width,
    displayedHeight: image.getBoundingClientRect().height,
    alt: image.getAttribute('alt') ?? '',
  }))
  const closeButton = dialog.getByRole('button', { name: /close|关闭/i })
  assertQa(opened.open && opened.focusedInside, `${viewport} dialog open/focus`)
  assertQa(await dialogImage.isVisible(), `${viewport} dialog image visible`)
  assertQa(dialogImageState.naturalWidth === 1200, `${viewport} dialog image width`)
  assertQa(dialogImageState.naturalHeight === 800, `${viewport} dialog image height`)
  assertQa(await closeButton.isVisible(), `${viewport} visible dialog close button`)
  await page.keyboard.press('Tab')
  const tabFocusInside = await dialog.evaluate((element) => element.contains(document.activeElement))
  await page.keyboard.press('Shift+Tab')
  const reverseTabFocusInside = await dialog.evaluate((element) => element.contains(document.activeElement))
  await page.screenshot({ path: outputPath(screenshotName), fullPage: true })

  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'hidden' })
  const escapeClosed = !(await dialog.isVisible())
  const escapeFocusReturned = await opener.evaluate((element) => document.activeElement === element)

  await opener.click()
  await dialog.waitFor({ state: 'visible' })
  await dialog.getByRole('button', { name: /close|关闭/i }).click()
  await dialog.waitFor({ state: 'hidden' })
  const buttonClosed = !(await dialog.isVisible())
  const buttonFocusReturned = await opener.evaluate((element) => document.activeElement === element)
  assertQa(tabFocusInside && reverseTabFocusInside, `${viewport} dialog focus trap`)
  assertQa(escapeClosed && escapeFocusReturned, `${viewport} Escape close/focus return`)
  assertQa(buttonClosed && buttonFocusReturned, `${viewport} visible close/focus return`)
  return {
    viewport,
    opener: { count: await opener.count(), visible: true, enabled: true },
    sourceDimensions,
    dialog: { ...opened, ...dialogImageState, tabFocusInside, reverseTabFocusInside },
    escapeClosed,
    escapeFocusReturned,
    buttonClosed,
    buttonFocusReturned,
    screenshot: outputPath(screenshotName),
  }
}

async function runQa(page, forwarding) {
  const consoleErrors = []
  const pageErrors = []
  const network = []
  const requestFailures = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('requestfailed', (request) =>
    requestFailures.push({ url: new URL(request.url()).pathname, failure: request.failure()?.errorText }),
  )
  page.on('response', (response) => {
    const url = response.url()
    if (url.includes('/api/v1/public/')) {
      network.push({ url: new URL(url).pathname, status: response.status() })
    }
  })

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${BASE_URL}/en/`, { waitUntil: 'networkidle' })
  const home = await page.evaluate(() => {
    const ids = [...document.querySelectorAll('[id]')].map((node) => node.id)
    return {
      title: document.title,
      canonical: document.querySelector('link[rel="canonical"]')?.getAttribute('href'),
      description: document.querySelector('meta[name="description"]')?.getAttribute('content'),
      schemas: document.querySelectorAll('script[type="application/ld+json"]').length,
      mainCount: document.querySelectorAll('main').length,
      mainContentCount: document.querySelectorAll('#main-content').length,
      h1Count: document.querySelectorAll('h1').length,
      duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index),
      skipTarget: document.querySelector('a[href="#main-content"]')?.getAttribute('href'),
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    }
  })
  await page.screenshot({
    path: outputPath('home-desktop.png'),
    fullPage: true,
  })

  const productHref = `/en/products/qa36-${RUN_ID}-screws/qa36-${RUN_ID}-extrusion-screw/`
  await page.locator(`.product-card a[href="${productHref}"]`).first().click()
  await page.waitForLoadState('networkidle')
  const product = await page.evaluate(() => ({
    h1: document.querySelector('h1')?.textContent?.trim(),
    imageSrc: document.querySelector('main img')?.getAttribute('src'),
    imageNaturalWidth: document.querySelector('main img')?.naturalWidth ?? 0,
    imageNaturalHeight: document.querySelector('main img')?.naturalHeight ?? 0,
    imageDisplayedWidth: document.querySelector('main img')?.getBoundingClientRect().width ?? 0,
    imageDisplayedHeight: document.querySelector('main img')?.getBoundingClientRect().height ?? 0,
    mainCount: document.querySelectorAll('main').length,
    mainContentCount: document.querySelectorAll('#main-content').length,
    h1Count: document.querySelectorAll('h1').length,
    specificationCount: document.querySelectorAll('.spec-table tbody tr').length,
    specificationValues: [...document.querySelectorAll('.spec-table tbody td')].map((node) =>
      node.textContent?.trim(),
    ),
  }))
  const desktopGallery = await exerciseGallery(page, 'gallery-open-desktop.png', 'desktop-1440')
  const rfqHref = await page
    .locator('a[href*="/request-a-quote/"][href*="source_type=product"]')
    .first()
    .getAttribute('href')
  await page.goto(new URL(rfqHref, page.url()).toString(), { waitUntil: 'networkidle' })
  const sourceContext = (await page.locator('.source-context').textContent())?.trim()
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-company').fill(`Phase36 ${RUN_ID} Product QA`)
  await page.locator('#rfq-email').fill(`phase36-${RUN_ID}-product@example.com`)
  await page.locator('#rfq-phone').fill('+86 000 0000 0000')
  await page.locator('#rfq-country').fill('CN')
  await page.locator('#rfq-message').fill('Local-only Phase 3.6 remediation browser QA.')
  await page.locator('fieldset').nth(1).locator('button').last().click()
  await page.locator('#rfq-product-1').fill('Second local QA item')
  await page.locator('#rfq-quantity-1').fill('2')
  await page.locator('#rfq-files').setInputFiles('apps/website/public/brand/junhui-mark.png')
  await page.locator('.rfq-form__check input[type="checkbox"]').first().check()
  await page.locator('button[type="submit"]').click()
  await page.locator('.status-success').waitFor({ state: 'visible', timeout: 30000 })
  await page.locator('.upload-status--uploaded').waitFor({ state: 'visible', timeout: 30000 })
  const successReferenceVisible =
    (await page.locator('.status-success .technical-number').count()) === 1
  // 截图落盘前覆盖公开编号；提交 token 从不进入 DOM 或此脚本结果。
  await page
    .locator('.status-success .technical-number')
    .evaluate((node) => (node.textContent = '[REDACTED]'))
  await page.screenshot({
    path: outputPath('rfq-submitted.png'),
    fullPage: true,
  })
  const secondItemPresent = (await page.locator('#rfq-product-1').count()) === 1

  // Search → Knowledge → Product，验证关系链接来自真实 Public DTO。
  await page.goto(`${BASE_URL}/en/search/?q=Extrusion`, { waitUntil: 'networkidle' })
  const knowledgeHref = `/en/knowledge/qa36-${RUN_ID}-guides/qa36-${RUN_ID}-screw-selection/`
  await page.locator(`a[href="${knowledgeHref}"]`).first().click()
  await page.waitForLoadState('networkidle')
  const relatedProductVisible = (await page.locator(`a[href="${productHref}"]`).count()) > 0
  const knowledgeRfqHref = await page
    .locator('a[href*="source_type=knowledge_article"]')
    .first()
    .getAttribute('href')
  await page.goto(new URL(knowledgeRfqHref, page.url()).toString(), { waitUntil: 'networkidle' })
  const knowledgeSourceVisible =
    (await page.locator('.source-context').textContent())?.includes(
      `knowledge_article: qa36-${RUN_ID}-screw-selection`,
    ) ?? false
  await page.locator('#rfq-company').fill(`Phase36 ${RUN_ID} Knowledge QA`)
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-email').fill(`phase36-${RUN_ID}-knowledge@example.com`)
  await page.locator('#rfq-message').fill('Local-only non-product source persistence QA.')
  await page.locator('.rfq-form__check input[type="checkbox"]').first().check()
  await page.locator('button[type="submit"]').click()
  await page.locator('.status-success').waitFor({ state: 'visible', timeout: 30000 })
  const knowledgeRfqCreated =
    (await page.locator('.status-success .technical-number').count()) === 1

  // 双语详情与缺失翻译回退：通过用户可见语言菜单真实点击，不使用 goto 替代。
  await page.goto(`${BASE_URL}${productHref}`, { waitUntil: 'networkidle' })
  const productZhAlternate = await page
    .locator('link[rel="alternate"][hreflang="zh-CN"]')
    .getAttribute('href')
  const chineseProductPath = new URL(productZhAlternate).pathname
  const chineseProduct = await clickLanguage(page, chineseProductPath)
  assertQa(chineseProduct.language.toLowerCase().startsWith('zh'), 'clicked Chinese document lang')
  assertQa(chineseProduct.heading.includes('螺杆'), 'clicked Chinese product heading')
  assertQa(chineseProduct.canonical === productZhAlternate, 'clicked Chinese self canonical')
  await page.screenshot({ path: outputPath('language-product-zh.png'), fullPage: true })
  const englishProduct = await clickLanguage(page, productHref)
  assertQa(englishProduct.language.toLowerCase().startsWith('en'), 'clicked English document lang')
  assertQa(englishProduct.url.endsWith(productHref), 'clicked English product URL')

  await page.goto(
    `${BASE_URL}/en/knowledge/qa36-${RUN_ID}-guides/qa36-${RUN_ID}-english-only/`,
    { waitUntil: 'networkidle' },
  )
  const missingTranslationFallback = await clickLanguage(page, '/zh-cn/')
  assertQa(missingTranslationFallback.url.endsWith('/zh-cn/'), 'clicked missing translation fallback URL')
  assertQa(missingTranslationFallback.language.toLowerCase().startsWith('zh'), 'clicked fallback document lang')
  await page.screenshot({ path: outputPath('language-fallback-home.png'), fullPage: true })

  // 分页正常可达，越界分页返回 404；随后返回有效列表验证错误恢复。
  const validPage = await page.goto(`${BASE_URL}/en/products/?page=2`, {
    waitUntil: 'networkidle',
  })
  const validPageCanonical = await page.locator('link[rel="canonical"]').getAttribute('href')
  const invalidFilter = await page.goto(`${BASE_URL}/en/products/?material=missing-filter`, {
    waitUntil: 'networkidle',
  })
  const zeroResult = await page.goto(
    `${BASE_URL}/en/products/?material=qa36-${RUN_ID}-unmatched-material`,
    { waitUntil: 'networkidle' },
  )
  const outOfRange = await page.goto(`${BASE_URL}/en/products/?page=99`, {
    waitUntil: 'networkidle',
  })
  await page.goto(`${BASE_URL}/en/products/?page=1`, { waitUntil: 'networkidle' })
  const recoveredProductCount = await page.locator('.product-card').count()

  // 匿名 Case → RFQ，证明非 Product CTA 不只停留在 query 字符串。
  const caseHref = `/en/case-studies/qa36-${RUN_ID}-anonymous-case/`
  await page.goto(`${BASE_URL}${caseHref}`, { waitUntil: 'networkidle' })
  const privateCaseLeak = (await page.locator('body').textContent())?.includes('QA PRIVATE CLIENT')
  const caseRfqHref = await page
    .locator('a[href*="source_type=case_study"]')
    .first()
    .getAttribute('href')
  await page.goto(new URL(caseRfqHref, page.url()).toString(), { waitUntil: 'networkidle' })
  const caseSourceVisible =
    (await page.locator('.source-context').textContent())?.includes(
      `case_study: qa36-${RUN_ID}-anonymous-case`,
    ) ?? false
  await page.locator('#rfq-company').fill(`Phase36 ${RUN_ID} Case QA`)
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-email').fill(`phase36-${RUN_ID}-case@example.com`)
  await page.locator('#rfq-message').fill('Local-only Case source persistence QA.')
  await page.locator('.rfq-form__check input[type="checkbox"]').first().check()
  await page.locator('button[type="submit"]').click()
  await page.locator('.status-success').waitFor({ state: 'visible', timeout: 30000 })
  const caseRfqCreated = (await page.locator('.status-success .technical-number').count()) === 1

  // 首页与代表产品覆盖全部冻结宽度，检查文档级溢出和结构地标。
  const viewportSmoke = []
  for (const width of [320, 375, 430, 768, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: width < 768 ? 800 : 1000 })
    for (const path of ['/en/', productHref]) {
      const response = await page.goto(`${BASE_URL}${path}`, { waitUntil: 'networkidle' })
      const dom = await page.evaluate(() => ({
        mainCount: document.querySelectorAll('main').length,
        h1Count: document.querySelectorAll('h1').length,
        duplicateMainId: document.querySelectorAll('#main-content').length,
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      }))
      viewportSmoke.push({ width, path, status: response?.status(), ...dom })
    }
  }

  // 移动菜单、移动端语言点击及 Gallery 强制交互；截图保存真实打开状态。
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto(`${BASE_URL}/en/`, { waitUntil: 'networkidle' })
  const mobileToggle = page.locator('[data-testid="mobile-nav-toggle"]')
  await mobileToggle.click()
  await page.locator('[data-testid="mobile-nav"]').waitFor({ state: 'visible' })
  const mobileMenuExpanded =
    (await mobileToggle.getAttribute('aria-expanded')) === 'true' &&
    (await page.locator('[data-testid="mobile-nav"]').count()) === 1
  const productAccordion = page.locator('[data-testid="mobile-products-toggle"]')
  assertQa((await productAccordion.count()) === 1, 'mobile Products accordion exists')
  await productAccordion.click()
  await page.locator('[data-testid="mobile-nav"] a[href="/en/products/"]').first().click()
  await page.waitForLoadState('networkidle')
  await page.locator(`.product-card a[href="${productHref}"]`).first().click()
  await page.waitForLoadState('networkidle')
  const mobileGallery = await exerciseGallery(page, 'gallery-open-mobile.png', 'mobile-320')
  await page.screenshot({ path: outputPath('product-mobile.png'), fullPage: true })
  const mobileRfqHref = await page
    .locator('a[href*="/request-a-quote/"][href*="source_type=product"]')
    .first()
    .getAttribute('href')

  await page.goto(`${BASE_URL}/en/`, { waitUntil: 'networkidle' })
  await page.locator('[data-testid="mobile-nav-toggle"]').click()
  await page.locator('[data-testid="mobile-nav"]').waitFor({ state: 'visible' })
  const mobileLanguage = page.locator('[data-testid="mobile-nav"] .language-switcher > button:visible')
  assertQa((await mobileLanguage.count()) === 1, 'mobile language toggle exists exactly once')
  await mobileLanguage.click()
  const mobileLanguageOption = page.locator('[data-testid="mobile-nav"] [data-testid="language-options"] a:visible')
  assertQa((await mobileLanguageOption.count()) === 1, 'mobile language option exists exactly once')
  const mobileLanguageHref = await mobileLanguageOption.getAttribute('href')
  const mobileLanguageTarget = new URL(mobileLanguageHref, page.url())
  assertQa(
    mobileLanguageTarget.origin === OFFICIAL_ORIGIN || mobileLanguageTarget.origin === LOCAL_ORIGIN,
    'mobile language official or isolated local origin',
  )
  await Promise.all([
    page.waitForURL(
      (url) =>
        (url.origin === OFFICIAL_ORIGIN || url.origin === LOCAL_ORIGIN) &&
        url.pathname === '/zh-cn/',
    ),
    mobileLanguageOption.click(),
  ])
  await page.waitForLoadState('networkidle')
  const mobileLanguageResult = await readLanguageDocument(page)
  assertQa(mobileLanguageResult.language.toLowerCase().startsWith('zh'), 'mobile language target')

  await page.goto(new URL(mobileRfqHref, BASE_URL).toString(), { waitUntil: 'networkidle' })
  const mobileRfqSourceVisible =
    (await page.locator('.source-context').textContent())?.includes(
      `product: qa36-${RUN_ID}-extrusion-screw`,
    ) ?? false

  const redactedNetwork = network.map((entry) => ({
    ...entry,
    url: entry.url
      .replace(/\/public\/rfqs\/[^/]+\/files$/, '/public/rfqs/[REDACTED]/files')
      .replace(/\/public\/media\/[^/]+$/, '/public/media/[REDACTED]'),
  }))
  const result = {
    browserVersion: await page.context().browser()?.version(),
    home,
    product: {
      ...product,
      imageSrc: product.imageSrc?.replace(/\/public\/media\/[^/]+$/, '/public/media/[REDACTED]'),
    },
    productSourceVisible: Boolean(
      sourceContext?.includes(`product: qa36-${RUN_ID}-extrusion-screw`),
    ),
    secondItemPresent,
    successReferenceVisible,
    attachmentUploaded: redactedNetwork.some(
      (entry) =>
        entry.url.includes('/public/rfqs/') && entry.url.endsWith('/files') && entry.status === 201,
    ),
    rfqCreated: redactedNetwork.some(
      (entry) => entry.url.endsWith('/public/rfqs') && entry.status === 201,
    ),
    relatedProductVisible,
    knowledgeSourceVisible,
    knowledgeRfqCreated,
    productZhAlternate,
    runId: RUN_ID,
    testedImplementationSha: TESTED_IMPLEMENTATION_SHA,
    chineseProduct: {
      status: 200,
      ...chineseProduct,
    },
    englishProduct,
    missingTranslationFallback,
    mobileLanguage: mobileLanguageResult,
    gallery: { desktop: desktopGallery, mobile: mobileGallery },
    pagination: {
      validStatus: validPage?.status(),
      validPageCanonical,
      invalidFilterStatus: invalidFilter?.status(),
      zeroResultStatus: zeroResult?.status(),
      outOfRangeStatus: outOfRange?.status(),
      recoveredProductCount,
    },
    mobileMenuExpanded,
    mobileRfqSourceVisible,
    caseSourceVisible,
    caseRfqCreated,
    privateCaseLeak: Boolean(privateCaseLeak),
    viewportSmoke,
    network: redactedNetwork,
    requestFailures,
    consoleErrors,
    unexpectedConsoleErrors: consoleErrors.filter(
      (message) => !(message.includes('404') && message.includes('Products not found')),
    ),
    pageErrors,
    localOriginForwarding: forwarding.forwarded,
    blockedExternalRequests: forwarding.blocked,
    expectedOutOfRangeConsoleObserved: consoleErrors.some(
      (message) => message.includes('404') && message.includes('Products not found'),
    ),
  }
  assertQa(result.home.mainCount === 1 && result.home.mainContentCount === 1, 'home landmarks')
  assertQa(result.home.h1Count === 1 && result.home.duplicateIds.length === 0, 'home heading/ids')
  assertQa(Boolean(result.home.description && result.home.canonical), 'home SEO')
  assertQa(result.product.mainCount === 1 && result.product.h1Count === 1, 'product landmarks')
  assertQa(result.product.imageNaturalWidth > 0, 'real public image decoded')
  assertQa(result.product.specificationCount === 5, 'all five specifications rendered')
  assertQa(result.productSourceVisible && result.rfqCreated, 'product RFQ source')
  assertQa(result.secondItemPresent && result.attachmentUploaded, 'multi-item private attachment')
  assertQa(result.relatedProductVisible && result.knowledgeSourceVisible, 'knowledge relation/source')
  assertQa(result.knowledgeRfqCreated, 'knowledge RFQ created')
  assertQa(result.caseSourceVisible && result.caseRfqCreated, 'case RFQ created')
  assertQa(!result.privateCaseLeak, 'anonymous Case privacy')
  assertQa(Boolean(result.productZhAlternate), 'bilingual alternate')
  assertQa(result.chineseProduct.status === 200, 'Chinese product HTTP')
  assertQa(result.chineseProduct.language.toLowerCase().startsWith('zh'), 'Chinese document lang')
  assertQa(Boolean(result.chineseProduct.heading?.includes('螺杆')), 'Chinese product heading')
  assertQa(result.chineseProduct.canonical === result.productZhAlternate, 'Chinese self canonical')
  assertQa(Boolean(result.chineseProduct.hreflang?.en), 'Chinese English alternate')
  assertQa(result.missingTranslationFallback.url.endsWith('/zh-cn/'), 'missing translation fallback')
  assertQa(result.pagination.validStatus === 200, 'valid page 2')
  assertQa(result.pagination.invalidFilterStatus === 404, 'invalid filter 404')
  assertQa(result.pagination.zeroResultStatus === 404, 'zero result 404')
  assertQa(result.pagination.outOfRangeStatus === 404, 'out-of-range 404')
  assertQa(result.pagination.recoveredProductCount > 0, 'pagination recovery')
  assertQa(result.mobileMenuExpanded, 'mobile menu')
  assertQa(result.mobileRfqSourceVisible, 'mobile menu to product/gallery/RFQ journey')
  assertQa(result.viewportSmoke.every((item) => item.status === 200), 'viewport HTTP')
  assertQa(
    result.viewportSmoke.every(
      (item) =>
        item.mainCount === 1 &&
        item.h1Count === 1 &&
        item.duplicateMainId === 1 &&
        !item.horizontalOverflow,
    ),
    'viewport DOM/overflow',
  )
  assertQa(result.pageErrors.length === 0, 'no browser pageerror')
  assertQa(result.unexpectedConsoleErrors.length === 0, 'no unexpected console errors')
  assertQa(result.requestFailures.length === 0, 'no failed browser requests')
  assertQa(result.blockedExternalRequests.length === 0, 'no external requests')
  return result
}

async function main() {
  // 复用机器已安装的稳定 Chrome，避免 QA 过程隐式下载浏览器二进制。
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  try {
    const context = await browser.newContext()
    const forwarding = await installLocalOriginForwarding(context)
    const page = await context.newPage()
    const result = await runQa(page, forwarding)
    const output = `${JSON.stringify(result, null, 2)}\n`
    writeFileSync(outputPath('browser-qa.json'), output, 'utf8')
    process.stdout.write(output)
    await context.close()
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
