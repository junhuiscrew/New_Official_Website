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
  category?: PublicLinkDto | PublicKnowledgeCategoryDto | null
  author?: string | null
  reviewer?: string | null
  published_at?: string | null
  updated_at?: string | null
  role_type?: PublicPersonRole | null
}

/** Search V1 仅允许检索的六类公开内容。 */
export type PublicSearchType =
  | 'product'
  | 'material'
  | 'application'
  | 'solution'
  | 'knowledge_article'
  | 'case_study'

/** Search API 按类型返回的 canonical 卡片集合。 */
export interface PublicSearchDto {
  query: string
  groups: Record<PublicSearchType, PublicLinkDto[]>
}

/** Knowledge 分类仅用于已发布文章筛选，不伪装成独立详情实体。 */
export interface PublicKnowledgeCategoryDto {
  slug: string
  name: string
  url: string
}

/** 后端 AuthorExpert 模型允许公开的人物职责类型。 */
export type PublicPersonRole = 'author' | 'expert' | 'author_expert'

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

/** About 页使用的完整 Company Public DTO；SEO/GEO/Schema 均由后端生成。 */
export interface PublicCompanyProfileDto extends PublicCompanyDto {
  seo: {
    title: string | null
    description: string | null
    canonical: string
    robots_index: boolean
    robots_follow: boolean
    hreflang: Array<{ hreflang: string; url: string }>
  }
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
}

/** Trust 聚合页卡片；details 仅含服务端按资源类型白名单输出的事实。 */
export interface PublicTrustListItemDto {
  type: PublicContentType | 'certificate' | 'patent' | 'honor'
  slug: string
  title: string
  summary: string | null
  url: string | null
  details?: Record<string, string | number | null>
}

/** Capability 内嵌的已发布 Equipment 翻译和结构化事实。 */
export interface PublicEquipmentDto {
  slug: string
  equipment_type: string
  manufacturer: string | null
  model: string | null
  quantity: number | null
  commissioning_year: number | null
  precision_text: string | null
  capacity_text: string | null
  featured: boolean
  translation: {
    name: string
    summary: string | null
    description: string | null
    public_specs_json: Record<string, string | number | boolean | null> | null
  }
}

/** Capability 详情只消费服务端发布门禁批准的证据和 canonical links。 */
export interface PublicCapabilityDetailDto {
  type: 'manufacturing_capability'
  slug: string
  translation: {
    name: string
    summary: string | null
    description: string | null
    key_facts_json: string[] | null
  }
  details: Record<string, string | number | null>
  url: string
  equipment: PublicEquipmentDto[]
  primary_media: PublicMediaDto | null
  media: PublicMediaDto[]
  relations: Partial<Record<'technologies' | 'products' | 'cases', PublicLinkDto[]>>
  seo: PublicTrustSeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
}

/** Exhibition 详情使用的 route-based Trust DTO。 */
export interface PublicExhibitionDetailDto {
  type: 'exhibition'
  slug: string
  translation: { title: string; summary: string | null; description: string | null }
  details: Record<string, string | number | null>
  url: string
  primary_media: PublicMediaDto | null
  seo: PublicTrustSeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
}

/** 兼容已冻结 Trust API 的 SEO 形状。 */
export interface PublicTrustSeoDto {
  title: string | null
  description: string | null
  canonical: string
  robots_index: boolean
  robots_follow?: boolean
  hreflang: Array<{ hreflang: string; url: string }>
}

/** 对象存储存在性已由后端核验的公开下载元数据。 */
export interface PublicDownloadDto {
  slug: string
  resource_type: string
  title: string
  summary: string | null
  version_label: string | null
  published_date: string | null
  url: string
  mime_type: string
  file_size_bytes: number
}

