<!-- 组件职责：为能力、设备、证书、专利、荣誉和展会提供共享的最小真实 CRUD。 -->
<script setup lang="ts">
interface TrustItem {
  id: string
  slug: string
  status: string
  sort_order: number
  translations?: Array<Record<string, unknown>>
  translation_statuses?: Array<{ locale_id: string; status: string }>
  publications?: Array<{ locale_id: string; status: string }>
  [key: string]: unknown
}

const props = defineProps<{ title: string; resource: string }>()
const api = useAuthorityApi()
const hasIndependentRoute = computed(() => ['capabilities', 'exhibitions'].includes(props.resource))
const items = ref<TrustItem[]>([])
const editingId = ref<string | null>(null)
const slug = ref('')
const status = ref('enabled')
const sortOrder = ref(0)
const fieldsJson = ref('{}')
const translationsJson = ref('[]')
const errorMessage = ref('')

// 读取当前 Trust 家族的真实数据库记录。
async function load() {
  const result = await api.list<TrustItem>(`/trust/${props.resource}`)
  items.value = result.items
}

function resetForm() {
  editingId.value = null
  slug.value = ''
  status.value = 'enabled'
  sortOrder.value = 0
  fieldsJson.value = '{}'
  translationsJson.value = '[]'
}

function edit(item: TrustItem) {
  editingId.value = item.id
  slug.value = item.slug
  status.value = item.status
  sortOrder.value = item.sort_order
  const masterFields = Object.fromEntries(
    Object.entries(item).filter(
      ([key]) =>
        ![
          'id',
          'slug',
          'status',
          'sort_order',
          'translations',
          'created_at',
          'updated_at',
        ].includes(key),
    ),
  )
  fieldsJson.value = JSON.stringify(masterFields, null, 2)
  translationsJson.value = JSON.stringify(
    (item.translations || []).map((translation) => ({
      locale_id: translation.locale_id,
      fields: Object.fromEntries(
        Object.entries(translation).filter(
          ([key]) =>
            ![
              'id',
              'locale_id',
              'created_at',
              'updated_at',
              `${props.resource.replace(/s$/, '')}_id`,
              'capability_id',
            ].includes(key),
        ),
      ),
    })),
    null,
    2,
  )
}

// JSON 编辑区保留结构化字段，不把不同 Trust 类型重新塞进单一富文本。
async function save() {
  errorMessage.value = ''
  try {
    const body = {
      slug: slug.value,
      status: status.value,
      sort_order: sortOrder.value,
      fields: JSON.parse(fieldsJson.value || '{}') as Record<string, unknown>,
      translations: JSON.parse(translationsJson.value || '[]') as Array<Record<string, unknown>>,
    }
    if (editingId.value) await api.update(`/trust/${props.resource}/${editingId.value}`, body)
    else await api.create(`/trust/${props.resource}`, body)
    resetForm()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save Trust content.'
  }
}

async function archiveEntity(item: TrustItem) {
  await api.update(`/trust/${props.resource}/${item.id}`, { slug: item.slug, status: 'retired' })
  await load()
}

function publicationStatus(item: TrustItem, localeId: string) {
  return (
    item.publications?.find((publication) => publication.locale_id === localeId)?.status || 'draft'
  )
}

// 审核、发布和归档均调用后端统一生命周期 API；前端按钮不承担权限判定。
async function reviewTranslation(item: TrustItem, localeId: string) {
  await api.archive(`/trust/${props.resource}/${item.id}/translations/${localeId}/review`)
  await load()
}

// Non-route Trust 只发布 TranslationStatus，不创建 ContentPublication 或 ContentRoute。
async function publishTranslation(item: TrustItem, localeId: string) {
  await api.archive(`/trust/${props.resource}/${item.id}/translations/${localeId}/publish`)
  await load()
}

async function transitionPublication(
  item: TrustItem,
  localeId: string,
  status: 'published' | 'archived',
) {
  await api.archive(`/trust/${props.resource}/${item.id}/publications/${localeId}/${status}`)
  await load()
}

onMounted(load)
</script>

<template>
  <main class="admin-shell">
    <h1>{{ title }}</h1>
    <form @submit.prevent="save">
      <label>Slug <input v-model="slug" required pattern="[a-z0-9-]+" /></label>
      <label
        >Status
        <select v-model="status">
          <option>enabled</option>
          <option>disabled</option>
          <option>retired</option>
        </select></label
      >
      <label>Sort order <input v-model.number="sortOrder" type="number" /></label>
      <label>Structured master fields <textarea v-model="fieldsJson" rows="8" /></label>
      <label
        >Translations (locale_id + fields) <textarea v-model="translationsJson" rows="10" />
      </label>
      <button type="submit">{{ editingId ? 'Update' : 'Create' }}</button>
      <button v-if="editingId" type="button" @click="resetForm">Cancel</button>
    </form>
    <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    <table>
      <thead>
        <tr>
          <th>Slug</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.slug }}</td>
          <td>{{ item.status }}</td>
          <td>
            <button type="button" @click="edit(item)">Edit</button
            ><button type="button" @click="archiveEntity(item)">Archive entity</button>
            <div
              v-for="translationStatus in item.translation_statuses || []"
              :key="translationStatus.locale_id"
            >
              <span>
                {{ translationStatus.locale_id }} · translation {{ translationStatus.status }}
                <template v-if="hasIndependentRoute">
                  · publication {{ publicationStatus(item, translationStatus.locale_id) }}
                </template>
              </span>
              <button
                v-if="translationStatus.status === 'draft'"
                type="button"
                @click="reviewTranslation(item, translationStatus.locale_id)"
              >
                Review
              </button>
              <button
                v-if="
                  hasIndependentRoute &&
                  publicationStatus(item, translationStatus.locale_id) === 'review'
                "
                type="button"
                @click="transitionPublication(item, translationStatus.locale_id, 'published')"
              >
                Publish
              </button>
              <button
                v-if="!hasIndependentRoute && translationStatus.status === 'human_reviewed'"
                type="button"
                @click="publishTranslation(item, translationStatus.locale_id)"
              >
                Publish translation
              </button>
              <button
                v-if="
                  hasIndependentRoute &&
                  publicationStatus(item, translationStatus.locale_id) === 'published'
                "
                type="button"
                @click="transitionPublication(item, translationStatus.locale_id, 'archived')"
              >
                Archive publication
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </main>
</template>
