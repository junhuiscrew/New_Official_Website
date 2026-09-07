// 测试用途：锁定 Products 固定页面的双语 SEO 后台入口与权限边界。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('products SitePage admin', () => {
  const pagePath = resolve(process.cwd(), 'app/pages/site-pages/products.vue')

  it('provides a fixed-key editor without asking operators for UUIDs', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('/discovery/site-pages/products')
    expect(source).toContain('/seo/${activeLanguage.value.locale.code}')
    expect(source).not.toMatch(/owner[_-]?id/i)
    expect(source).not.toContain('UUID')
  })

  it('edits only title and description while displaying lifecycle state', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('seo_title')
    expect(source).toContain('meta_description')
    expect(source).toContain('translation_status')
    expect(source).toContain('publication')
    expect(source).toContain('route')
    expect(source).not.toContain('canonical_override')
    expect(source).not.toContain('robots_index')
    expect(source).not.toContain('/publish')
    expect(source).not.toContain('/review')
    expect(source).toContain("permissions.includes('seo.update')")
    expect(source).toContain(':readonly="!canUpdate"')
    expect(source).toContain(':disabled="saving || !canUpdate"')
    expect(source).toContain('const reloaded = await loadPage()')
    expect(source).toContain('savedSeoMatches')
  })

  it('shows the navigation entry only to seo readers', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'app/app.vue'), 'utf8')
    expect(appSource).toContain("currentUser.permissions.includes('seo.read')")
    expect(appSource).toContain('to="/site-pages/products"')
  })
})
