// 测试用途：锁定 About、Contact、RFQ 的中文后台 SEO 保存与生命周期入口。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Demo SEO metadata R1 admin', () => {
  it('adds fixed Contact and RFQ editors without UUID or JSON input', () => {
    const pagePath = resolve(process.cwd(), 'app/pages/site-pages/[systemKey].vue')
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain("'contact'")
    expect(source).toContain("'request-a-quote'")
    expect(source).toContain('/discovery/site-pages/${pageConfig.systemKey}')
    expect(source).toContain('/seo/${activeLanguage.value.locale.code}')
    expect(source).toContain('/review')
    expect(source).toContain('/publish')
    expect(source).toContain('const reloaded = await loadPage()')
    expect(source).not.toMatch(/owner[_-]?id/i)
    expect(source).not.toContain('<textarea v-model="json')
  })

  it('adds a separate Company SEO save path that does not resave Company body fields', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/trust/company.vue'), 'utf8')

    expect(source).toContain('/discovery/seo/company_profile/')
    expect(source).toContain('saveCompanySeo')
    expect(source).toContain('companySeoDescription')
    expect(source).toContain('const reloadedSeo = await loadCompanySeo')
  })

  it('shows three explicit SEO navigation entries only to SEO readers', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/app.vue'), 'utf8')

    expect(source).toContain('to="/site-pages/products"')
    expect(source).toContain('to="/site-pages/contact"')
    expect(source).toContain('to="/site-pages/request-a-quote"')
    expect(source).toContain("currentUser.permissions.includes('seo.read')")
  })
})
