// 测试用途：锁定 Phase 3.4 Authority Content 最小真实 Admin CRUD 与通用编辑器。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('phase 3.4 authority admin', () => {
  it('ships Case, Knowledge, FAQ and Expert real CRUD pages', () => {
    for (const page of ['cases', 'knowledge', 'faqs', 'experts']) {
      const path = resolve(process.cwd(), 'app/pages', `${page}.vue`)
      expect(existsSync(path)).toBe(true)
      if (!existsSync(path)) continue
      expect(readFileSync(path, 'utf8')).toContain('AuthorityCrud')
    }
  })

  it('uses authenticated CSRF API calls for create, patch, archive and relations', () => {
    const path = resolve(process.cwd(), 'app/composables/useAuthorityApi.ts')
    expect(existsSync(path)).toBe(true)
    if (!existsSync(path)) return
    const source = readFileSync(path, 'utf8')
    expect(source).toContain("credentials: 'include'")
    expect(source).toContain('X-CSRF-Token')
    expect(source).toContain("method: 'POST'")
    expect(source).toContain("method: 'PATCH'")
    expect(source).toContain("method: 'PUT'")
  })

  it('provides reusable SEO, GEO and Source editors', () => {
    for (const component of ['SeoEditor', 'GeoEditor', 'SourceCitationEditor']) {
      const path = resolve(process.cwd(), 'app/components/discovery', `${component}.vue`)
      expect(existsSync(path)).toBe(true)
    }
    const geo = readFileSync(
      resolve(process.cwd(), 'app/components/discovery/GeoEditor.vue'),
      'utf8',
    )
    expect(geo).toContain('visible_source_text')
    expect(geo).toContain('direct_answer')
    expect(geo).toContain('key_facts_json')
    expect(geo).toContain('evidence_json')
  })

  it('renders customer privacy controls and real author verification', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )
    expect(source).toContain('client_name_public')
    expect(source).toContain('client_address_public')
    expect(source).toContain('client_logo_public')
    expect(source).toContain('is_real_person_verified')
    expect(source).toContain('public_profile_enabled')
    expect(source).toContain('/relations')
    expect(source).toContain('Publication lifecycle')
    expect(source).toContain('publications/${activeLocaleId.value}')
    expect(source).toContain('translations/${activeLocaleId.value}')
  })
})
