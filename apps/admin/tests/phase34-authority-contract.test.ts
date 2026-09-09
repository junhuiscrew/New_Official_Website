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
    expect(geo).not.toContain("updateText('visible_source_text'")
    expect(geo).toContain('serverVisibleSourceText')
    expect(geo).toContain('readonly')
    expect(geo).toContain('direct_answer')
    expect(geo).toContain('key_facts_json')
    expect(geo).toContain('evidence_json')

    const authorityCrud = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )
    expect(authorityCrud).toContain(
      "import SeoEditor, { type SeoDraft } from '~/components/discovery/SeoEditor.vue'",
    )
    expect(authorityCrud).toContain(
      "import GeoEditor, { type GeoDraft } from '~/components/discovery/GeoEditor.vue'",
    )
    expect(authorityCrud).toContain('import SourceCitationEditor, {')
    expect(authorityCrud).toContain("} from '~/components/discovery/SourceCitationEditor.vue'")
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
    expect(source).toContain('archivePublication')
    expect(source).toContain("transitionContentPublication('archived')")
    expect(source).toContain('watch(activeLocaleId')
    expect(source).toContain('emptySeoDraft()')
    expect(source).toContain('emptyGeoDraft()')
  })

  it('only exposes the record list after dependent editor data is ready', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )
    const loadIndex = source.indexOf('async function load')
    const resetIndex = source.indexOf('resetForm()', loadIndex)
    const itemAssignmentIndex = source.indexOf('items.value = loadedItems')

    expect(itemAssignmentIndex).toBeGreaterThan(resetIndex)
  })

  it('shows an explicit detail loading state instead of a misleading empty article form', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )

    expect(source).toContain('loadingRecordId')
    expect(source).toContain('正在读取记录')
    expect(source).toContain(':aria-busy="Boolean(loadingRecordId)"')
    expect(source).toContain("'record-list__item--selected'")
  })

  it('whitelists editable SEO and GEO fields when reading and saving documents', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )

    expect(source).toContain('function seoDraftFromDocument')
    expect(source).toContain('function geoDraftFromDocument')
    expect(source).toContain('function geoPayload')
    expect(source).not.toContain('...(geoDocument ?')
  })

  it('reloads lifecycle state by the captured record id instead of a mutable list lookup', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )

    expect(source).toContain('async function reloadSelectedItem')
    expect(source).not.toContain('items.value.find((item) => item.id === selectedId.value)!')
  })

  it('renders the complete publication state machine for routed authority content', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )

    expect(source).toContain('transitionContentPublication')
    expect(source).toContain('Restore draft')
    expect(source).toContain('Submit for review')
    expect(source).toContain("activeLifecycle.publication?.status === 'review'")
    expect(source).toContain("activeLifecycle.publication?.status === 'archived'")
  })

  it('loads readable FAQ labels for relation selectors without exposing UUID entry', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/authority/AuthorityCrud.vue'),
      'utf8',
    )

    expect(source).toContain('async function loadRelationOptions')
    expect(source).toContain("key !== 'faq_ids'")
    expect(source).toContain('`${source.path}/${option.id}`')
  })
})
