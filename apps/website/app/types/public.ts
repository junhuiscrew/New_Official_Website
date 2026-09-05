// 模块用途：集中定义公开站点可消费的白名单 DTO，禁止携带内部标识和存储字段。

/** URL 使用的受支持语言。 */
export type LocaleSlug = 'zh-cn' | 'en'

/** 公开内容类型，仅用于展示、导航和来源上下文。 */
export type PublicContentType =
  | 'product_category'
  | 'product'
  | 'material'
  | 'technology'
  | 'solution'
  | 'application'
  | 'manufacturing_capability'
  | 'case_study'
  | 'knowledge_article'
  | 'author_expert'
  | 'download_resource'
  | 'exhibition'

/** 已发布内容的 canonical 链接 DTO。 */
export interface PublicLinkDto {
  type: PublicContentType
  slug: string
  name: string
  url: string
  summary: string
}

/** 浏览器渲染公开媒体所需的完整白名单字段。 */
export interface PublicMediaDto {
  src: string
  type: 'image' | 'video' | 'document' | 'cad' | 'other'
  mime_type: string
  width: number | null
  height: number | null
  alt: string
  caption: string | null
  loading: 'eager' | 'lazy'
}

/** 后端已经格式化、可直接展示的产品规格。 */
export interface PublicSpecDto {
  name: string
  value: string
  unit: string | null
  group: string
  type: 'text' | 'number' | 'range' | 'boolean' | 'enum'
}

/** 列表与首页卡片可选的公开展示增强字段。 */
export interface PublicCardDto extends PublicLinkDto {
  media?: PublicMediaDto | null
  specifications?: PublicSpecDto[]
  category?: PublicLinkDto | null
  author?: string | null
  reviewer?: string | null
  published_at?: string | null
  updated_at?: string | null
}

/** 导航 API 中允许公开显示的公司联系方式。 */
export interface NavigationCompanyDto {
  name: string
  phone: string | null
  email: string | null
  address: string | null
}

/** Desktop、Mobile 与 Footer 共用的导航聚合 DTO。 */
export interface NavigationDto {
  locale: LocaleSlug
  primary: Array<
    | 'products'
    | 'solutions'
    | 'materials'
    | 'applications'
    | 'capabilities'
    | 'case_studies'
    | 'knowledge'
    | 'about'
  >
  products: {
    categories: PublicLinkDto[]
    featured: PublicLinkDto[]
  }
  solutions: {
    featured: PublicLinkDto[]
    problems: PublicLinkDto[]
  }
  materials: PublicLinkDto[]
  applications: PublicLinkDto[]
  company: NavigationCompanyDto | null
}

/** 首页 API 中经过发布门禁的公司公开事实。 */
export interface PublicCompanyDto {
  company_name: string
  short_intro: string | null
  full_intro: string | null
  mission: string | null
  advantages: string[] | null
  founded_year: number | null
  years_experience: number | null
  employee_count_range: string | null
  factory_area_sqm: number | null
  annual_capacity_text: string | null
  export_markets: string[] | null
  phone: string | null
  email: string | null
  address: string | null
  url: string
}

/** 首页可信度摘要，只允许后端真实存在的公开事实。 */
export interface PublicTrustSummaryDto {
  founded_year?: number
  years_experience?: number
  employee_count_range?: string
  factory_area_sqm?: number
  annual_capacity_text?: string
  export_markets?: string[]
}

/** 单次 SSR 首页请求返回的公开聚合 DTO。 */
export interface HomeDto {
  locale: LocaleSlug
  company: PublicCompanyDto | null
  hero_media: PublicMediaDto | null
  product_categories: PublicCardDto[]
  featured_products: PublicCardDto[]
  materials: PublicCardDto[]
  solutions: PublicCardDto[]
  capabilities: PublicCardDto[]
  applications: PublicCardDto[]
  cases: PublicCardDto[]
  knowledge: PublicCardDto[]
  trust_summary: PublicTrustSummaryDto | null
  seo?: SeoDto | null
  schema?: unknown | null
}

/** 后端生成且可直接用于页面 head 的 SEO DTO。 */
export interface SeoDto {
  title: string
  description: string | null
  canonical: string
  robots: string
  og_title?: string | null
  og_description?: string | null
  hreflang?: Partial<Record<'zh-CN' | 'en' | 'x-default', string>>
}

/** 页面正文必须可见的 GEO 内容 DTO。 */
export interface GeoDto {
  direct_answer: string | null
  key_facts: string[]
  evidence: string[]
  related_questions: string[]
  last_reviewed_at: string | null
}

/** 公开集合端点返回的统一分页 envelope。 */
export interface PublicCollectionDto<T extends PublicLinkDto = PublicCardDto> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
  filters: { [Key in keyof ProductFilters]: string | null }
  seo?: SeoDto
  schema?: unknown
  breadcrumb?: PublicBreadcrumbDto[]
}

/** 产品列表 URL 中允许出现的三项业务筛选。 */
export interface ProductFilters {
  category: string
  material: string
  application: string
}

/** 单个筛选选项只保留公开 slug 与显示名称。 */
export interface PublicFilterOption {
  value: string
  label: string
}

/** Product FilterBar 的三组已发布选项。 */
export interface ProductFilterOptions {
  categories: PublicFilterOption[]
  materials: PublicFilterOption[]
  applications: PublicFilterOption[]
}

/** 面包屑正文与后端 Breadcrumb Schema 共用的链接字段。 */
export interface PublicBreadcrumbDto {
  name: string
  url: string
}

/** 产品详情中的公开型号。 */
export interface PublicProductModelDto {
  model_code: string
  sort_order: number
}

/** 产品详情当前语言的结构化正文。 */
export interface PublicProductTranslationDto {
  name: string
  short_description: string | null
  description: string | null
  highlights: string[] | null
}

/** 产品详情端点的完整公开白名单 DTO。 */
export interface PublicProductDetailDto {
  slug: string
  category_slug: string
  translation: PublicProductTranslationDto
  models: PublicProductModelDto[]
  specifications: PublicSpecDto[]
  media: PublicMediaDto[]
  primary_media: PublicMediaDto | null
  relations: Record<string, PublicLinkDto[]>
  faqs: Array<{ question: string; answer: string }>
  cases: PublicLinkDto[]
  knowledge: PublicLinkDto[]
  trust_summary: PublicTrustSummaryDto | null
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}
