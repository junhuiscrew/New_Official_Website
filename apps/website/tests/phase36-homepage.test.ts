// 测试用途：锁定 Phase 3.6 首页的 SSR、发布内容、媒体性能、双语和事实边界。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ArticleCard from '../app/components/ArticleCard.vue'
import CaseCard from '../app/components/CaseCard.vue'
import HomePage from '../app/components/HomePage.vue'
import ProductCard from '../app/components/ProductCard.vue'
import type { HomeDto, PublicCardDto } from '../app/types/public'

vi.stubGlobal('useHead', vi.fn())
// RfqCta 使用公开运行配置区分 Demo 提示；基础首页测试保持非 Demo 环境。
vi.stubGlobal('useRuntimeConfig', () => ({ public: { demoMode: false } }))

/**
 * 构造只包含 Public API 白名单字段的 canonical 卡片。
 *
 * 输入：
 *   overrides: Partial<PublicCardDto>，当前场景要替换的公开字段。
 *
 * 输出：
 *   PublicCardDto，可安全渲染的已发布卡片数据。
 */
function publishedCard(overrides: Partial<PublicCardDto> = {}): PublicCardDto {
  return {
    type: 'product',
    slug: 'precision-screw',
    name: 'Published Precision Screw',
    url: '/en/products/injection/precision-screw/',
    summary: 'Published engineering summary.',
    media: {
      src: '/api/v1/public/media/published-card',
      type: 'image',
      mime_type: 'image/webp',
      width: 960,
      height: 640,
      alt: 'Published precision screw',
      caption: null,
      loading: 'lazy',
    },
    ...overrides,
  }
}

/** 返回包含所有可选首页区块的公开 API fixture。 */
function populatedHome(locale: HomeDto['locale'] = 'en'): HomeDto {
  return {
    locale,
    company: {
      company_name: locale === 'en' ? 'API Company Name' : '接口公司名称',
      short_intro: locale === 'en' ? 'API supplied introduction.' : '接口提供的公司简介。',
      full_intro: null,
      mission: null,
      advantages: locale === 'en' ? ['API supplied quality fact'] : ['接口提供的质量事实'],
      founded_year: null,
      years_experience: null,
      employee_count_range: null,
      factory_area_sqm: null,
      annual_capacity_text: null,
      export_markets: null,
      phone: null,
      email: null,
      address: null,
      url: `/${locale}/about/`,
    },
    hero_media: {
      src: '/api/v1/public/media/factory-hero',
      type: 'image',
      mime_type: 'image/webp',
      width: 1600,
      height: 900,
      alt: 'API factory media',
      caption: null,
      loading: 'eager',
    },
    product_categories: [
      publishedCard({
        type: 'product_category',
        slug: 'injection',
        name: 'Published Product Category',
        url: '/en/products/injection/',
      }),
    ],
    featured_products: [publishedCard()],
    materials: [
      publishedCard({
        type: 'material',
        slug: 'peek',
        name: 'Published Material',
        url: '/en/materials/peek/',
      }),
    ],
    solutions: [
      publishedCard({
        type: 'solution',
        slug: 'wear',
        name: 'Published Problem Solution',
        url: '/en/solutions/wear/',
      }),
    ],
    capabilities: [
      publishedCard({
        type: 'manufacturing_capability',
        slug: 'machining',
        name: 'Published Capability',
        url: '/en/capabilities/machining/',
      }),
    ],
    applications: [
      publishedCard({
        type: 'application',
        slug: 'automotive',
        name: 'Published Application',
        url: '/en/applications/automotive/',
      }),
    ],
    cases: [
      publishedCard({
        type: 'case_study',
        slug: 'wear-case',
        name: 'Published Anonymous Case',
        url: '/en/case-studies/wear-case/',
      }),
    ],
    knowledge: [
      publishedCard({
        type: 'knowledge_article',
        slug: 'selection-guide',
        name: 'Published Technical Guide',
        url: '/en/knowledge/guides/selection-guide/',
        author: 'Published Author',
      }),
    ],
    trust_summary: {
      founded_year: 1985,
      annual_capacity_text: 'API supplied capacity',
      export_markets: ['Market A', 'Market B'],
    },
    seo: {
      title: locale === 'en' ? 'Junhui Screw' : '骏辉螺杆',
      description: locale === 'en' ? 'API home description' : '接口首页描述',
      canonical: `https://junhuiscrewbarrel.com/${locale}/`,
      robots: 'index, follow',
      hreflang: {
        [locale === 'en' ? 'en' : 'zh-CN']: `https://junhuiscrewbarrel.com/${locale}/`,
      },
    },
    schema: [],
  }
}

