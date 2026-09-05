// 测试用途：锁定 Search、RFQ、语言切换、错误恢复与隐私安全遥测的最终交互契约。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import LanguageSwitcher from '../app/components/LanguageSwitcher.vue'
import { TELEMETRY_EVENTS, useTelemetry } from '../app/composables/useTelemetry'
import { buildRfqSubmissionPayload, pendingAttachmentSnapshot } from '../app/utils/rfqSubmission'

/** 读取 Website app 内的源文件，便于锁定必须由 Nuxt SSR 执行的页面契约。 */
function readAppSource(path: string): string {
  return readFileSync(resolve(process.cwd(), 'app', path), 'utf8')
}

afterEach(() => {
  delete window.__JUNHUI_PUBLIC_TELEMETRY__
  vi.unstubAllGlobals()
})

describe('Phase 3.6 search journey', () => {
  it('keeps q in the SSR request and query-preserving pagination', () => {
    const source = readAppSource('pages/[lang]/search/index.vue')

    expect(source).toContain('useAsyncData')
    expect(source).toContain('`/public/search/${locale}`')
    expect(source).toContain('route.query.q')
    expect(source).toContain('query: { q: query.value, page:')
    expect(source).toContain("content: 'noindex,follow'")
    expect(source).toContain("rel: 'canonical'")
    expect(source).toContain("telemetry.track('search_submit'")
    expect(source).toContain('<label')
    expect(source).not.toContain('<main id="main-content"')
  })

  it('renders all six approved groups and safe no-result recovery routes', () => {
    const source = readAppSource('pages/[lang]/search/index.vue')

    for (const type of [
      'product',
      'material',
      'application',
      'solution',
      'knowledge_article',
      'case_study',
    ]) {
      expect(source).toContain(type)
    }
    expect(source).toContain('labels.empty.searchResults')
    expect(source).toContain('`/${locale}/products/`')
    expect(source).toContain('`/${locale}/knowledge/`')
    expect(source).toContain('`/${locale}/request-a-quote/`')
  })
})

describe('Phase 3.6 RFQ journey', () => {
  it('creates one RFQ and retries a failed attachment with the original submission token', async () => {
    const api = vi
      .fn()
      .mockResolvedValueOnce({
        data: {
          reference: 'RFQ-20260905-ABC123',
          status: 'received',
          submission_token: 'short-lived-token',
        },
      })
      .mockRejectedValueOnce(new Error('upload failed'))
      .mockResolvedValueOnce({ data: { status: 'received' } })
    vi.stubGlobal('useApi', () => api)
    vi.stubGlobal('useRoute', () => ({
      params: { lang: 'en' },
      query: { source_type: 'product', source_slug: 'precision-screw' },
    }))
    vi.stubGlobal('useHead', vi.fn())
    const { default: RfqPage } = await import('../app/pages/[lang]/request-a-quote/index.vue')
    const wrapper = mount(RfqPage)

    await wrapper.get('#rfq-company').setValue('ACME')
    await wrapper.get('#rfq-contact').setValue('Lee')
    await wrapper.get('#rfq-email').setValue('lee@example.com')
    await wrapper.get<HTMLInputElement>('.rfq-form__check input').setValue(true)
    const fileInput = wrapper.get<HTMLInputElement>('#rfq-files')
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [new File(['%PDF-example'], 'drawing.pdf', { type: 'application/pdf' })],
    })
    await fileInput.trigger('change')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const retry = wrapper.findAll('button').find((button) => button.text().includes('Try Again'))
    expect(retry).toBeDefined()
    await retry!.trigger('click')
    await flushPromises()

    expect(api.mock.calls.filter(([path]) => path === '/public/rfqs')).toHaveLength(1)
    expect(api.mock.calls.filter(([path]) => String(path).endsWith('/files'))).toHaveLength(2)
    expect(api.mock.calls[0]?.[1]?.body).toMatchObject({
      country_code: null,
      source_type: 'product',
      source_slug: 'precision-screw',
    })
    expect(wrapper.html()).not.toContain('short-lived-token')
  })

  it('normalizes optional blanks and submits only server-resolvable product attribution', () => {
    const payload = buildRfqSubmissionPayload(
      {
        company_name: ' ACME ',
        contact_name: ' Lee ',
        email: 'LEE@example.com',
        phone: '',
        whatsapp: ' ',
        country_code: '',
        website: '',
        message: '',
        preferred_language: 'en',
        consent_privacy: true,
        consent_marketing: false,
        honeypot: '',
        items: [
          {
            item_type: 'product',
            product_name_text: 'precision-screw',
            quantity: '',
            material_text: '',
            screw_diameter: '',
            length: '',
            machine_brand: '',
            machine_model: '',
            requirements: '',
          },
        ],
      },
      { type: 'product', slug: 'precision-screw' },
    )

    expect(payload).toMatchObject({
      company_name: 'ACME',
      contact_name: 'Lee',
      email: 'LEE@example.com',
      phone: null,
      whatsapp: null,
      country_code: null,
      website: null,
      message: null,
      source_type: 'product',
      source_slug: 'precision-screw',
    })
    expect(payload.items[0]).toMatchObject({ quantity: null, material_text: null })
    expect(payload).not.toHaveProperty('source_owner_id')
  })

  it('snapshots only pending or failed files so retries never re-upload completed files', () => {
    const attachments = [
      { id: 'one', file: new File(['1'], 'one.pdf'), status: 'uploaded' as const },
      { id: 'two', file: new File(['2'], 'two.pdf'), status: 'pending' as const },
      { id: 'three', file: new File(['3'], 'three.pdf'), status: 'failed' as const },
    ]
    const snapshot = pendingAttachmentSnapshot(attachments)
    attachments.push({
      id: 'four',
      file: new File(['4'], 'four.pdf'),
      status: 'pending' as const,
    })

    expect(snapshot.map((attachment) => attachment.id)).toEqual(['two', 'three'])
  })

  it('preserves product source context, multi-item fields, and the secure upload flow', () => {
    const source = readAppSource('pages/[lang]/request-a-quote/index.vue')

    expect(source).toContain('route.query.source_type')
    expect(source).toContain('route.query.source_slug')
    expect(source).toContain('candidate.slice(0, 180)')
    expect(source).toContain('source-context')
    expect(source).toContain('addItem')
    expect(source).toContain('removeItem')
    for (const field of ['phone', 'whatsapp', 'country_code', 'website', 'item_type']) {
      expect(source).toContain(field)
    }
    expect(source).toContain('submission_token')
    expect(source).toContain("'/public/rfqs'")
    expect(source).toContain('submissionReference')
    expect(source).toContain('retryFailedAttachments')
    expect(source).toContain(':disabled="isSubmitting || Boolean(result)"')
    expect(source).toContain('/files`')
    expect(source).not.toContain('download_url')
    expect(source).not.toContain('presigned')
  })

  it('shows localized validation, file policy, upload states, and success reference', () => {
    const source = readAppSource('pages/[lang]/request-a-quote/index.vue')
    const translations = readAppSource('i18n/ui.ts')

    for (const state of ["'pending'", "'uploading'", "'uploaded'", "'failed'"]) {
      expect(source).toContain(state)
    }
    expect(source).toContain('labels.form.filePolicy')
    expect(translations).toContain('单个文件不超过 25 MB')
    expect(translations).toContain('Maximum 25 MB per file')
    expect(source).toContain('labels.value.error.validation')
    expect(source).toContain('labels.form.successReference')
    expect(source).toContain('aria-describedby')
    expect(source).toContain('role="alert"')
    expect(source).toContain('role="status"')
    expect(source).not.toContain('<main id="main-content"')
  })

  it('keeps the anti-bot honeypot out of the accessibility tree and keyboard order', async () => {
    vi.stubGlobal('useApi', () => vi.fn())
    vi.stubGlobal('useRoute', () => ({ params: { lang: 'en' }, query: {} }))
    vi.stubGlobal('useHead', vi.fn())
    const { default: RfqPage } = await import('../app/pages/[lang]/request-a-quote/index.vue')
    const wrapper = mount(RfqPage)
    const honeypot = wrapper.get('label.honeypot')

    expect(honeypot.attributes('hidden')).toBeDefined()
    expect(honeypot.get('input').attributes('tabindex')).toBe('-1')
    expect(readAppSource('pages/[lang]/request-a-quote/index.vue')).toMatch(
      /\.honeypot\[hidden\][\s\S]*display:\s*none/,
    )
  })
})

