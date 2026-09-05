// 测试用途：复现 Phase 3.6 Remediation 的多来源 RFQ 与单一 main 文档合同。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { rfqUrl } from '../app/composables/useLocalePath'

const appRoot = resolve(process.cwd(), 'app')

describe('Phase 3.6 remediation contracts', () => {
  it.each([
    'product',
    'material',
    'technology',
    'application',
    'solution',
    'case_study',
    'knowledge_article',
    'manufacturing_capability',
    'author_expert',
    'exhibition',
  ] as const)('preserves the approved %s RFQ source', (type) => {
    expect(rfqUrl({ locale: 'en', type, slug: 'qa-source' })).toBe(
      `/en/request-a-quote/?source_type=${type}&source_slug=qa-source`,
    )
  })

  it('keeps the default layout as the only normal-page main landmark', () => {
    const files = [
      'components/LocalePlaceholder.vue',
      'components/ProductListingView.vue',
      'pages/[lang]/products/[category]/[slug].vue',
    ]
    for (const file of files) {
      expect(readFileSync(resolve(appRoot, file), 'utf8'), file).not.toMatch(/<main(?:\s|>)/)
    }
  })

  it('keeps one focusable main-content target in the normal layout', () => {
    const layout = readFileSync(resolve(appRoot, 'layouts/default.vue'), 'utf8')
    expect(layout.match(/id="main-content"/g)).toHaveLength(1)
    expect(layout).toContain('<main id="main-content" tabindex="-1">')
    expect(layout).toContain('href="#main-content"')
  })
})
