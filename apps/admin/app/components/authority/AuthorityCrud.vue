<!-- 组件职责：提供 Case、Knowledge、FAQ、真实 Expert 的最小真实 CRUD 与发现层编辑。 -->
<script setup lang="ts">
import GeoEditor, { type GeoDraft } from '~/components/discovery/GeoEditor.vue'
import SeoEditor, { type SeoDraft } from '~/components/discovery/SeoEditor.vue'
import SourceCitationEditor, {
  type SourceDraft,
} from '~/components/discovery/SourceCitationEditor.vue'

type AuthorityResource = 'cases' | 'knowledge' | 'faqs' | 'experts'
interface AuthorityItem {
  id: string
  slug?: string
  status: string
  sort_order: number
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
const activeLocaleId = ref('')
const errorMessage = ref('')
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
const source = ref<SourceDraft>({ title: '', url: '', publisher: '', source_type: 'official' })

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

function emptyTranslations() {
  form.translations = locales.value.map((locale) => ({
    locale_id: locale.id,
    code: locale.code,
    fields: Object.fromEntries(translationFields.value.map((field) => [field, ''])),
  }))
}

function resetForm() {
  selectedId.value = ''
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
  if (key !== 'faq_ids') return options
  return Promise.all(
    options.map(async (option) => {
      if (option.translations?.length) return option
      const detail = await api.detail<RelationOption>(`${source.path}/${option.id}`)
      return { ...option, translations: detail.translations || [] }
    }),
  )
}

async function load() {
  try {
    const [result, localeItems] = await Promise.all([
      api.list<AuthorityItem>(`/authority/${props.resource}`),
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
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to load authority content.'
  }
}

async function editItem(item: Pick<AuthorityItem, 'id'>) {
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
    selectedId.value = item.id
    for (const key of Object.keys(form)) {
      if (key !== 'translations' && detail[key] !== undefined && detail[key] !== null)
        (form as Record<string, unknown>)[key] = detail[key]
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
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load detail.'
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
  if (item.slug) return item.slug
  const translation = item.translations?.[0]
  return String(translation?.title || translation?.name || translation?.question || '未命名内容')
}

/** 输入内容条目；输出列表中用于识别记录的可读名称。 */
function authorityLabel(item: AuthorityItem): string {
  return relationLabel(item as RelationOption)
}

/** 输出GEO复核人下拉框所需的可读专家选项。 */
const expertOptions = computed(() =>
  experts.value.map((expert) => ({ id: expert.id, label: authorityLabel(expert) })),
)

/** 输入关系字段键；输出稳定中文标签，防止模板读取可选对象时报错。 */
function relationSourceLabel(key: string): string {
  return relationSources[key]?.label || key
}

async function save() {
  try {
    const saved = selectedId.value
      ? await api.update<AuthorityItem>(
          `/authority/${props.resource}/${selectedId.value}`,
          masterPayload(),
        )
      : await api.create<AuthorityItem>(`/authority/${props.resource}`, masterPayload())
    if (hasRelations.value)
      await api.replace(`/authority/${props.resource}/${saved.id}/relations`, relationPayload())
    await load()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to save authority content.'
  }
}

async function archiveSelected() {
  if (!selectedId.value) return
  await api.archive(`/authority/${props.resource}/${selectedId.value}/archive`)
  await load()
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
}

async function saveSource() {
  if (props.resource === 'knowledge') source.value.article_id = selectedId.value
  await api.create('/discovery/sources', { ...source.value })
  source.value = { title: '', url: '', publisher: '', source_type: 'official' }
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

// 切换发现层语言时重新从后端读取该语言的 SEO、GEO 与正文来源，避免跨语言串值。
watch(activeLocaleId, async (localeId, previousLocaleId) => {
  if (!selectedId.value || !localeId || localeId === previousLocaleId) return
  const selectedItem = items.value.find((item) => item.id === selectedId.value)
  if (selectedItem) await editItem(selectedItem)
})

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>{{ title }}</h1>
          <p>Structured authority content, publication and discovery metadata.</p>
        </div>
        <button type="button" @click="resetForm">New</button>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <div class="catalog-grid">
        <div class="record-list">
          <button v-for="item in items" :key="item.id" type="button" @click="editItem(item)">
            <strong>{{ authorityLabel(item) }}</strong
            ><span>{{ item.status }}</span>
          </button>
        </div>
        <form class="editor-form" @submit.prevent="save">
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
            ><label>Processed material <textarea v-model="form.processed_material_text" /></label>
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
            <button type="submit">{{ selectedId ? 'Save changes' : 'Create' }}</button
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
          <p>Translation: {{ activeLifecycle.translation?.status || 'missing' }}</p>
          <p>Publication: {{ activeLifecycle.publication?.status || 'not applicable' }}</p>
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
  </main>
</template>
