// 脚本用途：在真实 localhost 服务上执行 Phase 3.6 有内容浏览器 QA，不启用任何 API mock。
const { chromium } = require('playwright')
const { mkdirSync, writeFileSync } = require('node:fs')

async function runQa(page) {
  const consoleErrors = []
  const network = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    const url = response.url()
    if (url.includes('/api/v1/public/')) {
      network.push({ url: new URL(url).pathname, status: response.status() })
    }
  })

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('http://localhost:8080/en/', { waitUntil: 'networkidle' })
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
    }
  })
  await page.screenshot({
    path: 'artifacts/phase3-6-remediation/home-desktop.png',
    fullPage: true,
  })

  const productHref =
    '/en/products/qa36-remediation-20260905-screws/qa36-remediation-20260905-extrusion-screw/'
  await page.locator(`.product-card a[href="${productHref}"]`).first().click()
  await page.waitForLoadState('networkidle')
  const product = await page.evaluate(() => ({
    h1: document.querySelector('h1')?.textContent?.trim(),
    imageSrc: document.querySelector('main img')?.getAttribute('src'),
    mainCount: document.querySelectorAll('main').length,
    mainContentCount: document.querySelectorAll('#main-content').length,
    h1Count: document.querySelectorAll('h1').length,
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
  await page.goto('http://localhost:8080/en/search/?q=Extrusion', { waitUntil: 'networkidle' })
  const knowledgeHref =
    '/en/knowledge/qa36-remediation-20260905-guides/qa36-remediation-20260905-screw-selection/'
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
      'knowledge_article: qa36-remediation-20260905-screw-selection',
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
  await page.goto(`http://localhost:8080${productHref}`, { waitUntil: 'networkidle' })
  const productZhAlternate = await page
    .locator('link[rel="alternate"][hreflang="zh-CN"]')
    .getAttribute('href')
  await page.goto(
    'http://localhost:8080/en/knowledge/qa36-remediation-20260905-guides/qa36-remediation-20260905-english-only/',
    { waitUntil: 'networkidle' },
  )
  await page.getByRole('button', { name: /language/i }).click()
  const missingTranslationFallback = await page
    .locator('[data-testid="language-options"] a')
    .getAttribute('href')

  // 分页正常可达，越界分页返回 404；随后返回有效列表验证错误恢复。
  const validPage = await page.goto('http://localhost:8080/en/products/?page=2', {
    waitUntil: 'networkidle',
  })
  const validPageCanonical = await page.locator('link[rel="canonical"]').getAttribute('href')
  const outOfRange = await page.goto('http://localhost:8080/en/products/?page=99', {
    waitUntil: 'networkidle',
  })
  await page.goto('http://localhost:8080/en/products/?page=1', { waitUntil: 'networkidle' })
  const recoveredProductCount = await page.locator('.product-card').count()

  // 移动菜单及基本画廊交互可操作；截图作为 320px 响应式证据。
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto(`http://localhost:8080${productHref}`, { waitUntil: 'networkidle' })
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
  return {
    home,
    product,
    productSourceVisible: Boolean(
      sourceContext?.includes('product: qa36-remediation-20260905-extrusion-screw'),
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
      outOfRangeStatus: outOfRange?.status(),
      recoveredProductCount,
    },
    mobileMenuExpanded,
    network: redactedNetwork,
    consoleErrors: consoleErrors.filter(
      (message) => !message.includes('404') || !message.includes('Products not found'),
    ),
    expectedOutOfRangeConsoleObserved: consoleErrors.some(
      (message) => message.includes('404') && message.includes('Products not found'),
    ),
  }
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
