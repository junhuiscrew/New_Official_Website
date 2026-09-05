// 测试用途：锁定匿名 RFQ 附件和真实 Trust 索引页契约。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('phase 3.5 remediation website', () => {
  it('provides multiple RFQ items and anonymous attachment upload', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/request-a-quote/index.vue'),
      'utf8',
    )
    expect(source).toContain('type="file"')
    expect(source).toContain('multiple')
    expect(source).toContain('submission_token')
    expect(source).toContain('/files')
    expect(source).toContain('removeItem')
    for (const field of [
      'phone',
      'whatsapp',
      'country_code',
      'website',
      'item_type',
      'quantity',
      'material_text',
      'screw_diameter',
      'machine_brand',
    ]) {
      expect(source).toContain(field)
    }
    expect(source).toContain('type="tel"')
    expect(source).toContain('type="url"')
    expect(source).toContain('<select v-model="item.item_type"')
  })

  it('uses lifecycle SEO canonical and strict hreflang on the SSR About page', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/[lang]/about.vue'), 'utf8')
    expect(source).toContain('page.value.seo.canonical')
    expect(source).toContain('page.value.seo.hreflang')
    expect(source).toContain("rel: 'alternate'")
    expect(source).toContain("name: 'robots'")
  })

  it('loads every Trust index from public API without unconfigured fact claims', () => {
    for (const page of ['capabilities', 'certificates', 'patents', 'honors', 'exhibitions']) {
      const source = readFileSync(
        resolve(process.cwd(), 'app/pages/[lang]', page, 'index.vue'),
        'utf8',
      )
      expect(source).toContain('useAsyncData')
      expect(source).toContain('/public/trust/')
      expect(source).not.toContain('Verified certificates')
    }
  })

  it('renders only server-approved equipment from the public Capability DTO', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/capabilities/[slug].vue'),
      'utf8',
    )
    expect(source).toContain('page.equipment')
    expect(source).toContain('equipment.translation.name')
    expect(source).toContain('equipment.translation.public_specs_json')
  })
})
