<!-- 组件职责：提供 Case、Knowledge、FAQ、真实 Expert 的最小真实 CRUD 与发现层编辑。 -->
<script setup lang="ts">
import GeoEditor, { type GeoDraft } from '~/components/discovery/GeoEditor.vue'
import SeoEditor, { type SeoDraft } from '~/components/discovery/SeoEditor.vue'
import SourceCitationEditor, {
  type SourceDraft,
} from '~/components/discovery/SourceCitationEditor.vue'
import {
  AUTHORITY_FIELD_LABELS,
  ENTITY_STATUS_LABELS,
  PUBLICATION_STATUS_LABELS,
  ROLE_TYPE_LABELS,
  TRANSLATION_STATUS_LABELS,
  formatBeijingTime,
  labelFrom,
} from '~/utils/adminZhCn'

type AuthorityResource = 'cases' | 'knowledge' | 'faqs' | 'experts'
interface AuthorityItem {
  id: string
  slug?: string
  display_title?: string
  display_title_en?: string
  translation_count?: number
  status: string
  sort_order: number
  updated_at?: string
  [key: string]: unknown
}
interface LocaleItem {
  id: string
  code: string
  native_name: string
}
interface TranslationDraft {
  locale_id: string
  code: string
  fields: Record<string, string>
}
interface LifecycleRow {
  locale_id: string
  status: string
  path?: string
  active?: boolean
  indexable?: boolean
}
interface MediaItem {
  id: string
  filename: string
  type: string
}
interface RelationOption {
  id: string
  slug?: string
  display_title?: string
  display_title_en?: string
  display_name?: string
  display_name_en?: string
  translations?: Array<Record<string, unknown>>
}

const props = defineProps<{ title: string; resource: AuthorityResource }>()
const api = useAuthorityApi()
const items = ref<AuthorityItem[]>([])
const locales = ref<LocaleItem[]>([])
const categories = ref<AuthorityItem[]>([])
const experts = ref<AuthorityItem[]>([])
const media = ref<MediaItem[]>([])
const selectedId = ref('')
const loadingRecordId = ref('')
const activeLocaleId = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const initialLoading = ref(true)
const saving = ref(false)
const editorMode = ref<'none' | 'create' | 'edit'>('none')
const searchTerm = ref('')
const page = ref(1)
const pageSize = 8
const baselineSnapshot = ref('')
let detailRequestVersion = 0
const translationStatuses = ref<LifecycleRow[]>([])
const publications = ref<LifecycleRow[]>([])
const routes = ref<LifecycleRow[]>([])

// 单一表单覆盖四类实体的最小结构化主字段；不使用 Rich Text 容器替代关系。
const form = reactive({
  slug: '',
  status: 'enabled',
  sort_order: 0,
  featured: false,
  country_code: '',
  industry: '',
  machine_brand: '',
  machine_model: '',
  screw_diameter: '',
  processed_material_text: '',
  filler_percentage: '',
  client_name: '',
  client_address: '',
  client_logo_media_id: '',
  client_name_public: false,
  client_address_public: false,
  client_logo_public: false,
  category_id: '',
  author_id: '',
  reviewer_id: '',
  role_type: 'expert',
  is_real_person_verified: false,
  public_profile_enabled: false,
  public_email: '',
  years_experience: 0,
  linkedin_url: '',
  translations: [] as TranslationDraft[],
})
const relationIds = reactive<Record<string, string[]>>({
  product_ids: [],
  material_ids: [],
  technology_ids: [],
  application_ids: [],
  solution_ids: [],
  case_ids: [],
  faq_ids: [],
  article_ids: [],
})
const relationOptions = reactive<Record<string, RelationOption[]>>({})
const relationSources: Record<string, { path: string; label: string }> = {
  product_ids: { path: '/catalog/products', label: '产品' },
  material_ids: { path: '/catalog/materials', label: '材料' },
  technology_ids: { path: '/catalog/technologies', label: '工艺' },
  application_ids: { path: '/catalog/applications', label: '应用' },
  solution_ids: { path: '/catalog/solutions', label: '方案' },
  case_ids: { path: '/authority/cases', label: '案例' },
  faq_ids: { path: '/authority/faqs', label: 'FAQ' },
  article_ids: { path: '/authority/knowledge', label: '文章' },
}

const resourceCopy = computed(
  () =>
    ({
      cases: {
        title: '客户案例',
        description: '维护案例正文、客户公开许可、关联内容与发布状态。',
        singular: '案例',
      },
      knowledge: {
        title: '知识文章',
        description: '维护双语文章正文、作者、分类、来源与发布状态。',
        singular: '文章',
      },
      faqs: {
        title: '常见问题',
        description: '维护双语问题与答案，并将其关联到对应内容。',
        singular: '常见问题',
      },
      experts: {
        title: '作者与专家',
        description: '维护真实作者或组织资料；身份核验状态不会由界面自动改变。',
        singular: '作者或专家',
      },
    })[props.resource],
)
/** 输出一份新的 SEO 空白表单，防止切换语言时沿用上一语言内容。 */
function emptySeoDraft(): SeoDraft {
  return {
    seo_title: '',
    meta_description: '',
    canonical_override: '',
    robots_index: true,
    robots_follow: true,
    og_title: '',
    og_description: '',
  }
}

/** 输出一份新的 GEO 空白表单，确保每个语言独立读取与保存。 */
function emptyGeoDraft(): GeoDraft {
  return {
    direct_answer: '',
    target_questions_json: [],
    key_facts_json: [],
    evidence_json: [],
    related_questions_json: [],
    reviewer_id: '',
    last_reviewed_at: '',
  }
}

/**
 * 将 API SEO 文档转换成仅含可编辑字段的表单。
 *
 * 输入：document，可能包含服务端只读元数据的 SEO 回读对象。
 * 输出：SeoDraft，不携带ID、owner或审计时间等只读字段。
 */
function seoDraftFromDocument(document?: Record<string, unknown>): SeoDraft {
  return {
    seo_title: String(document?.seo_title ?? ''),
    meta_description: String(document?.meta_description ?? ''),
    canonical_override: String(document?.canonical_override ?? ''),
    robots_index: typeof document?.robots_index === 'boolean' ? document.robots_index : true,
    robots_follow: typeof document?.robots_follow === 'boolean' ? document.robots_follow : true,
    og_title: String(document?.og_title ?? ''),
    og_description: String(document?.og_description ?? ''),
  }
}

/** 输入未知值；输出只保留字符串成员的数组。 */
function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

/**
 * 将 API GEO 文档转换成仅含可编辑字段的表单。
 *
 * 输入：document，可能包含服务端只读元数据的 GEO 回读对象。
 * 输出：GeoDraft，可安全再次提交给严格校验接口。
 */
function geoDraftFromDocument(document?: Record<string, unknown>): GeoDraft {
  return {
    direct_answer: String(document?.direct_answer ?? ''),
    target_questions_json: stringList(document?.target_questions_json),
    key_facts_json: stringList(document?.key_facts_json),
    evidence_json: stringList(document?.evidence_json),
    related_questions_json: stringList(document?.related_questions_json),
    reviewer_id: String(document?.reviewer_id ?? ''),
    last_reviewed_at: String(document?.last_reviewed_at ?? ''),
  }
}

