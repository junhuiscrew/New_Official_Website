// 测试用途：锁定 Product、Case、Knowledge 最小 SSR 与 SEO/GEO 可见性契约。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const pages = [
  'app/pages/[lang]/products/[category]/[slug].vue',
  'app/pages/[lang]/case-studies/[slug].vue',
  'app/pages/[lang]/knowledge/[category]/[slug].vue',
]

describe('phase 3.4 public SSR pages', () => {
  it('ships all three minimal SSR page families', () => {
    for (const page of pages) expect(existsSync(resolve(process.cwd(), page))).toBe(true)
  })

  it('fetches only the public API and renders canonical, hreflang and JSON-LD', () => {
    for (const page of pages) {
      const source = readFileSync(resolve(process.cwd(), page), 'utf8')
      expect(source).toContain('useApi()')
      expect(source).toContain('useAsyncData')
      expect(source).toContain('canonical')
      expect(source).toContain('hreflang')
      expect(source).toContain('application/ld+json')
      expect(source).toContain('<h1>')
      expect(source).not.toContain('v-html')
    }
  })

  it('renders direct answer, key facts and evidence as user-visible content', () => {
    const componentPath = resolve(process.cwd(), 'app/components/PublicGeoContent.vue')
    expect(existsSync(componentPath)).toBe(true)
    const source = readFileSync(componentPath, 'utf8')
    expect(source).toContain('direct_answer')
    expect(source).toContain('key_facts')
    expect(source).toContain('evidence')
    expect(source).toContain('Evidence')
  })

  it('uses a visible breadcrumb component matching Breadcrumb JSON-LD', () => {
    const path = resolve(process.cwd(), 'app/components/PublicBreadcrumb.vue')
    expect(existsSync(path)).toBe(true)
    expect(readFileSync(path, 'utf8')).toContain('aria-label="Breadcrumb"')
  })
})
