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
    for (const field of ['quantity', 'material_text', 'screw_diameter', 'machine_brand']) {
      expect(source).toContain(field)
    }
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
})
