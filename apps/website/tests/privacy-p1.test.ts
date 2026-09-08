// 测试用途：锁定 Privacy P1 的安全 Markdown、SSR 页面与 RFQ 政策上下文契约。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive, ref, type Component } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PrivacyMarkdown from '../app/components/PrivacyMarkdown.vue'
import { useRfqPrivacy } from '../app/composables/useRfqPrivacy'
import type { PublicPrivacyPolicyDto } from '../app/types/public'
import { parsePrivacyMarkdown } from '../app/utils/privacyMarkdown'
import { isPrivacyContextFailure, publicRequestErrorCode } from '../app/utils/publicRequest'

/** 构造字段完整的公开政策响应，避免不完整 mock 隐藏真实 DTO 假设。 */
function privacyPolicy(versionLabel: string): PublicPrivacyPolicyDto {
  return {
    locale: 'en',
    title: `Privacy ${versionLabel}`,
    body_markdown: '# Policy',
    content_format: 'markdown',
    rendering_trust: 'untrusted',
    version_label: versionLabel,
    content_hash: `hash-${versionLabel}`,
    hash_algorithm: 'sha256-nfc-json-v1',
    effective_at: '2026-09-08T00:00:00+00:00',
    canonical_path: '/en/privacy/',
    canonical_url: 'https://junhuiscrewbarrel.com/en/privacy/',
    alternates: { 'zh-CN': '/zh-cn/privacy/', en: '/en/privacy/' },
    robots: { index: false, follow: true },
  }
}

