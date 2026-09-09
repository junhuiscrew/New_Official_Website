// 测试用途：锁定首页模块编辑器、作者预览和全站模块总览的安全合同。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Website Presentation R1 Admin contract', () => {
  it('provides a bilingual module editor without UUID or JSON input', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/homepage.vue'), 'utf8')

    expect(source).toContain('/presentation/homepage/initialize')
    expect(source).toContain('/presentation/homepage/${activeLocaleCode.value}/draft')
    expect(source).toContain('/presentation/homepage/${activeLocaleCode.value}/apply')
    expect(source).toContain('/presentation/homepage/${activeLocaleCode.value}/restore')
    expect(source).toContain('expected_revision')
    expect(source).toContain('data-testid="homepage-module-editor"')
    expect(source).toContain('data-testid="homepage-product-reference"')
    expect(source).toContain('上移')
    expect(source).toContain('下移')
    expect(source).not.toMatch(/owner[_-]?id|UUID|JSON/i)
  })

  it('separates edit, preview and apply permissions', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/homepage.vue'), 'utf8')
    const demoNginx = readFileSync(
      resolve(process.cwd(), '../../infra/nginx/nginx.local-domain-demo-edge.conf'),
      'utf8',
    )

    expect(source).toContain("permissions.includes('content.read')")
    expect(source).toContain("permissions.includes('content.update')")
    expect(source).toContain("permissions.includes('content.publish')")
    expect(source).toContain('`/preview/${activeLanguage.value?.locale.slug')
    expect(source).not.toContain('https://admin.junhuiscrewbarrel.com/preview/')
    expect(demoNginx).toContain('set $demo_website_preview_upstream http://demo-r2-website:3000;')
    expect(demoNginx).toContain('location ^~ /preview/')
  })

  it('provides the site overview and guarded navigation entries', () => {
    const overview = readFileSync(resolve(process.cwd(), 'app/pages/site-overview.vue'), 'utf8')
    const app = readFileSync(resolve(process.cwd(), 'app/app.vue'), 'utf8')

    expect(overview).toContain('/presentation/site-overview/')
    expect(overview).toContain('Technologies')
    expect(overview).toContain('Contact')
    expect(app).toContain('to="/homepage"')
    expect(app).toContain('to="/site-overview"')
    expect(app).toContain("currentUser.permissions.includes('content.read')")
    expect(app).toContain('<ClientOnly>')
  })

  it('keeps hydrated admin content clear of the fixed sidebar', () => {
    const css = readFileSync(resolve(process.cwd(), 'app/assets/css/main.css'), 'utf8')

    expect(css).toContain('.admin-app:has(.admin-sidebar)')
    expect(css).toContain('grid-template-columns: var(--admin-sidebar-width) minmax(0, 1fr)')
  })

  it('uses a compact module navigator, focused properties and a live preview pane', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/homepage.vue'), 'utf8')

    expect(source).toContain('activeModuleKey')
    expect(source).toContain('activeModule')
    expect(source).toContain('homepage-preview-frame')
    expect(source).toContain('module-navigator')
    expect(source).toContain('module-properties')
  })
})
