// 测试用途：确保 Structured Core Catalog 最小管理入口不会在重构中丢失。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('catalog admin routes', () => {
  it('ships all Structured Core Admin pages', () => {
    const pages = [
      'index',
      'categories',
      'products',
      'specifications',
      'materials',
      'technologies',
      'applications',
      'solutions',
    ]
    for (const page of pages) {
      expect(existsSync(resolve(process.cwd(), 'app/pages/catalog', `${page}.vue`))).toBe(true)
    }
  })

  it('implements real Product CRUD, translations, models, relations and specifications', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')
    expect(source).toContain('useCatalogApi')
    expect(source).toContain('TranslationFields')
    expect(source).toContain('api.create')
    expect(source).toContain('api.update')
    expect(source).toContain('/relations')
    expect(source).toContain('/models')
    expect(source).toContain('/specifications/values')
  })

  it('implements real Material CRUD and archive operations', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/materials.vue'), 'utf8')
    const sharedSource = readFileSync(
      resolve(process.cwd(), 'app/components/catalog/EntityCrud.vue'),
      'utf8',
    )
    expect(source).toContain('EntityCrud')
    expect(sharedSource).toContain('useCatalogApi')
    expect(sharedSource).toContain('TranslationFields')
    expect(sharedSource).toContain("method: 'POST'")
    expect(sharedSource).toContain("method: 'PATCH'")
    expect(sharedSource).toContain('/archive')
  })

  it('provides shared cookie, CSRF and translation-tab contracts', () => {
    const apiSource = readFileSync(
      resolve(process.cwd(), 'app/composables/useCatalogApi.ts'),
      'utf8',
    )
    const translationSource = readFileSync(
      resolve(process.cwd(), 'app/components/catalog/TranslationFields.vue'),
      'utf8',
    )
    expect(apiSource).toContain("credentials: 'include'")
    expect(apiSource).toContain('X-CSRF-Token')
    expect(translationSource).toContain('zh-CN')
    expect(translationSource).toContain('en')
  })
})
