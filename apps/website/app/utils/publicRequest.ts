// 模块职责：统一公开 SSR 页面 URL 参数与后端 HTTP 错误的严格处理规则。
/** 创建 Nuxt 可识别、同时无需运行时别名依赖的 400 错误。 */
function invalidPaginationError(): Error & { statusCode: number; statusMessage: string } {
  const error = new Error('Invalid pagination') as Error & {
    statusCode: number
    statusMessage: string
  }
  error.statusCode = 400
  error.statusMessage = 'Invalid pagination'
  return error
}

/** 严格解析正整数查询参数；非法格式或越界值直接产生 400。 */
export function strictPositiveInteger(value: unknown, fallback: number, maximum?: number): number {
  const candidate = Array.isArray(value) ? value[0] : value
  if (candidate === undefined || candidate === null || candidate === '') return fallback
  const raw = typeof candidate === 'string' ? candidate.trim() : ''
  if (!/^\d+$/.test(raw)) {
    throw invalidPaginationError()
  }
  const parsed = Number(raw)
  if (parsed < 1 || (maximum !== undefined && parsed > maximum)) {
    throw invalidPaginationError()
  }
  return parsed
}

/** 从 Nuxt/$fetch 错误对象保留后端实际状态，未知异常才归为 500。 */
export function publicRequestStatus(value: unknown): number {
  if (!value || typeof value !== 'object') return 500
  const candidate = value as {
    statusCode?: number
    status?: number
    response?: { status?: number }
  }
  return candidate.statusCode ?? candidate.status ?? candidate.response?.status ?? 500
}

/** 从公开 API 错误中读取稳定 error.code；未知结构返回 null。 */
export function publicRequestErrorCode(value: unknown): string | null {
  if (!value || typeof value !== 'object') return null
  const candidate = value as {
    data?: { error?: { code?: unknown } }
    response?: { _data?: { error?: { code?: unknown } } }
  }
  const code = candidate.data?.error?.code ?? candidate.response?._data?.error?.code
  if (typeof code === 'string' && code.trim()) return code
  return null
}

/** 判断失败是否属于必须刷新政策并重新确认的 privacy_context_* 错误。 */
export function isPrivacyContextFailure(value: unknown): boolean {
  return publicRequestErrorCode(value)?.startsWith('privacy_context_') ?? false
}
