<!-- 页面用途：维护规格分组、规格定义，以及产品已经确认的结构化规格值。 -->
<script setup lang="ts">
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'
import {
  buildSpecificationValuePayload,
  type SpecificationValueDraft,
  type SpecificationValueType,
} from '~/utils/specificationValue'

interface TranslationItem extends Record<string, unknown> {
  locale_id: string
  name: string
}
interface GroupItem {
  id: string
  code: string
  status: string
  sort_order: number
  translations?: TranslationItem[]
}
interface DefinitionItem extends GroupItem {
  group_id: string
  value_type: SpecificationValueType
  default_unit: string | null
  is_filterable: boolean
}
interface ProductItem {
  id: string
  code: string | null
  slug: string
  status: string
}
interface SpecificationValueItem {
  id: string
  product_id: string | null
  product_model_id: string | null
  definition_id: string
  value_text: string | null
  value_number: number | null
  value_min: number | null
  value_max: number | null
  value_boolean: boolean | null
  enum_value: string | null
  unit_override: string | null
  sort_order: number
  is_public: boolean
}
interface LocaleItem {
  id: string
  code: string
  native_name: string
}

useHead({
  title: 'Catalog Specifications',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useCatalogApi()
const groups = ref<GroupItem[]>([])
const definitions = ref<DefinitionItem[]>([])
const products = ref<ProductItem[]>([])
const values = ref<SpecificationValueItem[]>([])
const locales = ref<LocaleItem[]>([])
const selectedGroupId = ref<string | null>(null)
const selectedDefinitionId = ref<string | null>(null)
const selectedProductId = ref('')
const valueDrafts = reactive<Record<string, SpecificationValueDraft>>({})
const errorMessage = ref('')
const successMessage = ref('')

const groupForm = reactive({
  code: '',
  status: 'enabled',
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})
const definitionForm = reactive({
  group_id: '',
  code: '',
  value_type: 'text' as SpecificationValueType,
  default_unit: '',
  is_filterable: false,
  status: 'enabled',
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})
const valueForm = reactive<SpecificationValueDraft>({
  product_id: '',
  product_model_id: '',
  definition_id: '',
  value_text: '',
  value_number: null,
  value_min: null,
  value_max: null,
  value_boolean: false,
  enum_value: '',
})

// 当前规格类型决定唯一显示和提交的值字段，避免多个类型字段同时进入请求体。
const selectedValueType = computed(
  () => definitions.value.find((item) => item.id === valueForm.definition_id)?.value_type ?? null,
)

function cleanTranslations(items: CatalogTranslationDraft[]) {
  return items
    .filter((item) => item.name.trim())
    .map(({ locale_id, name, fields }) => ({ locale_id, name, fields }))
}

// 将后端翻译 DTO 转成共享 TranslationFields 组件使用的表单结构。
function mapTranslations(items: TranslationItem[] | undefined, bodyField: string) {
  return (items || []).map((translation) => ({
    locale_id: String(translation.locale_id),
    code: locales.value.find((locale) => locale.id === translation.locale_id)?.code || '',
    name: String(translation.name || ''),
    fields: { [bodyField]: String(translation[bodyField] || '') },
  }))
}

function resetGroup() {
  selectedGroupId.value = null
  Object.assign(groupForm, { code: '', status: 'enabled', sort_order: 0, translations: [] })
}

function resetDefinition() {
  selectedDefinitionId.value = null
  Object.assign(definitionForm, {
    group_id: '',
    code: '',
    value_type: 'text',
    default_unit: '',
    is_filterable: false,
    status: 'enabled',
    sort_order: 0,
    translations: [],
  })
}

async function load() {
  try {
    const [groupResult, definitionResult, localeResult, productResult] = await Promise.all([
      api.list<GroupItem>('/catalog/specifications/groups?page_size=100'),
      api.list<DefinitionItem>('/catalog/specifications/definitions?page_size=100'),
      api.detail<LocaleItem[]>('/locales'),
      api.list<ProductItem>('/catalog/products?page_size=100'),
    ])
    groups.value = groupResult.items
    definitions.value = definitionResult.items
    locales.value = localeResult
    products.value = productResult.items
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load specifications.'
  }
}

async function editGroup(item: GroupItem) {
  const detail = await api.detail<GroupItem>(`/catalog/specifications/groups/${item.id}`)
  selectedGroupId.value = item.id
  Object.assign(groupForm, {
    code: detail.code,
    status: detail.status,
    sort_order: detail.sort_order,
    translations: mapTranslations(detail.translations, 'description'),
  })
}

async function saveGroup() {
  errorMessage.value = ''
  try {
    const body = {
      status: groupForm.status,
      sort_order: groupForm.sort_order,
      translations: cleanTranslations(groupForm.translations),
    }
    if (selectedGroupId.value) {
      await api.update(`/catalog/specifications/groups/${selectedGroupId.value}`, body)
    } else {
      await api.create('/catalog/specifications/groups', { ...body, code: groupForm.code })
    }
    resetGroup()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save group.'
  }
}

async function deleteGroup(item: GroupItem) {
  if (!confirm(`Delete empty group ${item.code}?`)) return
  try {
    await api.remove(`/catalog/specifications/groups/${item.id}`)
    if (selectedGroupId.value === item.id) resetGroup()
    await load()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Group still contains definitions.'
  }
}

async function editDefinition(item: DefinitionItem) {
  const detail = await api.detail<DefinitionItem>(`/catalog/specifications/definitions/${item.id}`)
  selectedDefinitionId.value = item.id
  Object.assign(definitionForm, {
    group_id: detail.group_id,
    code: detail.code,
    value_type: detail.value_type,
    default_unit: detail.default_unit || '',
    is_filterable: detail.is_filterable,
    status: detail.status,
    sort_order: detail.sort_order,
    translations: mapTranslations(detail.translations, 'help_text'),
  })
}

async function saveDefinition() {
  errorMessage.value = ''
  try {
    const body = {
      group_id: definitionForm.group_id,
      value_type: definitionForm.value_type,
      default_unit: definitionForm.default_unit || null,
      is_filterable: definitionForm.is_filterable,
      status: definitionForm.status,
      sort_order: definitionForm.sort_order,
      translations: cleanTranslations(definitionForm.translations),
    }
    if (selectedDefinitionId.value) {
      await api.update(`/catalog/specifications/definitions/${selectedDefinitionId.value}`, body)
    } else {
      await api.create('/catalog/specifications/definitions', {
        ...body,
        code: definitionForm.code,
      })
    }
    resetDefinition()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save definition.'
  }
}

async function deleteDefinition(item: DefinitionItem) {
  if (!confirm(`Delete unreferenced definition ${item.code}?`)) return
  try {
    await api.remove(`/catalog/specifications/definitions/${item.id}`)
    if (selectedDefinitionId.value === item.id) resetDefinition()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Definition is still referenced.'
  }
}

function toValueDraft(item: SpecificationValueItem): SpecificationValueDraft {
  return {
    product_id: item.product_id || '',
    product_model_id: item.product_model_id || '',
    definition_id: item.definition_id,
    value_text: item.value_text || '',
    value_number: item.value_number,
    value_min: item.value_min,
    value_max: item.value_max,
    value_boolean: item.value_boolean ?? false,
    enum_value: item.enum_value || '',
  }
}

async function loadProductValues() {
  values.value = []
  if (!selectedProductId.value) return
  const result = await api.list<SpecificationValueItem>(
    `/catalog/specifications/values?product_id=${selectedProductId.value}&page_size=100`,
  )
  values.value = result.items
  for (const item of values.value) valueDrafts[item.id] = toValueDraft(item)
  valueForm.product_id = selectedProductId.value
}

async function createValue() {
  if (!selectedValueType.value || !selectedProductId.value) return
  valueForm.product_id = selectedProductId.value
  valueForm.product_model_id = ''
  const body = buildSpecificationValuePayload(selectedValueType.value, valueForm)
  try {
    await api.create('/catalog/specifications/values', body)
    Object.assign(valueForm, {
      product_id: selectedProductId.value,
      product_model_id: '',
      definition_id: '',
      value_text: '',
      value_number: null,
      value_min: null,
      value_max: null,
      value_boolean: false,
      enum_value: '',
    })
    await loadProductValues()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to save specification value.'
  }
}

async function updateValue(item: SpecificationValueItem) {
  const definition = definitions.value.find((candidate) => candidate.id === item.definition_id)
  const draft = valueDrafts[item.id]
  if (!definition || !draft) return
  const {
    product_id: _productId,
    product_model_id: _modelId,
    definition_id: _definitionId,
    ...body
  } = buildSpecificationValuePayload(definition.value_type, draft)
  await api.update(`/catalog/specifications/values/${item.id}`, body)
  successMessage.value = `${definition.code} saved.`
  await loadProductValues()
}

async function clearValue(item: SpecificationValueItem) {
  if (!confirm('Clear this specification value?')) return
  await api.remove(`/catalog/specifications/values/${item.id}`)
  await loadProductValues()
}

function definitionFor(item: SpecificationValueItem) {
  return definitions.value.find((definition) => definition.id === item.definition_id)
}

function valueDraftFor(item: SpecificationValueItem): SpecificationValueDraft {
  return valueDrafts[item.id] || toValueDraft(item)
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>Specifications</h1>
          <p>Manage reusable fields and confirmed product values.</p>
        </div>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <p v-if="successMessage" role="status">{{ successMessage }}</p>
      <div class="catalog-grid">
        <section class="sub-editor">
          <h2>Groups</h2>
          <div class="record-list">
            <div v-for="item in groups" :key="item.id" class="record-actions">
              <button type="button" @click="editGroup(item)">
                {{ item.code }} — {{ item.status }}
              </button>
              <button type="button" @click="deleteGroup(item)">Delete</button>
            </div>
          </div>
          <form class="editor-form" @submit.prevent="saveGroup">
            <label
              >Code <input v-model="groupForm.code" required :disabled="Boolean(selectedGroupId)"
            /></label>
            <label
              >Status
              <select v-model="groupForm.status">
                <option>enabled</option>
                <option>disabled</option>
                <option>retired</option>
              </select></label
            >
            <label>Sort <input v-model.number="groupForm.sort_order" type="number" /></label>
            <TranslationFields v-model="groupForm.translations" :locales="locales" />
            <button type="submit">
              {{ selectedGroupId ? 'Save group' : 'Create group' }}
            </button>
            <button v-if="selectedGroupId" type="button" @click="resetGroup">Cancel</button>
          </form>
        </section>
        <section class="sub-editor">
          <h2>Definitions</h2>
          <div class="record-list">
            <div v-for="item in definitions" :key="item.id" class="record-actions">
              <button type="button" @click="editDefinition(item)">
                {{ item.code }} — {{ item.value_type }} {{ item.default_unit }}
              </button>
              <button type="button" @click="deleteDefinition(item)">Delete</button>
            </div>
          </div>
          <form class="editor-form" @submit.prevent="saveDefinition">
            <label
              >Group
              <select v-model="definitionForm.group_id" required>
                <option v-for="item in groups" :key="item.id" :value="item.id">
                  {{ item.code }}
                </option>
              </select></label
            >
            <label
              >Code
              <input
                v-model="definitionForm.code"
                required
                :disabled="Boolean(selectedDefinitionId)"
            /></label>
            <label
              >Value type
              <select v-model="definitionForm.value_type">
                <option>text</option>
                <option>number</option>
                <option>range</option>
                <option>boolean</option>
                <option>enum</option>
              </select></label
            >
            <label>Default unit <input v-model="definitionForm.default_unit" /></label>
            <label
              ><input v-model="definitionForm.is_filterable" type="checkbox" /> Filterable</label
            >
            <label
              >Status
              <select v-model="definitionForm.status">
                <option>enabled</option>
                <option>disabled</option>
                <option>retired</option>
              </select></label
            >
            <label
              >Sort order <input v-model.number="definitionForm.sort_order" type="number"
            /></label>
            <p>Type and unit cannot change after a product value references this definition.</p>
            <TranslationFields
              v-model="definitionForm.translations"
              :locales="locales"
              body-field="help_text"
            />
            <button type="submit">
              {{ selectedDefinitionId ? 'Save definition' : 'Create definition' }}
            </button>
            <button v-if="selectedDefinitionId" type="button" @click="resetDefinition">
              Cancel
            </button>
          </form>
        </section>
      </div>

      <section class="sub-editor">
        <h2>Product values</h2>
        <label
          >Product
          <select v-model="selectedProductId" @change="loadProductValues">
            <option value="">Choose product</option>
            <option v-for="item in products" :key="item.id" :value="item.id">
              {{ item.code || item.slug }} — {{ item.status }}
            </option>
          </select></label
        >
        <form class="inline-form" @submit.prevent="createValue">
          <select v-model="valueForm.definition_id" required>
            <option value="">Definition</option>
            <option
              v-for="item in definitions.filter((definition) => definition.status === 'enabled')"
              :key="item.id"
              :value="item.id"
            >
              {{ item.code }}
            </option>
          </select>
          <label v-if="selectedValueType === 'text'"
            >Text <input v-model="valueForm.value_text" required
          /></label>
          <label v-if="selectedValueType === 'number'"
            >Number
            <input v-model.number="valueForm.value_number" type="number" step="any" required
          /></label>
          <template v-if="selectedValueType === 'range'">
            <label
              >Minimum
              <input v-model.number="valueForm.value_min" type="number" step="any" required
            /></label>
            <label
              >Maximum
              <input v-model.number="valueForm.value_max" type="number" step="any" required
            /></label>
          </template>
          <label v-if="selectedValueType === 'boolean'"
            >Boolean
            <select v-model="valueForm.value_boolean">
              <option :value="true">True</option>
              <option :value="false">False</option>
            </select></label
          >
          <label v-if="selectedValueType === 'enum'"
            >Enum value <input v-model="valueForm.enum_value" required
          /></label>
          <button type="submit" :disabled="!selectedValueType || !selectedProductId">
            Add value
          </button>
        </form>
        <div v-for="item in values" :key="item.id" class="value-editor">
          <strong>{{ definitionFor(item)?.code }}</strong>
          <label v-if="definitionFor(item)?.value_type === 'text'"
            >Text <input v-model="valueDraftFor(item).value_text"
          /></label>
          <label v-if="definitionFor(item)?.value_type === 'number'"
            >Number
            <input v-model.number="valueDraftFor(item).value_number" type="number" step="any"
          /></label>
          <template v-if="definitionFor(item)?.value_type === 'range'">
            <label
              >Minimum
              <input v-model.number="valueDraftFor(item).value_min" type="number" step="any"
            /></label>
            <label
              >Maximum
              <input v-model.number="valueDraftFor(item).value_max" type="number" step="any"
            /></label>
          </template>
          <label v-if="definitionFor(item)?.value_type === 'boolean'"
            >Boolean
            <select v-model="valueDraftFor(item).value_boolean">
              <option :value="true">True</option>
              <option :value="false">False</option>
            </select></label
          >
          <label v-if="definitionFor(item)?.value_type === 'enum'"
            >Enum value <input v-model="valueDraftFor(item).enum_value"
          /></label>
          <button type="button" @click="updateValue(item)">Save</button>
          <button type="button" @click="clearValue(item)">Clear</button>
        </div>
      </section>
    </section>
  </main>
</template>
