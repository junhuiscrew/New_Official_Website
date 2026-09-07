// 测试用途：锁定 Phase 3.6 产品列表、规格、媒体画廊、详情与询价来源安全契约。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import EmptyState from '../app/components/EmptyState.vue'
import FilterBar from '../app/components/FilterBar.vue'
import MediaGallery from '../app/components/MediaGallery.vue'
import PaginationNav from '../app/components/PaginationNav.vue'
import ProductCard from '../app/components/ProductCard.vue'
import PublicImage from '../app/components/PublicImage.vue'
import PublicVideo from '../app/components/PublicVideo.vue'
import SpecTable from '../app/components/SpecTable.vue'
import type { PublicCardDto, PublicMediaDto, PublicSpecDto } from '../app/types/public'

enableAutoUnmount(afterEach)

const specifications: PublicSpecDto[] = [
  { name: 'Grade', value: 'Premium', unit: null, group: 'General', type: 'text' },
  { name: 'Diameter', value: '65', unit: 'mm', group: 'Dimensions', type: 'number' },
  { name: 'Working range', value: '20–80', unit: 'mm', group: 'Dimensions', type: 'range' },
  { name: 'Cooling', value: 'Yes', unit: null, group: 'Features', type: 'boolean' },
  { name: 'Surface', value: 'Nitrided', unit: null, group: 'Features', type: 'enum' },
]

const image: PublicMediaDto = {
  src: '/api/v1/public/media/public-product',
  type: 'image',
  mime_type: 'image/webp',
  width: 1200,
  height: 800,
  alt: 'Published precision screw',
  caption: 'Published media caption',
  loading: 'eager',
}

/** 创建只含公开白名单字段的产品卡片。 */
function productCard(): PublicCardDto {
  return {
    type: 'product',
    slug: 'precision-screw',
    name: 'Precision Screw',
    url: '/en/products/injection/precision-screw/',
    summary: 'Published product summary.',
    media: image,
    specifications,
    category: {
      type: 'product_category',
      slug: 'injection',
      name: 'Injection',
      url: '/en/products/injection/',
      summary: '',
    },
  }
}

describe('Phase 3.6 product list filters and pagination', () => {
  it('emits meaningful category, material, and application URL filters and resets page', async () => {
    const wrapper = mount(FilterBar, {
      props: {
        locale: 'en',
        modelValue: {
          category: 'injection',
          material: 'peek',
          application: 'automotive',
        },
        options: {
          categories: [{ value: 'injection', label: 'Injection' }],
          materials: [{ value: 'peek', label: 'PEEK' }],
          applications: [{ value: 'automotive', label: 'Automotive' }],
        },
      },
    })

    expect(wrapper.find('select[name="category"]').exists()).toBe(true)
    expect(wrapper.find('select[name="material"]').exists()).toBe(true)
    expect(wrapper.find('select[name="application"]').exists()).toBe(true)

    await wrapper.get('select[name="material"]').setValue('')
    const update = wrapper.emitted('update:modelValue')?.at(-1)?.[0]
    expect(update).toEqual({ category: 'injection', material: '', application: 'automotive' })
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ page: 1 })
  })

  it('renders canonical anchors, preserves filters, and never requests more than 48 items', () => {
    const wrapper = mount(PaginationNav, {
      props: {
        locale: 'en',
        basePath: '/en/products/',
        page: 2,
        pages: 4,
        pageSize: 99,
        query: { category: 'injection', material: 'peek', application: 'automotive' },
      },
    })

    const hrefs = wrapper.findAll('a').map((anchor) => anchor.attributes('href'))
    expect(hrefs.some((href) => href.includes('page=1'))).toBe(false)
    expect(hrefs.some((href) => href.includes('page=3'))).toBe(true)
    for (const href of hrefs) {
      expect(href).toContain('category=injection')
      expect(href).toContain('material=peek')
      expect(href).toContain('application=automotive')
      expect(href).toContain('page_size=48')
    }
  })

  it('does not duplicate a category already represented by the category path', () => {
    const wrapper = mount(PaginationNav, {
      props: {
        locale: 'en',
        basePath: '/en/products/injection/',
        page: 1,
        pages: 2,
        pageSize: 24,
        query: { material: 'peek', application: 'automotive' },
      },
    })
    for (const anchor of wrapper.findAll('a')) {
      expect(anchor.attributes('href')).not.toContain('category=')
      expect(anchor.attributes('href')).toContain('/en/products/injection/')
    }
  })

  it('uses the new SSR collection envelope and URL query as the only list state', () => {
    const listingView = readFileSync(
      resolve(process.cwd(), 'app/components/ProductListingView.vue'),
      'utf8',
    )
    expect(listingView).toContain('<FilterBar')
    expect(listingView).toContain('<PaginationNav')
    expect(listingView).toContain('<EmptyState')
    for (const pagePath of [
      'app/pages/[lang]/products/index.vue',
      'app/pages/[lang]/products/[category]/index.vue',
    ]) {
      const source = readFileSync(resolve(process.cwd(), pagePath), 'utf8')
      expect(source).toContain('await useAsyncData')
      expect(source).toContain('/public/products/')
      expect(source).toContain('route.query')
      expect(source).toContain('page_size')
      expect(source).toContain('48')
      expect(source).toContain('<ProductListingView')
      expect(source).toContain('useHead')
      expect(source).not.toContain('onMounted')
    }
  })

  it('keeps Products SEO API-owned without approved copy embedded in the page', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/products/index.vue'),
      'utf8',
    )

    expect(source).toContain('pageData.value.collection.seo')
    expect(source).toContain('/public/products/')
    expect(source).not.toContain('Junhui Screw and Barrel Products')
    expect(source).not.toContain('骏辉螺杆与机筒产品')
    expect(source).not.toContain(
      'Explore Junhui Nitrided Screw, Junhui Nitrided Barrel and Junhui Electroplated Screw',
    )
    expect(source).not.toContain('查看骏辉氮化螺杆、骏辉氮化机筒和骏辉电镀螺杆')
  })

  it('keeps category 404 status and renders category-visible semantics beside backend schema', () => {
    const categoryPage = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/products/[category]/index.vue'),
      'utf8',
    )
    const listingView = readFileSync(
      resolve(process.cwd(), 'app/components/ProductListingView.vue'),
      'utf8',
    )

    expect(categoryPage).toContain('publicRequestStatus(error.value)')
    expect(categoryPage).toContain('strictPositiveInteger(route.query.page')
    expect(categoryPage).toContain('watch(error')
    expect(categoryPage).toContain('listingSeo?.robots')
    expect(categoryPage).toContain(':title="pageData.categoryPage.translation.name"')
    expect(categoryPage).toContain(':breadcrumb="pageData.collection.breadcrumb"')
    expect(categoryPage).toContain(':geo="pageData.categoryPage.geo"')
    expect(categoryPage).toContain('serializeJsonLd(pageData.value.collection.schema)')
    expect(listingView).toContain('<PublicBreadcrumb')
    expect(listingView).toContain('<PublicGeoContent')
    expect(listingView).toContain('<h1>{{ title ?? labels.products.title }}</h1>')
  })
})