afterEach(() => {
  vi.mocked(useHead).mockClear()
})
enableAutoUnmount(afterEach)

describe('Phase 3.6 final homepage composition', () => {
  it('renders one H1, exactly two hero CTAs, and the approved section order', () => {
    const wrapper = mount(HomePage, {
      props: { locale: 'en', home: populatedHome() },
    })

    expect(wrapper.findAll('h1')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="hero-cta"]')).toHaveLength(2)
    const orderedSections = wrapper
      .findAll('[data-home-section]')
      .map((section) => section.attributes('data-home-section'))
    expect(orderedSections).toEqual([
      'hero',
      'product-categories',
      'trust-strip',
      'discovery',
      'capabilities',
      'featured-products',
      'applications',
      'cases',
      'knowledge',
      'trust-summary',
      'rfq',
    ])
  })

  it('renders only DTO content and omits every empty optional section', () => {
    const emptyHome: HomeDto = {
      ...populatedHome(),
      company: null,
      hero_media: null,
      product_categories: [],
      featured_products: [],
      materials: [],
      solutions: [],
      capabilities: [],
      applications: [],
      cases: [],
      knowledge: [],
      trust_summary: null,
    }
    const wrapper = mount(HomePage, {
      props: { locale: 'en', home: emptyHome },
    })

    expect(
      wrapper.findAll('[data-home-section]').map((node) => node.attributes('data-home-section')),
    ).toEqual(['hero', 'rfq'])
    expect(wrapper.text()).not.toContain('Published Precision Screw')
    expect(wrapper.text()).not.toContain('Draft Product')
    expect(wrapper.text().toLowerCase()).not.toContain('published')
    expect(wrapper.find('[data-testid="hero-media"]').exists()).toBe(false)
    expect(wrapper.get('[data-home-section="hero"]').classes()).toContain(
      'page-hero--without-media',
    )
    expect(wrapper.get('h1').text()).toBe('Tell us about your project')
  })

  it('uses DTO company and trust facts without replacing them with invented claims', () => {
    const wrapper = mount(HomePage, {
      props: { locale: 'en', home: populatedHome() },
    })

    expect(wrapper.get('h1').text()).toBe('API Company Name')
    expect(wrapper.get('.page-hero__content > p').text()).toBe('API supplied introduction.')
    expect(wrapper.text()).toContain('API Company Name')
    expect(wrapper.text()).toContain('API supplied introduction.')
    expect(wrapper.text()).toContain('API supplied quality fact')
    expect(wrapper.text()).toContain('1985')
    expect(wrapper.text()).toContain('API supplied capacity')
    expect(wrapper.text()).not.toContain('Certificates')
    expect(wrapper.text()).not.toMatch(/ISO|diameter|equipment count|years? experience/i)
  })

  it('renders English and Chinese UI without crossing locale labels', () => {
    const english = mount(HomePage, {
      props: { locale: 'en', home: populatedHome('en') },
    })
    expect(english.text()).toContain('Product Categories')
    expect(english.text()).toContain('Request a Quote')
    expect(english.text()).not.toContain('获取报价')

    const chinese = mount(HomePage, {
      props: { locale: 'zh-cn', home: populatedHome('zh-cn') },
    })
    expect(chinese.text()).toContain('产品类别')
    expect(chinese.text()).toContain('获取报价')
    expect(chinese.text()).not.toContain('Request a Quote')
  })
})

