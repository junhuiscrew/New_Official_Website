// 测试用途：锁定 Phase 3.5 Remediation 的 Trust、Media、Downloads 与 RFQ 可操作后台。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('phase 3.5 remediation admin', () => {
  it('renders nested Trust editors instead of swallowing their routes', () => {
    const parent = readFileSync(resolve(process.cwd(), 'app/pages/trust.vue'), 'utf8')
    expect(parent).toContain('<NuxtPage')
  })

  it('ships separate real CRUD pages for every Trust family', () => {
    for (const page of [
      'company',
      'capabilities',
      'equipment',
      'certificates',
      'patents',
      'honors',
      'exhibitions',
    ]) {
      const path = resolve(process.cwd(), 'app/pages/trust', `${page}.vue`)
      expect(existsSync(path)).toBe(true)
      if (!existsSync(path)) continue
      const source = readFileSync(path, 'utf8')
      expect(source).toContain('useAuthorityApi')
      expect(source).toContain('noindex, nofollow')
    }
  })

  it('supports real media upload and localized metadata editing', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/media.vue'), 'utf8')
    expect(source).toContain('type="file"')
    expect(source).toContain('/media/assets')
    expect(source).toContain('translations')
    expect(source).toContain('alt_text')
  })

  it('supports download create edit archive and public media selection', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/downloads.vue'), 'utf8')
    expect(source).toContain('/downloads')
    expect(source).toContain('media_asset_id')
    expect(source).toContain('translations')
    expect(source).toContain('archive')
    expect(source).toContain('/downloads/broken-media')
    expect(source).toContain('object_missing')
  })

  it('provides Trust translation review publish and publication archive actions', () => {
    const shared = readFileSync(
      resolve(process.cwd(), 'app/components/trust/TrustCrud.vue'),
      'utf8',
    )
    const company = readFileSync(resolve(process.cwd(), 'app/pages/trust/company.vue'), 'utf8')
    for (const source of [shared, company]) {
      expect(source).toContain('translation_statuses')
      expect(source).toContain('publications')
      expect(source).toContain('/review')
      expect(source).toContain('/publications/')
      expect(source).toContain('published')
      expect(source).toContain('archived')
    }
    expect(shared).toContain('hasIndependentRoute')
    expect(shared).toContain('/translations/${localeId}/publish')
    expect(shared).toContain("translationStatus.status === 'human_reviewed'")
  })

  it('links RFQ list to a detail page with files assignment and signed download', () => {
    const list = readFileSync(resolve(process.cwd(), 'app/pages/rfqs.vue'), 'utf8')
    const detailPath = resolve(process.cwd(), 'app/pages/rfqs/[id].vue')
    expect(list).toContain('/rfqs/${item.id}')
    expect(existsSync(detailPath)).toBe(true)
    if (!existsSync(detailPath)) return
    const detail = readFileSync(detailPath, 'utf8')
    for (const value of [
      'items',
      'files',
      'assigned_to',
      'status',
      'malware_scan_status',
      'download-url',
    ]) {
      expect(detail).toContain(value)
    }
  })
})