const seo = ref<SeoDraft>(emptySeoDraft())
const geo = ref<GeoDraft>(emptyGeoDraft())
const geoVisibleSourceText = ref('')
const source = ref<SourceDraft>({
  title: '',
  url: '',
  publisher: '',
  source_type: 'official',
})

/** 输出当前编辑区完整快照，用于离开和快切前检测未保存修改。 */
function editorSnapshot(): string {
  return JSON.stringify({
    form,
    relations: relationIds,
    seo: seo.value,
    geo: geo.value,
    source: source.value,
  })
}

const isDirty = computed(
  () => Boolean(baselineSnapshot.value) && editorSnapshot() !== baselineSnapshot.value,
)

/** 将当前服务端回读状态标记为未修改基线。 */
function markClean(): void {
  baselineSnapshot.value = editorSnapshot()
}

/** 输入可能丢失或英文的接口错误；输出面向员工的中文错误提示。 */
function readableError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : ''
  if (/403|permission|forbidden/i.test(message)) return '没有执行此操作的权限。'
  if (/404|not found/i.test(message)) return '记录不存在或已被其他人移除，请刷新后重试。'
  if (/409|conflict|revision/i.test(message)) return '内容已被其他人更新，请刷新后重新编辑。'
  if (/401|unauthor/i.test(message)) return '登录状态已失效，请重新登录。'
  return fallback
}

/** 有未保存修改时请求员工确认；确认仅影响本地编辑区，不写数据库。 */
function confirmDiscardChanges(): boolean {
  return !isDirty.value || window.confirm('当前有未保存的修改，离开后将丢失。是否继续？')
}

const translationFields = computed(() => {
  if (props.resource === 'cases')
    return [
      'title',
      'summary',
      'client_description',
      'problem',
      'analysis',
      'solution',
      'result',
      'engineer_comment',
    ]
  if (props.resource === 'knowledge') return ['title', 'summary', 'body_markdown']
  if (props.resource === 'faqs') return ['question', 'answer']
  return ['name', 'job_title', 'short_bio', 'expertise_json']
})
const hasRelations = computed(() => props.resource !== 'experts')
const ownerType = computed(
  () =>
    ({
      cases: 'case_study',
      knowledge: 'knowledge_article',
      faqs: 'faq',
      experts: 'author_expert',
    })[props.resource],
)

const filteredItems = computed(() => {
  const keyword = searchTerm.value.trim().toLocaleLowerCase('zh-CN')
  if (!keyword) return items.value
  return items.value.filter((item) =>
    [item.display_title, item.display_title_en, item.slug]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase('zh-CN').includes(keyword)),
  )
})
const paginatedItems = computed(() =>
  filteredItems.value.slice((page.value - 1) * pageSize, page.value * pageSize),
)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize)))

/** 输入翻译字段代码；输出中文业务标签，代码仅保留在辅助说明中。 */
function fieldLabel(field: string): string {
  return AUTHORITY_FIELD_LABELS[field] || field
}

/** 输入语言代码；输出后台固定中文语言标签。 */
function localeLabel(code: string): string {
  return code === 'zh-CN' ? '简体中文内容' : code === 'en' ? '英语内容' : code
}

function emptyTranslations() {
  form.translations = locales.value.map((locale) => ({
    locale_id: locale.id,
    code: locale.code,
    fields: Object.fromEntries(translationFields.value.map((field) => [field, ''])),
  }))
}

function resetForm(mode: 'none' | 'create' = 'none') {
  editorMode.value = mode
  selectedId.value = ''
  loadingRecordId.value = ''
  errorMessage.value = ''
  successMessage.value = ''
  Object.assign(form, {
    slug: '',
    status: 'enabled',
    sort_order: 0,
    featured: false,
    country_code: '',
    industry: '',
    machine_brand: '',
    machine_model: '',
    screw_diameter: '',
    processed_material_text: '',
    filler_percentage: '',
    client_name: '',
    client_address: '',
    client_logo_media_id: '',
    client_name_public: false,
    client_address_public: false,
    client_logo_public: false,
    category_id: '',
    author_id: '',
    reviewer_id: '',
    role_type: 'expert',
    is_real_person_verified: false,
    public_profile_enabled: false,
    public_email: '',
    years_experience: 0,
    linkedin_url: '',
  })
  Object.keys(relationIds).forEach((key) => {
    relationIds[key] = []
  })
  emptyTranslations()
  translationStatuses.value = []
  publications.value = []
  routes.value = []
  seo.value = emptySeoDraft()
  geo.value = emptyGeoDraft()
  source.value = { title: '', url: '', publisher: '', source_type: 'official' }
  nextTick(markClean)
}

/** 切换到新建状态；未保存修改必须由员工明确放弃。 */
function startCreate(): void {
  if (!confirmDiscardChanges()) return
  resetForm('create')
}

/**
 * 读取关系选择器的可读选项。
 *
 * 输入：key，关系字段名；source，受权限保护的实体列表地址与标签。
 * 输出：Promise<RelationOption[]>；FAQ 因无 slug 会补读详情中的双语问题，其余实体沿用列表。
 */
async function loadRelationOptions(
  key: string,
  source: { path: string; label: string },
): Promise<RelationOption[]> {
  const options = (await api.list<RelationOption>(source.path)).items
  if (key !== 'faq_ids' || options.every((option) => option.display_title)) return options
  return Promise.all(
    options.map(async (option) => {
      if (option.translations?.length) return option
      const detail = await api.detail<RelationOption>(`${source.path}/${option.id}`)
      return { ...option, translations: detail.translations || [] }
    }),
  )
}

async function load(reopenId = ''): Promise<void> {
  initialLoading.value = true
  try {
    const [result, localeItems] = await Promise.all([
      api.list<AuthorityItem>(`/authority/${props.resource}`, {
        page: 1,
        page_size: 100,
      }),
      api.detail<LocaleItem[]>('/locales'),
    ])
    // 列表要等依赖选项全部加载后再出现，避免用户点击记录后被初始化末尾重置为“新建”。
    const loadedItems = result.items
    locales.value = localeItems
    activeLocaleId.value ||= localeItems[0]?.id || ''
    const expertResult = await api.list<AuthorityItem>('/authority/experts')
    experts.value = expertResult.items
    if (props.resource === 'knowledge') {
      const categoryResult = await api.list<AuthorityItem>('/authority/knowledge-categories')
      categories.value = categoryResult.items
    }
    if (props.resource === 'cases') {
      try {
        media.value = await api.detail<MediaItem[]>('/media')
      } catch {
        media.value = []
      }
    }
    if (hasRelations.value) {
      const relationResults = await Promise.allSettled(
        Object.entries(relationSources).map(
          async ([key, source]) => [key, await loadRelationOptions(key, source)] as const,
        ),
      )
      for (const result of relationResults) {
        if (result.status === 'fulfilled') relationOptions[result.value[0]] = result.value[1]
      }
    }
    resetForm()
    items.value = loadedItems
    errorMessage.value = ''
    if (reopenId) {
      const reopened = loadedItems.find((item) => item.id === reopenId)
      if (reopened) await editItem(reopened, true)
    }
  } catch (error) {
    errorMessage.value = readableError(error, '无法读取内容，请检查网络或稍后重试。')
  } finally {
    initialLoading.value = false
  }
}

