// 测试用途：确保 Structured Core Catalog 最小管理入口不会在重构中丢失。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('catalog admin routes', () => {
  it('replaces the phase placeholder with a searchable Chinese catalog workspace', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/index.vue'), 'utf8')

    expect(source).toContain('catalogModules')
    expect(source).toContain('moduleSearch')
    expect(source).toContain('内容目录')
    expect(source).toContain('result.value.total')
    expect(source).not.toContain('Phase 3.3 最小模型与发布工作流验证入口')
  })

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

  it('offers a high-density product browser with readable searchable relations', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')
    expect(source).toContain('productSearch')
    expect(source).toContain('selectedCategoryFilter')
    expect(source).toContain('selectedStatusFilter')
    expect(source).toContain('pagedProducts')
    expect(source).toContain('product-media-thumb')
    expect(source).toContain('relationSearch')
    expect(source).toContain('filteredRelationOptions')
    expect(source).toContain('readableItemLabel')
    expect(source).toContain('hydrateNamedItems')
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

  it('explicitly imports the nested translation editor wherever it is rendered', () => {
    for (const path of [
      'app/pages/catalog/categories.vue',
      'app/pages/catalog/products.vue',
      'app/pages/catalog/specifications.vue',
      'app/components/catalog/EntityCrud.vue',
    ]) {
      const source = readFileSync(resolve(process.cwd(), path), 'utf8')
      expect(source).toContain(
        "import TranslationFields from '~/components/catalog/TranslationFields.vue'",
      )
    }
  })

  it('explicitly imports the nested shared entity editor on all four catalog routes', () => {
    for (const name of ['materials', 'technologies', 'applications', 'solutions']) {
      const source = readFileSync(resolve(process.cwd(), `app/pages/catalog/${name}.vue`), 'utf8')
      expect(source).toContain("import EntityCrud from '~/components/catalog/EntityCrud.vue'")
    }
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

    expect(buildSpecificationValuePayload('text', base)).toMatchObject({
      value_text: '316L',
    })
    expect(buildSpecificationValuePayload('number', base)).toMatchObject({
      value_number: 12.5,
    })
    expect(buildSpecificationValuePayload('range', base)).toMatchObject({
      value_min: 10,
      value_max: 15,
    })
    expect(buildSpecificationValuePayload('boolean', base)).toMatchObject({
      value_boolean: false,
    })
    expect(buildSpecificationValuePayload('enum', base)).toMatchObject({
      enum_value: 'A4-80',
    })
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

  it('renders readable product specification names, groups, units and type-specific values', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')

    expect(source).toContain('SpecificationDefinitionItem')
    expect(source).toContain('SpecificationGroupItem')
    expect(source).toContain('readableDefinitionLabel')
    expect(source).toContain('readableGroupLabel')
    expect(source).toContain('default_unit')
    expect(source).toContain('value_type')
    expect(source).toContain('spec-value-card')
    expect(source).toContain("definition.value_type === 'range'")
    expect(source).toContain('buildSpecificationValuePayload')
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

  it('only offers values for enabled definitions in enabled groups', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/catalog/specifications.vue'),
      'utf8',
    )
    expect(source).toContain('availableDefinitions')
    expect(source).toContain("group.status === 'enabled'")
    expect(source).toContain('v-for="item in availableDefinitions"')
  })

  it('keeps the product section navigator below the fixed admin topbar', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/pages/catalog/products.vue'), 'utf8')

    expect(source).toContain('top: 5rem')
    expect(source).toContain('scroll-margin-top:')
  })
})