describe('Phase 3.6 language, error, and telemetry behavior', () => {
  it('uses backend alternates and falls back to the target language home', async () => {
    const wrapper = mount(LanguageSwitcher, {
      props: {
        locale: 'en',
        alternates: { 'zh-CN': '/zh-cn/knowledge/published/' },
      },
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.get('a').attributes('href')).toBe('/zh-cn/knowledge/published/')
    await wrapper.setProps({ alternates: {} })
    expect(wrapper.get('a').attributes('href')).toBe('/zh-cn/')
    expect(wrapper.get('[data-testid="language-options"]').attributes('role')).toBeUndefined()
    expect(wrapper.get('a').attributes('role')).toBeUndefined()
  })

  it('offers friendly 404 and 500 recovery without rendering internal diagnostics', () => {
    const source = readAppSource('error.vue')

    expect(source).toContain('error.statusCode === 404')
    expect(source).toContain('labels.value.error.notFound')
    expect(source).toContain('labels.value.error.serverError')
    expect(source).toContain('`/${locale}/products/`')
    expect(source).toContain('`/${locale}/knowledge/`')
    expect(source).toContain('`/${locale}/search/`')
    expect(source).toContain('`/${locale}/request-a-quote/`')
    expect(source).not.toContain('error.stack')
    expect(source).not.toContain('error.message')
  })

  it('only exposes four typed events, no-ops without a provider, and strips unsafe payload keys', () => {
    expect(Object.keys(TELEMETRY_EVENTS)).toEqual([
      'rfq_cta_click',
      'search_submit',
      'download_click',
      'language_switch',
    ])

    const telemetry = useTelemetry()
    expect(() => telemetry.track('search_submit', { locale: 'en' })).not.toThrow()

    const provider = vi.fn()
    window.__JUNHUI_PUBLIC_TELEMETRY__ = provider
    telemetry.track('rfq_cta_click', {
      locale: 'en',
      sourceType: 'product',
      sourceSlug: 'published-product',
      ...({
        email: 'private@example.com',
        message: 'RFQ details',
        filename: 'secret.step',
      } as object),
    })

    expect(provider).toHaveBeenCalledWith('rfq_cta_click', {
      locale: 'en',
      sourceType: 'product',
      sourceSlug: 'published-product',
    })

    telemetry.track('search_submit', {
      locale: 'en',
      ...({ sourceSlug: 'must-not-cross-event-boundary' } as object),
    })
    expect(provider).toHaveBeenLastCalledWith('search_submit', { locale: 'en' })

    const callsBeforeUnknownEvent = provider.mock.calls.length
    ;(telemetry.track as (event: string, context: Record<string, unknown>) => void)(
      'unknown_event',
      { locale: 'en' },
    )
    expect(provider).toHaveBeenCalledTimes(callsBeforeUnknownEvent)
  })
})
