// 测试用途：验证 Privacy 权限状态机与受限 Markdown 预览组件的数据结构。
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Privacy Admin component logic', () => {
  const adminUtilityPath = resolve(process.cwd(), 'app/utils/privacyAdmin.ts')
  const markdownUtilityPath = resolve(process.cwd(), 'app/utils/privacyMarkdown.ts')

  it('审核与发布必须具备三项组合权限', async () => {
    expect(existsSync(adminUtilityPath)).toBe(true)
    if (!existsSync(adminUtilityPath)) return
    const { canReviewPrivacy, hasPrivacyPublishPermissions } = await import(
      '../app/utils/privacyAdmin'
    )

    expect(canReviewPrivacy(['privacy.review', 'content.review'])).toBe(false)
    expect(canReviewPrivacy(['privacy.review', 'content.review', 'translation.review'])).toBe(true)
    expect(hasPrivacyPublishPermissions(['privacy.publish', 'content.publish'])).toBe(false)
    expect(
      hasPrivacyPublishPermissions(['privacy.publish', 'content.publish', 'translation.publish']),
    ).toBe(true)
  })

  it('与后端当前 frozenset intersection 对齐：任一 supporting update 权限即可编辑', async () => {
    const adminModule = (await import('../app/utils/privacyAdmin')) as Record<string, unknown>
    expect(typeof adminModule.canEditPrivacy).toBe('function')
    if (typeof adminModule.canEditPrivacy !== 'function') return
    const canEditPrivacy = adminModule.canEditPrivacy as (permissions: string[]) => boolean

    expect(canEditPrivacy(['privacy.edit'])).toBe(false)
    expect(canEditPrivacy(['privacy.edit', 'content.update'])).toBe(true)
    expect(canEditPrivacy(['privacy.edit', 'translation.update'])).toBe(true)
    expect(canEditPrivacy(['content.update', 'translation.update'])).toBe(false)
  })

  it('只允许 draft 编辑且仅在双语审核和生效时间齐全时发布', async () => {
    expect(existsSync(adminUtilityPath)).toBe(true)
    if (!existsSync(adminUtilityPath)) return
    const { canPublishDraft, isDraftEditable } = await import('../app/utils/privacyAdmin')
    const draft = {
      version_label: 'PRIVACY-000001',
      revision: 2,
      effective_at: '2026-09-08T00:00:00Z',
      cloned_from_version_label: null,
      created_at: '2026-09-08T00:00:00Z',
      translations: {
        'zh-CN': {
          locale: 'zh-CN' as const,
          title: '隐私政策',
          body_markdown: '正文',
          translation_status: 'draft',
          publication_status: 'draft',
          canonical_path: '/zh-cn/privacy/',
          route_active: false,
          route_indexable: false,
        },
        en: {
          locale: 'en' as const,
          title: 'Privacy Notice',
          body_markdown: 'Body',
          translation_status: 'draft',
          publication_status: 'draft',
          canonical_path: '/en/privacy/',
          route_active: false,
          route_indexable: false,
        },
      },
    }

    expect(isDraftEditable(draft)).toBe(true)
    expect(canPublishDraft(draft)).toBe(false)
    draft.translations['zh-CN'].translation_status = 'human_reviewed'
    expect(isDraftEditable(draft)).toBe(false)
    expect(canPublishDraft(draft)).toBe(false)
    draft.translations.en.translation_status = 'human_reviewed'
    expect(canPublishDraft(draft)).toBe(true)
    draft.effective_at = null
    expect(canPublishDraft(draft)).toBe(false)
  })

  it('未编辑生效时间时保留原 ISO，编辑后按 datetime-local 本地整秒语义提交', async () => {
    const adminModule = (await import('../app/utils/privacyAdmin')) as Record<string, unknown>
    expect(typeof adminModule.toPrivacyDateTimeLocal).toBe('function')
    expect(typeof adminModule.resolvePrivacyEffectiveAt).toBe('function')
    if (
      typeof adminModule.toPrivacyDateTimeLocal !== 'function' ||
      typeof adminModule.resolvePrivacyEffectiveAt !== 'function'
    ) {
      return
    }
    const toPrivacyDateTimeLocal = adminModule.toPrivacyDateTimeLocal as (
      value: string | null,
    ) => string
    const resolvePrivacyEffectiveAt = adminModule.resolvePrivacyEffectiveAt as (
      originalIso: string | null,
      localValue: string,
      edited: boolean,
    ) => string | null
    const originalIso = '2026-09-08T00:00:47.321+05:30'
    const displayedValue = toPrivacyDateTimeLocal(originalIso)

    expect(displayedValue).toMatch(/:47$/)
    expect(resolvePrivacyEffectiveAt(originalIso, displayedValue, false)).toBe(originalIso)

    const editedLocalValue = '2026-09-08T08:09:47.987'
    const editedDate = new Date(editedLocalValue)
    editedDate.setMilliseconds(0)
    expect(resolvePrivacyEffectiveAt(originalIso, editedLocalValue, true)).toBe(
      editedDate.toISOString(),
    )
    expect(resolvePrivacyEffectiveAt(originalIso, '', true)).toBeNull()
  })

  it('fresh GET 必须匹配 PUT 返回的服务端确认草稿', async () => {
    expect(existsSync(adminUtilityPath)).toBe(true)
    if (!existsSync(adminUtilityPath)) return
    const { savedDraftMatches } = await import('../app/utils/privacyAdmin')
    const submitted = {
      effective_at: '2026-09-08T00:00:00.000Z',
      translations: [
        { locale: 'zh-CN' as const, title: '隐私政策', body_markdown: '完整正文' },
        { locale: 'en' as const, title: 'Privacy Notice', body_markdown: 'Complete body' },
      ],
    }
    const draft = {
      version_label: 'PRIVACY-000001',
      revision: 3,
      effective_at: '2026-09-08T00:00:00Z',
      cloned_from_version_label: null,
      created_at: '2026-09-08T00:00:00Z',
      translations: Object.fromEntries(
        submitted.translations.map((item) => [
          item.locale,
          {
            ...item,
            translation_status: 'draft',
            publication_status: 'draft',
            canonical_path: `/${item.locale}/privacy/`,
            route_active: false,
            route_indexable: false,
          },
        ]),
      ),
    }

    const acknowledgedDraft = structuredClone(draft)

    expect(savedDraftMatches(draft, acknowledgedDraft)).toBe(true)
    draft.translations.en.body_markdown = 'stale body'
    expect(savedDraftMatches(draft, acknowledgedDraft)).toBe(false)
  })

  it('Unicode 空白边界以服务端确认值为准，不在 JS 重复 Python strip', async () => {
    const adminModule = (await import('../app/utils/privacyAdmin')) as Record<string, unknown>
    expect(adminModule.normalizePrivacyContent).toBeUndefined()
    const savedDraftMatches = adminModule.savedDraftMatches as (
      freshDraft: unknown,
      acknowledgedDraft: unknown,
    ) => boolean
    const backendAcknowledgedDraft = {
      version_label: 'PRIVACY-000001',
      revision: 4,
      effective_at: '2026-09-08T00:00:00Z',
      cloned_from_version_label: null,
      created_at: '2026-09-08T00:00:00Z',
      translations: {
        'zh-CN': {
          locale: 'zh-CN' as const,
          // 后端 Python strip 会去掉 U+001C/U+0085，但不会去掉 U+FEFF。
          title: '隐私政策\uFEFF',
          body_markdown: '\uFEFF第一行\n第二行\uFEFF',
          translation_status: 'draft',
          publication_status: 'draft',
          canonical_path: '/zh-cn/privacy/',
          route_active: false,
          route_indexable: false,
        },
        en: {
          locale: 'en' as const,
          title: 'Privacy Notice\uFEFF',
          body_markdown: '\uFEFFComplete body\uFEFF',
          translation_status: 'draft',
          publication_status: 'draft',
          canonical_path: '/en/privacy/',
          route_active: false,
          route_indexable: false,
        },
      },
    }
    const freshDraft = structuredClone(backendAcknowledgedDraft)

    expect('\u001c'.trim()).toBe('\u001c')
    expect('\u0085'.trim()).toBe('\u0085')
    expect('\uFEFF'.trim()).toBe('')
    expect(savedDraftMatches(freshDraft, backendAcknowledgedDraft)).toBe(true)
    freshDraft.translations.en.title = 'Privacy Notice'
    expect(savedDraftMatches(freshDraft, backendAcknowledgedDraft)).toBe(false)
  })

  it('将 Privacy 主读取错误区分为未初始化和可恢复读取失败', async () => {
    const adminModule = (await import('../app/utils/privacyAdmin')) as Record<string, unknown>
    expect(typeof adminModule.resolvePrivacyLoadFailure).toBe('function')
    if (typeof adminModule.resolvePrivacyLoadFailure !== 'function') return
    const resolvePrivacyLoadFailure = adminModule.resolvePrivacyLoadFailure as (error: unknown) => {
      initialized: boolean
      errorMessage: string
    }

    expect(resolvePrivacyLoadFailure({ response: { status: 404 } })).toEqual({
      initialized: false,
      errorMessage: '',
    })
    expect(resolvePrivacyLoadFailure({ statusCode: 503 })).toEqual({
      initialized: true,
      errorMessage: 'Privacy 状态读取失败，请检查权限或稍后重试。',
    })
  })

  it('受限 Markdown 将正文标题降级并拒绝危险 URL 解释', async () => {
    expect(existsSync(markdownUtilityPath)).toBe(true)
    if (!existsSync(markdownUtilityPath)) return
    const { parsePrivacyMarkdown, sanitizePrivacyLink } = await import(
      '../app/utils/privacyMarkdown'
    )

    const blocks = parsePrivacyMarkdown(
      '# 正文标题\n\n## 二级标题\n\n**粗体**、`代码`与[安全链接](https://example.com)。\n\n- 条目\n\n> 引用\n\n```html\n<script>alert(1)</script>\n```',
    )
    expect(blocks[0]).toMatchObject({ kind: 'heading', level: 2 })
    expect(blocks[1]).toMatchObject({ kind: 'heading', level: 2 })
    expect(blocks.some((block) => block.kind === 'unordered-list')).toBe(true)
    expect(blocks.some((block) => block.kind === 'blockquote')).toBe(true)
    expect(blocks.some((block) => block.kind === 'code')).toBe(true)
    expect(sanitizePrivacyLink('https://example.com/path')).toBe('https://example.com/path')
    expect(sanitizePrivacyLink('mailto:privacy@example.com')).toBe('mailto:privacy@example.com')
    expect(sanitizePrivacyLink('mailto:privacy@example.com?subject=Injected')).toBeNull()
    expect(sanitizePrivacyLink('mailto:first@example.com,second@example.com')).toBeNull()
    expect(sanitizePrivacyLink('/privacy/help')).toBe('/privacy/help')
    expect(sanitizePrivacyLink('privacy/help?lang=zh-CN#request')).toBe(
      'privacy/help?lang=zh-CN#request',
    )
    expect(sanitizePrivacyLink('?lang=en')).toBe('?lang=en')
    expect(sanitizePrivacyLink('//evil.example/path')).toBeNull()
    expect(sanitizePrivacyLink('/\\evil.example/path')).toBeNull()
    expect(sanitizePrivacyLink('https:\\evil.example/path')).toBeNull()
    expect(sanitizePrivacyLink('https://safe.example\\@evil.example/path')).toBeNull()
    expect(sanitizePrivacyLink('/safe\npath')).toBeNull()
    expect(sanitizePrivacyLink('\u0000/privacy')).toBeNull()
    expect(sanitizePrivacyLink('javascript:alert(1)')).toBeNull()
    expect(sanitizePrivacyLink('data:text/html,boom')).toBeNull()

    const unsafeInline = parsePrivacyMarkdown(
      '[危险链接](https:\\evil.example/path) 与 [安全链接](/privacy/help)',
    )[0]
    expect(unsafeInline).toMatchObject({ kind: 'paragraph' })
    if (unsafeInline?.kind !== 'paragraph') return
    expect(
      unsafeInline.tokens.some((token) => token.kind === 'link' && token.text === '危险链接'),
    ).toBe(false)
    expect(unsafeInline.tokens).toContainEqual({
      kind: 'link',
      text: '安全链接',
      href: '/privacy/help',
    })
  })
})
