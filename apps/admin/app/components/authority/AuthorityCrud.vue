<!-- 组件职责：提供 Case、Knowledge、FAQ、真实 Expert 的最小真实 CRUD 与发现层编辑。 -->
<script setup lang="ts">
import type { GeoDraft } from '~/components/discovery/GeoEditor.vue'
import type { SeoDraft } from '~/components/discovery/SeoEditor.vue'
import type { SourceDraft } from '~/components/discovery/SourceCitationEditor.vue'

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

const props = defineProps<{ title: string; resource: AuthorityResource }>()
const api = useAuthorityApi()
const items = ref<AuthorityItem[]>([])
const locales = ref<LocaleItem[]>([])
const categories = ref<AuthorityItem[]>([])
const experts = ref<AuthorityItem[]>([])
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
const relationText = reactive({
  product_ids: '',
  material_ids: '',
  technology_ids: '',
  application_ids: '',
  solution_ids: '',
  case_ids: '',
  faq_ids: '',
  article_ids: '',
})
const seo = ref<SeoDraft>({
  seo_title: '',
  meta_description: '',
  canonical_override: '',
  robots_index: true,
  robots_follow: true,
  og_title: '',
  og_description: '',
})
const geo = ref<GeoDraft>({
  direct_answer: '',
  target_questions_json: [],
  key_facts_json: [],
  evidence_json: [],
  related_questions_json: [],
  reviewer_id: '',
  last_reviewed_at: '',
  visible_source_text: '',
})
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
  Object.keys(relationText).forEach((key) => {
    relationText[key as keyof typeof relationText] = ''
  })
  emptyTranslations()
  translationStatuses.value = []
  publications.value = []
  routes.value = []
}

async function load() {
  try {
    const [result, localeItems] = await Promise.all([
      api.list<AuthorityItem>(`/authority/${props.resource}`),
      api.detail<LocaleItem[]>('/locales'),
    ])
    items.value = result.items
    locales.value = localeItems
    activeLocaleId.value ||= localeItems[0]?.id || ''
    if (props.resource === 'knowledge') {
      const [categoryResult, expertResult] = await Promise.all([
        api.list<AuthorityItem>('/authority/knowledge-categories'),
        api.list<AuthorityItem>('/authority/experts'),
      ])
      categories.value = categoryResult.items
      experts.value = expertResult.items
    }
    resetForm()
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to load authority content.'
  }
}

async function editItem(item: AuthorityItem) {
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
    for (const key of Object.keys(relationText) as Array<keyof typeof relationText>)
      relationText[key] = (detail.relations?.[key] || []).join('\n')
    const seoDocument = detail.seo_documents?.find((row) => row.locale_id === activeLocaleId.value)
    if (seoDocument) seo.value = { ...seo.value, ...(seoDocument as unknown as SeoDraft) }
    const geoDocument = detail.geo_documents?.find((row) => row.locale_id === activeLocaleId.value)
    if (geoDocument) geo.value = { ...geo.value, ...(geoDocument as unknown as GeoDraft) }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load detail.'
  }
}

function translationsPayload() {
  return form.translations
    .map((translation) => ({
      locale_id: translation.locale_id,
      fields: Object.fromEntries(
        Object.entries(translation.fields).filter(([, value]) => value.trim()),
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
  return Object.fromEntries(
    Object.entries(relationText).map(([key, value]) => [
      key,
      value
        .split(/[\s,]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ]),
  )
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
    { ...seo.value, canonical_override: seo.value.canonical_override || null },
  )
}

async function saveGeo() {
  if (!selectedId.value || !activeLocaleId.value) return
  const result = await api.replace<{ id: string }>(
    `/discovery/geo/${ownerType.value}/${selectedId.value}/${activeLocaleId.value}`,
    {
      ...geo.value,
      reviewer_id: geo.value.reviewer_id || null,
      last_reviewed_at: geo.value.last_reviewed_at || null,
    },
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
  await api.request(
    `/authority/${props.resource}/${selectedId.value}/translations/${activeLocaleId.value}/review`,
    { method: 'POST' },
  )
  await editItem(items.value.find((item) => item.id === selectedId.value)!)
}

async function publishContent() {
  if (!selectedId.value || !activeLocaleId.value) return
  const suffix =
    props.resource === 'faqs'
      ? `translations/${activeLocaleId.value}/publish`
      : `publications/${activeLocaleId.value}/published`
  await api.request(`/authority/${props.resource}/${selectedId.value}/${suffix}`, {
    method: 'POST',
  })
  await editItem(items.value.find((item) => item.id === selectedId.value)!)
}

const activeLifecycle = computed(() => ({
  translation: translationStatuses.value.find((row) => row.locale_id === activeLocaleId.value),
  publication: publications.value.find((row) => row.locale_id === activeLocaleId.value),
  route: routes.value.find((row) => row.locale_id === activeLocaleId.value),
}))

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
            <strong>{{ item.slug || item.id }}</strong
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
              ><label>Client logo media ID <input v-model="form.client_logo_media_id" /></label
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
            <legend>Explicit relation IDs</legend>
            <label v-for="(_value, key) in relationText" :key="key"
              >{{ key
              }}<textarea v-model="relationText[key]" placeholder="One UUID per line" /></label
            ><small>Relations are explicit structured links, not hidden in rich text.</small>
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
          <button type="button" @click="reviewTranslation">Mark human reviewed</button
          ><button type="button" @click="publishContent">Publish</button>
        </fieldset>
        <SeoEditor v-model="seo" @save="saveSeo" /><GeoEditor
          v-model="geo"
          @save="saveGeo"
        /><SourceCitationEditor v-model="source" @save="saveSource" />
      </section>
    </section>
  </main>
</template>
