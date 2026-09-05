// 测试用途：锁定 Phase 3.6 四类目录列表/详情、公开关系、可见 GEO 与询价来源契约。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import type { PublicFaqDto, PublicLinkDto } from '../app/types/public'

import FAQAccordion from '../app/components/FAQAccordion.vue'
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

describe('Phase 3.6 authority content pages', () => {
  it('builds published Knowledge, Case Study, and Expert indexes with scoped filters', () => {
    const knowledge = sourceAt('app/pages/[lang]/knowledge/index.vue')
    const cases = sourceAt('app/pages/[lang]/case-studies/index.vue')
    const experts = sourceAt('app/pages/[lang]/experts/index.vue')

    for (const [source, endpoint] of [
      [knowledge, '/public/knowledge/'],
      [cases, '/public/case-studies/'],
      [experts, '/public/experts/'],
    ]) {
      expect(source).toContain('await useAsyncData')
      expect(source).toContain(endpoint)
      expect(source).toContain('<PaginationNav')
      expect(source).toContain('<EmptyState')
      expect(source).toContain('collection.value.seo.canonical')
      expect(source).toContain('serializeJsonLd(collection.value.schema)')
      expect(source).not.toContain('onMounted')
      expect(source).not.toContain('<pre')
      expect(source).not.toContain('JSON.stringify')
    }

    expect(knowledge).toContain('route.query.category')
    expect(knowledge).toContain('category: selectedCategory')
    expect(knowledge).toContain('<ArticleCard')
    expect(cases).toContain('<CaseCard')
    expect(experts).toContain('route.query.type')
    expect(experts).toContain('type: selectedType')
  })

  it('renders Knowledge authority metadata, visible answers, real sources, relations, and RFQ', () => {
    const source = sourceAt('app/pages/[lang]/knowledge/[category]/[slug].vue')

    for (const field of [
      'page.author.name',
      'page.reviewer',
      'page.published_at',
      'page.updated_at',
      'page.last_reviewed_at',
      'source.publisher',
      'source.publication_date',
      'source.source_type',
      'page.translation.body_markdown',
    ])
      expect(source).toContain(field)
    expect(source).toContain('<GeoAnswer')
    expect(source).toContain('<FAQAccordion')
    expect(source).toContain('<RelationLinks')
    expect(source).toContain('<RfqCta')
    expect(source).toContain('source-type="knowledge_article"')
    expect(source).toContain(':source-slug="page.slug"')
    expect(source).toContain(':href="source.url"')
    expect(source.indexOf('<GeoAnswer')).toBeLessThan(
      source.indexOf('page.translation.body_markdown'),
    )
    expect(source).not.toContain('v-html')
  })

  it('renders only the Case DTO allowlisted customer identity and public engineering facts', () => {
    const source = sourceAt('app/pages/[lang]/case-studies/[slug].vue')

    expect(source).toContain('page.customer_identity')
    expect(source).toContain('page.customer_identity.name')
    expect(source).toContain('page.customer_identity.address')
    expect(source).toContain('page.customer_identity.logo')
    for (const field of [
      'page.value.country_code',
      'page.value.industry',
      'page.value.machine_brand',
      'page.value.machine_model',
      'page.value.screw_diameter',
      'page.value.filler_percentage',
      'page.value.translation.problem',
      'page.value.translation.analysis',
      'page.value.translation.solution',
      'page.value.translation.result',
      'page.value.translation.engineer_comment',
    ])
      expect(source).toContain(field)
    expect(source).not.toMatch(/page\.client_(?:name|address|logo)/)
    expect(source).not.toContain('client_logo_media_id')
    expect(source).toContain('source-type="case_study"')
  })

  it('renders only a verified public Person profile and authored published Knowledge links', () => {
    const source = sourceAt('app/pages/[lang]/experts/[slug].vue')

    for (const field of [
      'page.name',
      'page.job_title',
      'page.short_bio',
      'page.expertise',
      'page.years_experience',
      'page.linkedin_url',
      'page.public_email',
      'page.profile_media',
      'page.authored_knowledge',
    ])
      expect(source).toContain(field)
    expect(source).toContain('page.is_real_person_verified')
    expect(source).toContain(':href="article.url"')
    expect(source).toContain('source-type="author_expert"')
    expect(source).not.toMatch(/AI Expert|fictional|placeholder/i)
  })

  it('keeps FAQ questions and answers visible from the exact list supplied to Schema', () => {
    const items: PublicFaqDto[] = [
      { question: 'Which evidence is public?', answer: 'Only reviewed published evidence.' },
      { question: 'Does this match Schema?', answer: 'The same ordered DTO list is used.' },
    ]
    const wrapper = mount(FAQAccordion, { props: { locale: 'en', items } })
    const componentPath = resolve(process.cwd(), 'app/components/FAQAccordion.vue')
    expect(existsSync(componentPath)).toBe(true)
    const source = sourceAt('app/components/FAQAccordion.vue')
    expect(wrapper.findAll('summary').map((item) => item.text())).toEqual(
      items.map((item) => item.question),
    )
    expect(wrapper.findAll('details p').map((item) => item.text())).toEqual(
      items.map((item) => item.answer),
    )
    expect(source).toContain('defineProps<{ locale: LocaleSlug; items: PublicFaqDto[] }>()')
    expect(source).toContain('data-schema-contract="same-items"')
    expect(source).toContain('v-for="item in items"')
    expect(source).toContain('{{ item.question }}')
    expect(source).toContain('{{ item.answer }}')
    expect(source).toContain('<details')
    expect(source).not.toContain('v-html')
  })

  it('distinguishes Authority 404 and 500 while consuming backend SEO and Schema only', () => {
    for (const path of [
      'app/pages/[lang]/knowledge/[category]/[slug].vue',
      'app/pages/[lang]/case-studies/[slug].vue',
      'app/pages/[lang]/experts/[slug].vue',
    ]) {
      const source = sourceAt(path)
      expect(source).toContain('error.value?.statusCode === 404 ? 404 : 500')
      expect(source).toContain('page.value.seo.canonical')
      expect(source).toContain('page.value.alternates')
      expect(source).toContain('serializeJsonLd(page.value.schema)')
      expect(source).not.toMatch(/['"]@type['"]\s*:/)
    }
  })
})
