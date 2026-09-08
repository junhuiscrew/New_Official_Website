// 模块用途：集中定义 Privacy Admin DTO、权限组合与保存回读校验逻辑。
export type PrivacyLocale = 'zh-CN' | 'en'

export interface PrivacyTranslation {
  locale: PrivacyLocale
  title: string | null
  body_markdown: string | null
  content_format?: string
  rendering_trust?: string
  content_hash?: string | null
  hash_algorithm?: string
  translation_status: string
  publication_status: string
  canonical_path: string
  route_active: boolean
  route_indexable: boolean
}

export interface PrivacyVersion {
  version_label: string
  revision: number
  effective_at: string | null
  cloned_from_version_label: string | null
  created_at: string
  translations: Record<PrivacyLocale, PrivacyTranslation>
}

export interface PrivacyState {
  page: { system_key: string; status: string }
  current: PrivacyVersion | null
  draft: PrivacyVersion | null
}

export interface PrivacyTranslationInput {
  locale: PrivacyLocale
  title: string
  body_markdown: string
}

/**
 * 判断权限集合是否包含指定权限。
 *
 * 输入：permissions，用户权限代码；required，必须同时具备的权限代码。
 * 输出：boolean，全部具备时返回 true。
 */
function hasAllPermissions(permissions: string[], required: string[]): boolean {
  return required.every((permission) => permissions.includes(permission))
}

/**
 * 判断用户是否满足后端当前 Privacy 编辑组合权限。
 *
 * 输入：permissions，当前用户权限代码。
 * 输出：boolean，具备 privacy.edit 且至少一种 supporting update 权限时返回 true。
 */
export function canEditPrivacy(permissions: string[]): boolean {
  return (
    permissions.includes('privacy.edit') &&
    (permissions.includes('content.update') || permissions.includes('translation.update'))
  )
}

/**
 * 判断用户是否满足 Privacy 人工审核组合权限。
 *
 * 输入：permissions，当前用户权限代码。
 * 输出：boolean，同时具备三项审核权限时返回 true。
 */
export function canReviewPrivacy(permissions: string[]): boolean {
  return hasAllPermissions(permissions, ['privacy.review', 'content.review', 'translation.review'])
}

/**
 * 判断用户是否满足 Privacy 发布组合权限。
 *
 * 输入：permissions，当前用户权限代码。
 * 输出：boolean，同时具备三项发布权限时返回 true。
 */
export function hasPrivacyPublishPermissions(permissions: string[]): boolean {
  return hasAllPermissions(permissions, [
    'privacy.publish',
    'content.publish',
    'translation.publish',
  ])
}

/**
 * 判断服务端草稿是否仍可编辑。
 *
 * 输入：draft，当前 Privacy 草稿。
 * 输出：boolean，仅双语均处于 draft 且未发布时返回 true。
 */
export function isDraftEditable(draft: PrivacyVersion | null): boolean {
  if (!draft) return false
  return (Object.values(draft.translations) as PrivacyTranslation[]).every(
    (translation) =>
      translation.translation_status === 'draft' && translation.publication_status === 'draft',
  )
}

/**
 * 判断草稿状态是否达到发布门槛。
 *
 * 输入：draft，当前 Privacy 草稿。
 * 输出：boolean，存在生效时间且双语都已人工审核时返回 true。
 */
export function canPublishDraft(draft: PrivacyVersion | null): boolean {
  if (!draft?.effective_at) return false
  return (Object.values(draft.translations) as PrivacyTranslation[]).every(
    (translation) => translation.translation_status === 'human_reviewed',
  )
}

/**
 * 将服务端 ISO 时间转换为 datetime-local 的本地整秒显示值。
 *
 * 输入：value，服务端 ISO 时间或 null。
 * 输出：string，包含秒但不包含毫秒的浏览器本地时间输入值。
 */
export function toPrivacyDateTimeLocal(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return localDate.toISOString().slice(0, 19)
}

/**
 * 决定保存时使用原始 ISO，还是采用用户编辑后的本地整秒时间。
 *
 * 输入：originalIso，服务端原始 ISO；localValue，datetime-local 值；edited，用户是否编辑。
 * 输出：string | null，未编辑时原样返回 ISO；编辑时按本地时区转换并明确归零毫秒。
 */
export function resolvePrivacyEffectiveAt(
  originalIso: string | null,
  localValue: string,
  edited: boolean,
): string | null {
  if (!edited) return originalIso
  if (!localValue) return null
  const editedDate = new Date(localValue)
  if (Number.isNaN(editedDate.getTime())) {
    throw new Error('Privacy 生效时间格式无效')
  }
  // datetime-local 使用浏览器本地时区；页面以 step=1 编辑到秒，因此毫秒固定归零。
  editedDate.setMilliseconds(0)
  return editedDate.toISOString()
}

/**
 * 比较 PUT 服务端确认草稿与随后 fresh GET 返回的草稿。
 *
 * 输入：draft，重新读取的草稿；acknowledgedDraft，PUT 返回的服务端规范化草稿。
 * 输出：boolean，版本、实际时间与双语完整正文逐项一致时返回 true。
 */
export function savedDraftMatches(
  draft: PrivacyVersion | null,
  acknowledgedDraft: PrivacyVersion | null,
): boolean {
  if (!draft || !acknowledgedDraft) return false
  if (
    draft.version_label !== acknowledgedDraft.version_label ||
    draft.revision !== acknowledgedDraft.revision ||
    draft.effective_at !== acknowledgedDraft.effective_at
  ) {
    return false
  }
  // 以同一后端返回的规范化值为准，避免在 JS 中近似复制 Python Unicode strip。
  return (['zh-CN', 'en'] as const).every((locale) => {
    const actual = draft.translations[locale]
    const acknowledged = acknowledgedDraft.translations[locale]
    return (
      actual?.title === acknowledged?.title && actual?.body_markdown === acknowledged?.body_markdown
    )
  })
}

/**
 * 从 Nuxt Fetch 错误中提取 HTTP 状态码。
 *
 * 输入：error，未知请求错误。
 * 输出：number | undefined，可识别时返回状态码。
 */
export function getPrivacyErrorStatus(error: unknown): number | undefined {
  const failure = error as {
    statusCode?: number
    status?: number
    response?: { status?: number }
  }
  return failure.statusCode ?? failure.status ?? failure.response?.status
}

export interface PrivacyLoadFailure {
  initialized: boolean
  errorMessage: string
}

/**
 * 将主 Privacy GET 错误映射为页面可恢复状态。
 *
 * 输入：error，未知请求错误。
 * 输出：PrivacyLoadFailure，404 表示未初始化，其他错误保留已初始化语义并显示提示。
 */
export function resolvePrivacyLoadFailure(error: unknown): PrivacyLoadFailure {
  if (getPrivacyErrorStatus(error) === 404) {
    return { initialized: false, errorMessage: '' }
  }
  return {
    initialized: true,
    errorMessage: 'Privacy 状态读取失败，请检查权限或稍后重试。',
  }
}
