// 组合式模块用途：统一 Catalog CRUD 的 Cookie、CSRF、错误处理和响应解包。
interface ApiEnvelope<T> {
  success: boolean
  data: T
  error: { code: string; message: string } | null
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

type CatalogMethod = 'GET' | 'POST' | 'PATCH' | 'PUT'

export function useCatalogApi() {
  const { apiBase } = useAuth()
  const csrfToken = useCookie<string | null>('junhui_csrf')

  // 所有写请求统一携带 HttpOnly 认证 Cookie 配套的双提交 CSRF Header。
  async function request<T>(
    path: string,
    options: { method?: CatalogMethod; body?: Record<string, unknown> } = {},
  ): Promise<T> {
    const response = await $fetch<ApiEnvelope<T>>(path, {
      baseURL: apiBase,
      credentials: 'include',
      method: options.method || 'GET',
      body: options.body,
      headers:
        options.method && options.method !== 'GET'
          ? { 'X-CSRF-Token': csrfToken.value || '' }
          : undefined,
    })
    return response.data
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

  return { request, list, detail, create, update, replace, archive }
}
