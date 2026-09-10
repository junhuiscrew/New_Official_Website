// 组合式模块用途：管理 Current User 和 Cookie 认证请求，不保存 refresh credential。
import { resolveApiBase } from '@junhui/config/api-base'
import { shouldAttemptSessionRefresh } from '../auth-policy'

export interface AdminUser {
  id: string
  email: string
  display_name: string | null
  roles: string[]
  permissions: string[]
}

interface ApiEnvelope<T> {
  success: boolean
  data: T
}

interface FetchFailure {
  statusCode?: number
  response?: { status?: number }
}

// 浏览器多个并发请求同时遇到过期访问 Cookie 时只允许轮换一次 refresh credential。
let clientRefreshPromise: Promise<AdminUser> | null = null

export function useAuth() {
  const currentUser = useState<AdminUser | null>('admin-current-user', () => null)
  const config = useRuntimeConfig()
  const apiBase = resolveApiBase(import.meta.server, config.public.apiBase, config.apiInternalBase)

  // SSR 时转发浏览器 Cookie，客户端继续使用同源 HttpOnly Cookie。
  const requestHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined

  async function loadCurrentUser(): Promise<AdminUser> {
    try {
      const response = await $fetch<ApiEnvelope<AdminUser>>('/auth/me', {
        baseURL: apiBase,
        credentials: 'include',
        headers: requestHeaders,
      })
      currentUser.value = response.data
      return response.data
    } catch (error) {
      const failure = error as FetchFailure
      const statusCode = failure.statusCode ?? failure.response?.status
      if (shouldAttemptSessionRefresh(statusCode, import.meta.server)) {
        return refreshCurrentUser()
      }
      throw error
    }
  }

  async function performSessionRefresh(): Promise<AdminUser> {
    // Refresh 凭据只由 HttpOnly Cookie 携带，客户端仅读取非敏感 CSRF Cookie。
    const csrfToken = useCookie<string | null>('junhui_csrf')
    const response = await $fetch<ApiEnvelope<AdminUser>>('/auth/refresh', {
      method: 'POST',
      baseURL: apiBase,
      credentials: 'include',
      headers: { 'X-CSRF-Token': csrfToken.value || '' },
    })
    // 服务端轮换访问、刷新和 CSRF Cookie 后，同步客户端可读的 CSRF ref。
    if (import.meta.client) refreshCookie('junhui_csrf')
    currentUser.value = response.data
    return response.data
  }

  /**
   * 原子恢复浏览器登录会话。
   *
   * 输入：无，凭据只来自安全 Cookie。
   * 输出：Promise<AdminUser>，返回刷新后的当前用户；并发调用共享同一个刷新请求。
   */
  async function refreshCurrentUser(): Promise<AdminUser> {
    if (import.meta.server) return performSessionRefresh()
    if (!clientRefreshPromise) {
      clientRefreshPromise = performSessionRefresh().finally(() => {
        clientRefreshPromise = null
      })
    }
    return clientRefreshPromise
  }

  async function login(email: string, password: string): Promise<AdminUser> {
    const response = await $fetch<ApiEnvelope<AdminUser>>('/auth/login', {
      method: 'POST',
      baseURL: apiBase,
      credentials: 'include',
      body: { email, password },
    })
    currentUser.value = response.data
    return response.data
  }

  async function logout(): Promise<void> {
    const csrfToken = useCookie<string | null>('junhui_csrf')
    await $fetch('/auth/logout', {
      method: 'POST',
      baseURL: apiBase,
      credentials: 'include',
      headers: { 'X-CSRF-Token': csrfToken.value || '' },
    })
    currentUser.value = null
  }

  return {
    currentUser,
    apiBase,
    loadCurrentUser,
    refreshCurrentUser,
    login,
    logout,
  }
}
