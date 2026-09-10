<!-- 页面用途：维护规格分组、规格定义，以及产品已经确认的结构化规格值。 -->
<script setup lang="ts">
import TranslationFields from '~/components/catalog/TranslationFields.vue'
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'
import { ENTITY_STATUS_LABELS, labelFrom } from '~/utils/adminZhCn'
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
  display_name?: string
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
  display_name?: string
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
  title: '产品规格',
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

// 新增值只能选择同时启用的字段与分组，和后端新增门禁保持同一套生命周期判断。
const availableDefinitions = computed(() => {
  const enabledGroupIds = new Set(
    groups.value.filter((group) => group.status === 'enabled').map((group) => group.id),
  )
  return definitions.value.filter(
    (definition) => definition.status === 'enabled' && enabledGroupIds.has(definition.group_id),
  )
})

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
  () =>
    availableDefinitions.value.find((item) => item.id === valueForm.definition_id)?.value_type ??
    null,
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
  Object.assign(groupForm, {
    code: '',
    status: 'enabled',
    sort_order: 0,
    translations: [],
  })
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
    errorMessage.value = error instanceof Error ? error.message : '无法读取产品规格。'
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
      await api.create('/catalog/specifications/groups', {
        ...body,
        code: groupForm.code,
      })
    }
    resetGroup()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法保存规格分组。'
  }
}

async function deleteGroup(item: GroupItem) {
  if (!confirm(`确认删除未被引用的空分组“${item.display_name || item.code}”吗？`)) return
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
    errorMessage.value = error instanceof Error ? error.message : '无法保存规格字段。'
  }
}

