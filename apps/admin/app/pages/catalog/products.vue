<!-- 页面用途：Product 主实体、双语正文、型号、关系和动态规格的最小真实 CRUD。 -->
<script setup lang="ts">
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'

interface NamedItem {
  id: string
  slug?: string
  code?: string | null
  status: string
}
interface LocaleItem {
  id: string
  code: string
  native_name: string
}
interface ProductModelItem {
  id: string
  model_code: string
  status: string
}
interface SpecValue {
  id: string
  definition_id: string
  value_number: number | null
  value_text: string | null
}
interface ProductDetail extends NamedItem {
  category_id: string
  slug: string
  code: string | null
  featured: boolean
  sort_order: number
  translations: Array<Record<string, unknown>>
  models: ProductModelItem[]
  specifications: SpecValue[]
  relations: {
    material_ids: string[]
    technology_ids: string[]
    application_ids: string[]
    solution_ids: string[]
  }
}

useHead({ title: 'Catalog Products', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useCatalogApi()
const products = ref<ProductDetail[]>([])
const categories = ref<NamedItem[]>([])
const materials = ref<NamedItem[]>([])
const technologies = ref<NamedItem[]>([])
const applications = ref<NamedItem[]>([])
const solutions = ref<NamedItem[]>([])
const definitions = ref<NamedItem[]>([])
const locales = ref<LocaleItem[]>([])
const selectedId = ref<string | null>(null)
const errorMessage = ref('')
const modelCode = ref('')
const specification = reactive({ definition_id: '', value_number: 0 })
const form = reactive({
  category_id: '',
  code: '',
  slug: '',
  status: 'enabled',
  featured: false,
  sort_order: 0,
  translations: [] as CatalogTranslationDraft[],
  material_ids: [] as string[],
  technology_ids: [] as string[],
  application_ids: [] as string[],
  solution_ids: [] as string[],
  models: [] as ProductModelItem[],
  specifications: [] as SpecValue[],
})

async function load() {
  try {
    const [
      productResult,
      categoryResult,
      materialResult,
      technologyResult,
      applicationResult,
      solutionResult,
      definitionResult,
      localeResult,
    ] = await Promise.all([
      api.list<ProductDetail>('/catalog/products'),
      api.list<NamedItem>('/catalog/categories'),
      api.list<NamedItem>('/catalog/materials'),
      api.list<NamedItem>('/catalog/technologies'),
      api.list<NamedItem>('/catalog/applications'),
      api.list<NamedItem>('/catalog/solutions'),
      api.list<NamedItem>('/catalog/specifications/definitions'),
      api.detail<LocaleItem[]>('/locales'),
    ])
    products.value = productResult.items
    categories.value = categoryResult.items
    materials.value = materialResult.items
    technologies.value = technologyResult.items
    applications.value = applicationResult.items
    solutions.value = solutionResult.items
    definitions.value = definitionResult.items
    locales.value = localeResult
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load products.'
  }
}

function resetForm() {
  selectedId.value = null
  Object.assign(form, {
    category_id: '',
    code: '',
    slug: '',
    status: 'enabled',
    featured: false,
    sort_order: 0,
    translations: [],
    material_ids: [],
    technology_ids: [],
    application_ids: [],
    solution_ids: [],
    models: [],
    specifications: [],
  })
}

async function editProduct(item: ProductDetail) {
  try {
    const detail = await api.detail<ProductDetail>(`/catalog/products/${item.id}`)
    selectedId.value = detail.id
    form.category_id = detail.category_id
    form.code = detail.code || ''
    form.slug = detail.slug
    form.status = detail.status
    form.featured = detail.featured
    form.sort_order = detail.sort_order
    form.models = detail.models
    form.specifications = detail.specifications
    Object.assign(form, detail.relations)
    form.translations = detail.translations.map((translation) => ({
      locale_id: String(translation.locale_id),
      code: locales.value.find((locale) => locale.id === translation.locale_id)?.code || '',
      name: String(translation.name || ''),
      fields: { description: String(translation.description || '') },
    }))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load product detail.'
  }
}

function productBody() {
  return {
    category_id: form.category_id,
    code: form.code || null,
    slug: form.slug,
    status: form.status,
    featured: form.featured,
    sort_order: form.sort_order,
    translations: form.translations
      .filter((item) => item.name.trim())
      .map(({ locale_id, name, fields }) => ({ locale_id, name, fields })),
  }
}

async function saveProduct() {
  try {
    if (selectedId.value) await api.update(`/catalog/products/${selectedId.value}`, productBody())
    else await api.create('/catalog/products', productBody())
    resetForm()
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to save product.'
  }
}

async function archiveProduct() {
  if (!selectedId.value) return
  await api.archive(`/catalog/products/${selectedId.value}/archive`)
  resetForm()
  await load()
}

async function addModel() {
  if (!selectedId.value || !modelCode.value.trim()) return
  await api.create(`/catalog/products/${selectedId.value}/models`, {
    model_code: modelCode.value,
    translations: [],
  })
  modelCode.value = ''
  await editProduct({ id: selectedId.value } as ProductDetail)
}

async function retireModel(model: ProductModelItem) {
  await api.update(`/catalog/product-models/${model.id}`, { status: 'retired' })
  await editProduct({ id: selectedId.value } as ProductDetail)
}

async function saveRelations() {
  if (!selectedId.value) return
  await api.replace(`/catalog/products/${selectedId.value}/relations`, {
    material_ids: form.material_ids,
    technology_ids: form.technology_ids,
    application_ids: form.application_ids,
    solution_ids: form.solution_ids,
  })
  await editProduct({ id: selectedId.value } as ProductDetail)
}

async function addSpecification() {
  if (!selectedId.value || !specification.definition_id) return
  await api.create('/catalog/specifications/values', {
    product_id: selectedId.value,
    definition_id: specification.definition_id,
    value_number: specification.value_number,
  })
  await editProduct({ id: selectedId.value } as ProductDetail)
}

async function updateSpecification(value: SpecValue) {
  await api.update(`/catalog/specifications/values/${value.id}`, {
    value_number: value.value_number,
    value_text: value.value_text,
  })
  if (selectedId.value) await editProduct({ id: selectedId.value } as ProductDetail)
}

onMounted(load)
</script>

<template>
  <main class="admin-shell catalog-page">
    <section>
      <header class="page-heading">
        <div>
          <h1>Products &amp; Models</h1>
          <p>Structured product editing and publication foundation.</p>
        </div>
        <button type="button" @click="resetForm">New</button>
      </header>
      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <div class="catalog-grid">
        <div class="record-list">
          <button v-for="item in products" :key="item.id" type="button" @click="editProduct(item)">
            <strong>{{ item.slug }}</strong
            ><span>{{ item.status }}</span>
          </button>
        </div>
        <form class="editor-form" @submit.prevent="saveProduct">
          <label
            >Category
            <select v-model="form.category_id" required>
              <option value="" disabled>Select</option>
              <option v-for="item in categories" :key="item.id" :value="item.id">
                {{ item.slug }}
              </option>
            </select></label
          >
          <label>Code <input v-model="form.code" /></label
          ><label>Slug <input v-model="form.slug" required /></label>
          <label
            >Status
            <select v-model="form.status">
              <option>enabled</option>
              <option>disabled</option>
              <option>retired</option>
            </select></label
          >
          <label>Sort order <input v-model.number="form.sort_order" type="number" /></label
          ><label><input v-model="form.featured" type="checkbox" /> Featured</label>
          <TranslationFields v-model="form.translations" :locales="locales" />
          <div class="form-actions">
            <button type="submit">{{ selectedId ? 'Save changes' : 'Create product' }}</button
            ><button v-if="selectedId" type="button" class="danger" @click="archiveProduct">
              Archive
            </button>
          </div>
        </form>
      </div>
      <section v-if="selectedId" class="sub-editor">
        <h2>Product Models</h2>
        <div class="inline-form">
          <input v-model="modelCode" placeholder="Model code" /><button
            type="button"
            @click="addModel"
          >
            Add model
          </button>
        </div>
        <ul>
          <li v-for="model in form.models" :key="model.id">
            {{ model.model_code }} — {{ model.status }}
            <button type="button" @click="retireModel(model)">Retire</button>
          </li>
        </ul>
      </section>
      <section v-if="selectedId" class="sub-editor">
        <h2>Relations</h2>
        <label
          >Materials
          <select v-model="form.material_ids" multiple>
            <option v-for="item in materials" :key="item.id" :value="item.id">
              {{ item.slug }}
            </option>
          </select></label
        >
        <label
          >Technologies
          <select v-model="form.technology_ids" multiple>
            <option v-for="item in technologies" :key="item.id" :value="item.id">
              {{ item.slug }}
            </option>
          </select></label
        >
        <label
          >Applications
          <select v-model="form.application_ids" multiple>
            <option v-for="item in applications" :key="item.id" :value="item.id">
              {{ item.slug }}
            </option>
          </select></label
        >
        <label
          >Solutions
          <select v-model="form.solution_ids" multiple>
            <option v-for="item in solutions" :key="item.id" :value="item.id">
              {{ item.slug }}
            </option>
          </select></label
        >
        <button type="button" @click="saveRelations">Save relations</button>
      </section>
      <section v-if="selectedId" class="sub-editor">
        <h2>Specifications</h2>
        <div class="inline-form">
          <select v-model="specification.definition_id">
            <option value="">Definition</option>
            <option v-for="item in definitions" :key="item.id" :value="item.id">
              {{ item.code }}
            </option></select
          ><input v-model.number="specification.value_number" type="number" /><button
            type="button"
            @click="addSpecification"
          >
            Add value
          </button>
        </div>
        <ul>
          <li v-for="value in form.specifications" :key="value.id">
            <input v-model.number="value.value_number" type="number" /><button
              type="button"
              @click="updateSpecification(value)"
            >
              Save
            </button>
          </li>
        </ul>
      </section>
    </section>
  </main>
</template>