async function editItem(item: Pick<AuthorityItem, 'id'>, force = false): Promise<void> {
  if (!force && item.id !== selectedId.value && !confirmDiscardChanges()) return
  const requestVersion = ++detailRequestVersion
  resetForm()
  // 点击后立即标记选中与加载状态，避免把尚未返回的空表单误认为数据库正文丢失。
  selectedId.value = item.id
  loadingRecordId.value = item.id
  editorMode.value = 'edit'
  baselineSnapshot.value = ''
  try {
    const detail = await api.detail<
      AuthorityItem & {
        translations?: Array<Record<string, unknown>>
        translation_statuses?: LifecycleRow[]
        publications?: LifecycleRow[]
        routes?: LifecycleRow[]
        seo_documents?: Array<Record<string, unknown>>
        geo_documents?: Array<Record<string, unknown>>
        relations?: Record<string, string[]>
      }
    >(`/authority/${props.resource}/${item.id}`)
    // 快速切换记录时只允许最后一次点击的详情写入表单。
    if (selectedId.value !== item.id || requestVersion !== detailRequestVersion) return
    for (const key of Object.keys(form)) {
      if (key !== 'translations' && detail[key] !== undefined)
        (form as Record<string, unknown>)[key] = detail[key] ?? ''
    }
    form.translations = locales.value.map((locale) => {
      const existing = detail.translations?.find((row) => row.locale_id === locale.id)
      return {
        locale_id: locale.id,
        code: locale.code,
        fields: Object.fromEntries(
          translationFields.value.map((field) => [field, String(existing?.[field] ?? '')]),
        ),
      }
    })
    translationStatuses.value = detail.translation_statuses || []
    publications.value = detail.publications || []
    routes.value = detail.routes || []
    for (const key of Object.keys(relationIds)) relationIds[key] = detail.relations?.[key] || []
    const seoDocument = detail.seo_documents?.find((row) => row.locale_id === activeLocaleId.value)
    seo.value = seoDraftFromDocument(seoDocument)
    const geoDocument = detail.geo_documents?.find((row) => row.locale_id === activeLocaleId.value)
    geo.value = geoDraftFromDocument(geoDocument)
    if (activeLocaleId.value) {
      try {
        const preview = await api.detail<{ visible_source_text: string }>(
          `/discovery/geo-visible-source/${ownerType.value}/${item.id}/${activeLocaleId.value}`,
        )
        geoVisibleSourceText.value = preview.visible_source_text
      } catch {
        // 翻译尚未建立时只清空预览，不影响主体内容编辑。
        geoVisibleSourceText.value = ''
      }
    }
    await nextTick()
    markClean()
  } catch (error) {
    errorMessage.value = readableError(error, '无法读取记录详情，请刷新后重试。')
  } finally {
    if (loadingRecordId.value === item.id && requestVersion === detailRequestVersion)
      loadingRecordId.value = ''
  }
}

/**
 * 按操作开始时固定的记录ID重新读取编辑器。
 *
 * 输入：recordId，生命周期请求发出前捕获的实体ID。
 * 输出：Promise<void>，回读同一实体且不依赖异步变化中的列表。
 */
async function reloadSelectedItem(recordId: string) {
  if (!recordId) return
  await editItem({ id: recordId })
}

function translationsPayload() {
  return form.translations
    .map((translation) => ({
      locale_id: translation.locale_id,
      fields: Object.fromEntries(
        Object.entries(translation.fields)
          .filter(([, value]) => value.trim())
          .map(([key, value]) => [
            key,
            key === 'expertise_json'
              ? value
                  .split(/\r?\n/)
                  .map((item) => item.trim())
                  .filter(Boolean)
              : value,
          ]),
      ),
    }))
    .filter((translation) => Object.keys(translation.fields).length > 0)
}

function masterPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    status: form.status,
    sort_order: form.sort_order,
    translations: translationsPayload(),
  }
  if (props.resource !== 'faqs') payload.slug = form.slug
  if (props.resource === 'cases')
    Object.assign(payload, {
      featured: form.featured,
      country_code: form.country_code || null,
      industry: form.industry || null,
      machine_brand: form.machine_brand || null,
      machine_model: form.machine_model || null,
      screw_diameter: form.screw_diameter || null,
      processed_material_text: form.processed_material_text || null,
      filler_percentage: form.filler_percentage || null,
      client_name: form.client_name || null,
      client_address: form.client_address || null,
      client_logo_media_id: form.client_logo_media_id || null,
      client_name_public: form.client_name_public,
      client_address_public: form.client_address_public,
      client_logo_public: form.client_logo_public,
    })
  if (props.resource === 'knowledge')
    Object.assign(payload, {
      category_id: form.category_id,
      author_id: form.author_id,
      reviewer_id: form.reviewer_id || null,
      featured: form.featured,
    })
  if (props.resource === 'experts')
    Object.assign(payload, {
      role_type: form.role_type,
      is_real_person_verified: form.is_real_person_verified,
      public_profile_enabled: form.public_profile_enabled,
      public_email: form.public_email || null,
      years_experience: form.years_experience || null,
      linkedin_url: form.linkedin_url || null,
    })
  return payload
}

function relationPayload(): Record<string, unknown> {
  return Object.fromEntries(Object.entries(relationIds))
}

/** 输入关系选项；输出优先使用slug或翻译标题的可读名称，永不显示UUID。 */
function relationLabel(item: RelationOption): string {
  if (item.display_title || item.display_name) return item.display_title || item.display_name || ''
  const translation = item.translations?.[0]
  return String(
    translation?.title || translation?.name || translation?.question || item.slug || '未命名内容',
  )
}

/** 输入内容条目；输出列表中用于识别记录的可读名称。 */
function authorityLabel(item: AuthorityItem): string {
  return item.display_title || relationLabel(item as RelationOption)
}

/** 输出GEO复核人下拉框所需的可读专家选项。 */
const expertOptions = computed(() =>
  experts.value.map((expert) => ({
    id: expert.id,
    label: authorityLabel(expert),
  })),
)

/** 输入关系字段键；输出稳定中文标签，防止模板读取可选对象时报错。 */
function relationSourceLabel(key: string): string {
  return relationSources[key]?.label || key
}

