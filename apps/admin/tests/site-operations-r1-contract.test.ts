// 测试用途：锁定站点运营三个中文入口、真实保存链和受控输入边界。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('站点运营设置 R1 后台合同', () => {
  it('在侧栏提供三个具备现有权限门禁的中文入口', () => {
    const app = source('app/app.vue')
    expect(app).toContain("label: '站点运营'")
    expect(app).toContain("to: '/site-operations/brand'")
    expect(app).toContain("to: '/site-operations/navigation'")
    expect(app).toContain("to: '/site-operations/redirects'")
    expect(app).toContain("permission: 'redirect.read'")
  })

  it('品牌页保存完整双语草稿并提供认证预览、应用和恢复', () => {
    const page = source('app/pages/site-operations/brand.vue')
    expect(page).toContain("'/site-operations/brand/draft'")
    expect(page).toContain("'/site-operations/brand/preview'")
    expect(page).toContain("'/site-operations/brand/apply'")
    expect(page).toContain("'/site-operations/brand/restore'")
    expect(page).toContain("'zh-CN': { ...translations['zh-CN'] }")
    expect(page).toContain('en: { ...translations.en }')
  })

  it('导航页只用目标下拉框并提供排序、启停、应用和恢复', () => {
    const page = source('app/pages/site-operations/navigation.vue')
    expect(page).toContain('availableTargets')
    expect(page).toContain('targetOptions')
    expect(page).toContain('当前不可公开')
    expect(page).toContain('moveItem')
    expect(page).toContain('item.enabled')
    expect(page).toContain('/apply`')
    expect(page).toContain('/restore`')
    expect(page).not.toContain('JSON.stringify')
  })

  it('重定向页固定正式目标域并执行草稿、检查、确认、停用和历史链', () => {
    const page = source('app/pages/site-operations/redirects.vue')
    expect(page).toContain('official_target_origin')
    expect(page).toContain('/check`')
    expect(page).toContain('/confirm`')
    expect(page).toContain('/disable`')
    expect(page).toContain('/history`')
    expect(page).not.toContain('fetch(')
    expect(page).not.toContain('UUID')
  })
})
