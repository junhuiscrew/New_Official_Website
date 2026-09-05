// 模块用途：集中生成公开语言路径、alternate 回退和带来源上下文的 RFQ URL。
import type { LocaleSlug, PublicContentType } from '../types/public'

const DEFAULT_LOCALE: LocaleSlug = 'zh-cn'

/** 可由公开 CTA 带入 RFQ 的最小来源上下文。 */
export interface RfqSource {
  locale?: unknown
  type?: PublicContentType
  slug?: string
}

/**
 * 将路由或接口输入规范化为受支持语言。
 *
 * 输入：
 *   locale: unknown，路由参数或外部语言值。
 *
 * 输出：
 *   LocaleSlug，支持的语言；未知值安全回退到 zh-cn。
 */
export function normalizeLocale(locale: unknown): LocaleSlug {
  if (typeof locale !== 'string') return DEFAULT_LOCALE

  const normalized = locale.trim().toLowerCase().replace('_', '-')
  if (normalized === 'en' || normalized.startsWith('en-')) return 'en'
  if (normalized === 'zh' || normalized === 'zh-cn' || normalized === 'zh-hans') return 'zh-cn'
  return DEFAULT_LOCALE
}

/**
 * 返回指定语言首页路径。
 *
 * 输入：
 *   locale: unknown，待规范化语言值。
 *
 * 输出：
 *   string，带结尾斜杠的本地化首页路径。
 */
export function localeHome(locale: unknown): string {
  return `/${normalizeLocale(locale)}/`
}

/**
 * 选择后端提供的同内容 alternate；不存在时回退目标语言首页。
 *
 * 输入：
 *   targetLocale: unknown，用户选择的目标语言。
 *   alternates: Record<string, string | null | undefined>，后端严格发布的 hreflang 映射。
 *
 * 输出：
 *   string，可访问的 alternate 或目标语言首页。
 */
export function alternateTarget(
  targetLocale: unknown,
  alternates?: Readonly<Record<string, string | null | undefined>> | null,
): string {
  const target = normalizeLocale(targetLocale)
  const keys = target === 'zh-cn' ? ['zh-CN', 'zh-cn'] : ['en']
  const alternate = keys
    .map((key) => alternates?.[key])
    .find((candidate): candidate is string => Boolean(candidate?.trim()))

  return alternate?.trim() ?? localeHome(target)
}

/**
 * 根据公开内容 slug 构建 RFQ 地址，不接受内部 ID 或任意表单内容。
 *
 * 输入：
 *   source: RfqSource，语言、公开内容类型与公开 slug。
 *
 * 输出：
 *   string，本地化 RFQ 地址；无完整来源时不添加查询参数。
 */
export function rfqUrl(source: RfqSource): string {
  const base = `/${normalizeLocale(source.locale)}/request-a-quote/`
  if (!source.type || !source.slug?.trim()) return base

  const query = new URLSearchParams({
    source_type: source.type,
    source_slug: source.slug.trim(),
  })
  return `${base}?${query.toString()}`
}