/** Trust 与 Downloads 聚合页后端统一生成的页面级元数据。 */
export interface PublicPageMetadataDto {
  seo: SeoDto
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
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

/** 四类 Catalog 页面使用的稳定复数资源名。 */
export type CatalogResource = 'materials' | 'technologies' | 'applications' | 'solutions'

/** Catalog 关系区允许显示的后端分组键。 */
export type CatalogRelationGroup =
  | 'products'
  | 'materials'
  | 'technologies'
  | 'applications'
  | 'solutions'
  | 'cases'
  | 'knowledge'

/** 四类 Catalog 翻译 DTO 的显式字段并集；不同类型未使用字段保持缺省。 */
export interface PublicCatalogTranslationDto {
  name: string
  definition?: string | null
  processing_characteristics?: string | null
  screw_impact?: string | null
  recommendations?: string | null
  limitations?: string | null
  process_description?: string | null
  benefits?: string | null
  description?: string | null
  technical_requirements?: string | null
  common_problems?: string | null
  symptoms?: string | null
  causes?: string | null
  diagnosis?: string | null
  solution?: string | null
}

/** 四类 Catalog 详情端点的公开白名单 DTO。 */
export interface PublicCatalogDetailDto {
  type: 'material' | 'technology' | 'application' | 'solution'
  slug: string
  translation: PublicCatalogTranslationDto
  relations: Partial<Record<CatalogRelationGroup, PublicLinkDto[]>>
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}

/** 公开集合端点返回的统一分页 envelope。 */
export interface PublicCollectionDto<T extends PublicLinkDto = PublicCardDto> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
  filters: PublicCollectionFilters
  seo?: SeoDto
  schema?: unknown
  breadcrumb?: PublicBreadcrumbDto[]
}

/** 所有公开集合共用的白名单筛选回显。 */
export interface PublicCollectionFilters {
  category: string | null
  material: string | null
  application: string | null
  type?: PublicPersonRole | null
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

/** 与后端 FAQPage Schema 使用同一数组的可见问答 DTO。 */
export interface PublicFaqDto {
  question: string
  answer: string
}

/** Knowledge 来源引用的公开可核验字段。 */
export interface PublicSourceCitationDto {
  title: string
  url: string
  publisher: string | null
  publication_date: string | null
  source_type: string
}

/** Knowledge Article 详情端点的权威公开 DTO。 */
export interface PublicKnowledgeDetailDto {
  slug: string
  category_slug: string
  category: PublicKnowledgeCategoryDto
  translation: {
    title: string
    summary: string | null
    body_markdown: string
  }
  author: {
    name: string
    job_title: string | null
    short_bio: string | null
    is_real_person_verified: true
  }
  reviewer: { name: string; job_title: string | null } | null
  published_at: string | null
  updated_at: string | null
  last_reviewed_at: string | null
  sources: PublicSourceCitationDto[]
  faqs: PublicFaqDto[]
  relations: Partial<Record<CatalogRelationGroup, PublicLinkDto[]>>
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}

/** Case 仅在后端逐项许可后才返回的客户身份。 */
export interface PublicCustomerIdentityDto {
  name: string | null
  address: string | null
  logo: PublicMediaDto | null
}

/** Case Study 详情端点的隐私安全 DTO。 */
export interface PublicCaseDetailDto {
  slug: string
  country_code: string | null
  industry: string | null
  machine_brand: string | null
  machine_model: string | null
  screw_diameter: string | null
  filler_percentage: string | null
  media: PublicMediaDto | null
  customer_identity: PublicCustomerIdentityDto | null
  translation: {
    title: string
    summary: string | null
    client_description: string | null
    problem: string | null
    analysis: string | null
    solution: string | null
    result: string | null
    engineer_comment: string | null
  }
  faqs: PublicFaqDto[]
  relations: Partial<Record<CatalogRelationGroup, PublicLinkDto[]>>
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}

/** 仅代表已经由后端核验并授权公开的真实人物详情。 */
export interface PublicExpertDetailDto {
  slug: string
  name: string
  job_title: string | null
  short_bio: string | null
  expertise: string[]
  role_type: PublicPersonRole
  years_experience: number | null
  linkedin_url: string | null
  public_email: string | null
  is_real_person_verified: true
  profile_media: PublicMediaDto | null
  authored_knowledge: PublicLinkDto[]
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}
