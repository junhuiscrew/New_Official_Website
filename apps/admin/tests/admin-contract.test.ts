// 测试用途：约束 Phase 3.2 管理后台壳的索引策略。
import { describe, expect, it } from 'vitest'

import { adminMeta } from '../app/admin-config'
import { ADMIN_ROBOTS } from '../app/auth-policy'

describe('admin placeholder contract', () => {
  it('keeps the administration shell out of search indexes', () => {
    expect(adminMeta.robots).toBe('noindex, nofollow')
    expect(adminMeta.title).toContain('Admin')
    expect(ADMIN_ROBOTS).toBe('noindex, nofollow')
  })
})
