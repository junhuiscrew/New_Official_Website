// 模块用途：集中维护后台简体中文界面词表；接口枚举、权限代码和业务正文保持原值。

export const ENTITY_STATUS_LABELS: Record<string, string> = {
  enabled: '启用',
  disabled: '停用',
  retired: '已退役',
}

export const PUBLICATION_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  review: '待审核',
  scheduled: '已安排发布',
  published: '已发布',
  archived: '已归档',
}

export const TRANSLATION_STATUS_LABELS: Record<string, string> = {
  missing: '缺少译文',
  draft: '翻译草稿',
  machine_translated: '机器翻译待审核',
  human_reviewed: '已人工审核',
  published: '已发布',
}

export const RFQ_STATUS_LABELS: Record<string, string> = {
  new: '待处理',
  qualified: '已确认需求',
  in_progress: '跟进中',
  waiting_customer: '等待客户回复',
  quoted: '已报价',
  won: '已成交',
  lost: '未成交',
  spam: '垃圾询盘',
  closed: '已关闭',
}

export const RFQ_PRIORITY_LABELS: Record<string, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
}

export const ROLE_TYPE_LABELS: Record<string, string> = {
  author: '作者',
  expert: '专家',
  author_expert: '作者兼专家',
}

export const ROLE_NAME_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  admin: '管理员',
  content_admin: '内容管理员',
  content_manager: '内容管理员',
  editor: '内容编辑',
  media_manager: '媒体管理员',
  reviewer: '审核员',
  translator: '翻译人员',
  seo_manager: 'SEO/GEO 管理员',
  sales: '销售人员',
  viewer: '只读人员',
}

export const PERMISSION_RESOURCE_LABELS: Record<string, string> = {
  application: '应用',
  audit: '审计记录',
  capability: '制造能力',
  case: '客户案例',
  catalog: '产品目录',
  certificate: '证书',
  company: '企业资料',
  content: '网站内容',
  download: '下载资料',
  equipment: '设备',
  exhibition: '展会',
  expert: '作者与专家',
  faq: '常见问题',
  geo: 'GEO（答案优化）',
  honor: '荣誉',
  knowledge: '知识文章',
  locale: '网站语言',
  material: '材料',
  media: '媒体资源',
  patent: '专利',
  privacy: '隐私版本',
  product: '产品',
  redirect: '重定向',
  rfq: '询盘',
  role: '角色权限',
  seo: 'SEO（搜索优化）',
  settings: '系统设置',
  solution: '解决方案',
  source: '来源引用',
  specification: '规格参数',
  technology: '技术工艺',
  translation: '多语言内容',
  user: '用户',
}

export const PERMISSION_ACTION_LABELS: Record<string, string> = {
  read: '查看',
  create: '新建',
  update: '编辑',
  review: '审核',
  publish: '发布',
  archive: '归档',
  manage: '管理',
  assign: '分配',
  download: '下载',
  delete: '删除',
  disable: '停用',
  edit: '编辑',
  history: '查看历史',
  upload: '上传',
  download_private_file: '下载私有附件',
}

export const AUTHORITY_FIELD_LABELS: Record<string, string> = {
  title: '标题',
  summary: '摘要',
  body_markdown: '正文（Markdown）',
  question: '问题',
  answer: '答案',
  name: '名称',
  job_title: '职位',
  short_bio: '简短介绍',
  expertise_json: '专业领域（每行一项）',
  client_description: '公开客户说明',
  problem: '问题描述',
  analysis: '技术分析',
  solution: '实施方案',
  result: '实施结果',
  engineer_comment: '工程师点评',
}

export const NAVIGATION_STATUS_LABELS: Record<string, string> = {
  visible: '导航中显示',
  hidden: '导航中隐藏',
  not_primary_navigation: '不属于主导航',
  not_in_primary_registry: '未登记到主导航',
  route_only: '仅路由可访问',
  utility_navigation: '工具入口（不进入主导航）',
  footer_when_published: '发布后显示在页脚',
  footer_or_rfq_entry: '仅在页脚或询价入口出现',
}

export const IMPLEMENTATION_STATUS_LABELS: Record<string, string> = {
  homepage_renderer_and_source: '首页组件与数据源已接通',
  frontend_and_admin: '前台与后台均已接通',
  frontend_only: '仅前台已接通',
  admin_only: '仅后台已接通',
  route_only: '仅路由已实现',
  missing: '尚未实现',
  public_search_service: '站内搜索服务',
  private_draft_current_empty: '当前私有草稿（未设置公开版本）',
  contact_entry_only: '仅作为联系入口使用',
}

export const HIDDEN_REASON_LABELS: Record<string, string> = {
  utility_navigation: '工具入口暂不进入主导航',
  public_search_service: '站内搜索服务入口',
  footer_when_published: '发布后显示在页脚',
  private_draft_current_empty: '当前为私有草稿，暂未设置公开版本',
  footer_or_rfq_entry: '仅在页脚或询价入口出现',
  contact_entry_only: '仅作为联系入口使用',
  正式政策未批准发布: '正式政策尚未批准发布',
}

export const DOWNLOAD_RESOURCE_TYPE_LABELS: Record<string, string> = {
  document: '文档',
  catalog: '产品目录',
  datasheet: '数据表',
  manual: '使用手册',
  certificate: '证书文件',
  video: '视频资料',
  other: '其他资料',
}

export const MEDIA_USAGE_ROLE_LABELS: Record<string, string> = {
  primary: '主图',
  logo: '企业 Logo',
  factory_primary: '工厂主图',
  gallery: '图库',
  video: '视频',
  video_poster: '视频封面',
  download: '下载资料',
  cover: '封面',
  hero: '首页主视觉',
  profile: '公开头像',
}

/**
 * 将语言代码转换为中文后台的操作标签，业务正文和接口代码保持原值。
 *
 * 输入：code，接口语言代码；nativeName，接口原生语言名称。
 * 输出：string，员工操作界面使用的简体中文标签。
 */
export function localeOperationLabel(code: string, nativeName?: string): string {
  if (code === 'zh-CN') return '简体中文'
  if (code === 'en') return '英语'
  return nativeName || code || '未知语言'
}

/**
 * 将接口时间转换为北京时间；缺失时区的值不擅自偏移。
 *
 * 输入：value，ISO 时间字符串、Date、空值或未知值。
 * 输出：string，可读北京时间；无值返回“—”，无时区字符串保留原值并提示。
 */
export function formatBeijingTime(value: unknown): string {
  if (!value) return '—'
  if (typeof value === 'string' && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value.trim())) {
    return `${value}（未标明时区）`
  }
  const date = value instanceof Date ? value : new Date(String(value))
  if (Number.isNaN(date.getTime())) return '时间格式无效'
  return `${new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)}（北京时间）`
}

/** 输入接口枚举与词表；输出中文显示值，未知代码保留原值供排查。 */
export function labelFrom(map: Record<string, string>, value: unknown, fallback = '—'): string {
  const code = String(value ?? '')
  return map[code] || code || fallback
}

/**
 * 拆分权限代码供中文矩阵展示，权限代码本身仍保留在技术详情中。
 *
 * 输入：code，形如 rfq.update 的权限代码。
 * 输出：资源、动作和对应中文标签。
 */
export function permissionPresentation(code: string): {
  resource: string
  action: string
  resourceLabel: string
  actionLabel: string
} {
  const [resource = code, action = ''] = code.split('.', 2)
  return {
    resource,
    action,
    resourceLabel: PERMISSION_RESOURCE_LABELS[resource] || resource,
    actionLabel: PERMISSION_ACTION_LABELS[action] || action,
  }
}
