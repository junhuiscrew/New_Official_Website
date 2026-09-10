// 模块用途：为角色权限编辑器计算稳定、可复核的前后差异。

export interface PermissionChange {
  added: string[]
  removed: string[]
  unchanged: string[]
  changed: boolean
}

/**
 * 比较保存前后的权限代码，去重并按代码排序。
 *
 * 输入：before，原权限代码；after，待保存权限代码。
 * 输出：PermissionChange，新增、移除、未变化以及是否发生变更。
 */
export function buildPermissionChange(before: string[], after: string[]): PermissionChange {
  const beforeSet = new Set(before)
  const afterSet = new Set(after)
  const added = [...afterSet].filter((code) => !beforeSet.has(code)).sort()
  const removed = [...beforeSet].filter((code) => !afterSet.has(code)).sort()
  const unchanged = [...beforeSet].filter((code) => afterSet.has(code)).sort()
  return {
    added,
    removed,
    unchanged,
    changed: added.length > 0 || removed.length > 0,
  }
}
