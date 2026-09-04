// 测试用途：约束 Admin 浏览器与 SSR 的 API 地址边界。
import { describe, expect, it } from 'vitest'

import { resolveApiBase } from '@junhui/config/api-base'

describe('admin API base', () => {
  it('never exposes a Docker hostname to browser code', () => {
    expect(resolveApiBase(false, '/api/v1', 'http://api:8000/api/v1')).toBe('/api/v1')
  })

  it('uses the internal service address for server rendering', () => {
    expect(resolveApiBase(true, '/api/v1', 'http://api:8000/api/v1')).toBe('http://api:8000/api/v1')
  })
})
