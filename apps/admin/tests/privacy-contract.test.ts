// 测试用途：锁定 Privacy P1 Admin 页面、权限、固定 API 路径与显式生命周期操作。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('Privacy P1 Admin contract', () => {
  const pagePath = resolve(process.cwd(), 'app/pages/privacy.vue')
  const previewPath = resolve(process.cwd(), 'app/components/privacy/SafeMarkdownPreview.vue')

  it('提供固定 Privacy 页面且不要求 UUID 或 owner 输入', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('useAuthorityApi')
    expect(source).toContain("api.detail<PrivacyState>('/privacy')")
    expect(source).toContain("api.create<PrivacyState>('/privacy/initialize', {})")
    expect(source).toContain("api.create<PrivacyState>('/privacy/drafts', { clone_current: true })")
    expect(source).toContain("api.replace<PrivacyState>('/privacy/draft'")
    expect(source).toContain('/privacy/draft/review/${locale}')
    expect(source).toContain('expected_version_label: activeDraft.version_label')
    expect(source).toContain('expected_revision: activeDraft.revision')
    expect(source).toContain('expected_content_hash: translation.content_hash')
    expect(source).toContain("api.create<PrivacyState>('/privacy/draft/publish'")
    expect(source).toContain('expected_content_hashes: buildExpectedContentHashes(activeDraft)')
    expect(source).not.toMatch(/owner[_-]?id/i)
    expect(source).not.toContain('UUID')
  })

  it('仅向 privacy.read 用户显示导航并保护固定路由', () => {
    const appSource = readFileSync(resolve(process.cwd(), 'app/app.vue'), 'utf8')
    const policySource = readFileSync(resolve(process.cwd(), 'app/auth-policy.ts'), 'utf8')

    expect(appSource).toContain("currentUser.permissions.includes('privacy.read')")
    expect(appSource).toContain('to="/privacy"')
    expect(policySource).toContain("'/privacy': 'privacy.read'")
  })

  it('按状态提供初始化、克隆草稿和不可变版本提示', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('canEditPrivacy(permissions.value)')
    expect(source).toContain('初始化 Privacy 页面')
    expect(source).toContain('创建/克隆草稿')
    expect(source).toContain('已审核或已发布版本不能直接编辑，请创建新草稿')
    expect(source).toContain('NOT APPROVED')
    expect(source).toContain('created.draft?.cloned_from_version_label')
  })

  it('保存使用 expected revision 并在 fresh GET 后比对实际值', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('expected_revision: activeDraft.revision')
    expect(source).toContain('translations: buildTranslationPayload')
    expect(source).toContain('const reloaded = await loadPrivacy()')
    expect(source).toContain('savedDraftMatches')
    expect(source).toContain('statusCode === 409')
    expect(source).toContain('刷新后再编辑')
  })

  it('生效时间未编辑时保留服务端 ISO，编辑后使用支持秒的本地时间输入', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('const originalEffectiveAt = ref<string | null>(null)')
    expect(source).toContain('const effectiveAtEdited = ref(false)')
    expect(source).toContain('resolvePrivacyEffectiveAt(')
    expect(source).toContain('@input="effectiveAtEdited = true"')
    expect(source).toContain('step="1"')
  })

  it('fresh GET 与 PUT 服务端确认值比较，不在浏览器重复 Python strip', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const pageSource = readFileSync(pagePath, 'utf8')
    const utilitySource = readFileSync(resolve(process.cwd(), 'app/utils/privacyAdmin.ts'), 'utf8')
    expect(pageSource).toContain('const saved = await api.replace<PrivacyState>')
    expect(pageSource).toContain('savedDraftMatches(reloaded.draft, saved.draft)')
    expect(utilitySource).not.toContain('normalizePrivacyContent')
    expect(utilitySource).not.toContain('.trim()')
  })

  it('审核与发布要求完整组合权限、显式按钮和确认对话框', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('canReviewPrivacy(permissions.value)')
    expect(source).toContain('hasPrivacyPublishPermissions(permissions.value)')
    expect(source).toContain('window.confirm')
    expect(source).toContain('发布会切换 current')
    expect(source).toContain('@click="reviewTranslation(locale.code)"')
    expect(source).toContain('@click="publishDraft"')
    expect(source).toContain("translation_status === 'human_reviewed'")
    expect(source).toContain('draft.effective_at')
    expect(source).toContain('onMounted(loadPrivacy)')
  })

  it('仅有 privacy.history 权限时请求并展示历史', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain("permissions.value.includes('privacy.history')")
    expect(source).toContain("api.detail<PrivacyHistory>('/privacy/history')")
    expect(source).toContain('v-if="canReadHistory"')
    expect(source).toContain("const historyError = ref('')")
    expect(source).toContain('historyError.value =')
    expect(source).toContain('v-if="historyError"')
  })

  it('主状态读取成功清除旧错误，历史失败不丢失编辑状态', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toMatch(
      /const response = await api\.detail<PrivacyState>\('\/privacy'\)[\s\S]*?errorMessage\.value = ''[\s\S]*?privacyState\.value = response/,
    )
    expect(source).toContain('resolvePrivacyLoadFailure(error)')
    expect(source).toMatch(
      /async function loadHistory\(\): Promise<void> \{[\s\S]*?try \{[\s\S]*?\/privacy\/history[\s\S]*?catch[\s\S]*?historyError\.value/,
    )
  })

  it('语言切换使用普通按钮组而不是不完整的 tab ARIA', () => {
    expect(existsSync(pagePath)).toBe(true)
    if (!existsSync(pagePath)) return

    const source = readFileSync(pagePath, 'utf8')
    expect(source).toContain('role="group"')
    expect(source).toContain(':aria-pressed="activeLocale === locale.code"')
    expect(source).not.toContain('role="tablist"')
    expect(source).not.toContain('role="tab"')
    expect(source).not.toContain('aria-selected')
    expect(source).not.toContain('aria-controls')
  })

  it('使用不含 v-html、脚本和远程嵌入的安全预览组件', () => {
    expect(existsSync(previewPath)).toBe(true)
    if (!existsSync(previewPath)) return

    const pageSource = readFileSync(pagePath, 'utf8')
    const previewSource = readFileSync(previewPath, 'utf8')
    const inlineSource = readFileSync(
      resolve(process.cwd(), 'app/components/privacy/SafeMarkdownInline.vue'),
      'utf8',
    )
    expect(pageSource).toContain('SafeMarkdownPreview')
    expect(pageSource).not.toContain('v-html')
    expect(previewSource).not.toContain('v-html')
    expect(previewSource).not.toMatch(/<(?:iframe|img|video|audio|object|embed)\b/i)
    expect(previewSource).not.toContain('<h1')
    expect(previewSource).toContain('<h2')
    expect(previewSource).toContain('<h3')
    expect(inlineSource).not.toContain('v-html')
    expect(inlineSource).toContain(':href="token.href"')
    expect(inlineSource).toContain('rel="nofollow noopener noreferrer"')
  })
})
