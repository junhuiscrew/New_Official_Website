// 测试用途：锁定中文后台 R1 收尾的可读列表、状态区分和能力核对入口。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const appRoot = resolve(process.cwd(), 'app')

function source(path: string): string {
  return readFileSync(resolve(appRoot, path), 'utf8')
}

describe('中文后台 R1 有限收尾', () => {
  it('共享 Authority 列表为中文标题保留可伸缩宽度', () => {
    const content = source('components/authority/AuthorityCrud.vue')
    expect(content).toContain('authority-record-list__primary')
    expect(content).toContain('min-width: 0')
    expect(content).toContain('overflow-wrap: anywhere')
    expect(content).not.toContain('<small>{{ field }}</small>')
  })

  it('集中词表覆盖总览原因、下载类型和媒体用途', () => {
    const content = source('utils/adminZhCn.ts')
    for (const token of [
      'HIDDEN_REASON_LABELS',
      'DOWNLOAD_RESOURCE_TYPE_LABELS',
      'MEDIA_USAGE_ROLE_LABELS',
    ]) {
      expect(content).toContain(token)
    }
  })

  it('下载页区分新建、编辑、加载状态并使用资料类型下拉', () => {
    const content = source('pages/downloads.vue')
    for (const token of [
      'downloads-editor-state',
      '正在编辑：',
      '正在加载下载资料…',
      'DOWNLOAD_RESOURCE_TYPE_LABELS',
      '<select v-model="form.resource_type">',
    ]) {
      expect(content).toContain(token)
    }
  })

  it('媒体库提供搜索、类型筛选和可维护的具体引用位置', () => {
    const content = source('pages/media.vue')
    for (const token of [
      'mediaSearch',
      'mediaTypeFilter',
      '/usage',
      'content_name',
      'admin_url',
      '打开维护位置',
    ]) {
      expect(content).toContain(token)
    }
  })

  it('角色页提供中文权限编辑、变更确认、保存与 fresh GET 回读', () => {
    const content = source('pages/roles.vue')
    for (const token of [
      'roleSearch',
      'filteredRoles',
      'role.manage',
      '查看变更并确认',
      '确认保存权限',
      'beforePermissions',
      'fresh GET',
      'is_system',
    ]) {
      expect(content).toContain(token)
    }
  })

  it('目标运营页面将英语语言操作标签显示为中文', () => {
    for (const page of ['pages/downloads.vue', 'pages/media.vue', 'pages/site-overview.vue']) {
      expect(source(page)).toContain('localeOperationLabel')
    }
  })

  it('网站总览不直接显示隐藏原因代码', () => {
    const content = source('pages/site-overview.vue')
    expect(content).toContain('HIDDEN_REASON_LABELS')
    expect(content).toContain('labelFrom(HIDDEN_REASON_LABELS')
    expect(content).not.toContain('{{ item.hidden_reason }}')
  })
})
