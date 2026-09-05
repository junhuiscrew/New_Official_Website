// 脚本用途：在真实 localhost 服务上执行 Phase 3.6 有内容浏览器 QA，不启用任何 API mock。
const { chromium } = require('playwright')
const { mkdirSync, writeFileSync } = require('node:fs')

const RUN_ID = process.env.PHASE36_QA_RUN_ID || 'remediation-20260905'
const BASE_URL = process.env.PHASE36_QA_BASE_URL || 'http://localhost:8080'

function assertQa(condition, message) {
  if (!condition) throw new Error(`QA assertion failed: ${message}`)
}

async function runQa(page) {
  const consoleErrors = []
  const pageErrors = []
  const network = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
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
    path: 'artifacts/phase3-6-remediation/home-desktop.png',
    fullPage: true,
  })

  const productHref = `/en/products/qa36-${RUN_ID}-screws/qa36-${RUN_ID}-extrusion-screw/`
  await page.locator(`.product-card a[href="${productHref}"]`).first().click()
  await page.waitForLoadState('networkidle')
  const product = await page.evaluate(() => ({
    h1: document.querySelector('h1')?.textContent?.trim(),
    imageSrc: document.querySelector('main img')?.getAttribute('src'),
    imageNaturalWidth: document.querySelector('main img')?.naturalWidth ?? 0,
    mainCount: document.querySelectorAll('main').length,
    mainContentCount: document.querySelectorAll('#main-content').length,
    h1Count: document.querySelectorAll('h1').length,
    specificationCount: document.querySelectorAll('.spec-table tbody tr').length,
    specificationValues: [...document.querySelectorAll('.spec-table tbody td')].map((node) =>
      node.textContent?.trim(),
    ),
  }))
  const rfqHref = await page
    .locator('a[href*="/request-a-quote/"][href*="source_type=product"]')
    .first()
    .getAttribute('href')
  await page.goto(new URL(rfqHref, page.url()).toString(), { waitUntil: 'networkidle' })
  const sourceContext = (await page.locator('.source-context').textContent())?.trim()
  await page.locator('#rfq-company').fill('Phase36 Local QA')
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-email').fill('phase36-qa@example.com')
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
    path: 'artifacts/phase3-6-remediation/rfq-submitted.png',
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
  await page.locator('#rfq-company').fill('Phase36 Knowledge QA')
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-email').fill('phase36-qa-knowledge@example.com')
  await page.locator('#rfq-message').fill('Local-only non-product source persistence QA.')
  await page.locator('.rfq-form__check input[type="checkbox"]').first().check()
  await page.locator('button[type="submit"]').click()
  await page.locator('.status-success').waitFor({ state: 'visible', timeout: 30000 })
  const knowledgeRfqCreated =
    (await page.locator('.status-success .technical-number').count()) === 1

  // 双语详情与缺失翻译回退：首页 alternate 存在，英文单语页回退 zh-cn 首页。
  await page.goto(`${BASE_URL}${productHref}`, { waitUntil: 'networkidle' })
  const productZhAlternate = await page
    .locator('link[rel="alternate"][hreflang="zh-CN"]')
    .getAttribute('href')
  await page.goto(
    `${BASE_URL}/en/knowledge/qa36-${RUN_ID}-guides/qa36-${RUN_ID}-english-only/`,
    { waitUntil: 'networkidle' },
  )
  await page.getByRole('button', { name: /language/i }).click()
  const missingTranslationFallback = await page
    .locator('[data-testid="language-options"] a')
    .getAttribute('href')

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
  await page.locator('#rfq-company').fill('Phase36 Case QA')
  await page.locator('#rfq-contact').fill('Local QA Contact')
  await page.locator('#rfq-email').fill('phase36-qa-case@example.com')
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

  // 移动菜单及基本画廊交互可操作；截图作为 320px 响应式证据。
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto(`${BASE_URL}${productHref}`, { waitUntil: 'networkidle' })
  const mobileToggle = page.locator('[data-testid="mobile-nav-toggle"]')
  await mobileToggle.click()
  await page.locator('[data-testid="mobile-nav"]').waitFor({ state: 'visible' })
  const mobileMenuExpanded =
    (await mobileToggle.getAttribute('aria-expanded')) === 'true' &&
    (await page.locator('[data-testid="mobile-nav"]').count()) === 1
  const galleryButton = page.locator('.product-gallery button').first()
  if (await galleryButton.count()) await galleryButton.click()
  await page.screenshot({
    path: 'artifacts/phase3-6-remediation/product-mobile.png',
    fullPage: true,
  })

  const redactedNetwork = network.map((entry) => ({
    ...entry,
    url: entry.url.replace(/\/public\/rfqs\/[^/]+\/files$/, '/public/rfqs/[REDACTED]/files'),
  }))
  const result = {
    browserVersion: await page.context().browser()?.version(),
    home,
    product,
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
    missingTranslationFallback,
    pagination: {
      validStatus: validPage?.status(),
      validPageCanonical,
      invalidFilterStatus: invalidFilter?.status(),
      zeroResultStatus: zeroResult?.status(),
      outOfRangeStatus: outOfRange?.status(),
      recoveredProductCount,
    },
    mobileMenuExpanded,
    caseSourceVisible,
    caseRfqCreated,
    privateCaseLeak: Boolean(privateCaseLeak),
    viewportSmoke,
    network: redactedNetwork,
    consoleErrors: consoleErrors.filter(
      (message) => !message.includes('404') || !message.includes('Products not found'),
    ),
    pageErrors,
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
  assertQa(result.missingTranslationFallback === '/zh-cn/', 'missing translation fallback')
  assertQa(result.pagination.validStatus === 200, 'valid page 2')
  assertQa(result.pagination.invalidFilterStatus === 404, 'invalid filter 404')
  assertQa(result.pagination.zeroResultStatus === 404, 'zero result 404')
  assertQa(result.pagination.outOfRangeStatus === 404, 'out-of-range 404')
  assertQa(result.pagination.recoveredProductCount > 0, 'pagination recovery')
  assertQa(result.mobileMenuExpanded, 'mobile menu')
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
  assertQa(result.consoleErrors.length === 0, 'no unexpected console errors')
  return result
}

async function main() {
  // 复用机器已安装的稳定 Chrome，避免 QA 过程隐式下载浏览器二进制。
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  try {
    const page = await browser.newPage()
    const result = await runQa(page)
    const output = `${JSON.stringify(result, null, 2)}\n`
    mkdirSync('artifacts/phase3-6-remediation', { recursive: true })
    writeFileSync('artifacts/phase3-6-remediation/browser-qa.json', output, 'utf8')
    process.stdout.write(output)
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
