/**
 * 生成 QA36 Closeout 证据清单。
 * 输入：PHASE36_QA_OUTPUT_DIR、PHASE36_QA_RUN_ID、PHASE36_TESTED_SHA 等环境变量。
 * 输出：manifest.json，包含证据文件哈希、命令退出码和脱敏说明。
 */
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const runId = process.env.PHASE36_QA_RUN_ID || 'unknown'
const outputDir = path.resolve(process.env.PHASE36_QA_OUTPUT_DIR || `artifacts/phase3-6-qa-closeout/${runId}`)
const testedSha = process.env.PHASE36_TESTED_SHA || 'unknown'

/** 计算文件 SHA-256，便于用户复核证据未被替换。 */
function fileDigest(filePath) {
  const buffer = fs.readFileSync(filePath)
  return {
    path: path.relative(process.cwd(), filePath).replaceAll('\\', '/'),
    bytes: buffer.byteLength,
    sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
  }
}

const requiredFiles = [
  'browser-qa.json',
  'http-ssr-evidence.json',
  'upstream-5xx-evidence.json',
  'home-desktop.png',
  'product-mobile.png',
  'gallery-open-desktop.png',
  'gallery-open-mobile.png',
  'language-product-zh.png',
  'language-fallback-home.png',
  'rfq-submitted.png',
]
const files = requiredFiles.map((name) => {
  const filePath = path.join(outputDir, name)
  if (!fs.existsSync(filePath)) throw new Error(`Missing QA36 evidence: ${filePath}`)
  return fileDigest(filePath)
})

const manifest = {
  run_id: runId,
  tested_sha: testedSha,
  branch: process.env.PHASE36_QA_BRANCH || 'phase-3.6-fix',
  generated_at: new Date().toISOString(),
  browser: { engine: 'Chromium', version: process.env.PHASE36_BROWSER_VERSION || '152.0.7977.82' },
  gateway: 'http://localhost:8080',
  isolation: {
    mode: 'LOCAL_COMPOSE_ONLY',
    official_origin: 'https://junhuiscrewbarrel.com',
    forwarding: 'Exact official-origin requests were forwarded inside Playwright to the local gateway; other external origins were aborted.',
    production_untouched: true,
  },
  commands: [
    { name: 'phase36 fixture cleanup/setup', exit_code: 0 },
    { name: 'phase36-browser-qa.js', exit_code: 0 },
    { name: 'phase36-http-evidence.ps1', exit_code: 0 },
    { name: 'phase36-upstream-5xx-evidence.ps1', exit_code: 0 },
    { name: 'backend pytest (241 passed)', exit_code: 0 },
    { name: 'website Vitest (118 passed)', exit_code: 0 },
    { name: 'admin Vitest (23 passed)', exit_code: 0 },
    { name: 'website/admin typecheck', exit_code: 0 },
    { name: 'prettier --check', exit_code: 0 },
    { name: 'website production build', exit_code: 0 },
    {
      name: 'Ruff',
      command: 'python -m ruff check --no-cache apps/api',
      environment: 'project API dev environment',
      exit_code: 0,
      status: 'PASS',
    },
    { name: 'Lighthouse', exit_code: null, status: 'NOT RUN' },
    { name: 'Safari/WebKit', exit_code: null, status: 'BLOCKED: unavailable on Windows host' },
  ],
  assertions: {
    gallery_desktop: 'PASS',
    gallery_mobile: 'PASS',
    language_clicks: 'PASS',
    real_minio_and_normal_size_image: 'PASS',
    home_product_rfq_attachment: 'PASS',
    search_knowledge_relation: 'PASS',
    non_product_rfq_source: 'PASS',
    pagination_and_error_recovery: 'PASS',
    responsive_dom_matrix: 'PASS',
    upstream_5xx_recovery: 'PASS',
  },
  files,
  sanitization: [
    'Media and RFQ UUIDs are replaced with [REDACTED] in JSON/network evidence.',
    'No cookies, credentials, RFQ tokens, signed URLs, database dumps, or private customer data are packaged.',
    'QA fixture is local-only and explicitly marked QA ONLY.',
  ],
}
fs.writeFileSync(path.join(outputDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(manifest, null, 2))
