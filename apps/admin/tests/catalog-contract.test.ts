// 测试用途：确保 Structured Core Catalog 最小管理入口不会在重构中丢失。
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('catalog admin routes', () => {
  it('ships the Phase 3.3 entity placeholder pages', () => {
    const pages = ['index', 'categories', 'products', 'specifications', 'materials', 'technologies', 'applications', 'solutions']
    for (const page of pages) {
      expect(existsSync(resolve(process.cwd(), 'app/pages/catalog', `${page}.vue`))).toBe(true)
    }
  })
})
