// 测试用途：锁定官网呈现 R1 的十四模块、公开空态和认证预览边界。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import HomePage from '../app/components/HomePage.vue'
import type { HomeDto, HomepageModuleKey, PublicCardDto } from '../app/types/public'

vi.stubGlobal('useHead', vi.fn())
enableAutoUnmount(afterEach)

const moduleKeys: HomepageModuleKey[] = [
  'hero',
  'core_product_families',
  'materials',
  'special_applications',
  'technologies',
  'manufacturing_capability',
  'why_junhui',
  'factory_equipment',
  'solutions',
  'case_studies',
  'technical_knowledge',
  'certificates_patents',
  'global_markets',
  'rfq_cta',
]

function product(slug: string): PublicCardDto {
  return {
    type: 'product',
    slug,
    name: slug,
    url: `/zh-cn/products/screws/${slug}/`,
    summary: `${slug} summary`,
    media: {
      src: `/api/v1/public/media/${slug}`,
      type: 'image',
      mime_type: 'image/webp',
      width: 700,
      height: 700,
      alt: slug,
      caption: null,
      loading: 'lazy',
    },
  }
}

function homepage(preview = false): HomeDto {
  return {
    locale: 'zh-cn',
    company: {
      company_name: '舟山骏辉塑料机械有限公司',
      short_intro: '已批准的公司简介。',
      full_intro: '已批准的公司完整介绍。',
      mission: null,
      advantages: null,
      founded_year: null,
      years_experience: null,
      employee_count_range: null,
      factory_area_sqm: null,
      annual_capacity_text: null,
      export_markets: null,
      phone: null,
      email: null,
      address: null,
      url: '/zh-cn/about/',
    },
    hero_media: null,
    product_categories: [],
    featured_products: [],
    homepage_products: [
      product('nitrided-screw'),
      product('junhui-nitrided-barrel'),
      product('electroplated-screw'),
    ],
    materials: [],
    technologies: [],
    solutions: [],
    capabilities: [],
    equipment: [],
    applications: [],
    cases: [],
    knowledge: [],
    certificates: [],
    patents: [],
    trust_summary: null,
    presentation: {
      revision: 2,
      modules: moduleKeys.map((key, index) => ({
        key,
        visible: true,
        variant: index % 2 ? 'soft' : 'light',
        product_slugs: key === 'hero' ? ['nitrided-screw'] : [],
        content_status: ['hero', 'core_product_families', 'why_junhui', 'rfq_cta'].includes(key)
          ? 'available'
          : 'missing',
        missing_reason: '尚无可展示的已发布内容',
        management_url: '/homepage',
      })),
    },
    preview,
    seo: {
      title: '骏辉螺杆',
      description: '已批准描述',
      canonical: 'https://junhuiscrewbarrel.com/zh-cn/',
      robots: 'index, follow',
    },
    schema: [],
  }
}

describe('Website Presentation R1 shared renderer', () => {
  it('uses the configured order and renders real selected products', () => {
    const wrapper = mount(HomePage, { props: { locale: 'zh-cn', home: homepage() } })
    const rendered = wrapper
      .findAll('[data-home-module]')
      .map((node) => node.attributes('data-home-module'))

    expect(rendered).toEqual(['hero', 'core_product_families', 'why_junhui', 'rfq_cta'])
    expect(wrapper.findAll('[data-testid="homepage-product-card"]')).toHaveLength(3)
    expect(wrapper.findAll('[data-testid="homepage-product-card"] img')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('尚无可展示的已发布内容')
  })

  it('renders all fourteen positions only in authenticated preview mode', () => {
    const wrapper = mount(HomePage, {
      props: { locale: 'zh-cn', home: homepage(true), preview: true },
    })

    expect(
      wrapper.findAll('[data-home-module]').map((node) => node.attributes('data-home-module')),
    ).toEqual(moduleKeys)
    expect(wrapper.findAll('[data-testid="homepage-module-empty"]')).toHaveLength(10)
    expect(wrapper.findAll('h1')).toHaveLength(1)
  })

  it('keeps the preview route SSR-authenticated and no-store', () => {
    const route = readFileSync(resolve(process.cwd(), 'app/pages/preview/[lang]/index.vue'), 'utf8')
    const homePage = readFileSync(resolve(process.cwd(), 'app/components/HomePage.vue'), 'utf8')
    const nginx = readFileSync(
      resolve(process.cwd(), '../../infra/nginx/nginx.local-domain.conf'),
      'utf8',
    )

    expect(route).toContain('/presentation/homepage/${locale}/preview')
    expect(route).toContain("useRequestHeaders(['cookie'])")
    expect(route).toContain("'Cache-Control': 'private, no-store'")
    expect(route).toContain('noindex, nofollow')
    expect(homePage).toContain("props.preview ? 'noindex, nofollow' : seo.robots")
    expect(route).not.toMatch(/localStorage|route\\.query|preview=1/)
    expect(nginx).toContain('location ^~ /preview/')
    expect(nginx).toContain('location ^~ /preview-assets/_nuxt/')
    expect(nginx).toContain(`sub_filter '\"/_nuxt/' '\"/preview-assets/_nuxt/'`)
    expect(nginx).toContain('proxy_pass $website_preview_upstream')
  })

  it('uses differentiated visual structures for key homepage content families', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/components/HomepagePresentation.vue'),
      'utf8',
    )
    const about = readFileSync(resolve(process.cwd(), 'app/pages/[lang]/about.vue'), 'utf8')

    expect(source).toContain('presentation-materials')
    expect(source).toContain('presentation-applications')
    expect(source).toContain('presentation-technologies')
    expect(source).toContain('presentation-about__facts')
    expect(about).toContain('/public/products/${locale.value}')
    expect(about).toContain('about-page__product-rail')
    expect(about).toContain('about-page__market-grid')
    expect(about).toContain('about-page__advantages-grid')
    expect(about).toContain('about-page__contact-panel')
  })

  it('renders backend company advantages and a compact application text state', () => {
    const data = homepage()
    data.company!.full_intro = 'DEMO工作流说明。'
    data.company!.advantages = ['定制需求沟通', '加工与检测衔接', '配套件协同']
    data.applications = [
      {
        type: 'application',
        slug: 'demo-application',
        name: '汽车部件应用场景（演示）',
        url: '/zh-cn/applications/demo-application/',
        summary: '围绕需求记录与检查节点组织演示场景。',
        media: null,
      },
    ]
    data.presentation!.modules = data.presentation!.modules.map((module) =>
      module.key === 'special_applications'
        ? { ...module, content_status: 'available' }
        : module.key === 'why_junhui'
          ? { ...module, content_status: 'available' }
          : module,
    )

    const wrapper = mount(HomePage, { props: { locale: 'zh-cn', home: data } })

    expect(wrapper.text()).toContain('定制需求沟通')
    expect(wrapper.find('.presentation-applications__feature--text-only').exists()).toBe(true)
    expect(wrapper.find('.presentation-applications__feature').text()).toContain(
      '汽车部件应用场景（演示）',
    )
  })
})
