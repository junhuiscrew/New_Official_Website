<!-- 组件职责：为 Material / Technology / Application / Solution 提供最小真实 CRUD。 -->
<script setup lang="ts">
import TranslationFields from '~/components/catalog/TranslationFields.vue'
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'
import { ENTITY_STATUS_LABELS, labelFrom } from '~/utils/adminZhCn'

interface EntityItem {
  id: string
  slug: string
  display_name?: string
  display_name_en?: string
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
const loading = ref(true)
const successMessage = ref('')
const form = reactive({
  slug: '',
  status: 'enabled',
  featured: false,
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})

async function load() {
  loading.value = true
  try {
    const [result, localeItems] = await Promise.all([
      api.list<EntityItem>(`/catalog/${props.resource}`),
      api.detail<LocaleItem[]>('/locales'),
    ])
    items.value = result.items
    locales.value = localeItems
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取内容记录。'
  } finally {
    loading.value = false
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
    errorMessage.value = error instanceof Error ? error.message : '无法读取内容详情。'
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
    successMessage.value = '已保存并从接口重新读取。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法保存内容记录。'
  }
}

async function archiveItem(item: EntityItem) {
  try {
    await api.archive(`/catalog/${props.resource}/${item.id}/archive`)
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法归档内容记录。'
  }
}

/** 输入目录记录；输出优先中文、其次英文的可读名称。 */
function itemTitle(item: EntityItem): string {
  if (item.display_name) return item.display_name
  const rows = item.translations || []
  const localized =
    rows.find(
      (row) => locales.value.find((locale) => locale.id === row.locale_id)?.code === 'zh-CN',
    ) ||
    rows.find(
      (row) => locales.value.find((locale) => locale.id === row.locale_id)?.code === 'en',
    ) ||
    rows[0]
  return String(localized?.name || item.slug)
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>{{ title }}</h1>
          <p>维护结构化主记录和中英文内容；Slug 与枚举代码保持原值。</p>
        </div>
        <button type="button" @click="resetForm">新建内容</button>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">
        {{ errorMessage }}
      </p>
      <p v-if="successMessage" role="status">{{ successMessage }}</p>
      <p v-if="loading" role="status">正在读取内容…</p>
      <div class="catalog-grid">
        <div class="record-list">
          <button v-for="item in items" :key="item.id" type="button" @click="editItem(item)">
            <strong>{{ itemTitle(item) }}</strong
            ><small>{{ item.slug }}</small>
            <span>{{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}</span>
          </button>
        </div>
        <form class="editor-form" @submit.prevent="save">
          <label
            >Slug（路径标识）
            <input v-model="form.slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
          /></label>
          <label
            >状态
            <select v-model="form.status">
              <option value="enabled">启用</option>
              <option value="disabled">停用</option>
              <option value="retired">已退役</option>
            </select>
          </label>
          <label>排序 <input v-model.number="form.sort_order" type="number" /></label>
          <label><input v-model="form.featured" type="checkbox" /> 首页推荐</label>
          <TranslationFields
            v-model="form.translations"
            :locales="locales"
            :body-field="bodyField"
          />
          <div class="form-actions">
            <button type="submit">
              {{ selectedId ? '保存更改' : '创建内容' }}
            </button>
            <button
              v-if="selectedId"
              type="button"
              class="danger"
              @click="archiveItem(items.find((item) => item.id === selectedId)!)"
            >
              归档
            </button>
          </div>
        </form>
      </div>
    </section>
  </main>
</template>
