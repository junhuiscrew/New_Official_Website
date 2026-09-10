// 测试用途：锁定中文后台 R1 要求的官网定向修复，不改变真实业务正文。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const appRoot = resolve(process.cwd(), 'app')
const source = (path: string) => readFileSync(resolve(appRoot, path), 'utf8')

describe('官网定向复核', () => {
  it('Demo询价入口明确说明当前不能创建或发送询盘', () => {
    const dictionary = source('i18n/ui.ts')
    const cta = source('components/RfqCta.vue')
    const homepage = source('components/HomepagePresentation.vue')

    expect(dictionary).toContain('demoRfqSummary')
    expect(dictionary).toContain('不会创建或发送询盘')
    expect(dictionary).toContain('demoRfqAction')
    expect(cta).toContain('runtimeConfig.public.demoMode')
    expect(homepage).toContain('home.demo_mode ? labels.home.demoRfqSummary')
  })

  it('首页和About的系统装饰标签随语言切换', () => {
    const dictionary = source('i18n/ui.ts')
    const homepage = source('components/HomepagePresentation.vue')
    const about = source('pages/[lang]/about.vue')

    for (const token of [
      'featuredApplicationLabel',
      'demoVideoLabel',
      'companyProfileLabel',
      'verifiedDataLabel',
      'marketDirectoryLabel',
      'workingPrinciplesLabel',
      'contactLabel',
    ])
      expect(dictionary).toContain(token)
    expect(homepage).not.toContain('FEATURED DEMO APPLICATION')
    expect(homepage).not.toContain('DEMO VIDEO {{')
    expect(about).not.toContain('COMPANY PROFILE')
    expect(about).not.toContain('VERIFIED DATA')
  })

  it('375px首页使用紧凑续屏节奏且不产生横向溢出', () => {
    const homepage = source('components/HomepagePresentation.vue')
    expect(homepage).toContain('@media (max-width: 48rem)')
    expect(homepage).toContain('padding-block: 3.25rem')
    expect(homepage).toContain('min-width: 0')
  })
})