async function save(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const saved = selectedId.value
      ? await api.update<AuthorityItem>(
          `/authority/${props.resource}/${selectedId.value}`,
          masterPayload(),
        )
      : await api.create<AuthorityItem>(`/authority/${props.resource}`, masterPayload())
    if (hasRelations.value)
      await api.replace(`/authority/${props.resource}/${saved.id}/relations`, relationPayload())
    await load(saved.id)
    successMessage.value = '已保存，并通过详情接口重新读取当前记录。'
    markClean()
  } catch (error) {
    errorMessage.value = readableError(error, '保存失败，请检查必填项和内容格式。')
  } finally {
    saving.value = false
  }
}

async function archiveSelected() {
  if (!selectedId.value) return
  if (!window.confirm(`确认归档当前${resourceCopy.value.singular}？`)) return
  await api.archive(`/authority/${props.resource}/${selectedId.value}/archive`)
  await load()
  successMessage.value = '内容已归档。'
}

async function saveSeo() {
  if (!selectedId.value || !activeLocaleId.value) return
  await api.replace(
    `/discovery/seo/${ownerType.value}/${selectedId.value}/${activeLocaleId.value}`,
    {
      seo_title: seo.value.seo_title,
      meta_description: seo.value.meta_description,
      canonical_override: seo.value.canonical_override || null,
      robots_index: seo.value.robots_index,
      robots_follow: seo.value.robots_follow,
      og_title: seo.value.og_title,
      og_description: seo.value.og_description,
    },
  )
  successMessage.value = 'SEO 已保存。'
  markClean()
}

/** 输出严格符合 GEO Upsert 的字段，阻止服务端只读元数据回灌。 */
function geoPayload() {
  return {
    direct_answer: geo.value.direct_answer,
    target_questions_json: geo.value.target_questions_json,
    key_facts_json: geo.value.key_facts_json,
    evidence_json: geo.value.evidence_json,
    related_questions_json: geo.value.related_questions_json,
    reviewer_id: geo.value.reviewer_id || null,
    last_reviewed_at: geo.value.last_reviewed_at || null,
  }
}

async function saveGeo() {
  if (!selectedId.value || !activeLocaleId.value) return
  const result = await api.replace<{ id: string }>(
    `/discovery/geo/${ownerType.value}/${selectedId.value}/${activeLocaleId.value}`,
    geoPayload(),
  )
  source.value.geo_document_id = result.id
  successMessage.value = 'GEO 已校验并保存。'
  markClean()
}

async function saveSource() {
  if (props.resource === 'knowledge') source.value.article_id = selectedId.value
  await api.create('/discovery/sources', { ...source.value })
  source.value = { title: '', url: '', publisher: '', source_type: 'official' }
  successMessage.value = '来源引用已保存。'
  markClean()
}

async function reviewTranslation() {
  if (!selectedId.value || !activeLocaleId.value) return
  const recordId = selectedId.value
  await api.request(
    `/authority/${props.resource}/${recordId}/translations/${activeLocaleId.value}/review`,
    { method: 'POST' },
  )
  await reloadSelectedItem(recordId)
}

async function publishContent() {
  if (!selectedId.value || !activeLocaleId.value) return
  if (props.resource !== 'faqs') {
    await transitionContentPublication('published')
    return
  }
  const recordId = selectedId.value
  await api.request(
    `/authority/${props.resource}/${recordId}/translations/${activeLocaleId.value}/publish`,
    {
      method: 'POST',
    },
  )
  await reloadSelectedItem(recordId)
}

/**
 * 按服务端状态机转换当前语言的页面发布状态。
 *
 * 输入：targetStatus，目标发布状态，仅允许恢复草稿、送审、发布或撤回。
 * 输出：Promise<void>，转换完成后重新读取该实体的真实生命周期。
 */
async function transitionContentPublication(
  targetStatus: 'draft' | 'review' | 'published' | 'archived',
) {
  if (!selectedId.value || !activeLocaleId.value || props.resource === 'faqs') return
  const recordId = selectedId.value
  await api.request(
    `/authority/${props.resource}/${recordId}/publications/${activeLocaleId.value}/${targetStatus}`,
    {
      method: 'POST',
    },
  )
  await reloadSelectedItem(recordId)
}

/**
 * 撤回当前语言的独立页面发布。
 *
 * 输入：无，使用当前实体和语言选择。
 * 输出：Promise<void>，后端完成 archived 转换后重新读取生命周期状态。
 */
async function archivePublication() {
  await transitionContentPublication('archived')
}

const activeLifecycle = computed(() => ({
  translation: translationStatuses.value.find((row) => row.locale_id === activeLocaleId.value),
  publication: publications.value.find((row) => row.locale_id === activeLocaleId.value),
  route: routes.value.find((row) => row.locale_id === activeLocaleId.value),
}))

/**
 * 切换发现层语言并重新回读，未保存修改时先给出明确提醒。
 *
 * 输入：浏览器 select change 事件。
 * 输出：Promise<void>，取消切换时恢复原选择；确认后读取新语言文档。
 */
async function changeDiscoveryLocale(event: Event): Promise<void> {
  const selectElement = event.target as HTMLSelectElement
  const nextLocaleId = selectElement.value
  const previousLocaleId = activeLocaleId.value
  if (nextLocaleId === previousLocaleId) return
  if (!confirmDiscardChanges()) {
    selectElement.value = previousLocaleId
    return
  }
  activeLocaleId.value = nextLocaleId
  const selectedItem = items.value.find((item) => item.id === selectedId.value)
  if (selectedItem) await editItem(selectedItem, true)
}

/** 浏览器关闭或刷新时阻止静默丢失未保存内容。 */
function warnBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => confirmDiscardChanges())
// 语言变化时先清空发现层表单；随后由当前记录的 fresh GET 回填，避免中英文串线。
watch(activeLocaleId, () => {
  seo.value = emptySeoDraft()
  geo.value = emptyGeoDraft()
  geoVisibleSourceText.value = ''
  source.value = { title: '', url: '', publisher: '', source_type: 'official' }
})
watch(searchTerm, () => {
  page.value = 1
})
onMounted(() => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  void load()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload))
</script>

