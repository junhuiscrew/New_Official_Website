// 模块用途：定义 Admin 路由所需的 API 权限；前端结果仅用于 UX，不替代服务端授权。
export const ADMIN_ROBOTS = 'noindex, nofollow' as const

const routePermissions: Record<string, string> = {
  '/users': 'user.read',
  '/roles': 'role.read',
  '/locales': 'locale.read',
  '/privacy': 'privacy.read',
  '/homepage': 'content.read',
  '/site-overview': 'content.read',
}

export type AdminRouteDecision = 'allow' | 'login' | 'forbidden'

/**
 * 规范化 Admin 路由尾斜杠，防止同一页面绕过前端权限提示。
 *
 * 输入：path，Nuxt 路由路径。
 * 输出：string，根路径保持不变，其他路径移除全部尾斜杠。
 */
function normalizeAdminRoutePath(path: string): string {
  if (path === '/') return path
  return path.replace(/\/+$/, '') || '/'
}

export function shouldAttemptSessionRefresh(
  statusCode: number | undefined,
  isServer: boolean,
): boolean {
  // SSR 无法安全地把内部 API 的 Set-Cookie 回传给浏览器，刷新只在客户端执行。
  return !isServer && statusCode === 401
}

/**
 * 判断受保护 API 请求是否可以在刷新会话后重试。
 *
 * 输入：statusCode，HTTP 状态码；alreadyRetried，是否已经重试；isServer，是否为 SSR。
 * 输出：boolean，仅浏览器首次收到 401 时返回 true，避免递归刷新或 SSR 误轮换 Cookie。
 */
export function shouldRetryAuthenticatedRequest(
  statusCode: number | undefined,
  alreadyRetried: boolean,
  isServer: boolean,
): boolean {
  return !alreadyRetried && shouldAttemptSessionRefresh(statusCode, isServer)
}

export function decideAdminRouteAccess(
  path: string,
  isAuthenticated: boolean,
  permissions: string[],
): AdminRouteDecision {
  const normalizedPath = normalizeAdminRoutePath(path)
  if (normalizedPath === '/login') return 'allow'
  if (!isAuthenticated) return 'login'
  const requiredPermission = routePermissions[normalizedPath]
  if (requiredPermission && !permissions.includes(requiredPermission)) return 'forbidden'
  return 'allow'
}
