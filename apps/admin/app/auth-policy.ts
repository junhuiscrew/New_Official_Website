// 模块用途：定义 Admin 路由所需的 API 权限；前端结果仅用于 UX，不替代服务端授权。
export const ADMIN_ROBOTS = 'noindex, nofollow' as const

const routePermissions: Record<string, string> = {
  '/users': 'user.read',
  '/roles': 'role.read',
  '/locales': 'locale.read',
}

export type AdminRouteDecision = 'allow' | 'login' | 'forbidden'

export function shouldAttemptSessionRefresh(
  statusCode: number | undefined,
  isServer: boolean,
): boolean {
  // SSR 无法安全地把内部 API 的 Set-Cookie 回传给浏览器，刷新只在客户端执行。
  return !isServer && statusCode === 401
}

export function decideAdminRouteAccess(
  path: string,
  isAuthenticated: boolean,
  permissions: string[],
): AdminRouteDecision {
  if (path === '/login') return 'allow'
  if (!isAuthenticated) return 'login'
  const requiredPermission = routePermissions[path]
  if (requiredPermission && !permissions.includes(requiredPermission)) return 'forbidden'
  return 'allow'
}
