// 测试用途：锁定 Phase 3.6 全局 SSR Layout、桌面导航、移动导航、语言切换与 Footer 契约。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import LanguageSwitcher from '../app/components/LanguageSwitcher.vue'
import MobileNav from '../app/components/MobileNav.vue'
import SiteFooter from '../app/components/SiteFooter.vue'
import SiteHeader from '../app/components/SiteHeader.vue'
import { resolveRouteLocale } from '../app/composables/useLocalePath'
import type { NavigationDto, PublicLinkDto } from '../app/types/public'

/**
 * 构造严格发布的 canonical 导航链接。
 *
 * 输入：
 *   overrides: Partial<PublicLinkDto>，单测场景需要覆盖的公开字段。
 *
 * 输出：
 *   PublicLinkDto，不含任何内部 ID 的公开链接。
 */
function publishedLink(overrides: Partial<PublicLinkDto> = {}): PublicLinkDto {
  return {
    type: 'product',
    slug: 'injection-screws',
    name: 'Injection Molding Screws',
    url: '/en/products/injection-molding/injection-screws/',
    summary: 'Published navigation summary.',
    ...overrides,
  }
}

/** 返回覆盖桌面和移动导航的已发布 API fixture。 */
function navigationFixture(): NavigationDto {
  return {
    locale: 'en',
    primary: [
      'products',
      'solutions',
      'materials',
      'applications',
      'capabilities',
      'case_studies',
      'knowledge',
      'about',
    ],
    products: {
      categories: [publishedLink()],
      featured: [
        publishedLink({
          slug: 'twin-screw',
          name: 'Twin Screws & Barrels',
          url: '/en/products/extrusion/twin-screw/',
        }),
      ],
    },
    solutions: {
      featured: [
        publishedLink({
          type: 'solution',
          slug: 'corrosion-resistant',
          name: 'Corrosion Resistance',
          url: '/en/solutions/corrosion-resistant/',
        }),
      ],
      problems: [
        publishedLink({
          type: 'solution',
          slug: 'screw-wear',
          name: 'Screw Wear',
          url: '/en/solutions/screw-wear/',
        }),
      ],
    },
    materials: [
      publishedLink({
        type: 'material',
        slug: 'peek',
        name: 'PEEK',
        url: '/en/materials/peek/',
      }),
    ],
    applications: [],
    company: {
      name: 'API Company Name',
      phone: '+86 000 0000',
      email: 'public@example.com',
      address: null,
    },
  }
}

