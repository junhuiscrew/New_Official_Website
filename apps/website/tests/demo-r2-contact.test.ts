import { describe, expect, it } from 'vitest'

import { telephoneHref } from '../app/utils/contact'

describe('Demo R2 contact rendering', () => {
  it('creates telephone links only for plausible telephone values', () => {
    expect(telephoneHref('+86 580 1234 567')).toBe('tel:+865801234567')
    expect(telephoneHref('演示联系电话 / Demo phone')).toBeNull()
    expect(telephoneHref('')).toBeNull()
  })
})
