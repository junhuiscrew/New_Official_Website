// 测试用途：锁定 Demo About、Contact、RFQ 六页的服务端 SEO 元数据接线。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function pageSource(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('Demo SEO metadata R1', () => {
  it('keeps About metadata owned by the public Company profile', () => {
    const source = pageSource('app/pages/[lang]/about.vue')

    expect(source).toContain('/public/company-profile/${locale.value}')
    expect(source).toContain('page.value.seo.description')
    expect(source).toContain('page.value.seo.canonical')
    expect(source).toContain('page.value.seo.hreflang')
  })

  it.each([
    ['contact', 'contact/index.vue'],
    ['request-a-quote', 'request-a-quote/index.vue'],
  ])('loads %s title, description, canonical and hreflang from a fixed SitePage', (key, file) => {
    const source = pageSource(`app/pages/[lang]/${file}`)

    expect(source).toContain(`/public/site-pages/${key}/`)
    expect(source).toContain('.seo.description')
    expect(source).toContain('.seo.canonical')
    expect(source).toContain('.seo.hreflang')
    expect(source).not.toContain('canonical: route.fullPath')
    expect(source).not.toContain('canonical: route.query')
  })
})
