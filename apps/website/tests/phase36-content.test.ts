// 测试用途：锁定 Phase 3.6 四类目录列表/详情、公开关系、可见 GEO 与询价来源契约。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import type { PublicLinkDto } from '../app/types/public'

import PaginationNav from '../app/components/PaginationNav.vue'

enableAutoUnmount(afterEach)

const contentFamilies = [
  { resource: 'materials', sourceType: 'material' },
  { resource: 'technologies', sourceType: 'technology' },
  { resource: 'applications', sourceType: 'application' },
  { resource: 'solutions', sourceType: 'solution' },
] as const

/** 读取 Website 文件；文件尚未创建时返回空字符串，使 RED 阶段产生清晰断言失败。 */
function sourceAt(relativePath: string): string {
  const absolutePath = resolve(process.cwd(), relativePath)
  return existsSync(absolutePath) ? readFileSync(absolutePath, 'utf8') : ''
}

/** 构造已经由后端发布门禁批准的 canonical Link DTO。 */
function publishedLink(overrides: Partial<PublicLinkDto> = {}): PublicLinkDto {
  return {
    type: 'product',
    slug: 'precision-screw',
    name: 'Precision Screw',
    url: '/en/products/injection/precision-screw/',
    summary: 'Published relation summary.',
    ...overrides,
  }
}

