// 测试用途：约束 website placeholder 的语言路由与 SEO/GEO 基线。
import { describe, expect, it } from 'vitest'

import { SITE_URL, localePages } from '../app/site-config'

describe('website SSR contract', () => {
  it('uses the frozen canonical host', () => {
    expect(SITE_URL).toBe('https://junhuiscrewbarrel.com')
  })

  it('defines only the two Phase 3.1 locale placeholders', () => {
    expect(Object.keys(localePages)).toEqual(['zh-cn', 'en'])
    expect(localePages['zh-cn'].localeCode).toBe('zh-CN')
    expect(localePages.en.localeCode).toBe('en')
  })

  it('gives each language a self-canonical and reciprocal hreflang links', () => {
    for (const [slug, page] of Object.entries(localePages)) {
      expect(page.canonical).toBe(`${SITE_URL}/${slug}/`)
      expect(page.alternates).toEqual({
        'zh-CN': `${SITE_URL}/zh-cn/`,
        en: `${SITE_URL}/en/`,
      })
    }
  })
})
