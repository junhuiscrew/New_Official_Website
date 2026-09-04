// 组合式模块用途：统一 Authority、SEO/GEO、Source 与 Redirect 的认证/CSRF 请求。
interface ApiEnvelope<T> {
  success: boolean
  data: T
  error: { code: string; message: string } | null
}

export interface AuthorityList<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

type AuthorityMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export function useAuthorityApi() {
  const { apiBase } = useAuth()
  const csrfToken = useCookie<string | null>('junhui_csrf')

  // 所有写请求统一携带认证 Cookie 与双提交 CSRF Header。
  async function request<T>(
    path: string,
    options: { method?: AuthorityMethod; body?: Record<string, unknown> | FormData } = {},
  ): Promise<T> {
    const method = options.method || 'GET'
    const response = await $fetch<ApiEnvelope<T>>(path, {
      baseURL: apiBase,
      credentials: 'include',
      method,
      body: options.body,
      headers: method !== 'GET' ? { 'X-CSRF-Token': csrfToken.value || '' } : undefined,
    })
    return response.data
  }

  const list = <T>(path: string) => request<AuthorityList<T>>(path)
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