describe('Phase 3.6 catalog page system', () => {
  it('generates pagination hrefs that match backend canonical URL normalization', () => {
    const wrapper = mount(PaginationNav, {
      props: {
        locale: 'en',
        basePath: '/en/materials/',
        page: 2,
        pages: 3,
        pageSize: 24,
      },
    })

    const previous = wrapper.get('a[rel="prev"]').attributes('href')
    const current = wrapper.get('a[aria-current="page"]').attributes('href')
    const next = wrapper.get('a[rel="next"]').attributes('href')
    expect(previous).toBe('/en/materials/')
    expect(current).toBe('/en/materials/?page=2')
    expect(next).toBe('/en/materials/?page=3')
  })

  it('windows large pagination sets and localizes the navigation landmark', () => {
    const wrapper = mount(PaginationNav, {
      props: {
        locale: 'zh-cn',
        basePath: '/zh-cn/materials/',
        page: 5000,
        pages: 10000,
        pageSize: 24,
      },
    })

    const hrefs = wrapper.findAll('a').map((anchor) => anchor.attributes('href'))
    expect(wrapper.get('nav').attributes('aria-label')).toBe('分页')
    expect(hrefs.length).toBeLessThanOrEqual(9)
    expect(hrefs).toContain('/zh-cn/materials/')
    expect(hrefs).toContain('/zh-cn/materials/?page=5000')
    expect(hrefs).toContain('/zh-cn/materials/?page=10000')
    expect(wrapper.findAll('[aria-hidden="true"]')).toHaveLength(2)
  })

  it('creates all four list/detail routes from one typed SSR page shell', () => {
    for (const family of contentFamilies) {
      const listSource = sourceAt(`app/pages/[lang]/${family.resource}/index.vue`)
      const detailSource = sourceAt(`app/pages/[lang]/${family.resource}/[slug].vue`)

      expect(listSource).toContain(
        `<PublicCatalogEntityPage resource="${family.resource}" mode="list" />`,
      )
      expect(detailSource).toContain(
        `<PublicCatalogEntityPage resource="${family.resource}" mode="detail" />`,
      )
    }

    const shell = sourceAt('app/components/PublicCatalogEntityPage.vue')
    expect(shell).toContain('satisfies Record<CatalogResource, CatalogPageConfig>')
    expect(shell).toContain('await useAsyncData')
    expect(shell).toContain('const requestKey = computed')
    expect(shell).toContain('const locale = computed')
    expect(shell).toContain('const slug = computed')
    expect(shell).not.toContain('route.fullPath')
    expect(shell).toContain('route.query.page')
    expect(shell).toContain('page_size')
    expect(shell).toContain('48')
    expect(shell).not.toContain('onMounted')
  })

  it('renders one H1, a visible breadcrumb, early answer, empty state, and canonical pagination', () => {
    const shell = sourceAt('app/components/PublicCatalogEntityPage.vue')

    expect(shell.match(/<h1\b/g)).toHaveLength(1)
    expect(shell).not.toContain('<main')
    expect(shell).not.toContain('id="main-content"')
    expect(shell).toContain('<PublicBreadcrumb')
    expect(shell).toContain('<GeoAnswer')
    expect(shell).toContain('<EmptyState')
    expect(shell).toContain('<PaginationNav')
    expect(shell).toContain(':href="item.url"')
    expect(shell.indexOf('<GeoAnswer')).toBeLessThan(shell.indexOf('catalog-page__sections'))
  })

  it('maps explicit semantic DTO fields and never iterates arbitrary translation keys', () => {
    const shell = sourceAt('app/components/PublicCatalogEntityPage.vue')

    for (const field of [
      'definition',
      'processing_characteristics',
      'screw_impact',
      'recommendations',
      'limitations',
      'process_description',
      'benefits',
      'description',
      'technical_requirements',
      'common_problems',
      'symptoms',
      'causes',
      'diagnosis',
      'solution',
    ]) {
      expect(shell).toContain(field)
    }
    expect(shell).not.toMatch(/Object\.(?:entries|keys|values)\([^)]*translation/)
    expect(shell).not.toMatch(/v-for="[^\"]+\sin\spage\.translation/)
    expect(shell).not.toContain('<pre')
    expect(shell).not.toContain('JSON.stringify')
  })

  it('distinguishes 404 from 500 and consumes only backend SEO, alternates, and schema', () => {
    const shell = sourceAt('app/components/PublicCatalogEntityPage.vue')

    expect(shell).toContain('error.value?.statusCode === 404 ? 404 : 500')
    expect(shell).toContain('page.value.seo.canonical')
    expect(shell).toContain('page.value.alternates')
    expect(shell).toContain('serializeJsonLd(page.value.schema)')
    expect(shell).not.toMatch(/['"]@type['"]\s*:/)
  })

  it('preserves a localized RFQ source for every content family', () => {
    const shell = sourceAt('app/components/PublicCatalogEntityPage.vue')

    expect(shell).toContain('<RfqCta')
    expect(shell).toContain(':source-type="config.sourceType"')
    expect(shell).toContain(':source-slug="page.slug"')
    for (const family of contentFamilies)
      expect(shell).toContain(`sourceType: '${family.sourceType}'`)
  })
})

describe('Phase 3.6 approved relation anchors', () => {
  it('renders only whitelisted backend groups and uses the supplied canonical URL', async () => {
    const componentPath = resolve(process.cwd(), 'app/components/RelationLinks.vue')
    expect(existsSync(componentPath)).toBe(true)
    const { default: RelationLinks } = await import('../app/components/RelationLinks.vue')
    const approved = publishedLink()
    const wrapper = mount(RelationLinks, {
      props: {
        locale: 'en',
        relations: {
          products: [approved],
          internal_relation: [
            publishedLink({ name: 'Private relation', url: '/internal/private/' }),
          ],
        },
        groups: ['products'],
      },
    })

    expect(wrapper.get('a').attributes('href')).toBe(approved.url)
    expect(wrapper.text()).toContain(approved.name)
    expect(wrapper.text()).not.toContain('Private relation')
    expect(wrapper.html()).not.toContain('internal_relation')
  })

  it('localizes every relation heading without reconstructing URLs from slugs', async () => {
    const componentPath = resolve(process.cwd(), 'app/components/RelationLinks.vue')
    expect(existsSync(componentPath)).toBe(true)
    const { default: RelationLinks } = await import('../app/components/RelationLinks.vue')
    const wrapper = mount(RelationLinks, {
      props: {
        locale: 'zh-cn',
        relations: { technologies: [publishedLink({ type: 'technology' })] },
        groups: ['technologies'],
      },
    })

    expect(wrapper.text()).toContain('处理技术')
    const source = sourceAt('app/components/RelationLinks.vue')
    expect(source).toContain(':href="link.url"')
    expect(source).not.toMatch(/:href="[^\"]*slug/)
  })
})

describe('Phase 3.6 visible GEO answer', () => {
  it('keeps direct answer, facts, evidence, and related questions user-visible', async () => {
    const componentPath = resolve(process.cwd(), 'app/components/GeoAnswer.vue')
    expect(existsSync(componentPath)).toBe(true)
    const { default: GeoAnswer } = await import('../app/components/GeoAnswer.vue')
    const wrapper = mount(GeoAnswer, {
      props: {
        locale: 'en',
        geo: {
          direct_answer: 'Use the published processing window.',
          key_facts: ['Published key fact'],
          evidence: ['Published evidence'],
          related_questions: ['Which product is suitable?'],
          last_reviewed_at: null,
        },
      },
    })

    expect(wrapper.text()).toContain('Quick Answer')
    expect(wrapper.text()).toContain('Use the published processing window.')
    expect(wrapper.text()).toContain('Published key fact')
    expect(wrapper.text()).toContain('Published evidence')
    expect(wrapper.text()).toContain('Which product is suitable?')
    expect(wrapper.attributes('hidden')).toBeUndefined()
    expect(wrapper.html()).not.toMatch(/display:\s*none|visibility:\s*hidden/)
  })

  it('uses Chinese UI labels and omits an empty GEO shell', async () => {
    const componentPath = resolve(process.cwd(), 'app/components/GeoAnswer.vue')
    expect(existsSync(componentPath)).toBe(true)
    const { default: GeoAnswer } = await import('../app/components/GeoAnswer.vue')
    const chinese = mount(GeoAnswer, {
      props: {
        locale: 'zh-cn',
        geo: {
          direct_answer: '直接答案',
          key_facts: ['事实'],
          evidence: ['依据'],
          related_questions: ['相关问题？'],
          last_reviewed_at: null,
        },
      },
    })
    expect(chinese.text()).toContain('快速解答')
    expect(chinese.text()).toContain('关键事实')
    expect(chinese.text()).toContain('依据')
    expect(chinese.text()).toContain('相关问题')

    const factsOnly = mount(GeoAnswer, {
      props: {
        locale: 'en',
        geo: {
          direct_answer: null,
          key_facts: ['Visible fact without a direct answer'],
          evidence: [],
          related_questions: [],
          last_reviewed_at: null,
        },
      },
    })
    expect(factsOnly.get('section').attributes('aria-labelledby')).toBe('geo-answer-heading')
    expect(factsOnly.find('#geo-answer-heading').exists()).toBe(true)

    const empty = mount(GeoAnswer, {
      props: {
        locale: 'en',
        geo: {
          direct_answer: null,
          key_facts: [],
          evidence: [],
          related_questions: [],
          last_reviewed_at: null,
        },
      },
    })
    expect(empty.find('section').exists()).toBe(false)
  })
})
