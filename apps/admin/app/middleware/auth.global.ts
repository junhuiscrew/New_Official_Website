// 中间件用途：根据 API Current User 提供 Admin 导航体验；真实权限仍由 FastAPI 强制执行。
import { decideAdminRouteAccess } from '../auth-policy'

export default defineNuxtRouteMiddleware(async (to) => {
  // 认证刷新留在浏览器执行，避免 SSR 内部请求产生无法透传的 Set-Cookie。
  if (import.meta.server) return
  const { currentUser, loadCurrentUser } = useAuth()
  if (to.path !== '/login' && !currentUser.value) {
    try {
      await loadCurrentUser()
    } catch {
      currentUser.value = null
    }
  }

  const decision = decideAdminRouteAccess(
    to.path,
    currentUser.value !== null,
    currentUser.value?.permissions || [],
  )
  if (decision === 'login') return navigateTo('/login')
  if (decision === 'forbidden') return navigateTo('/forbidden')
  if (to.path === '/login' && currentUser.value) return navigateTo('/')
})
