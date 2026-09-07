// 测试用途：锁定 Phase 3.6 公开站点 DTO、双语字典、路由、遥测与设计令牌契约。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, expectTypeOf, it, vi } from 'vitest'

import { ui } from '../app/i18n/ui'
import {
  alternateTarget,
  localeHome,
  normalizeLocale,
  rfqUrl,
  sameSiteRelativeTarget,
} from '../app/composables/useLocalePath'
import { useTelemetry } from '../app/composables/useTelemetry'
import type {
  GeoDto,
  HomeDto,
  NavigationDto,
  PublicCardDto,
  PublicLinkDto,
  PublicMediaDto,
  PublicSpecDto,
  SeoDto,
} from '../app/types/public'

/**
 * 递归收集本地化字典中的叶子 key。
 *
 * 输入：
 *   value: unknown，当前遍历的字典节点。
 *   prefix: string，当前节点的点分路径。
 *
 * 输出：
 *   string[]，排序后的所有叶子 key。
 */
function leafKeys(value: unknown, prefix = ''): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [prefix]

  return Object.entries(value)
    .flatMap(([key, child]) => leafKeys(child, prefix ? `${prefix}.${key}` : key))
    .sort()
}

describe('Phase 3.6 public foundation', () => {
  it('keeps zh-cn and en dictionary keys recursively identical', () => {
    expect(Object.keys(ui)).toEqual(['zh-cn', 'en'])
    expect(leafKeys(ui['zh-cn'])).toEqual(leafKeys(ui.en))

    // 所有公开 UI 文案必须是非空字符串，避免页面出现 undefined 或空按钮。
    for (const dictionary of Object.values(ui)) {
      for (const key of leafKeys(dictionary)) {
        const label = key
          .split('.')
          .reduce<unknown>(
            (current, segment) => (current as Record<string, unknown>)[segment],
            dictionary,
          )
        expect(label, key).toEqual(expect.any(String))
        expect((label as string).trim(), key).not.toBe('')
      }
    }
  })

  it('covers navigation, CTA, form, empty-state, error, and status labels', () => {
    const keys = leafKeys(ui.en)
    for (const requiredKey of [
      'navigation.products',
      'navigation.solveAProblem',
      'navigation.search',
      'navigation.language',
      'cta.requestQuote',
      'cta.exploreProducts',
      'cta.readTechnicalGuide',
      'form.contactInformation',
      'form.inquiryItems',
      'form.attachments',
      'form.privacy',
      'form.submit',
      'upload.pending',
      'upload.uploading',
      'upload.uploaded',
      'upload.failed',
      'empty.products',
      'empty.knowledge',
      'empty.searchResults',
      'error.notFound',
      'error.serverError',
      'error.validation',
      'error.uploadFailed',
    ]) {
      expect(keys).toContain(requiredKey)
    }
  })

  it('defines exact public DTOs without internal identifiers', () => {
    const link: PublicLinkDto = {
      type: 'product',
      slug: 'precision-screw',
      name: 'Precision Screw',
      url: '/en/products/injection/precision-screw/',
      summary: 'A published product.',
    }
    const media: PublicMediaDto = {
      src: '/api/v1/public/media/asset',
      type: 'image',
      mime_type: 'image/webp',
      width: 1200,
      height: 800,
      alt: 'Precision screw',
      caption: null,
      loading: 'lazy',
    }
    const specification: PublicSpecDto = {
      name: 'Outer Diameter',
      value: '65',
      unit: 'mm',
      group: 'Dimensions',
      type: 'number',
    }
    const card: PublicCardDto = { ...link, media, specifications: [specification] }
    const seo: SeoDto = {
      title: 'Precision Screw',
      description: 'Published summary',
      canonical: 'https://junhuiscrewbarrel.com/en/products/injection/precision-screw/',
      robots: 'index, follow',
      hreflang: { en: 'https://junhuiscrewbarrel.com/en/products/injection/precision-screw/' },
    }
    const geo: GeoDto = {
      direct_answer: 'A concise public answer.',
      key_facts: ['Published fact'],
      evidence: ['Published evidence'],
      related_questions: ['Related question?'],
      last_reviewed_at: null,
    }
    const navigation: NavigationDto = {
      locale: 'en',
      primary: ['products', 'solutions'],
      products: { categories: [link], featured: [link] },
      solutions: { featured: [], problems: [] },
      materials: [],
      applications: [],
      company: null,
    }
    const home: HomeDto = {
      locale: 'en',
      company: null,
      hero_media: null,
      product_categories: [],
      featured_products: [card],
      materials: [],
      solutions: [],
      capabilities: [],
      applications: [],
      cases: [],
      knowledge: [],
      trust_summary: null,
      seo,
      schema: [],
    }

    expectTypeOf(link).toMatchTypeOf<PublicLinkDto>()
    expectTypeOf(media).toMatchTypeOf<PublicMediaDto>()
    expectTypeOf(specification).toMatchTypeOf<PublicSpecDto>()
    expectTypeOf(card).toMatchTypeOf<PublicCardDto>()
    expectTypeOf(navigation).toMatchTypeOf<NavigationDto>()
    expectTypeOf(home).toMatchTypeOf<HomeDto>()
    expectTypeOf(seo).toMatchTypeOf<SeoDto>()
    expectTypeOf(geo).toMatchTypeOf<GeoDto>()

    const typeSource = readFileSync(resolve(process.cwd(), 'app/types/public.ts'), 'utf8')
    expect(typeSource).not.toMatch(/\b(?:id|owner_id|storage_path|media_asset_id)\s*[?:]/i)
  })

  it('normalizes locales and falls back safely when an alternate is unavailable', () => {
    expect(normalizeLocale('zh-CN')).toBe('zh-cn')
    expect(normalizeLocale('EN')).toBe('en')
    expect(normalizeLocale('fr')).toBe('zh-cn')
    expect(localeHome('EN')).toBe('/en/')
    expect(localeHome(undefined)).toBe('/zh-cn/')
    expect(
      alternateTarget('zh-cn', {
        'zh-CN': 'https://junhuiscrewbarrel.com/zh-cn/products/precision-screw/',
      }),
    ).toBe('/zh-cn/products/precision-screw/')
    expect(alternateTarget('en', { 'zh-CN': '/zh-cn/products/precision-screw/' })).toBe('/en/')
    expect(
      alternateTarget('en', {
        en: 'https://junhuiscrewbarrel.com/en/products/precision-screw/?from=language#details',
      }),
    ).toBe('/en/products/precision-screw/?from=language#details')
    expect(alternateTarget('en', { en: 'https://example.com/en/products/foreign/' })).toBe('/en/')
    expect(alternateTarget('en', { en: 'javascript:alert(1)' })).toBe('/en/')
    expect(alternateTarget('en', { en: '//example.com/en/products/foreign/' })).toBe('/en/')
    expect(alternateTarget('en', { en: '/\\example.com/en/products/foreign/' })).toBe('/en/')
    expect(
      sameSiteRelativeTarget('//junhuiscrewbarrel.com/en/products/protocol-relative/', '/'),
    ).toBe('/')
    expect(
      sameSiteRelativeTarget('https://user@junhuiscrewbarrel.com/en/products/userinfo/', '/'),
    ).toBe('/')
    expect(sameSiteRelativeTarget('/en/products/%ZZ/', '/')).toBe('/')
  })

  it('builds an RFQ URL from public source context only', () => {
    expect(rfqUrl({ locale: 'en', type: 'product', slug: 'precision screw' })).toBe(
      '/en/request-a-quote/?source_type=product&source_slug=precision+screw',
    )
    expect(rfqUrl({ locale: 'zh-CN' })).toBe('/zh-cn/request-a-quote/')
  })

  it('keeps telemetry disabled without an adapter and excludes sensitive payload fields', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const telemetry = useTelemetry()

    telemetry.track('rfq_cta_click', {
      locale: 'en',
      sourceType: 'product',
      sourceSlug: 'precision-screw',
    })

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(Object.keys(telemetry.events)).toEqual([
      'rfq_cta_click',
      'search_submit',
      'download_click',
      'language_switch',
    ])
    const telemetrySource = readFileSync(
      resolve(process.cwd(), 'app/composables/useTelemetry.ts'),
      'utf8',
    )
    expect(telemetrySource).not.toMatch(/\b(?:formValue|email|phone|message|inquiry|rfqContent)\b/)
    expect(telemetrySource).not.toMatch(/(?:fetch\(|\$fetch|sendBeacon)/)
    fetchSpy.mockRestore()
  })

  it('forwards only allowlisted telemetry context and isolates adapter failures', () => {
    const adapter = vi.fn()
    vi.stubGlobal('window', { __JUNHUI_PUBLIC_TELEMETRY__: adapter })
    const telemetry = useTelemetry()

    try {
      telemetry.track('download_click', {
        locale: 'en',
        sourceSlug: ' public-download ',
        resourceType: 'document',
        privateValue: 'must-not-leave-page',
      } as Parameters<typeof telemetry.track>[1])
      expect(adapter).toHaveBeenCalledWith('download_click', {
        locale: 'en',
        sourceSlug: 'public-download',
        resourceType: 'document',
      })

      adapter.mockImplementation(() => {
        throw new Error('optional adapter unavailable')
      })
      expect(() => telemetry.track('language_switch', { targetLocale: 'zh-cn' })).not.toThrow()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('defines final public design tokens and safe semantic base styles', () => {
    const css = readFileSync(resolve(process.cwd(), 'app/assets/css/main.css'), 'utf8')
    for (const token of [
      '--color-navy-',
      '--color-blue-',
      '--color-green-',
      '--color-neutral-',
      '--color-success',
      '--color-warning',
      '--color-error',
      '--font-sans',
      '--font-technical',
      '--space-1: 0.25rem',
      '--space-2: 0.5rem',
      '--container-max',
      '--focus-ring',
      '--border-',
      '--shadow-',
      '--transition-',
      '--breakpoint-sm: 20rem',
      '--breakpoint-md: 48rem',
      '--breakpoint-lg: 64rem',
      '--breakpoint-xl: 80rem',
    ]) {
      expect(css).toContain(token)
    }
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
    expect(css).toContain(':focus-visible')
    expect(css).not.toMatch(/checkerboard|checkered/i)
    expect(css).not.toMatch(/\.admin(?:[-_\s:{.#]|$)/)
    expect(css).not.toContain('2 * var(')
  })

  it('installs both immutable brand PNG assets and keeps the wordmark RGBA', () => {
    for (const filename of ['junhui-mark.png', 'junhui-wordmark.png']) {
      const path = resolve(process.cwd(), 'public/brand', filename)
      expect(existsSync(path), filename).toBe(true)
      const image = readFileSync(path)
      expect(image.subarray(1, 4).toString('ascii')).toBe('PNG')
      if (filename === 'junhui-wordmark.png') {
        // PNG IHDR 的 color type 6 表示 RGBA，满足透明背景横向品牌素材契约。
        expect(image[25], filename).toBe(6)
      }
    }
  })

  it('sets browser security headers at the public reverse-proxy boundary', () => {
    const nginx = readFileSync(resolve(process.cwd(), '../../infra/nginx/nginx.conf'), 'utf8')

    expect(nginx).toContain('Content-Security-Policy')
    expect(nginx).toContain('X-Content-Type-Options')
    expect(nginx).toContain('Referrer-Policy')
    expect(nginx).toContain('X-Frame-Options')
  })
})
