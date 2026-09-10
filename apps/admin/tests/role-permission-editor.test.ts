// 测试用途：验证角色权限编辑器的纯前端变更计算，不依赖真实员工或系统角色。
import { describe, expect, it } from 'vitest'

import { buildPermissionChange } from '../app/utils/rolePermissions'

describe('角色权限变更对比', () => {
  it('分别列出新增、移除和未变化权限', () => {
    expect(
      buildPermissionChange(
        ['catalog.read', 'media.read', 'role.read'],
        ['catalog.read', 'media.update', 'role.read'],
      ),
    ).toEqual({
      added: ['media.update'],
      removed: ['media.read'],
      unchanged: ['catalog.read', 'role.read'],
      changed: true,
    })
  })

  it('忽略输入顺序和重复项，避免产生虚假变更', () => {
    expect(
      buildPermissionChange(
        ['media.read', 'catalog.read'],
        ['catalog.read', 'media.read', 'media.read'],
      ),
    ).toEqual({
      added: [],
      removed: [],
      unchanged: ['catalog.read', 'media.read'],
      changed: false,
    })
  })
})