describe('Phase 3.6 product cards and clean specification rendering', () => {
  it('shows at most four DTO specs and no ecommerce facts or controls', () => {
    const wrapper = mount(ProductCard, { props: { item: productCard(), locale: 'en' } })

    expect(wrapper.findAll('.product-card__specs > div')).toHaveLength(4)
    expect(wrapper.text()).not.toMatch(/price|add to cart|rating|stock/i)
    expect(wrapper.html()).not.toMatch(
      /data-(?:price|stock|rating)|itemprop="(?:price|ratingValue)"/i,
    )
  })

  it('groups all five clean DTO types using table and definition-list semantics', () => {
    const wrapper = mount(SpecTable, { props: { specifications, locale: 'en' } })

    expect(wrapper.findAll('section[data-spec-group]')).toHaveLength(3)
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('dl').exists()).toBe(true)
    expect(wrapper.find('pre').exists()).toBe(false)
    for (const specification of specifications)
      expect(wrapper.text()).toContain(specification.value)
    expect(wrapper.text()).not.toContain('[object Object]')
  })
})

describe('Phase 3.6 public product media', () => {
  it('requires alt and intrinsic dimensions while honoring eager/high and lazy loading', () => {
    const eager = mount(PublicImage, { props: { media: image, priority: true } })
    const rendered = eager.get('img')
    expect(rendered.attributes()).toMatchObject({
      alt: image.alt,
      width: '1200',
      height: '800',
      loading: 'eager',
      fetchpriority: 'high',
    })

    const lazy = mount(PublicImage, { props: { media: { ...image, loading: 'lazy' } } })
    expect(lazy.get('img').attributes('loading')).toBe('lazy')
    expect(lazy.get('img').attributes('fetchpriority')).toBeUndefined()

    const invalid = mount(PublicImage, {
      props: { media: { ...image, alt: '', width: null, height: null }, locale: 'en' },
    })
    expect(invalid.find('img').exists()).toBe(false)
  })

  it('renders accessible video controls without autoplay and defers below-fold loading', () => {
    const wrapper = mount(PublicVideo, {
      props: {
        media: { ...image, type: 'video', mime_type: 'video/mp4', loading: 'lazy' },
        poster: { ...image, loading: 'lazy' },
      },
    })
    const video = wrapper.get('video')
    expect(video.attributes('controls')).toBeDefined()
    expect(video.attributes('preload')).toBe('none')
    expect(video.attributes('autoplay')).toBeUndefined()
    expect(video.attributes('poster')).toBe(image.src)
  })

  it('closes the gallery dialog with Escape and restores focus to its opener', async () => {
    const wrapper = mount(MediaGallery, {
      attachTo: document.body,
      props: { media: [image, { ...image, src: '/api/v1/public/media/second' }], locale: 'en' },
    })
    const opener = wrapper.get('[data-testid="gallery-open"]')
    ;(opener.element as HTMLElement).focus()
    await opener.trigger('click')
    expect(wrapper.get('[role="dialog"]').attributes('aria-modal')).toBe('true')

    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(opener.element)
  })

  it('opens the native dialog modally and loops Tab focus inside it', async () => {
    const showModal = HTMLElement.prototype.focus
    const originalShowModal = HTMLDialogElement.prototype.showModal
    let modalCalls = 0
    HTMLDialogElement.prototype.showModal = function showModalStub() {
      modalCalls += 1
      this.setAttribute('open', '')
    }
    try {
      const wrapper = mount(MediaGallery, {
        attachTo: document.body,
        props: { media: [image, { ...image, src: '/api/v1/public/media/second' }], locale: 'en' },
      })
      await wrapper.get('[data-testid="gallery-open"]').trigger('click')
      const dialog = wrapper.get('dialog')
      const buttons = dialog.findAll('button')
      ;(buttons.at(-1)!.element as HTMLElement).focus()
      await dialog.trigger('keydown', { key: 'Tab' })
      expect(document.activeElement).toBe(buttons[0]!.element)
      expect(modalCalls).toBe(1)
      expect(showModal).toBeTypeOf('function')
    } finally {
      HTMLDialogElement.prototype.showModal = originalShowModal
    }
  })
})