describe('Phase 3.6 homepage cards and media', () => {
  it('prioritizes the DTO hero image and keeps below-fold card images lazy', () => {
    const wrapper = mount(HomePage, {
      props: { locale: 'en', home: populatedHome() },
    })
    const hero = wrapper.get('[data-testid="hero-media"]')
    expect(hero.attributes('src')).toBe('/api/v1/public/media/factory-hero')
    expect(hero.attributes('loading')).toBe('eager')
    expect(hero.attributes('fetchpriority')).toBe('high')
    expect(hero.attributes('width')).toBe('1600')
    expect(hero.attributes('height')).toBe('900')

    for (const image of wrapper.findAll('[data-testid="card-media"]')) {
      expect(image.attributes('loading')).toBe('lazy')
      expect(image.attributes('fetchpriority')).toBeUndefined()
    }
  })

  it('uses the single-column hero layout when the DTO media is not an image', () => {
    const home = populatedHome()
    home.hero_media = {
      ...home.hero_media!,
      type: 'video',
      mime_type: 'video/mp4',
    }
    const wrapper = mount(HomePage, { props: { locale: 'en', home } })

    expect(wrapper.find('[data-testid="hero-media"]').exists()).toBe(false)
    expect(wrapper.get('[data-home-section="hero"]').classes()).toContain(
      'page-hero--without-media',
    )
  })

  it('uses only canonical DTO links for product, article, and case cards', () => {
    const product = publishedCard()
    const article = publishedCard({
      type: 'knowledge_article',
      url: '/en/knowledge/guides/published/',
      author: 'API Author',
    })
    const caseStudy = publishedCard({
      type: 'case_study',
      url: '/en/case-studies/published/',
      name: 'Anonymous case',
    })

    const productWrapper = mount(ProductCard, {
      props: { item: product, locale: 'en' },
    })
    const articleWrapper = mount(ArticleCard, {
      props: { item: article, locale: 'en' },
    })
    const caseWrapper = mount(CaseCard, {
      props: { item: caseStudy, locale: 'en' },
    })

    expect(productWrapper.get('[data-testid="card-primary-link"]').attributes('href')).toBe(
      product.url,
    )
    expect(articleWrapper.get('[data-testid="card-primary-link"]').attributes('href')).toBe(
      article.url,
    )
    expect(caseWrapper.get('[data-testid="card-primary-link"]').attributes('href')).toBe(
      caseStudy.url,
    )
    expect(caseWrapper.text()).not.toContain('Private Client')
  })

  it('uses a full-width case layout when the Public API card has no image', () => {
    const item = publishedCard({
      type: 'case_study',
      url: '/en/case-studies/without-media/',
      media: null,
    })
    const wrapper = mount(CaseCard, { props: { item, locale: 'en' } })

    expect(wrapper.classes()).toContain('case-card--without-media')
    expect(wrapper.find('[data-testid="card-media"]').exists()).toBe(false)
  })

  it('shows only supplied article authorship and review metadata with localized labels', () => {
    const item = publishedCard({
      type: 'knowledge_article',
      author: 'API Author',
      reviewer: 'API Reviewer',
      published_at: '2026-09-01',
      updated_at: '2026-09-03',
    })
    const wrapper = mount(ArticleCard, { props: { item, locale: 'en' } })

    expect(wrapper.text()).toContain('Author: API Author')
    expect(wrapper.text()).toContain('Reviewer: API Reviewer')
    expect(wrapper.text()).toContain('Published: 2026-09-01')
    expect(wrapper.text()).toContain('Updated: 2026-09-03')

    const chinese = mount(ArticleCard, { props: { item, locale: 'zh-cn' } })
    expect(chinese.text()).toContain('作者：API Author')
    expect(chinese.text()).toContain('审核：API Reviewer')
  })

  it('contains no carousel or hardcoded manufacturing claims in homepage sources', () => {
    const componentSource = [
      'HomePage.vue',
      'PageHero.vue',
      'ProductCard.vue',
      'ArticleCard.vue',
      'CaseCard.vue',
      'TrustMetric.vue',
      'RfqCta.vue',
    ]
      .map((filename) => readFileSync(resolve(process.cwd(), 'app/components', filename), 'utf8'))
      .join('\n')

    expect(componentSource).not.toMatch(/carousel|swiper|splide/i)
    expect(componentSource).not.toMatch(/\bISO\s?\d*|\b\d+\+?\s*years?|\b\d+\s*(?:mm|毫米)/i)
    expect(componentSource).not.toMatch(/(?:equipment|设备)\s*(?:count|数量)?\s*[:：=]\s*\d+/i)
  })
})