<template>
  <main class="admin-shell authority-page">
    <!-- 中文运营界面：列表、编辑状态和表单分组均与底层字段代码解耦。 -->
    <header class="authority-heading">
      <div>
        <p>内容运营</p>
        <h1>{{ resourceCopy.title }}</h1>
        <span>{{ resourceCopy.description }}</span>
      </div>
      <button type="button" @click="startCreate">新建{{ resourceCopy.singular }}</button>
    </header>

    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" class="success-message" role="status">
      {{ successMessage }}
    </p>

    <section class="authority-workspace">
      <aside class="authority-records" aria-label="内容列表">
        <label class="authority-search">
          <span>搜索标题或编号</span>
          <input v-model="searchTerm" type="search" placeholder="输入中文标题、英语标题或 slug" />
        </label>
        <p v-if="initialLoading" class="authority-state" role="status">正在加载内容列表…</p>
        <p v-else-if="!items.length" class="authority-state">目前没有内容，可点击右上角新建。</p>
        <p v-else-if="!filteredItems.length" class="authority-state">
          没有符合当前筛选条件的内容。
        </p>
        <div v-else class="record-list authority-record-list">
          <button
            v-for="item in paginatedItems"
            :key="item.id"
            type="button"
            :class="{
              'record-list__item--selected': selectedId === item.id,
              'record-list__item--loading': loadingRecordId === item.id,
            }"
            @click="editItem(item)"
          >
            <span class="authority-record-list__heading">
              <strong>{{ authorityLabel(item) }}</strong>
              <em>{{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}</em>
            </span>
            <small v-if="item.display_title_en && item.display_title_en !== item.display_title">
              {{ item.display_title_en }}
            </small>
            <span class="authority-record-list__meta">
              <code>{{ item.slug || `FAQ-${item.sort_order + 1}` }}</code>
              <span>{{ item.translation_count || 0 }}/{{ locales.length }} 种语言</span>
            </span>
            <time v-if="item.updated_at">{{ formatBeijingTime(item.updated_at) }}</time>
          </button>
        </div>
        <nav
          v-if="filteredItems.length > pageSize"
          class="authority-pagination"
          aria-label="列表分页"
        >
          <button type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
          <span>第 {{ page }} / {{ pageCount }} 页</span>
          <button type="button" :disabled="page >= pageCount" @click="page += 1">下一页</button>
        </nav>
      </aside>

      <section v-if="editorMode === 'none'" class="authority-empty-editor">
        <span aria-hidden="true">＋</span>
        <h2>尚未选择内容</h2>
        <p>请选择左侧记录，或新建内容。</p>
      </section>

      <div v-else class="authority-editor">
        <header class="authority-editor__heading">
          <div>
            <p>{{ editorMode === 'create' ? '新建内容' : '编辑已有内容' }}</p>
            <h2>
              {{
                editorMode === 'create'
                  ? `新建${resourceCopy.singular}`
                  : authorityLabel(
                      items.find((item) => item.id === selectedId) || {
                        id: selectedId,
                        status: form.status,
                        sort_order: form.sort_order,
                      },
                    )
              }}
            </h2>
          </div>
          <span v-if="isDirty" class="authority-dirty">有未保存的修改</span>
        </header>

        <p v-if="loadingRecordId" class="authority-editor-loading" role="status">
          正在读取记录，正文返回后才可编辑…
        </p>

        <form
          class="authority-form"
          :aria-busy="Boolean(loadingRecordId) || saving"
          @submit.prevent="save"
        >
          <fieldset class="form-section">
            <legend>基本信息</legend>
            <div class="form-grid">
              <label v-if="resource !== 'faqs'">
                <span>固定地址标识（slug）</span>
                <input v-model="form.slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" />
                <small>只使用小写字母、数字和连字符；不会自动翻译。</small>
              </label>
              <label>
                <span>启用状态</span>
                <select v-model="form.status">
                  <option value="enabled">启用</option>
                  <option value="disabled">停用</option>
                  <option value="retired">已退役</option>
                </select>
              </label>
              <label>
                <span>排序</span>
                <input v-model.number="form.sort_order" type="number" />
              </label>
              <label v-if="resource === 'cases' || resource === 'knowledge'" class="checkbox-label">
                <input v-model="form.featured" type="checkbox" /> 设为推荐内容
              </label>
            </div>
          </fieldset>

          <fieldset v-if="resource === 'cases'" class="form-section">
            <legend>案例与设备信息</legend>
            <div class="form-grid form-grid--three">
              <label><span>行业</span><input v-model="form.industry" /></label>
              <label
                ><span>国家或地区代码</span><input v-model="form.country_code" maxlength="2"
              /></label>
              <label><span>设备品牌</span><input v-model="form.machine_brand" /></label>
              <label><span>设备型号</span><input v-model="form.machine_model" /></label>
              <label><span>螺杆直径</span><input v-model="form.screw_diameter" /></label>
              <label><span>填充比例</span><input v-model="form.filler_percentage" /></label>
              <label class="form-grid__wide"
                ><span>加工材料说明</span
                ><textarea v-model="form.processed_material_text" rows="3" />
              </label>
            </div>
          </fieldset>

          <fieldset v-if="resource === 'cases'" class="form-section form-section--private">
            <legend>客户隐私信息</legend>
            <p>以下信息默认仅后台可见。只有取得真实公开许可后，才可开启对应公开项。</p>
            <div class="form-grid">
              <label><span>客户名称</span><input v-model="form.client_name" /></label>
              <label
                ><span>客户地址</span><textarea v-model="form.client_address" rows="2" />
              </label>
              <label>
                <span>客户 Logo 媒体</span>
                <select v-model="form.client_logo_media_id">
                  <option value="">未选择客户 Logo</option>
                  <option
                    v-for="asset in media.filter((item) => item.type === 'image')"
                    :key="asset.id"
                    :value="asset.id"
                  >
                    {{ asset.filename }}
                  </option>
                </select>
              </label>
              <div class="checkbox-stack">
                <label
                  ><input v-model="form.client_name_public" type="checkbox" />
                  已获客户名称公开许可</label
                >
                <label
                  ><input v-model="form.client_address_public" type="checkbox" />
                  已获客户地址公开许可</label
                >
                <label
                  ><input v-model="form.client_logo_public" type="checkbox" /> 已获客户 Logo
                  公开许可</label
                >
              </div>
            </div>
          </fieldset>

          <fieldset v-if="resource === 'knowledge'" class="form-section">
            <legend>文章归属</legend>
            <div class="form-grid form-grid--three">
              <label>
                <span>文章分类</span>
                <select v-model="form.category_id" required>
                  <option value="" disabled>请选择分类</option>
                  <option v-for="category in categories" :key="category.id" :value="category.id">
                    {{ authorityLabel(category) }}
                  </option>
                </select>
              </label>
              <label>
                <span>作者</span>
                <select v-model="form.author_id" required>
                  <option value="" disabled>请选择作者</option>
                  <option v-for="expert in experts" :key="expert.id" :value="expert.id">
                    {{ authorityLabel(expert) }}
                  </option>
                </select>
              </label>
              <label>
                <span>复核人</span>
                <select v-model="form.reviewer_id">
                  <option value="">尚未指定</option>
                  <option v-for="expert in experts" :key="expert.id" :value="expert.id">
                    {{ authorityLabel(expert) }}
                  </option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset v-if="resource === 'experts'" class="form-section">
            <legend>身份与公开设置</legend>
            <div class="form-grid">
              <label>
                <span>身份类型</span>
                <select v-model="form.role_type">
                  <option
                    v-for="(roleLabel, roleCode) in ROLE_TYPE_LABELS"
                    :key="roleCode"
                    :value="roleCode"
                  >
                    {{ roleLabel }}
                  </option>
                </select>
              </label>
              <label><span>公开邮箱</span><input v-model="form.public_email" type="email" /></label>
              <label
                ><span>从业年限</span
                ><input v-model.number="form.years_experience" type="number" min="0"
              /></label>
              <label
                ><span>LinkedIn 地址</span><input v-model="form.linkedin_url" type="url"
              /></label>
              <div class="checkbox-stack">
                <label
                  ><input v-model="form.is_real_person_verified" type="checkbox" />
                  已核验为真实人物</label
                >
                <label
                  ><input v-model="form.public_profile_enabled" type="checkbox" />
                  允许公开个人资料页</label
                >
              </div>
            </div>
            <p class="form-note">演示编辑组织保持“未核验”；此界面不会自动伪造核验身份。</p>
          </fieldset>

          <fieldset class="form-section form-section--content">
            <legend>内容编辑</legend>
            <div
              v-for="translation in form.translations"
              :key="translation.locale_id"
              class="translation-panel"
            >
              <header>
                <strong>{{ localeLabel(translation.code) }}</strong>
                <code>{{ translation.code }}</code>
              </header>
              <label v-for="field in translationFields" :key="field">
                <span>{{ fieldLabel(field) }}</span>
                <input
                  v-if="['title', 'question', 'name', 'job_title'].includes(field)"
                  v-model="translation.fields[field]"
                />
                <textarea
                  v-else
                  v-model="translation.fields[field]"
                  :rows="
                    field === 'body_markdown'
                      ? 12
                      : field === 'summary' || field === 'short_bio'
                        ? 3
                        : 5
                  "
                />
                <small>{{ field }}</small>
                <section
                  v-if="field === 'body_markdown'"
                  class="markdown-preview"
                  aria-label="正文预览"
                >
                  <strong>正文预览</strong>
                  <p>
                    {{ translation.fields[field] || '正文为空，保存前请补充内容。' }}
                  </p>
                </section>
              </label>
            </div>
          </fieldset>

          <fieldset v-if="hasRelations" class="form-section">
            <legend>相关内容</legend>
            <div class="form-grid form-grid--three">
              <label v-for="relationKey in Object.keys(relationSources)" :key="relationKey">
                <span>{{ relationSourceLabel(relationKey) }}</span>
                <select v-model="relationIds[relationKey]" multiple>
                  <option
                    v-for="option in relationOptions[relationKey] || []"
                    :key="option.id"
                    :value="option.id"
                  >
                    {{ relationLabel(option) }}
                  </option>
                </select>
              </label>
            </div>
            <small>按住 Ctrl / Command 可多选；系统在内部保存关系 ID，员工无需录入 UUID。</small>
          </fieldset>

          <footer class="authority-form-actions">
            <button type="submit" :disabled="saving || Boolean(loadingRecordId)">
              {{ saving ? '正在保存…' : editorMode === 'create' ? '创建并回读' : '保存修改' }}
            </button>
            <button type="button" class="button-secondary" @click="startCreate">取消并新建</button>
            <button v-if="selectedId" type="button" class="danger" @click="archiveSelected">
              归档
            </button>
          </footer>
        </form>

        <details v-if="selectedId" class="authority-secondary-panel">
          <summary>搜索与答案优化</summary>
          <label class="discovery-locale">
            <span>编辑语言</span>
            <select :value="activeLocaleId" @change="changeDiscoveryLocale">
              <option v-for="locale in locales" :key="locale.id" :value="locale.id">
                {{ locale.native_name }}
              </option>
            </select>
          </label>
          <SeoEditor v-model="seo" @save="saveSeo" />
          <GeoEditor
            v-model="geo"
            :reviewers="expertOptions"
            :server-visible-source-text="geoVisibleSourceText"
            @save="saveGeo"
          />
          <SourceCitationEditor v-model="source" @save="saveSource" />
        </details>

        <details v-if="selectedId" class="authority-secondary-panel" open>
          <summary>发布与历史</summary>
          <div class="lifecycle-summary">
            <p>
              <span>翻译状态</span
              ><strong>{{
                labelFrom(
                  TRANSLATION_STATUS_LABELS,
                  activeLifecycle.translation?.status,
                  '缺少译文',
                )
              }}</strong>
            </p>
            <p>
              <span>发布状态</span
              ><strong>{{
                labelFrom(PUBLICATION_STATUS_LABELS, activeLifecycle.publication?.status, '不适用')
              }}</strong>
            </p>
            <p>
              <span>页面路由</span><code>{{ activeLifecycle.route?.path || '不适用' }}</code>
            </p>
            <p>
              <span>路由可见性</span
              ><strong
                >{{ activeLifecycle.route?.active ? '已启用' : '已关闭' }} ·
                {{ activeLifecycle.route?.indexable ? '可索引' : '不可索引' }}</strong
              >
            </p>
          </div>
          <div class="lifecycle-actions">
            <button
              v-if="
                !['human_reviewed', 'published'].includes(
                  activeLifecycle.translation?.status || 'missing',
                )
              "
              type="button"
              @click="reviewTranslation"
            >
              标记为已人工审核
            </button>
            <button
              v-if="resource === 'faqs' && activeLifecycle.translation?.status !== 'published'"
              type="button"
              @click="publishContent"
            >
              发布答案
            </button>
            <button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'archived'"
              type="button"
              @click="transitionContentPublication('draft')"
            >
              恢复为草稿
            </button>
            <button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'draft'"
              type="button"
              @click="transitionContentPublication('review')"
            >
              提交审核
            </button>
            <button
              v-if="
                resource !== 'faqs' &&
                ['review', 'scheduled'].includes(activeLifecycle.publication?.status || '')
              "
              type="button"
              @click="publishContent"
            >
              发布
            </button>
            <button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'published'"
              type="button"
              class="danger"
              @click="archivePublication"
            >
              撤回发布
            </button>
          </div>
        </details>
      </div>
    </section>

    <!-- 旧版模板保留一轮作为字段覆盖核对基线，但不再渲染给员工。 -->
    <template v-if="false">
      <section>
        <header class="page-heading">
          <div>
            <h1>{{ title }}</h1>
            <p>结构化内容、发布和搜索信息。</p>
          </div>
          <button type="button" @click="resetForm()">新建</button>
        </header>
        <p v-if="errorMessage" class="error-message" role="alert">
          {{ errorMessage }}
        </p>
        <div class="catalog-grid">
          <div class="record-list">
            <button
              v-for="item in items"
              :key="item.id"
              type="button"
              :class="{
                'record-list__item--selected': selectedId === item.id,
                'record-list__item--loading': loadingRecordId === item.id,
              }"
              @click="editItem(item)"
            >
              <strong>{{ authorityLabel(item) }}</strong
              ><span>{{ loadingRecordId === item.id ? '正在读取…' : item.status }}</span>
            </button>
          </div>
          <form
            class="editor-form authority-editor-form"
            :aria-busy="Boolean(loadingRecordId)"
            @submit.prevent="save"
          >
            <p v-if="loadingRecordId" class="authority-editor-loading" role="status">
              正在读取记录，正文返回后才可编辑…
            </p>
            <label v-if="resource !== 'faqs'"
              >Slug <input v-model="form.slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            /></label>
            <label
              >Status
              <select v-model="form.status">
                <option>enabled</option>
                <option>disabled</option>
                <option>retired</option>
              </select></label
            >
            <label>Sort order <input v-model.number="form.sort_order" type="number" /></label>
            <template v-if="resource === 'cases'">
              <label>Industry <input v-model="form.industry" /></label
              ><label>Country code <input v-model="form.country_code" maxlength="2" /></label>
              <label>Machine brand <input v-model="form.machine_brand" /></label
              ><label>Machine model <input v-model="form.machine_model" /></label>
              <label>Screw diameter <input v-model="form.screw_diameter" /></label
              ><label
                >Processed material
                <textarea v-model="form.processed_material_text" />
              </label>
              <fieldset>
                <legend>Private client identity and explicit consent</legend>
                <label>Client name <input v-model="form.client_name" /></label
                ><label>Client address <textarea v-model="form.client_address" /></label
                ><label
                  >Client logo media
                  <select v-model="form.client_logo_media_id">
                    <option value="">No client logo</option>
                    <option
                      v-for="asset in media.filter((item) => item.type === 'image')"
                      :key="asset.id"
                      :value="asset.id"
                    >
                      {{ asset.filename }}
                    </option>
                  </select> </label
                ><label
                  ><input v-model="form.client_name_public" type="checkbox" />
                  client_name_public</label
                ><label
                  ><input v-model="form.client_address_public" type="checkbox" />
                  client_address_public</label
                ><label
                  ><input v-model="form.client_logo_public" type="checkbox" />
                  client_logo_public</label
                >
              </fieldset>
            </template>
            <template v-if="resource === 'knowledge'">
              <label
                >Category
                <select v-model="form.category_id" required>
                  <option v-for="category in categories" :key="category.id" :value="category.id">
                    {{ category.slug }}
                  </option>
                </select></label
              >
              <label
                >Real author
                <select v-model="form.author_id" required>
                  <option v-for="expert in experts" :key="expert.id" :value="expert.id">
                    {{ expert.slug }}
                  </option>
                </select></label
              >
              <label
                >Reviewer
                <select v-model="form.reviewer_id">
                  <option value="">None</option>
                  <option v-for="expert in experts" :key="expert.id" :value="expert.id">
                    {{ expert.slug }}
                  </option>
                </select></label
              >
            </template>
            <template v-if="resource === 'experts'">
              <label
                >Role type
                <select v-model="form.role_type">
                  <option>author</option>
                  <option>expert</option>
                  <option>author_expert</option>
                </select></label
              >
              <label
                ><input v-model="form.is_real_person_verified" type="checkbox" />
                is_real_person_verified</label
              >
              <label
                ><input v-model="form.public_profile_enabled" type="checkbox" />
                public_profile_enabled</label
              >
              <label>Public email <input v-model="form.public_email" type="email" /></label
              ><label
                >Years experience
                <input v-model.number="form.years_experience" type="number" min="0" /></label
              ><label>LinkedIn URL <input v-model="form.linkedin_url" type="url" /></label>
            </template>
            <fieldset
              v-for="translation in form.translations"
              :key="translation.locale_id"
              class="translation-fields"
            >
              <legend>{{ translation.code }}</legend>
              <label v-for="field in translationFields" :key="field"
                >{{ field }}<textarea v-model="translation.fields[field]" />
              </label>
            </fieldset>
            <fieldset v-if="hasRelations">
              <legend>内容关系</legend>
              <label v-for="source in Object.keys(relationSources)" :key="source">
                {{ relationSourceLabel(source) }}
                <select v-model="relationIds[source]" multiple>
                  <option
                    v-for="option in relationOptions[source] || []"
                    :key="option.id"
                    :value="option.id"
                  >
                    {{ relationLabel(option) }}
                  </option>
                </select>
              </label>
              <small>按住 Ctrl / Command 可多选；后台仅显示可读名称，关联ID由表单内部提交。</small>
            </fieldset>
            <div class="form-actions">
              <button type="submit">
                {{ selectedId ? 'Save changes' : 'Create' }}</button
              ><button v-if="selectedId" type="button" class="danger" @click="archiveSelected">
                Archive
              </button>
            </div>
          </form>
        </div>
        <section v-if="selectedId" class="sub-editor">
          <label
            >Discovery locale
            <select v-model="activeLocaleId">
              <option v-for="locale in locales" :key="locale.id" :value="locale.id">
                {{ locale.native_name }}
              </option>
            </select></label
          >
          <!-- 生命周期状态只展示并调用统一后端事务，不在前端复制权限或发布规则。 -->
          <fieldset class="lifecycle-status">
            <legend>Publication lifecycle</legend>
            <p>
              Translation:
              {{ activeLifecycle.translation?.status || 'missing' }}
            </p>
            <p>
              Publication:
              {{ activeLifecycle.publication?.status || 'not applicable' }}
            </p>
            <p>
              Route: {{ activeLifecycle.route?.path || 'not applicable' }} · active={{
                activeLifecycle.route?.active ?? false
              }}
              · indexable={{ activeLifecycle.route?.indexable ?? false }}
            </p>
            <button
              v-if="
                !['human_reviewed', 'published'].includes(
                  activeLifecycle.translation?.status || 'missing',
                )
              "
              type="button"
              @click="reviewTranslation"
            >
              Mark human reviewed</button
            ><button
              v-if="resource === 'faqs' && activeLifecycle.translation?.status !== 'published'"
              type="button"
              @click="publishContent"
            >
              Publish answer</button
            ><button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'archived'"
              type="button"
              @click="transitionContentPublication('draft')"
            >
              Restore draft</button
            ><button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'draft'"
              type="button"
              @click="transitionContentPublication('review')"
            >
              Submit for review</button
            ><button
              v-if="
                resource !== 'faqs' &&
                (activeLifecycle.publication?.status === 'review' ||
                  activeLifecycle.publication?.status === 'scheduled')
              "
              type="button"
              @click="publishContent"
            >
              Publish</button
            ><button
              v-if="resource !== 'faqs' && activeLifecycle.publication?.status === 'published'"
              type="button"
              class="danger"
              @click="archivePublication"
            >
              Withdraw publication
            </button>
          </fieldset>
          <SeoEditor v-model="seo" @save="saveSeo" /><GeoEditor
            v-model="geo"
            :reviewers="expertOptions"
            :server-visible-source-text="geoVisibleSourceText"
            @save="saveGeo"
          /><SourceCitationEditor v-model="source" @save="saveSource" />
        </section>
      </section>
    </template>
  </main>
