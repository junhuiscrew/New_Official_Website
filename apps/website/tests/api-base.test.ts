// 测试用途：约束浏览器与 Nuxt SSR 使用不同的 API 地址。
import { describe, expect, it } from 'vitest'

import { resolveApiBase } from '@junhui/config/api-base'

describe('website API base', () => {
  it('uses the Docker service address during SSR', () => {
    expect(resolveApiBase(true, '/api/v1', 'http://api:8000/api/v1')).toBe('http://api:8000/api/v1')
  })

  it('uses the same-origin public path in the browser', () => {
    expect(resolveApiBase(false, '/api/v1', 'http://api:8000/api/v1')).toBe('/api/v1')
  })
})