afterEach(() => {
  document.body.style.overflow = ''
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('Phase 3.6 desktop navigation', () => {
  it('renders the fixed desktop routes, RFQ CTA, and canonical published DTO links', async () => {
    const wrapper = mount(SiteHeader, {
      props: { navigation: navigationFixture(), locale: 'en' },
      attachTo: document.body,
    })

    for (const label of [
      'Products',
      'Solutions',
      'Materials',
      'Applications',
      'Capabilities',
      'Case Studies',
      'Knowledge',
      'About',
    ]) {
      expect(wrapper.get('[data-testid="desktop-nav"]').text()).toContain(label)
    }
    expect(wrapper.get('[data-testid="rfq-cta"]').attributes('href')).toBe('/en/request-a-quote/')

    await wrapper.get('[data-testid="desktop-products-toggle"]').trigger('click')
    expect(wrapper.getComponent({ name: 'MegaMenu' }).isVisible()).toBe(true)
    expect(wrapper.html()).toContain('Injection Molding Screws')
    expect(
      wrapper.find('a[href="/en/products/injection-molding/injection-screws/"]').exists(),
    ).toBe(true)
    expect(wrapper.find('a[href="/en/products/extrusion/twin-screw/"]').exists()).toBe(true)
  })

  it('opens Product and Solution menus with button semantics and problem grouping', async () => {
    const wrapper = mount(SiteHeader, {
      props: { navigation: navigationFixture(), locale: 'en' },
      attachTo: document.body,
    })
    const products = wrapper.get('[data-testid="desktop-products-toggle"]')
    const solutions = wrapper.get('[data-testid="desktop-solutions-toggle"]')

    expect(products.element.tagName).toBe('BUTTON')
    expect(products.attributes('aria-expanded')).toBe('false')
    await products.trigger('click')
    expect(products.attributes('aria-expanded')).toBe('true')

    await solutions.trigger('click')
    expect(products.attributes('aria-expanded')).toBe('false')
    expect(solutions.attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('Solve a Problem')
    expect(wrapper.text()).toContain('Screw Wear')
    expect(wrapper.find('a[href="/en/solutions/"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/en/materials/"]').exists()).toBe(true)

    // Disclosure 的首个子链接必须紧随触发按钮，避免键盘焦点绕过整个 Header。
    const interactiveElements = wrapper.findAll('button, a')
    const productToggleIndex = interactiveElements.findIndex(
      (item) => item.attributes('data-testid') === 'desktop-products-toggle',
    )
    const firstProductLinkIndex = interactiveElements.findIndex(
      (item) => item.attributes('href') === '/en/products/injection-molding/injection-screws/',
    )
    expect(firstProductLinkIndex).toBe(productToggleIndex + 1)
  })

  it('closes on Escape and outside click, then restores focus to the opener', async () => {
    const wrapper = mount(SiteHeader, {
      props: { navigation: navigationFixture(), locale: 'en' },
      attachTo: document.body,
    })
    const toggle = wrapper.get<HTMLButtonElement>('[data-testid="desktop-products-toggle"]')

    await toggle.trigger('click')
    await toggle.trigger('keydown', { key: 'Escape' })
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(toggle.element)

    await toggle.trigger('click')
    const outsideButton = document.createElement('button')
    document.body.append(outsideButton)
    outsideButton.focus()
    outsideButton.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(outsideButton)
  })

  it('keeps static routes when optional groups are empty and omits empty dynamic panels', () => {
    const navigation: NavigationDto = {
      ...navigationFixture(),
      primary: [],
      products: { categories: [], featured: [] },
      solutions: { featured: [], problems: [] },
      materials: [],
      applications: [],
    }
    const wrapper = mount(SiteHeader, { props: { navigation, locale: 'en' } })

    expect(wrapper.get('[data-testid="desktop-nav"]').text()).toContain('Products')
    expect(wrapper.get('[data-testid="desktop-nav"]').text()).toContain('Applications')
    expect(wrapper.find('[data-testid="desktop-products-toggle"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="products-mega-menu"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Solve a Problem')
  })
})

describe('Phase 3.6 language and mobile navigation', () => {
  it('uses a published alternate and falls back to the target locale home', async () => {
    const wrapper = mount(LanguageSwitcher, {
      props: {
        locale: 'en',
        alternates: { 'zh-CN': '/zh-cn/products/injection-molding/injection-screws/' },
      },
      attachTo: document.body,
    })
    await wrapper.get('button').trigger('click')
    expect(wrapper.get('a').attributes('href')).toBe(
      '/zh-cn/products/injection-molding/injection-screws/',
    )

    await wrapper.setProps({ alternates: {} })
    expect(wrapper.get('a').attributes('href')).toBe('/zh-cn/')
  })

  it('reads the current page published hreflang link when the layout has no alternate prop', async () => {
    const alternate = document.createElement('link')
    alternate.rel = 'alternate'
    alternate.hreflang = 'zh-CN'
    alternate.href = 'https://junhuiscrewbarrel.com/zh-cn/products/published/'
    document.head.append(alternate)
    const wrapper = mount(LanguageSwitcher, {
      props: { locale: 'en' },
      attachTo: document.body,
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.get('a').attributes('href')).toBe(
      'https://junhuiscrewbarrel.com/zh-cn/products/published/',
    )
    alternate.remove()
  })

  it('locks body scroll only while open, closes with Escape, and restores trigger focus', async () => {
    const wrapper = mount(SiteHeader, {
      props: { navigation: navigationFixture(), locale: 'en' },
      attachTo: document.body,
    })
    const toggle = wrapper.get<HTMLButtonElement>('[data-testid="mobile-nav-toggle"]')

    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(document.body.style.overflow).toBe('')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.activeElement).toBe(
      wrapper.getComponent(MobileNav).get('[data-testid="mobile-nav-close"]').element,
    )
    expect(wrapper.getComponent(MobileNav).attributes('role')).toBe('dialog')
    expect(wrapper.getComponent(MobileNav).attributes('aria-modal')).toBe('true')
    expect(
      wrapper.getComponent(MobileNav).get('[data-testid="mobile-rfq-cta"]').attributes('href'),
    ).toBe('/en/request-a-quote/')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(toggle.element)
  })

  it('removes the body lock on unmount and renders published accordion links only', async () => {
    const wrapper = mount(MobileNav, {
      props: { open: true, navigation: navigationFixture(), locale: 'en' },
      attachTo: document.body,
    })
    expect(document.body.style.overflow).toBe('hidden')

    const products = wrapper.get('[data-testid="mobile-products-toggle"]')
    expect(products.attributes('aria-expanded')).toBe('false')
    await products.trigger('click')
    expect(products.attributes('aria-expanded')).toBe('true')
    expect(
      wrapper.find('a[href="/en/products/injection-molding/injection-screws/"]').exists(),
    ).toBe(true)
    expect(wrapper.find('[data-testid="mobile-applications-toggle"]').exists()).toBe(false)

    wrapper.unmount()
    expect(document.body.style.overflow).toBe('')
  })
})

describe('Phase 3.6 footer and SSR layout', () => {
  it('renders only returned company fields plus legal, sitemap, and locale links', () => {
    const wrapper = mount(SiteFooter, {
      props: { navigation: navigationFixture(), locale: 'en', termsUrl: null },
    })

    expect(wrapper.text()).toContain('API Company Name')
    expect(wrapper.text()).toContain('+86 000 0000')
    expect(wrapper.text()).toContain('public@example.com')
    expect(wrapper.text()).not.toContain('undefined')
    expect(wrapper.text()).not.toContain('Terms')
    expect(wrapper.find('a[href="/en/privacy/"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/sitemap.xml"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/zh-cn/"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(String(new Date().getFullYear()))
  })

  it('renders Terms only when a published route is supplied and omits absent company data', () => {
    const wrapper = mount(SiteFooter, {
      props: {
        navigation: { ...navigationFixture(), company: null },
        locale: 'en',
        termsUrl: '/en/terms/',
      },
    })

    expect(wrapper.text()).not.toContain('API Company Name')
    expect(wrapper.find('a[href="/en/terms/"]').text()).toBe('Terms')
  })

  it('uses the Nuxt default layout and a stable SSR navigation request', () => {
    const app = readFileSync(resolve(process.cwd(), 'app/app.vue'), 'utf8')
    const layout = readFileSync(resolve(process.cwd(), 'app/layouts/default.vue'), 'utf8')

    expect(app).toContain('<NuxtLayout>')
    expect(layout).toMatch(/await\s+useAsyncData/)
    expect(layout).toContain('`navigation:${locale}`')
    expect(layout).toContain('`/public/navigation/${locale}`')
    expect(layout).toContain('<SiteHeader')
    expect(layout).toContain('<SiteFooter')
    expect(layout).toContain('<main id="main-content"')
  })

  it('derives locale from static locale homepage paths and keeps navigation fetch reactive', () => {
    expect(resolveRouteLocale(undefined, '/en/')).toBe('en')
    expect(resolveRouteLocale(undefined, '/zh-cn/')).toBe('zh-cn')
    expect(resolveRouteLocale('en', '/zh-cn/products/')).toBe('en')

    const layout = readFileSync(resolve(process.cwd(), 'app/layouts/default.vue'), 'utf8')
    expect(layout).toContain('route.path')
    expect(layout).toContain('navigationKey')
    expect(layout).toContain(':alternates="alternates"')
    expect(layout).toContain("useState('public-current-year'")
    expect(layout).toContain(':year="currentYear"')
  })

  it('keeps responsive breakpoints aligned and references only defined design tokens', () => {
    const globalCss = readFileSync(resolve(process.cwd(), 'app/assets/css/main.css'), 'utf8')
    const componentSources = [
      'SiteHeader.vue',
      'MegaMenu.vue',
      'MobileNav.vue',
      'LanguageSwitcher.vue',
      'SiteFooter.vue',
    ]
      .map((filename) => readFileSync(resolve(process.cwd(), 'app/components', filename), 'utf8'))
      .join('\n')

    expect(componentSources.match(/@media \(max-width: 74rem\)/g)).toHaveLength(2)
    const mobileSource = readFileSync(
      resolve(process.cwd(), 'app/components/MobileNav.vue'),
      'utf8',
    )
    expect(mobileSource).toContain("matchMedia('(min-width: 74.001rem)')")
    const referencedTokens = [...componentSources.matchAll(/var\((--[a-z0-9-]+)\)/g)].map(
      ([, token]) => token,
    )
    for (const token of referencedTokens) expect(globalCss).toContain(`${token}:`)
  })
})