</template>

<style scoped>
.record-list button.record-list__item--selected {
  color: #103e63;
  background: #e8f4fd;
  border-color: #70afe0;
}
.record-list button.record-list__item--loading {
  cursor: progress;
}
.authority-editor-form {
  position: relative;
}
.authority-editor-loading {
  position: sticky;
  z-index: 2;
  top: 0;
  margin: 0;
  padding: 0.75rem 0.9rem;
  color: #0b5f9f;
  background: #e7f5ff;
  border: 1px solid #a8d5f2;
  border-radius: 0.55rem;
}
.authority-editor-form[aria-busy='true'] > :not(.authority-editor-loading) {
  pointer-events: none;
  opacity: 0.42;
}
.authority-page {
  display: grid;
  align-content: start;
  gap: 1rem;
}
.authority-heading,
.authority-editor__heading,
.authority-record-list__heading,
.authority-record-list__meta,
.authority-form-actions,
.lifecycle-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}
.authority-heading {
  padding: 1.25rem 1.4rem;
  color: #dceaf6;
  background: linear-gradient(112deg, #07192c, #0c558d);
  border-radius: 0.9rem;
}
.authority-heading p,
.authority-heading h1,
.authority-editor__heading p,
.authority-editor__heading h2 {
  margin: 0;
}
.authority-heading p,
.authority-editor__heading p {
  color: #65c1f2;
  font-size: 0.67rem;
  font-weight: 850;
  letter-spacing: 0.12em;
}
.authority-heading h1 {
  color: #fff;
  font-size: clamp(1.45rem, 2.6vw, 2.1rem);
}
.authority-heading span {
  display: block;
  margin-top: 0.3rem;
  font-size: 0.78rem;
}
.authority-workspace {
  display: grid;
  grid-template-columns: minmax(16rem, 0.64fr) minmax(0, 1.8fr);
  gap: 1rem;
  align-items: start;
}
.authority-records,
.authority-editor,
.authority-empty-editor {
  min-width: 0;
  background: #fff;
  border: 1px solid #d9e3ec;
  border-radius: 0.8rem;
}
.authority-records {
  position: sticky;
  top: 1rem;
  padding: 0.9rem;
}
.authority-search {
  display: grid;
  gap: 0.35rem;
  color: #4b6176;
  font-size: 0.74rem;
}
.authority-record-list {
  margin-top: 0.8rem;
  display: grid;
  gap: 0.45rem;
}
.authority-record-list > button {
  padding: 0.75rem;
  display: grid;
  gap: 0.35rem;
  text-align: left;
}
.authority-record-list__heading strong {
  overflow: hidden;
  text-overflow: ellipsis;
}
.authority-record-list__heading em {
  padding: 0.18rem 0.45rem;
  flex: 0 0 auto;
  color: #17633a;
  font-size: 0.65rem;
  font-style: normal;
  background: #e7f5eb;
  border-radius: 999px;
}
.authority-record-list small,
.authority-record-list time,
.authority-record-list__meta {
  color: #718293;
  font-size: 0.68rem;
}
.authority-record-list__meta code {
  overflow: hidden;
  max-width: 65%;
  text-overflow: ellipsis;
}
.authority-state,
.authority-empty-editor {
  padding: 1.2rem;
  color: #667a8c;
}
.authority-empty-editor {
  min-height: 20rem;
  display: grid;
  place-content: center;
  text-align: center;
}
.authority-empty-editor > span {
  color: #1787d1;
  font-size: 2rem;
}
.authority-empty-editor h2,
.authority-empty-editor p {
  margin: 0.25rem;
}
.authority-pagination {
  margin-top: 0.8rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  color: #687c8d;
  font-size: 0.68rem;
}
.authority-pagination button {
  padding: 0.42rem 0.65rem;
}
.authority-editor {
  overflow: hidden;
}
.authority-editor__heading {
  padding: 1rem 1.2rem;
  border-bottom: 1px solid #e2e9ef;
}
.authority-editor__heading h2 {
  margin-top: 0.2rem;
  color: #133650;
  font-size: 1.1rem;
}
.authority-dirty {
  padding: 0.28rem 0.55rem;
  color: #815b05;
  font-size: 0.68rem;
  background: #fff2c9;
  border-radius: 999px;
}
.authority-form {
  padding: 1rem 1.2rem;
  display: grid;
  gap: 1rem;
}
.authority-form[aria-busy='true'] {
  pointer-events: none;
  opacity: 0.65;
}
.form-section {
  margin: 0;
  padding: 1rem;
  border: 1px solid #dfe7ee;
  border-radius: 0.65rem;
}
.form-section > legend {
  padding-inline: 0.4rem;
  color: #153f60;
  font-weight: 800;
}
.form-section--private {
  background: #fffaf0;
  border-color: #ead5a8;
}
.form-section--private > p,
.form-note {
  color: #786643;
  font-size: 0.73rem;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}
.form-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.form-grid__wide {
  grid-column: 1 / -1;
}
.authority-form label,
.discovery-locale {
  display: grid;
  align-content: start;
  gap: 0.35rem;
  color: #40576b;
  font-size: 0.75rem;
}
.checkbox-label,
.checkbox-stack label {
  display: flex !important;
  align-items: center;
}
.checkbox-stack {
  display: grid;
  align-content: start;
  gap: 0.6rem;
}
.translation-panel {
  padding: 0.9rem;
  display: grid;
  gap: 0.75rem;
  background: #f6f9fb;
  border: 1px solid #e0e8ef;
  border-radius: 0.55rem;
}
.translation-panel + .translation-panel {
  margin-top: 0.8rem;
}
.translation-panel > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.translation-panel label > small {
  color: #91a0ad;
  font-family: monospace;
}
.markdown-preview {
  max-height: 16rem;
  padding: 0.8rem;
  overflow: auto;
  color: #385369;
  white-space: pre-wrap;
  background: #fff;
  border-left: 3px solid #1688d2;
}
.markdown-preview p {
  margin-bottom: 0;
}
.authority-form-actions {
  justify-content: flex-start;
  flex-wrap: wrap;
}
.button-secondary {
  color: #15486d;
  background: #eaf3f9;
}
.authority-secondary-panel {
  margin: 0 1.2rem 1rem;
  padding: 0.8rem 1rem;
  border: 1px solid #dce5ec;
  border-radius: 0.65rem;
}
.authority-secondary-panel > summary {
  color: #173f5d;
  font-weight: 800;
  cursor: pointer;
}
.discovery-locale {
  margin-block: 1rem;
}
.lifecycle-summary {
  margin-top: 0.8rem;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.6rem;
}
.lifecycle-summary p {
  margin: 0;
  padding: 0.7rem;
  display: grid;
  gap: 0.25rem;
  background: #f4f8fb;
}
.lifecycle-summary span {
  color: #708395;
  font-size: 0.68rem;
}
.lifecycle-actions {
  margin-top: 0.8rem;
  justify-content: flex-start;
  flex-wrap: wrap;
}
.success-message {
  margin: 0;
  padding: 0.75rem 0.9rem;
  color: #176036;
  background: #e8f6ed;
  border: 1px solid #b9dfc5;
  border-radius: 0.55rem;
}
@media (max-width: 70rem) {
  .authority-workspace,
  .form-grid--three {
    grid-template-columns: minmax(0, 1fr);
  }
  .authority-records {
    position: static;
  }
}
@media (max-width: 44rem) {
  .authority-heading,
  .authority-editor__heading {
    align-items: stretch;
    flex-direction: column;
  }
  .form-grid,
  .lifecycle-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