async function deleteDefinition(item: DefinitionItem) {
  if (!confirm(`确认删除未被引用的字段“${item.display_name || item.code}”吗？`)) return
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
    errorMessage.value = error instanceof Error ? error.message : '无法保存产品参数值。'
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

/** 输入规格值类型代码；输出后台中文标签，枚举代码本身保持不变。 */
function valueTypeLabel(value: SpecificationValueType): string {
  return (
    {
      text: '文本',
      number: '数值',
      range: '范围',
      boolean: '是 / 否',
      enum: '选项',
    } as Record<SpecificationValueType, string>
  )[value]
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
          <h1>产品规格</h1>
          <p>维护可复用的规格分组、字段定义和已确认产品参数值。</p>
        </div>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">
        {{ errorMessage }}
      </p>
      <p v-if="successMessage" role="status">{{ successMessage }}</p>
      <div class="catalog-grid">
        <section class="sub-editor">
          <h2>规格分组</h2>
          <div class="record-list">
            <div v-for="item in groups" :key="item.id" class="record-actions">
              <button type="button" @click="editGroup(item)">
                {{ item.display_name || item.code }} · {{ item.code }} ·
                {{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}
              </button>
              <button type="button" @click="deleteGroup(item)">删除</button>
            </div>
          </div>
          <form class="editor-form" @submit.prevent="saveGroup">
            <label
              >分组代码
              <input v-model="groupForm.code" required :disabled="Boolean(selectedGroupId)"
            /></label>
            <label
              >状态
              <select v-model="groupForm.status">
                <option value="enabled">启用</option>
                <option value="disabled">停用</option>
                <option value="retired">已退役</option>
              </select></label
            >
            <label>排序 <input v-model.number="groupForm.sort_order" type="number" /></label>
            <TranslationFields v-model="groupForm.translations" :locales="locales" />
            <button type="submit">
              {{ selectedGroupId ? '保存分组' : '创建分组' }}
            </button>
            <button v-if="selectedGroupId" type="button" @click="resetGroup">取消</button>
          </form>
        </section>
        <section class="sub-editor">
          <h2>字段定义</h2>
          <div class="record-list">
            <div v-for="item in definitions" :key="item.id" class="record-actions">
              <button type="button" @click="editDefinition(item)">
                {{ item.display_name || item.code }} · {{ item.code }} ·
                {{ valueTypeLabel(item.value_type) }} {{ item.default_unit }}
              </button>
              <button type="button" @click="deleteDefinition(item)">删除</button>
            </div>
          </div>
          <form class="editor-form" @submit.prevent="saveDefinition">
            <label
              >所属分组
              <select v-model="definitionForm.group_id" required>
                <option v-for="item in groups" :key="item.id" :value="item.id">
                  {{ item.display_name || item.code }} · {{ item.code }}
                </option>
              </select></label
            >
            <label
              >字段代码
              <input
                v-model="definitionForm.code"
                required
                :disabled="Boolean(selectedDefinitionId)"
            /></label>
            <label
              >值类型
              <select v-model="definitionForm.value_type">
                <option value="text">文本</option>
                <option value="number">数值</option>
                <option value="range">范围</option>
                <option value="boolean">是 / 否</option>
                <option value="enum">选项</option>
              </select></label
            >
            <label>默认单位 <input v-model="definitionForm.default_unit" /></label>
            <label
              ><input v-model="definitionForm.is_filterable" type="checkbox" /> 可用于筛选</label
            >
            <label
              >状态
              <select v-model="definitionForm.status">
                <option value="enabled">启用</option>
                <option value="disabled">停用</option>
                <option value="retired">已退役</option>
              </select></label
            >
            <label>排序 <input v-model.number="definitionForm.sort_order" type="number" /></label>
            <p>产品参数引用此字段后，值类型和单位不能更改。</p>
            <TranslationFields
              v-model="definitionForm.translations"
              :locales="locales"
              body-field="help_text"
            />
            <button type="submit">
              {{ selectedDefinitionId ? '保存字段' : '创建字段' }}
            </button>
            <button v-if="selectedDefinitionId" type="button" @click="resetDefinition">取消</button>
          </form>
        </section>
      </div>

      <section class="sub-editor">
        <h2>产品参数值</h2>
        <label
          >产品
          <select v-model="selectedProductId" @change="loadProductValues">
            <option value="">请选择产品</option>
            <option v-for="item in products" :key="item.id" :value="item.id">
              {{ item.display_name || item.code || item.slug }} · {{ item.code || item.slug }} ·
              {{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}
            </option>
          </select></label
        >
        <form class="inline-form" @submit.prevent="createValue">
          <select v-model="valueForm.definition_id" required>
            <option value="">请选择规格字段</option>
            <option v-for="item in availableDefinitions" :key="item.id" :value="item.id">
              {{ item.display_name || item.code }} · {{ item.code }}
            </option>
          </select>
          <label v-if="selectedValueType === 'text'"
            >文本值 <input v-model="valueForm.value_text" required
          /></label>
          <label v-if="selectedValueType === 'number'"
            >数值 <input v-model.number="valueForm.value_number" type="number" step="any" required
          /></label>
          <template v-if="selectedValueType === 'range'">
            <label
              >最小值 <input v-model.number="valueForm.value_min" type="number" step="any" required
            /></label>
            <label
              >最大值 <input v-model.number="valueForm.value_max" type="number" step="any" required
            /></label>
          </template>
          <label v-if="selectedValueType === 'boolean'"
            >是 / 否
            <select v-model="valueForm.value_boolean">
              <option :value="true">是</option>
              <option :value="false">否</option>
            </select></label
          >
          <label v-if="selectedValueType === 'enum'"
            >选项值 <input v-model="valueForm.enum_value" required
          /></label>
          <button type="submit" :disabled="!selectedValueType || !selectedProductId">
            添加参数值
          </button>
        </form>
        <div v-for="item in values" :key="item.id" class="value-editor">
          <strong>{{ definitionFor(item)?.code }}</strong>
          <label v-if="definitionFor(item)?.value_type === 'text'"
            >文本值 <input v-model="valueDraftFor(item).value_text"
          /></label>
          <label v-if="definitionFor(item)?.value_type === 'number'"
            >数值 <input v-model.number="valueDraftFor(item).value_number" type="number" step="any"
          /></label>
          <template v-if="definitionFor(item)?.value_type === 'range'">
            <label
              >最小值
              <input v-model.number="valueDraftFor(item).value_min" type="number" step="any"
            /></label>
            <label
              >最大值
              <input v-model.number="valueDraftFor(item).value_max" type="number" step="any"
            /></label>
          </template>
          <label v-if="definitionFor(item)?.value_type === 'boolean'"
            >是 / 否
            <select v-model="valueDraftFor(item).value_boolean">
              <option :value="true">是</option>
              <option :value="false">否</option>
            </select></label
          >
          <label v-if="definitionFor(item)?.value_type === 'enum'"
            >选项值 <input v-model="valueDraftFor(item).enum_value"
          /></label>
          <button type="button" @click="updateValue(item)">保存</button>
          <button type="button" @click="clearValue(item)">清空</button>
        </div>
      </section>
    </section>
  </main>
</template>
