<!-- 页面用途：ProductCategory 树形列表、父级选择、状态排序和双语 CRUD。 -->
<script setup lang="ts">
import TranslationFields from '~/components/catalog/TranslationFields.vue'
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'
import { ENTITY_STATUS_LABELS, labelFrom } from '~/utils/adminZhCn'

interface CategoryItem {
  id: string
  parent_id: string | null
  slug: string
  display_name?: string
  display_name_en?: string
  status: string
  sort_order: number
  translations?: Array<Record<string, unknown>>
}
interface LocaleItem {
  id: string
  code: string
  native_name: string
}

useHead({
  title: '产品分类',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useCatalogApi()
const categories = ref<CategoryItem[]>([])
const locales = ref<LocaleItem[]>([])
const selectedId = ref<string | null>(null)
const errorMessage = ref('')
const form = reactive({
  parent_id: '',
  slug: '',
  status: 'enabled',
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})

async function load() {
  try {
    const [categoryResult, localeResult] = await Promise.all([
      api.list<CategoryItem>('/catalog/categories'),
      api.detail<LocaleItem[]>('/locales'),
    ])
    categories.value = categoryResult.items
    locales.value = localeResult
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取产品分类。'
  }
}

function resetForm() {
  selectedId.value = null
  Object.assign(form, {
    parent_id: '',
    slug: '',
    status: 'enabled',
    sort_order: 0,
    translations: [],
  })
}

async function editCategory(item: CategoryItem) {
  const detail = await api.detail<CategoryItem>(`/catalog/categories/${item.id}`)
  selectedId.value = item.id
  form.parent_id = detail.parent_id || ''
  form.slug = detail.slug
  form.status = detail.status
  form.sort_order = detail.sort_order
  form.translations = (detail.translations || []).map((translation) => ({
    locale_id: String(translation.locale_id),
    code: locales.value.find((locale) => locale.id === translation.locale_id)?.code || '',
    name: String(translation.name || ''),
    fields: { description: String(translation.description || '') },
  }))
}

async function saveCategory() {
  const body = {
    parent_id: form.parent_id || null,
    slug: form.slug,
    status: form.status,
    sort_order: form.sort_order,
    translations: form.translations
      .filter((item) => item.name.trim())
      .map(({ locale_id, name, fields }) => ({ locale_id, name, fields })),
  }
  try {
    if (selectedId.value) await api.update(`/catalog/categories/${selectedId.value}`, body)
    else await api.create('/catalog/categories', body)
    resetForm()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法保存产品分类。'
  }
}

/** 输入分类记录；输出优先中文的可读名称。 */
function categoryTitle(item: CategoryItem): string {
  if (item.display_name) return item.display_name
  const rows = item.translations || []
  const localized =
    rows.find(
      (row) => locales.value.find((locale) => locale.id === row.locale_id)?.code === 'zh-CN',
    ) || rows[0]
  return String(localized?.name || item.slug)
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>产品分类</h1>
          <p>维护稳定分类树和中英文名称；路径标识保持原值。</p>
        </div>
        <button type="button" @click="resetForm">新建分类</button>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">
        {{ errorMessage }}
      </p>
      <div class="catalog-grid">
        <div class="record-list">
          <button
            v-for="item in categories"
            :key="item.id"
            type="button"
            @click="editCategory(item)"
          >
            <strong>{{ categoryTitle(item) }}</strong
            ><small>{{ item.slug }}</small>
            <span>{{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}</span>
          </button>
        </div>
        <form class="editor-form" @submit.prevent="saveCategory">
          <label
            >上级分类
            <select v-model="form.parent_id">
              <option value="">顶级分类</option>
              <option
                v-for="item in categories.filter((category) => category.id !== selectedId)"
                :key="item.id"
                :value="item.id"
              >
                {{ item.slug }}
              </option>
            </select></label
          >
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
            </select></label
          >
          <label>排序 <input v-model.number="form.sort_order" type="number" /></label>
          <TranslationFields v-model="form.translations" :locales="locales" />
          <button type="submit">
            {{ selectedId ? '保存更改' : '创建分类' }}
          </button>
        </form>
      </div>
    </section>
  </main>
</template>