describe('Phase 3.6 homepage SSR and metadata contract', () => {
  it('performs one SSR aggregate request per locale page and uses the shared renderer', () => {
    for (const [pagePath, locale] of [
      ['app/pages/en/index.vue', 'en'],
      ['app/pages/zh-cn/index.vue', 'zh-cn'],
    ] as const) {
      const source = readFileSync(resolve(process.cwd(), pagePath), 'utf8')
      expect(source).toMatch(/await\s+useAsyncData/)
      expect(source).toContain(`const locale = '${locale}'`)
      expect(source).toContain('`/public/home/${locale}`')
      expect(source.match(/\/public\/home\//g)).toHaveLength(1)
      expect(source).toContain('<HomePage')
      expect(source).toContain('error.value?.statusCode === 404 ? 404 : 500')
    }
  })

  it('uses only an optional API SEO/Schema payload and the safe JSON-LD serializer', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/components/HomePage.vue'), 'utf8')

    expect(source).toContain("import { serializeJsonLd } from '~/utils/jsonLd'")
    expect(source).toContain('home.seo')
    expect(source).toContain('home.schema')
    expect(source).toContain('serializeJsonLd(props.home.schema)')
    expect(source).not.toMatch(/['"]@type['"]\s*:/)
  })

  it('always declares the document language and preloads only API hero media', () => {
    mount(HomePage, { props: { locale: 'en', home: populatedHome('en') } })
    const englishHeadFactory = vi.mocked(useHead).mock.calls.at(-1)?.[0]
    expect(typeof englishHeadFactory).toBe('function')
    const englishHead = (englishHeadFactory as () => Record<string, unknown>)()
    expect(englishHead).toMatchObject({
      htmlAttrs: { lang: 'en' },
      title: 'Junhui Screw',
    })
    expect(englishHead.link).toContainEqual({
      rel: 'preload',
      as: 'image',
      href: '/api/v1/public/media/factory-hero',
      fetchpriority: 'high',
    })

    const noMedia = populatedHome('zh-cn')
    noMedia.hero_media = null
    mount(HomePage, { props: { locale: 'zh-cn', home: noMedia } })
    const chineseHeadFactory = vi.mocked(useHead).mock.calls.at(-1)?.[0]
    const chineseHead = (chineseHeadFactory as () => Record<string, unknown>)()
    expect(chineseHead).toMatchObject({ htmlAttrs: { lang: 'zh-CN' } })
    expect(chineseHead.link ?? []).not.toContainEqual(expect.objectContaining({ rel: 'preload' }))
  })

  it('applies an optional API SEO/Schema payload and safely escapes JSON-LD', () => {
    const home = populatedHome()
    home.seo = {
      title: 'API SEO Title',
      description: 'API SEO description',
      canonical: 'https://junhuiscrewbarrel.com/en/',
      robots: 'index, follow',
      hreflang: {
        en: 'https://junhuiscrewbarrel.com/en/',
        'zh-CN': 'https://junhuiscrewbarrel.com/zh-cn/',
      },
    }
    home.schema = { value: '</script><script>alert(1)</script>' }
    mount(HomePage, { props: { locale: 'en', home } })

    const headFactory = vi.mocked(useHead).mock.calls.at(-1)?.[0]
    const head = (
      headFactory as () => {
        title: string
        meta: Array<Record<string, string>>
        link: Array<Record<string, string>>
        script: Array<{ innerHTML: string }>
      }
    )()
    expect(head.title).toBe('API SEO Title')
    expect(head.meta).toContainEqual({
      name: 'robots',
      content: 'index, follow',
    })
    expect(head.link).toContainEqual({
      rel: 'canonical',
      href: 'https://junhuiscrewbarrel.com/en/',
    })
    expect(head.link).toContainEqual({
      rel: 'alternate',
      hreflang: 'zh-CN',
      href: 'https://junhuiscrewbarrel.com/zh-cn/',
    })
    expect(head.script[0]?.innerHTML).toContain('\\u003c/script>')
    expect(head.script[0]?.innerHTML).not.toContain('</script>')
  })
})
