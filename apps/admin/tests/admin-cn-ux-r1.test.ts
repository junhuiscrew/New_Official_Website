// 测试用途：锁定中文后台运营化 R1 的共享词表、状态语义与十个重点页面合同。
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const appRoot = resolve(process.cwd(), 'app')

function source(path: string): string {
  return readFileSync(resolve(appRoot, path), 'utf8')
}

describe('中文后台运营化 R1', () => {
  it('提供集中中文词表、北京时间和状态映射', () => {
    const path = resolve(appRoot, 'utils/adminZhCn.ts')
    expect(existsSync(path)).toBe(true)
    if (!existsSync(path)) return
    const content = readFileSync(path, 'utf8')

    for (const token of [
      'ENTITY_STATUS_LABELS',
      'PUBLICATION_STATUS_LABELS',
      'TRANSLATION_STATUS_LABELS',
      'RFQ_STATUS_LABELS',
      'PERMISSION_RESOURCE_LABELS',
      'formatBeijingTime',
      '北京时间',
      "upload: '上传'",
      "download_private_file: '下载私有附件'",
      "specification: '规格参数'",
    ]) {
      expect(content).toContain(token)
    }
  })

  it('目录列表和关系选择优先使用服务端可读中文名称', () => {
    expect(source('components/catalog/EntityCrud.vue')).toContain('item.display_name')
    expect(source('pages/catalog/categories.vue')).toContain('item.display_name')
    expect(source('pages/catalog/products.vue')).toContain('item.display_name')
    expect(source('components/authority/AuthorityCrud.vue')).toContain('item.display_name')
  })

  it('四类 Authority 编辑器使用中文分组、可读标题和明确状态', () => {
    const content = source('components/authority/AuthorityCrud.vue')

    for (const text of [
      '基本信息',
      '内容编辑',
      '客户隐私信息',
      '相关内容',
      '搜索与答案优化',
      '发布与历史',
      '请选择左侧记录，或新建内容。',
      '没有符合当前筛选条件的内容。',
      '未保存的修改',
      'display_title',
      '正文预览',
    ]) {
      expect(content).toContain(text)
    }
    expect(content).not.toContain(
      'Structured authority content, publication and discovery metadata.',
    )
  })

  it('十个重点页面均提供中文运营界面', () => {
    const requirements: Record<string, string[]> = {
      'pages/site-overview.vue': ['网站总览', '导航状态', '实现状态'],
      'pages/cases.vue': ['客户案例'],
      'pages/knowledge.vue': ['知识文章'],
      'pages/faqs.vue': ['常见问题'],
      'pages/experts.vue': ['作者与专家'],
      'pages/trust.vue': ['企业资料与制造能力', '内容数量'],
      'pages/downloads.vue': ['下载资料', '基本信息'],
      'pages/media.vue': ['媒体资源库', '元数据修改', '指定位置换图', '新上传'],
      'pages/rfqs.vue': ['询盘中心', '北京时间', '清空筛选', '下一页'],
      'pages/roles.vue': [
        '角色权限',
        '权限分组',
        '技术详情',
        'v-if="loading"',
        'onMounted(() => loadRoles(false))',
      ],
    }

    for (const [path, tokens] of Object.entries(requirements)) {
      const content = source(path)
      for (const token of tokens) expect(content, `${path} 缺少 ${token}`).toContain(token)
    }
  })

  it('发现层和系统页不再使用英文操作标签作为主界面', () => {
    const files = [
      'components/discovery/SeoEditor.vue',
      'components/discovery/GeoEditor.vue',
      'components/discovery/SourceCitationEditor.vue',
      'pages/locales.vue',
      'pages/users.vue',
      'pages/rfqs/[id].vue',
    ]
    for (const path of files) {
      const content = source(path)
      expect(content, path).toContain('中文')
    }
  })

  it('后台根节点不根据仅客户端用户状态改变 SSR 结构', () => {
    const content = source('app.vue')
    expect(content).toContain('<div class="admin-app">')
    expect(content).not.toContain('admin-app--authenticated')
  })

  it('后台品牌和系统页浏览器标题使用简体中文', () => {
    expect(source('admin-config.ts')).toContain("title: '骏辉全球官网后台'")
    expect(source('pages/homepage.vue')).toContain('首页模块编辑器 ·')
    expect(source('pages/site-pages/products.vue')).toContain('产品总列表 SEO ·')
    expect(source('pages/privacy.vue')).toContain('隐私说明管理 ·')
    expect(source('pages/users.vue')).toContain("title: '后台用户'")
    expect(source('pages/locales.vue')).toContain("title: '网站语言'")
  })
})
