// 组合式模块用途：统一 Catalog CRUD 的 Cookie、CSRF、错误处理和响应解包。
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

export interface CatalogList<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface CatalogTranslationDraft {
  locale_id: string
  code: string
  name: string
  fields: Record<string, string>
}

type CatalogMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export function useCatalogApi() {
  const { apiBase, refreshCurrentUser } = useAuth()
  const csrfToken = useCookie<string | null>('junhui_csrf')

  // 所有写请求统一携带 HttpOnly 认证 Cookie 配套的双提交 CSRF Header。
  async function request<T>(
    path: string,
    options: { method?: CatalogMethod; body?: Record<string, unknown> } = {},
  ): Promise<T> {
    const method = options.method || 'GET'
    let alreadyRetried = false

    /** 单次请求读取最新 CSRF ref，确保会话轮换后写请求不会使用旧 Token。 */
    const execute = async (): Promise<T> => {
      const response = await $fetch<ApiEnvelope<T>>(path, {
        baseURL: apiBase,
        credentials: 'include',
        method,
        body: options.body,
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

  function list<T>(path: string): Promise<CatalogList<T>> {
    return request<CatalogList<T>>(path)
  }

  function detail<T>(path: string): Promise<T> {
    return request<T>(path)
  }

  function create<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return request<T>(path, { method: 'POST', body })
  }

  function update<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return request<T>(path, { method: 'PATCH', body })
  }

  function replace<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return request<T>(path, { method: 'PUT', body })
  }

  function archive<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'POST' })
  }

  function remove<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  }

  return { request, list, detail, create, update, replace, archive, remove }
}
