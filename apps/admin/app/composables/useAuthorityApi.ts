// 组合式模块用途：统一 Authority、SEO/GEO、Source 与 Redirect 的认证/CSRF 请求。
import { shouldRetryAuthenticatedRequest } from '../auth-policy'

interface ApiEnvelope<T> {
  success: boolean
  data: T
  error: { code: string; message: string } | null
}

interface FetchFailure {
  statusCode?: number
  response?: { status?: number }
}

export interface AuthorityList<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

type AuthorityMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export function useAuthorityApi() {
  const { apiBase, refreshCurrentUser } = useAuth()
  const csrfToken = useCookie<string | null>('junhui_csrf')

  // 所有写请求统一携带认证 Cookie 与双提交 CSRF Header。
  async function request<T>(
    path: string,
    options: {
      method?: AuthorityMethod
      body?: Record<string, unknown> | FormData
      query?: Record<string, string | number | boolean | null | undefined>
      signal?: AbortSignal
    } = {},
  ): Promise<T> {
    const method = options.method || 'GET'
    let alreadyRetried = false

    /** 单次请求始终读取最新 CSRF ref，确保 refresh 轮换后写请求使用新值。 */
    const execute = async (): Promise<T> => {
      const response = await $fetch<ApiEnvelope<T>>(path, {
        baseURL: apiBase,
        credentials: 'include',
        method,
        body: options.body,
        query: options.query,
        signal: options.signal,
        headers: method !== 'GET' ? { 'X-CSRF-Token': csrfToken.value || '' } : undefined,
      })
      return response.data
    }

    try {
      return await execute()
    } catch (error) {
      const failure = error as FetchFailure
      const statusCode = failure.statusCode ?? failure.response?.status
      if (!shouldRetryAuthenticatedRequest(statusCode, alreadyRetried, import.meta.server))
        throw error
      alreadyRetried = true
      await refreshCurrentUser()
      return execute()
    }
  }

  const list = <T>(
    path: string,
    query?: Record<string, string | number | boolean | null | undefined>,
  ) => request<AuthorityList<T>>(path, { query })
  const detail = <T>(path: string) => request<T>(path)
  const create = <T>(path: string, body: Record<string, unknown>) =>
    request<T>(path, { method: 'POST', body })
  const update = <T>(path: string, body: Record<string, unknown>) =>
    request<T>(path, { method: 'PATCH', body })
  const replace = <T>(path: string, body: Record<string, unknown>) =>
    request<T>(path, { method: 'PUT', body })
  const archive = <T>(path: string) => request<T>(path, { method: 'POST' })
  const upload = <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body })

  return { request, list, detail, create, update, replace, archive, upload }
}
