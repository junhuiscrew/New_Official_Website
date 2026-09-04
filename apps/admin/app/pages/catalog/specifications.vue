<!-- 页面用途：Specification Group、Definition 与 Product/ProductModel Value 基础编辑。 -->
<script setup lang="ts">
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'

interface GroupItem {
  id: string
  code: string
  status: string
}
interface DefinitionItem extends GroupItem {
  group_id: string
  value_type: string
  default_unit: string | null
  is_filterable: boolean
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
const locales = ref<LocaleItem[]>([])
const errorMessage = ref('')
const groupForm = reactive({
  code: '',
  status: 'enabled',
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})
const definitionForm = reactive({
  group_id: '',
  code: '',
  value_type: 'text',
  default_unit: '',
  is_filterable: false,
  status: 'enabled',
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
})
const valueForm = reactive({
  product_id: '',
  product_model_id: '',
  definition_id: '',
  value_text: '',
  value_number: 0,
})

function cleanTranslations(items: CatalogTranslationDraft[]) {
  return items
    .filter((item) => item.name.trim())
    .map(({ locale_id, name, fields }) => ({ locale_id, name, fields }))
}

async function load() {
  try {
    const [groupResult, definitionResult, localeResult] = await Promise.all([
      api.list<GroupItem>('/catalog/specifications/groups'),
      api.list<DefinitionItem>('/catalog/specifications/definitions'),
      api.detail<LocaleItem[]>('/locales'),
    ])
    groups.value = groupResult.items
    definitions.value = definitionResult.items
    locales.value = localeResult
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load specifications.'
  }
}

async function createGroup() {
  try {
    await api.create('/catalog/specifications/groups', {
      ...groupForm,
      translations: cleanTranslations(groupForm.translations),
    })
    Object.assign(groupForm, { code: '', status: 'enabled', sort_order: 0, translations: [] })
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to create group.'
  }
}

async function createDefinition() {
  try {
    await api.create('/catalog/specifications/definitions', {
      ...definitionForm,
      default_unit: definitionForm.default_unit || null,
      translations: cleanTranslations(definitionForm.translations),
    })
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
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to create definition.'
  }
}

async function createValue() {
  const definition = definitions.value.find((item) => item.id === valueForm.definition_id)
  if (!definition) return
  const body: Record<string, unknown> = {
    product_id: valueForm.product_id || null,
    product_model_id: valueForm.product_model_id || null,
    definition_id: valueForm.definition_id,
  }
  if (definition.value_type === 'number') body.value_number = valueForm.value_number
  else body.value_text = valueForm.value_text
  try {
    await api.create('/catalog/specifications/values', body)
    Object.assign(valueForm, {
      product_id: '',
      product_model_id: '',
      definition_id: '',
      value_text: '',
      value_number: 0,
    })
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'Unable to save specification value.'
  }
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <h1>Specifications</h1>
      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <div class="catalog-grid">
        <section class="sub-editor">
          <h2>Groups</h2>
          <ul>
            <li v-for="item in groups" :key="item.id">{{ item.code }} — {{ item.status }}</li>
          </ul>
          <form class="editor-form" @submit.prevent="createGroup">
            <label>Code <input v-model="groupForm.code" required /></label
            ><label>Sort <input v-model.number="groupForm.sort_order" type="number" /></label
            ><TranslationFields v-model="groupForm.translations" :locales="locales" /><button
              type="submit"
            >
              Create group
            </button>
          </form>
        </section>
        <section class="sub-editor">
          <h2>Definitions</h2>
          <ul>
            <li v-for="item in definitions" :key="item.id">
              {{ item.code }} — {{ item.value_type }} {{ item.default_unit }}
            </li>
          </ul>
          <form class="editor-form" @submit.prevent="createDefinition">
            <label
              >Group
              <select v-model="definitionForm.group_id" required>
                <option v-for="item in groups" :key="item.id" :value="item.id">
                  {{ item.code }}
                </option>
              </select></label
            ><label>Code <input v-model="definitionForm.code" required /></label
            ><label
              >Value type
              <select v-model="definitionForm.value_type">
                <option>text</option>
                <option>number</option>
                <option>range</option>
                <option>boolean</option>
                <option>enum</option>
              </select></label
            ><label>Default unit <input v-model="definitionForm.default_unit" /></label
            ><label
              ><input v-model="definitionForm.is_filterable" type="checkbox" /> Filterable</label
            ><TranslationFields
              v-model="definitionForm.translations"
              :locales="locales"
              body-field="help_text"
            /><button type="submit">Create definition</button>
          </form>
        </section>
      </div>
      <section class="sub-editor">
        <h2>Product / Model value</h2>
        <form class="inline-form" @submit.prevent="createValue">
          <input v-model="valueForm.product_id" placeholder="Product UUID" /><input
            v-model="valueForm.product_model_id"
            placeholder="ProductModel UUID"
          /><select v-model="valueForm.definition_id" required>
            <option value="">Definition</option>
            <option v-for="item in definitions" :key="item.id" :value="item.id">
              {{ item.code }}
            </option></select
          ><input v-model="valueForm.value_text" placeholder="Text / enum value" /><input
            v-model.number="valueForm.value_number"
            type="number"
            placeholder="Number"
          /><button type="submit">Save value</button>
        </form>
      </section>
    </section>
  </main>
</template>