describe('Phase 3.6 product detail and RFQ safety', () => {
  it('composes approved detail sections and consumes backend SEO/schema only', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/products/[category]/[slug].vue'),
      'utf8',
    )
    for (const component of [
      'PageHero',
      'MediaGallery',
      'SpecTable',
      'PublicRelationLinks',
      'PublicFaqList',
      'PublicGeoContent',
      'RfqCta',
    ]) {
      expect(source).toContain(component)
    }
    expect(source).toContain('serializeJsonLd(page.value.schema)')
    expect(source).not.toContain('<pre')
    expect(source).not.toMatch(/['"]@type['"]\s*:/)
    expect(source).not.toContain('onMounted')
    expect(source).toContain('caseRelations')
    expect(source).toContain('knowledgeRelations')
    expect(source).toContain('page.trust_summary')
    expect(source).toContain('TrustMetric')
    expect(source.indexOf('<PublicFaqList')).toBeLessThan(
      source.indexOf(':relations="knowledgeRelations"'),
    )
  })

  it('localizes whitelisted relation headings and omits unknown backend keys', async () => {
    const { default: PublicRelationLinks } = await import(
      '../app/components/PublicRelationLinks.vue'
    )
    const relations = {
      materials: [productCard().category!],
      internal_relation: [productCard().category!],
    }
    const chinese = mount(PublicRelationLinks, { props: { relations, locale: 'zh-cn' } })
    expect(chinese.text()).toContain('相关内容')
    expect(chinese.text()).toContain('材料')
    expect(chinese.text()).not.toContain('internal_relation')
  })

  it('renders every relation through backend canonical anchors', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/PublicRelationLinks.vue'),
      'utf8',
    )
    expect(source).toContain(':href="link.url"')
    expect(source).not.toMatch(/:href="[^\"]*slug/)
  })

  it('builds RFQ links from allowed product type/slug context without internal IDs', () => {
    const wrapper = mount(ProductCard, { props: { item: productCard(), locale: 'en' } })
    const rfq = wrapper.findAll('a').find((anchor) => anchor.text() === 'Request a Quote')
    expect(rfq?.attributes('href')).toBe(
      '/en/request-a-quote/?source_type=product&source_slug=precision-screw',
    )
    expect(rfq?.attributes('href')).not.toMatch(/(?:owner|internal|uuid|_id)=/i)
  })

  it('renders a localized neutral empty state without fabricated claims', () => {
    const wrapper = mount(EmptyState, { props: { locale: 'en', kind: 'products' } })
    expect(wrapper.text()).toContain('No published products are available yet.')
    expect(wrapper.text()).not.toMatch(/ISO|in stock|best seller/i)
  })
})
