<!-- 组件职责：为 Material / Technology / Application / Solution 提供最小真实 CRUD。 -->
<script setup lang="ts">
import TranslationFields from '~/components/catalog/TranslationFields.vue'
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'

interface EntityItem {
  id: string
  slug: string
  status: string
  featured: boolean
  sort_order: number
  translations?: Array<Record<string, unknown>>
}

interface LocaleItem {
  id: string
  code: string
  native_name: string
}

const props = defineProps<{
  title: string
  resource: 'materials' | 'technologies' | 'applications' | 'solutions'
  bodyField: string
}>()
const api = useCatalogApi()
const items = ref<EntityItem[]>([])
const locales = ref<LocaleItem[]>([])
const selectedId = ref<string | null>(null)
const errorMessage = ref('')
const form = reactive({
  slug: '',
  status: 'enabled',
  featured: false,
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})

async function load() {
  try {
    const [result, localeItems] = await Promise.all([
      api.list<EntityItem>(`/catalog/${props.resource}`),
      api.detail<LocaleItem[]>('/locales'),
    ])
    items.value = result.items
    locales.value = localeItems
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load records.'
  }
}

function resetForm() {
  selectedId.value = null
  Object.assign(form, {
    slug: '',
    status: 'enabled',
    featured: false,
    sort_order: 0,
    translations: [],
  })
}

async function editItem(item: EntityItem) {
  try {
    const detail = await api.detail<EntityItem>(`/catalog/${props.resource}/${item.id}`)
    selectedId.value = item.id
    form.slug = detail.slug
    form.status = detail.status
    form.featured = detail.featured
    form.sort_order = detail.sort_order
    form.translations = (detail.translations || []).map((translation) => ({
      locale_id: String(translation.locale_id),
      code: locales.value.find((locale) => locale.id === translation.locale_id)?.code || '',
      name: String(translation.name || ''),
      fields: { [props.bodyField]: String(translation[props.bodyField] || '') },
    }))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load detail.'
  }
}

function translationPayload() {
  return form.translations
    .filter((translation) => translation.name.trim())
    .map(({ locale_id, name, fields }) => ({ locale_id, name, fields }))
}

async function save() {
  const body = {
    slug: form.slug,
    status: form.status,
    featured: form.featured,
    sort_order: form.sort_order,
    translations: translationPayload(),
  }
  try {
    if (selectedId.value) {
      await api.update(`/catalog/${props.resource}/${selectedId.value}`, body) // method: 'PATCH'
    } else {
      await api.create(`/catalog/${props.resource}`, body) // method: 'POST'
    }
    resetForm()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save record.'
  }
}

async function archiveItem(item: EntityItem) {
  try {
    await api.archive(`/catalog/${props.resource}/${item.id}/archive`)
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to archive record.'
  }
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>{{ title }}</h1>
          <p>Structured Core master entity and translations.</p>
        </div>
        <button type="button" @click="resetForm">New</button>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <div class="catalog-grid">
        <div class="record-list">
          <button v-for="item in items" :key="item.id" type="button" @click="editItem(item)">
            <strong>{{ item.slug }}</strong
            ><span>{{ item.status }}</span>
          </button>
        </div>
        <form class="editor-form" @submit.prevent="save">
          <label
            >Slug <input v-model="form.slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
          /></label>
          <label
            >Status
            <select v-model="form.status">
              <option>enabled</option>
              <option>disabled</option>
              <option>retired</option>
            </select>
          </label>
          <label>Sort order <input v-model.number="form.sort_order" type="number" /></label>
          <label><input v-model="form.featured" type="checkbox" /> Featured</label>
          <TranslationFields
            v-model="form.translations"
            :locales="locales"
            :body-field="bodyField"
          />
          <div class="form-actions">
            <button type="submit">{{ selectedId ? 'Save changes' : 'Create' }}</button>
            <button
              v-if="selectedId"
              type="button"
              class="danger"
              @click="archiveItem(items.find((item) => item.id === selectedId)!)"
            >
              Archive
            </button>
          </div>
        </form>
      </div>
    </section>
  </main>
</template>
