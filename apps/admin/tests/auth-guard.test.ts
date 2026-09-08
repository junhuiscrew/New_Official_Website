// 测试用途：约束 Admin Route Guard 只承担 UX，按 API 返回权限决定路由。
import { describe, expect, it } from 'vitest'

import { decideAdminRouteAccess, shouldAttemptSessionRefresh } from '../app/auth-policy'

describe('admin route guard policy', () => {
  it('allows the login page without a session', () => {
    expect(decideAdminRouteAccess('/login', false, [])).toBe('allow')
  })

  it('redirects unauthenticated users to login', () => {
    expect(decideAdminRouteAccess('/users', false, [])).toBe('login')
  })

  it('sends authenticated users without route permission to forbidden', () => {
    expect(decideAdminRouteAccess('/users', true, ['locale.read'])).toBe('forbidden')
  })

  it('allows a route when the API-provided permission is present', () => {
    expect(decideAdminRouteAccess('/users', true, ['user.read'])).toBe('allow')
  })

  it('normalizes trailing slashes before enforcing Privacy permission', () => {
    expect(decideAdminRouteAccess('/privacy', true, [])).toBe('forbidden')
    expect(decideAdminRouteAccess('/privacy/', true, [])).toBe('forbidden')
    expect(decideAdminRouteAccess('/privacy///', true, ['privacy.read'])).toBe('allow')
  })

  it('refreshes an expired access session only in the browser', () => {
    expect(shouldAttemptSessionRefresh(401, false)).toBe(true)
    expect(shouldAttemptSessionRefresh(401, true)).toBe(false)
    expect(shouldAttemptSessionRefresh(403, false)).toBe(false)
  })
})
