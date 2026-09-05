// 模块用途：提供默认 no-op 的隐私安全遥测钩子，只允许公开页面上下文。
import type { LocaleSlug, PublicContentType } from '../types/public'

/** Phase 3.6 唯一允许预留的公开事件。 */
export const TELEMETRY_EVENTS = {
  rfq_cta_click: true,
  search_submit: true,
  download_click: true,
  language_switch: true,
} as const

export type TelemetryEvent = keyof typeof TELEMETRY_EVENTS

/** 遥测允许字段白名单；不提供自由结构 payload。 */
export interface TelemetryContext {
  locale?: LocaleSlug
  sourceType?: PublicContentType
  sourceSlug?: string
  resourceType?: string
  targetLocale?: LocaleSlug
}

export type TelemetryAdapter = (event: TelemetryEvent, context: TelemetryContext) => void

declare global {
  interface Window {
    __JUNHUI_PUBLIC_TELEMETRY__?: TelemetryAdapter
  }
}

/**
 * 清理公开上下文，限制动态文本长度并丢弃空值。
 *
 * 输入：
 *   context: TelemetryContext，类型受限的公开页面上下文。
 *
 * 输出：
 *   TelemetryContext，只含允许上报的短公开标识。
 */
function sanitizeContext(context: TelemetryContext): TelemetryContext {
  const sanitized: TelemetryContext = {}
  if (context.locale) sanitized.locale = context.locale
  if (context.sourceType) sanitized.sourceType = context.sourceType
  if (context.sourceSlug?.trim()) sanitized.sourceSlug = context.sourceSlug.trim().slice(0, 180)
  if (context.resourceType?.trim())
    sanitized.resourceType = context.resourceType.trim().slice(0, 64)
  if (context.targetLocale) sanitized.targetLocale = context.targetLocale
  return sanitized
}

/**
 * 返回隐私安全事件记录器；未配置 adapter 时保持 no-op 且不发网络请求。
 *
 * 输入：无。
 *
 * 输出：事件白名单与 track 方法。
 */
export function useTelemetry() {
  /**
   * 向可选站内 adapter 发送白名单事件。
   *
   * 输入：
   *   event: TelemetryEvent，允许的事件名称。
   *   context: TelemetryContext，可选公开上下文。
   *
   * 输出：void；SSR 或 adapter 未配置时不执行任何副作用。
   */
  function track(event: TelemetryEvent, context: TelemetryContext = {}): void {
    if (typeof window === 'undefined') return
    try {
      window.__JUNHUI_PUBLIC_TELEMETRY__?.(event, sanitizeContext(context))
    } catch {
      // 遥测属于可选增强，adapter 故障不得影响公开页面的核心交互。
    }
  }

  return {
    events: TELEMETRY_EVENTS,
    track,
  }
}
