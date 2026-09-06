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

  it('submits product primary media, summaries and structured highlights', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')
    expect(source).toContain("api.detail<MediaItem[]>('/media')")
    expect(source).toContain('v-model="form.primary_media_id"')
    expect(source).toContain('short_description')
    expect(source).toContain('highlights_jsonb')
    expect(source).toContain('parseHighlights')
  })

  it('provides real Product translation review and publication actions', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')
    expect(source).toContain('translation_statuses')
    expect(source).toContain('publications')
    expect(source).toContain('reviewTranslation')
    expect(source).toContain('/translations/${localeId}/review')
    expect(source).toContain('transitionPublication')
    expect(source).toContain('/publications/${localeId}/${targetStatus}')
    expect(source).toContain("'published'")
    expect(source).toContain("'archived'")
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

  it('builds exact API payloads for all five specification value types', async () => {
    const utilityPath = resolve(process.cwd(), 'app/utils/specificationValue.ts')
    expect(existsSync(utilityPath)).toBe(true)
    if (!existsSync(utilityPath)) return

    const { buildSpecificationValuePayload } = await import('../app/utils/specificationValue')
    const base = {
      product_id: 'product-id',
      product_model_id: '',
      definition_id: 'definition-id',
      value_text: '316L',
      value_number: 12.5,
      value_min: 10,
      value_max: 15,
      value_boolean: false,
      enum_value: 'A4-80',
    }

    expect(buildSpecificationValuePayload('text', base)).toMatchObject({ value_text: '316L' })
    expect(buildSpecificationValuePayload('number', base)).toMatchObject({ value_number: 12.5 })
    expect(buildSpecificationValuePayload('range', base)).toMatchObject({
      value_min: 10,
      value_max: 15,
    })
    expect(buildSpecificationValuePayload('boolean', base)).toMatchObject({
      value_boolean: false,
    })
    expect(buildSpecificationValuePayload('enum', base)).toMatchObject({ enum_value: 'A4-80' })
  })

  it('renders a dedicated input contract for every specification value type', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/catalog/specifications.vue'),
      'utf8',
    )
    expect(source).toContain('buildSpecificationValuePayload')
    expect(source).toContain("selectedValueType === 'text'")
    expect(source).toContain("selectedValueType === 'number'")
    expect(source).toContain("selectedValueType === 'range'")
    expect(source).toContain("selectedValueType === 'boolean'")
    expect(source).toContain("selectedValueType === 'enum'")
  })

  it('supports specification dictionary maintenance and product value clearing', () => {
    const pageSource = readFileSync(
      resolve(process.cwd(), 'app/pages/catalog/specifications.vue'),
      'utf8',
    )
    const apiSource = readFileSync(
      resolve(process.cwd(), 'app/composables/useCatalogApi.ts'),
      'utf8',
    )

    expect(apiSource).toContain("'DELETE'")
    expect(apiSource).toContain('function remove')
    expect(pageSource).toContain("api.list<ProductItem>('/catalog/products?page_size=100')")
    expect(pageSource).toContain('editGroup')
    expect(pageSource).toContain('editDefinition')
    expect(pageSource).toContain('deleteDefinition')
    expect(pageSource).toContain('loadProductValues')
    expect(pageSource).toContain('updateValue')
    expect(pageSource).toContain('clearValue')
    expect(pageSource).not.toContain('placeholder="Product UUID"')
  })
})