/** 在 Suspense 中真实挂载带顶层 await 的 Nuxt 页面，并等待挂载后的 context 请求。 */
async function mountAsyncPage(component: Component, attachToDocument = false) {
  const frameworkInfo = vi.spyOn(console, 'info').mockImplementation(() => undefined)
  try {
    const wrapper = mount(
      defineComponent({
        components: { AsyncPage: component },
        template: '<Suspense><AsyncPage /></Suspense>',
      }),
      attachToDocument ? { attachTo: document.body } : undefined,
    )
    await flushPromises()
    return wrapper
  } finally {
    frameworkInfo.mockRestore()
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('Privacy P1 website surface', () => {
  it('provides a dedicated SSR page and restricted Markdown renderer', () => {
    for (const path of [
      'app/pages/[lang]/privacy/index.vue',
      'app/components/PrivacyMarkdown.vue',
      'app/components/PrivacyInline.vue',
      'app/utils/privacyMarkdown.ts',
      'app/composables/useRfqPrivacy.ts',
    ]) {
      expect(existsSync(resolve(process.cwd(), path)), path).toBe(true)
    }
  })

  it('exports the restricted Markdown parser', async () => {
    const markdown = await import('../app/utils/privacyMarkdown')

    expect(typeof markdown.parsePrivacyMarkdown).toBe('function')
  })

  it('exports the RFQ privacy state factory', async () => {
    const rfqPrivacy = await import('../app/composables/useRfqPrivacy')

    expect(typeof rfqPrivacy.useRfqPrivacy).toBe('function')
  })

  it('exports privacy-context error classification helpers', async () => {
    const publicRequest = await import('../app/utils/publicRequest')

    expect(typeof publicRequest.publicRequestErrorCode).toBe('function')
    expect(typeof publicRequest.isPrivacyContextFailure).toBe('function')
  })

  it('classifies every backend privacy_context_* error from ofetch error envelopes', () => {
    for (const code of [
      'privacy_context_stale',
      'privacy_context_required',
      'privacy_context_expired',
      'privacy_context_invalid',
      'privacy_context_locale_mismatch',
    ]) {
      const dataFailure = { data: { success: false, data: null, error: { code } } }
      const responseFailure = {
        response: { _data: { success: false, data: null, error: { code } } },
      }
      expect(publicRequestErrorCode(dataFailure)).toBe(code)
      expect(publicRequestErrorCode(responseFailure)).toBe(code)
      expect(isPrivacyContextFailure(dataFailure)).toBe(true)
    }

    expect(isPrivacyContextFailure({ data: { error: { code: 'validation_error' } } })).toBe(false)
    expect(publicRequestErrorCode(new Error('network'))).toBeNull()
  })

  it('exposes explicit client-context initialization and recovery actions', () => {
    const initialPolicy = privacyPolicy('privacy-v1')
    const state = useRfqPrivacy({
      initialPolicy,
      consentPrivacy: ref(false),
      loadPolicy: async () => initialPolicy,
      loadContext: async () => ({
        token: 'token-v1',
        expires_at: '2026-09-08T00:15:00+00:00',
        version_label: 'privacy-v1',
        locale: 'en',
      }),
    }) as {
      initializeContext?: unknown
      recoverContext?: unknown
      contextToken?: unknown
    }

    expect(typeof state.initializeContext).toBe('function')
    expect(typeof state.recoverContext).toBe('function')
    expect(state.contextToken).toBeDefined()
  })

  it('requests context only for an available current policy and never checks consent automatically', async () => {
    const initialPolicy = privacyPolicy('privacy-v1')
    const consentPrivacy = ref(false)
    const loadContext = vi.fn(async () => ({
      token: 'token-v1',
      expires_at: '2026-09-08T00:15:00+00:00',
      version_label: 'privacy-v1',
      locale: 'en' as const,
    }))
    const state = useRfqPrivacy({
      initialPolicy,
      consentPrivacy,
      loadPolicy: async () => initialPolicy,
      loadContext,
    })

    expect(state.contextToken.value).toBe('')
    expect(consentPrivacy.value).toBe(false)
    await expect(state.initializeContext()).resolves.toBe(true)
    expect(loadContext).toHaveBeenCalledWith(initialPolicy)
    expect(state.contextToken.value).toBe('token-v1')
    expect(consentPrivacy.value).toBe(false)
  })

  it('recovers once when SSR policy changes before the first context is issued', async () => {
    const policyA = privacyPolicy('privacy-v1')
    const policyB = privacyPolicy('privacy-v2')
    const loadPolicy = vi.fn(async () => policyB)
    const loadContext = vi
      .fn()
      .mockRejectedValueOnce(new Error('stale A'))
      .mockResolvedValueOnce({
        token: 'token-v2',
        expires_at: '2026-09-08T00:15:00+00:00',
        version_label: 'privacy-v2',
        locale: 'en' as const,
      })
    const consentPrivacy = ref(true)
    const state = useRfqPrivacy({
      initialPolicy: policyA,
      consentPrivacy,
      loadPolicy,
      loadContext,
    })

    await expect(state.initializeContext()).resolves.toBe(true)
    expect(loadPolicy).toHaveBeenCalledOnce()
    expect(loadContext).toHaveBeenNthCalledWith(1, policyA)
    expect(loadContext).toHaveBeenNthCalledWith(2, policyB)
    expect(state.policy.value?.version_label).toBe('privacy-v2')
    expect(state.contextToken.value).toBe('token-v2')
    expect(consentPrivacy.value).toBe(false)
  })

  it('does not request a token when SSR found no publishable policy', async () => {
    const loadContext = vi.fn()
    const state = useRfqPrivacy({
      initialPolicy: null,
      consentPrivacy: ref(false),
      loadPolicy: async () => privacyPolicy('privacy-v1'),
      loadContext,
    })

    await expect(state.initializeContext()).resolves.toBe(false)
    expect(loadContext).not.toHaveBeenCalled()
    expect(state.contextToken.value).toBe('')
  })

  it('recovers A to B by clearing consent while preserving form fields and selected File objects', async () => {
    const policyA = privacyPolicy('privacy-v1')
    const policyB = privacyPolicy('privacy-v2')
    const consentPrivacy = ref(true)
    const form = reactive({ company_name: 'ACME', message: 'Keep these dimensions' })
    const selectedFile = new File(['step-data'], 'assembly.step', {
      type: 'application/step',
    })
    const attachments = [{ id: 'file-1', file: selectedFile, status: 'pending' as const }]
    const state = useRfqPrivacy({
      initialPolicy: policyA,
      consentPrivacy,
      loadPolicy: async () => policyB,
      loadContext: async (policy) => ({
        token: policy.version_label === 'privacy-v1' ? 'token-v1' : 'token-v2',
        expires_at: '2026-09-08T00:15:00+00:00',
        version_label: policy.version_label,
        locale: policy.locale,
      }),
    })

    await state.initializeContext()
    expect(state.contextToken.value).toBe('token-v1')
    await expect(state.recoverContext()).resolves.toBe(true)

    expect(state.policy.value?.version_label).toBe('privacy-v2')
    expect(state.contextToken.value).toBe('token-v2')
    expect(consentPrivacy.value).toBe(false)
    expect(form).toEqual({ company_name: 'ACME', message: 'Keep these dimensions' })
    expect(attachments[0]?.file).toBe(selectedFile)
    expect(attachments[0]?.status).toBe('pending')
  })

  it('keeps submission disabled when refreshing the latest policy fails', async () => {
    const consentPrivacy = ref(true)
    const state = useRfqPrivacy({
      initialPolicy: privacyPolicy('privacy-v1'),
      consentPrivacy,
      loadPolicy: async () => {
        throw new Error('privacy unavailable')
      },
      loadContext: vi.fn(),
    })

    await expect(state.recoverContext()).resolves.toBe(false)
    expect(state.policy.value).toBeNull()
    expect(state.contextToken.value).toBe('')
    expect(consentPrivacy.value).toBe(false)
  })

  it('parses and renders only the supported structural Markdown subset', () => {
    const markdown = [
      '# Collection',
      '',
      'A **strong** and *careful* paragraph with `inline code`.',
      '',
      '- First item',
      '- Second item',
      '',
      '1. Ordered item',
      '2. Another item',
      '',
      '> Quoted policy note',
      '',
      '```text',
      'const value = "safe"',
      '```',
      '',
      '[Website](https://example.com) [Email](mailto:privacy@example.com) [Local](/en/privacy/)',
    ].join('\n')

    expect(parsePrivacyMarkdown(markdown).map((block) => block.type)).toEqual([
      'heading',
      'paragraph',
      'list',
      'list',
      'blockquote',
      'code',
      'paragraph',
    ])

    const wrapper = mount(PrivacyMarkdown, { props: { markdown } })
    expect(wrapper.find('h1').exists()).toBe(false)
    expect(wrapper.get('h2').text()).toBe('Collection')
    expect(wrapper.get('strong').text()).toBe('strong')
    expect(wrapper.get('em').text()).toBe('careful')
    expect(wrapper.get('p code').text()).toBe('inline code')
    expect(wrapper.findAll('ul > li')).toHaveLength(2)
    expect(wrapper.findAll('ol > li')).toHaveLength(2)
    expect(wrapper.get('blockquote').text()).toContain('Quoted policy note')
    expect(wrapper.get('pre code').text()).toContain('const value = "safe"')
    expect(wrapper.get('a[href="https://example.com"]').exists()).toBe(true)
    expect(wrapper.get('a[href="mailto:privacy@example.com"]').exists()).toBe(true)
    expect(wrapper.get('a[href="/en/privacy/"]').exists()).toBe(true)
  })

  it('keeps invalid Unicode numeric entities inert instead of crashing SSR rendering', () => {
    for (const markdown of [
      '[overflow](&#999999999999;)',
      '[decimal surrogate](&#55296;)',
      '[hex surrogate](&#xDFFF;)',
    ]) {
      expect(() => parsePrivacyMarkdown(markdown)).not.toThrow()
      const wrapper = mount(PrivacyMarkdown, { props: { markdown } })
      expect(wrapper.findAll('a')).toHaveLength(0)
      expect(wrapper.text()).toContain(markdown)
    }
  })

  it('uses an index-based inline scanner and preserves a large malformed token run', () => {
    const source = readFileSync(resolve(process.cwd(), 'app/utils/privacyMarkdown.ts'), 'utf8')
    expect(source).not.toContain('remaining = remaining.slice')

    const malformed = '['.repeat(20_000)
    const blocks = parsePrivacyMarkdown(malformed)
    expect(blocks).toHaveLength(1)
    expect(blocks[0]?.type).toBe('paragraph')
    if (blocks[0]?.type === 'paragraph') {
      expect(blocks[0].children).toEqual([{ type: 'text', value: malformed }])
    }
  })

  it('keeps malicious HTML, unsafe links, images, and unknown syntax inert as text', () => {
    const markdown = [
      '<script>alert("x")</script>',
      '<img src="https://attacker.example/tracker.png">',
      '![remote](https://attacker.example/pixel.png)',
      '[script](javascript:alert(1))',
      '[encoded](java%73cript:alert(1))',
      '[payload](data:text/html,boom)',
      '[mail header](mailto:privacy@example.com?body=%0ABcc:attacker@example.com)',
      '| unsupported | table |',
    ].join('\n\n')

    const wrapper = mount(PrivacyMarkdown, { props: { markdown } })
    const html = wrapper.html()

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(html).not.toContain('href="javascript:')
    expect(html).not.toContain('href="data:')
    expect(wrapper.text()).toContain('<script>alert("x")</script>')
    expect(wrapper.text()).toContain('![remote](https://attacker.example/pixel.png)')
    expect(wrapper.text()).toContain('| unsupported | table |')
  })

  it('implements a real SSR Privacy route with strict 404 and backend-owned SEO', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/privacy/index.vue'),
      'utf8',
    )

    expect(source).toContain('await useAsyncData')
    expect(source).toContain('`/public/privacy/${locale}`')
    expect(source).toContain('publicRequestStatus(error.value)')
    expect(source).toContain('createError')
    expect(source).toContain('statusCode: 404')
    expect(source).toContain('policy.value.canonical_url')
    expect(source).toContain('policy.value.alternates')
    expect(source).toContain('policy.value.robots')
    expect(source).toContain('<PrivacyMarkdown :markdown="policy.body_markdown" />')
    expect(source.match(/<h1(?:\s|>)/g)).toHaveLength(1)
    expect(source).toContain('policy.version_label')
    expect(source).toContain('policy.value.effective_at')
    expect(source).not.toContain('v-html')
    expect(source).not.toContain('<img')
  })

  it('binds RFQ submission to a client-memory privacy context with explicit recovery', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'app/pages/[lang]/request-a-quote/index.vue'),
      'utf8',
    )

    expect(source).toContain('await useAsyncData(`rfq-privacy:${locale}`')
    expect(source).toContain('`/public/privacy/${locale}`')
    expect(source).toContain('useRfqPrivacy')
    expect(source).toContain('onMounted')
    expect(source).toContain('`/public/privacy/${locale}/context/${encodeURIComponent(')
    expect(source).toContain('isPrivacyContextFailure(failure)')
    expect(source).toContain('recoverContext()')
    expect(source).toContain('contextToken.value')
    expect(source).toContain('labels.privacy.unavailable')
    expect(source).toContain(':disabled="!privacyPolicy || !contextToken || isContextLoading"')
    expect(source).toContain('!canSubmit')
    expect(source).not.toContain('localStorage')
    expect(source).not.toContain('sessionStorage')
    expect(source).not.toContain('console.')
    expect(source).not.toContain('useAsyncData(`privacy-context')
  })

  it('keeps the RFQ visible but disables consent and submission when SSR finds no policy', async () => {
    const api = vi.fn()
    vi.stubGlobal('useApi', () => api)
    vi.stubGlobal('useRoute', () => ({ params: { lang: 'en' }, query: {} }))
    vi.stubGlobal('useAsyncData', async () => ({
      data: ref(null),
      error: ref({ statusCode: 404 }),
    }))
    vi.stubGlobal('useHead', vi.fn())
    const { default: RfqPage } = await import('../app/pages/[lang]/request-a-quote/index.vue')
    const wrapper = await mountAsyncPage(RfqPage)

    expect(wrapper.get('#rfq-company').exists()).toBe(true)
    expect(wrapper.text()).toContain(
      'The privacy notice is awaiting publication. Submission is unavailable.',
    )
    expect(wrapper.get<HTMLInputElement>('.rfq-form__check input').element.checked).toBe(false)
    expect(wrapper.get('.rfq-form__check input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.rfq-form__submit').attributes('disabled')).toBeDefined()
    expect(wrapper.get('a[href="/en/privacy/"]').exists()).toBe(true)
    expect(api).not.toHaveBeenCalled()
  })

  it.each([
    {
      scenario: 'stale version',
      failure: {
        data: {
          success: false,
          data: null,
          error: { code: 'privacy_context_stale', message: 'stale', details: null },
        },
      },
    },
    {
      scenario: 'forged token',
      failure: {
        data: {
          success: false,
          data: null,
          error: { code: 'privacy_context_invalid', message: 'invalid', details: null },
        },
      },
    },
    {
      scenario: 'wrong-language token',
      failure: {
        response: {
          _data: {
            success: false,
            data: null,
            error: {
              code: 'privacy_context_locale_mismatch',
              message: 'locale mismatch',
              details: null,
            },
          },
        },
      },
    },
  ])(
    'recovers $scenario from A to B, preserves fields and File, focuses summary, and uploads nothing',
    async ({ failure }) => {
      const policyA = privacyPolicy('privacy-v1')
      const policyB = privacyPolicy('privacy-v2')
      const api = vi
        .fn()
        .mockResolvedValueOnce({
          data: {
            token: 'token-v1',
            expires_at: '2026-09-08T00:15:00+00:00',
            version_label: policyA.version_label,
            locale: policyA.locale,
          },
        })
        .mockRejectedValueOnce(failure)
        .mockResolvedValueOnce({ success: true, data: policyB, error: null })
        .mockResolvedValueOnce({
          data: {
            token: 'token-v2',
            expires_at: '2026-09-08T00:30:00+00:00',
            version_label: policyB.version_label,
            locale: policyB.locale,
          },
        })
      vi.stubGlobal('useApi', () => api)
      vi.stubGlobal('useRoute', () => ({ params: { lang: 'en' }, query: {} }))
      vi.stubGlobal('useAsyncData', async () => ({
        data: ref({ success: true, data: policyA, error: null }),
        error: ref(null),
      }))
      vi.stubGlobal('useHead', vi.fn())
      const { default: RfqPage } = await import('../app/pages/[lang]/request-a-quote/index.vue')
      const wrapper = await mountAsyncPage(RfqPage, true)

      await wrapper.get('#rfq-company').setValue('ACME')
      await wrapper.get('#rfq-contact').setValue('Lee')
      await wrapper.get('#rfq-email').setValue('lee@example.com')
      await wrapper.get<HTMLInputElement>('.rfq-form__check input').setValue(true)
      const selectedFile = new File(['step-data'], 'assembly.step', { type: 'application/step' })
      const fileInput = wrapper.get<HTMLInputElement>('#rfq-files')
      Object.defineProperty(fileInput.element, 'files', {
        configurable: true,
        value: [selectedFile],
      })
      await fileInput.trigger('change')
      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.get<HTMLInputElement>('#rfq-company').element.value).toBe('ACME')
      expect(wrapper.get<HTMLInputElement>('#rfq-email').element.value).toBe('lee@example.com')
      expect(wrapper.get<HTMLInputElement>('.rfq-form__check input').element.checked).toBe(false)
      expect(wrapper.text()).toContain('assembly.step')
      expect(wrapper.text()).toContain('actively confirm again')
      expect(document.activeElement).toBe(wrapper.get('[role="alert"]').element)
      expect(api.mock.calls.filter(([path]) => path === '/public/rfqs')).toHaveLength(1)
      expect(api.mock.calls.some(([path]) => String(path).endsWith('/files'))).toBe(false)
      expect(api.mock.calls[1]?.[1]?.body).toMatchObject({
        privacy_context_token: 'token-v1',
        consent_privacy: true,
      })
      expect(api.mock.calls.at(-1)?.[0]).toContain('/context/privacy-v2')
    },
  )

  it('distinguishes an available refreshed policy from a temporarily unavailable context', async () => {
    const policyA = privacyPolicy('privacy-v1')
    const policyB = privacyPolicy('privacy-v2')
    const api = vi
      .fn()
      .mockResolvedValueOnce({
        data: {
          token: 'token-v1',
          expires_at: '2026-09-08T00:15:00+00:00',
          version_label: policyA.version_label,
          locale: policyA.locale,
        },
      })
      .mockRejectedValueOnce({ data: { error: { code: 'privacy_context_expired' } } })
      .mockResolvedValueOnce({ success: true, data: policyB, error: null })
      .mockRejectedValueOnce(new Error('context unavailable'))
    vi.stubGlobal('useApi', () => api)
    vi.stubGlobal('useRoute', () => ({ params: { lang: 'en' }, query: {} }))
    vi.stubGlobal('useAsyncData', async () => ({
      data: ref({ success: true, data: policyA, error: null }),
      error: ref(null),
    }))
    vi.stubGlobal('useHead', vi.fn())
    const { default: RfqPage } = await import('../app/pages/[lang]/request-a-quote/index.vue')
    const wrapper = await mountAsyncPage(RfqPage)

    await wrapper.get('#rfq-company').setValue('ACME')
    await wrapper.get('#rfq-contact').setValue('Lee')
    await wrapper.get('#rfq-email').setValue('lee@example.com')
    await wrapper.get<HTMLInputElement>('.rfq-form__check input').setValue(true)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Privacy confirmation is temporarily unavailable.')
    expect(wrapper.text()).toContain('privacy-v2')
    expect(wrapper.get('.rfq-form__check input').attributes('disabled')).toBeDefined()
  })
})
