<!-- 页面用途：Product 主实体、双语正文、型号、关系和动态规格的最小真实 CRUD。 -->
<script setup lang="ts">
import TranslationFields from '~/components/catalog/TranslationFields.vue'
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'

interface NamedItem {
  id: string
  slug?: string
  code?: string | null
  status: string
  primary_media_id?: string | null
  category_id?: string
  translations?: Array<Record<string, unknown>>
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
interface MediaItem {
  id: string
  type: string
  filename: string
  url: string | null
}
interface LifecycleItem {
  locale_id: string
  status: string
}
interface RouteItem {
  locale_id: string
  active: boolean
  indexable: boolean
}
interface ProductDetail extends NamedItem {
  category_id: string
  slug: string
  code: string | null
  featured: boolean
  sort_order: number
  primary_media_id: string | null
  translations: Array<Record<string, unknown>>
  translation_statuses: LifecycleItem[]
  publications: LifecycleItem[]
  routes: RouteItem[]
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
const media = ref<MediaItem[]>([])
const translationStatuses = ref<LifecycleItem[]>([])
const publications = ref<LifecycleItem[]>([])
const routes = ref<RouteItem[]>([])
const selectedId = ref<string | null>(null)
const errorMessage = ref('')
const modelCode = ref('')
const specification = reactive({ definition_id: '', value_number: 0 })
const productSearch = ref('')
const selectedCategoryFilter = ref('')
const selectedStatusFilter = ref('')
const productPage = ref(1)
const PRODUCT_PAGE_SIZE = 6
type RelationKey = 'material_ids' | 'technology_ids' | 'application_ids' | 'solution_ids'
const relationSearch = reactive<Record<RelationKey, string>>({
  material_ids: '',
  technology_ids: '',
  application_ids: '',
  solution_ids: '',
})
const form = reactive({
  category_id: '',
  code: '',
  slug: '',
  status: 'enabled',
  featured: false,
  sort_order: 0,
  primary_media_id: '',
  translations: [] as CatalogTranslationDraft[],
  material_ids: [] as string[],
  technology_ids: [] as string[],
  application_ids: [] as string[],
  solution_ids: [] as string[],
  models: [] as ProductModelItem[],
  specifications: [] as SpecValue[],
})

/**
 * 输出后台列表和关系选择器中的可读名称。
 *
 * 输入：item，包含 slug、code 或双语翻译的业务实体。
 * 输出：string，优先中文、其次英文，最后回退 slug/code；绝不显示 UUID。
 */
function readableItemLabel(item: NamedItem): string {
  const translation =
    item.translations?.find((row) =>
      String(
        row.locale_code ||
          row.code ||
          locales.value.find((locale) => locale.id === row.locale_id)?.code ||
          '',
      )
        .toLowerCase()
        .startsWith('zh'),
    ) ||
    item.translations?.find((row) =>
      String(
        row.locale_code ||
          row.code ||
          locales.value.find((locale) => locale.id === row.locale_id)?.code ||
          '',
      )
        .toLowerCase()
        .startsWith('en'),
    ) ||
    item.translations?.[0]
  return String(
    translation?.name ||
      translation?.title ||
      translation?.question ||
      item.slug ||
      item.code ||
      '未命名内容',
  )
}

/** 输入业务实体；输出名称、标题、slug 与 code 组成的完整检索词集合。 */
function searchableItemValues(item: NamedItem): string[] {
  const translationValues =
    item.translations?.flatMap((row) => [row.name, row.title, row.question]) || []
  return [...translationValues, item.slug, item.code].filter(Boolean).map(String)
}

/** 输入媒体ID；输出可在同源后台显示的缩略图地址。 */
function productMediaUrl(mediaId?: string | null): string {
  if (!mediaId) return ''
  return media.value.find((item) => item.id === mediaId)?.url || ''
}

const filteredProducts = computed(() => {
  const needle = productSearch.value.trim().toLocaleLowerCase()
  return products.value.filter((item) => {
    const matchesSearch =
      !needle ||
      searchableItemValues(item).some((value) => value.toLocaleLowerCase().includes(needle))
    const matchesCategory =
      !selectedCategoryFilter.value || item.category_id === selectedCategoryFilter.value
    const matchesStatus = !selectedStatusFilter.value || item.status === selectedStatusFilter.value
    return matchesSearch && matchesCategory && matchesStatus
  })
})
const productPages = computed(() =>
  Math.max(1, Math.ceil(filteredProducts.value.length / PRODUCT_PAGE_SIZE)),
)
const pagedProducts = computed(() => {
  const start = (productPage.value - 1) * PRODUCT_PAGE_SIZE
  return filteredProducts.value.slice(start, start + PRODUCT_PAGE_SIZE)
})

watch([productSearch, selectedCategoryFilter, selectedStatusFilter], () => {
  productPage.value = 1
})

/**
 * 按名称或 slug 过滤关系选项。
 *
 * 输入：key，关系字段；items，该关系可选实体。
 * 输出：NamedItem[]，匹配搜索词的可读选项。
 */
function filteredRelationOptions(key: RelationKey, items: NamedItem[]): NamedItem[] {
  const needle = relationSearch[key].trim().toLocaleLowerCase()
  if (!needle) return items
  return items.filter((item) =>
    searchableItemValues(item).some((value) => value.toLocaleLowerCase().includes(needle)),
  )
}

/**
 * 为轻量列表补齐后台可读名称所需的详情字段。
 *
 * 输入：basePath，实体 API 路径；items，轻量列表记录。
 * 输出：Promise<T[]>，包含双语翻译的详情记录，供搜索和选择器使用。
 */
async function hydrateNamedItems<T extends NamedItem>(basePath: string, items: T[]): Promise<T[]> {
  return Promise.all(items.map((item) => api.detail<T>(`${basePath}/${item.id}`)))
}

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
      mediaResult,
    ] = await Promise.all([
      api.list<ProductDetail>('/catalog/products'),
      api.list<NamedItem>('/catalog/categories'),
      api.list<NamedItem>('/catalog/materials'),
      api.list<NamedItem>('/catalog/technologies'),
      api.list<NamedItem>('/catalog/applications'),
      api.list<NamedItem>('/catalog/solutions'),
      api.list<NamedItem>('/catalog/specifications/definitions'),
      api.detail<LocaleItem[]>('/locales'),
      api.detail<MediaItem[]>('/media'),
    ])
    const [
      productDetails,
      categoryDetails,
      materialDetails,
      technologyDetails,
      applicationDetails,
      solutionDetails,
    ] = await Promise.all([
      hydrateNamedItems('/catalog/products', productResult.items),
      hydrateNamedItems('/catalog/categories', categoryResult.items),
      hydrateNamedItems('/catalog/materials', materialResult.items),
      hydrateNamedItems('/catalog/technologies', technologyResult.items),
      hydrateNamedItems('/catalog/applications', applicationResult.items),
      hydrateNamedItems('/catalog/solutions', solutionResult.items),
    ])
    products.value = productDetails
    categories.value = categoryDetails
    materials.value = materialDetails
    technologies.value = technologyDetails
    applications.value = applicationDetails
    solutions.value = solutionDetails
    definitions.value = definitionResult.items
    locales.value = localeResult
    media.value = mediaResult
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
    primary_media_id: '',
    translations: [],
    material_ids: [],
    technology_ids: [],
    application_ids: [],
    solution_ids: [],
    models: [],
    specifications: [],
  })
  translationStatuses.value = []
  publications.value = []
  routes.value = []
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
    form.primary_media_id = detail.primary_media_id || ''
    form.models = detail.models
    form.specifications = detail.specifications
    translationStatuses.value = detail.translation_statuses || []
    publications.value = detail.publications || []
    routes.value = detail.routes || []
    Object.assign(form, detail.relations)
    form.translations = detail.translations.map((translation) => ({
      locale_id: String(translation.locale_id),
      code: locales.value.find((locale) => locale.id === translation.locale_id)?.code || '',
      name: String(translation.name || ''),
      fields: {
        short_description: String(translation.short_description || ''),
        description: String(translation.description || ''),
        highlights_jsonb: Array.isArray(translation.highlights_jsonb)
          ? translation.highlights_jsonb.join('\n')
          : '',
      },
    }))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to load product detail.'
  }
}

// 将“一行一项”的可读编辑框转换为后端结构化 highlights 数组。
function parseHighlights(value: string | undefined): string[] {
  if (!value?.trim()) return []
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function productBody() {
  return {
    category_id: form.category_id,
    code: form.code || null,
    slug: form.slug,
    status: form.status,
    featured: form.featured,
    sort_order: form.sort_order,
    primary_media_id: form.primary_media_id || null,
    translations: form.translations
      .filter((item) => item.name.trim())
      .map(({ locale_id, name, fields }) => ({
        locale_id,
        name,
        fields: {
          short_description: fields.short_description || null,
          description: fields.description || null,
          highlights_jsonb: parseHighlights(fields.highlights_jsonb),
        },
      })),
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

// 获取当前语言的生命周期状态，供审核与发布按钮使用。
function lifecycleStatus(items: LifecycleItem[], localeId: string, fallback: string) {
  return items.find((item) => item.locale_id === localeId)?.status || fallback
}

function routeStatus(localeId: string) {
  return routes.value.find((item) => item.locale_id === localeId)
}

async function reloadSelectedProduct() {
  if (!selectedId.value) return
  await editProduct({ id: selectedId.value } as ProductDetail)
}

// Translation Review 由后端同时校验 catalog.review、translation.review 与 content.review。
async function reviewTranslation(localeId: string) {
  if (!selectedId.value) return
  try {
    await api.request(`/catalog/products/${selectedId.value}/translations/${localeId}/review`, {
      method: 'POST',
    })
    await reloadSelectedProduct()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to review translation.'
  }
}

// Publication 状态转换继续由后端统一事务控制 Route、Translation 与 Audit。
async function transitionPublication(localeId: string, targetStatus: 'published' | 'archived') {
  if (!selectedId.value) return
  try {
    await api.request(
      `/catalog/products/${selectedId.value}/publications/${localeId}/${targetStatus}`,
      { method: 'POST' },
    )
    await reloadSelectedProduct()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to change publication.'
  }
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
        <aside class="product-browser" aria-label="产品记录浏览器">
          <div class="product-browser__filters">
            <label>
              <span>Search products</span>
              <input v-model="productSearch" type="search" placeholder="Name, slug or code" />
            </label>
            <div>
              <label>
                <span>Category</span>
                <select v-model="selectedCategoryFilter">
                  <option value="">All categories</option>
                  <option v-for="item in categories" :key="item.id" :value="item.id">
                    {{ readableItemLabel(item) }}
                  </option>
                </select>
              </label>
              <label>
                <span>Status</span>
                <select v-model="selectedStatusFilter">
                  <option value="">All statuses</option>
                  <option value="enabled">Enabled</option>
                  <option value="disabled">Disabled</option>
                  <option value="retired">Retired</option>
                </select>
              </label>
            </div>
          </div>
          <div class="record-list product-record-list">
            <button
              v-for="item in pagedProducts"
              :key="item.id"
              :class="{ 'is-selected': selectedId === item.id }"
              type="button"
              @click="editProduct(item)"
            >
              <img
                v-if="productMediaUrl(item.primary_media_id)"
                class="product-media-thumb"
                :src="productMediaUrl(item.primary_media_id)"
                alt=""
                width="52"
                height="52"
              />
              <span v-else class="product-media-thumb product-media-thumb--empty">PR</span>
              <span class="product-record-list__identity">
                <strong>{{ readableItemLabel(item) }}</strong>
                <small>{{ item.slug }} · {{ item.code || 'No code' }}</small>
              </span>
              <span class="product-record-list__status">{{ item.status }}</span>
            </button>
            <p v-if="!pagedProducts.length" class="product-browser__empty">No matching products.</p>
          </div>
          <nav
            v-if="productPages > 1"
            class="product-browser__pagination"
            aria-label="Product list pagination"
          >
            <button type="button" :disabled="productPage <= 1" @click="productPage -= 1">
              Previous
            </button>
            <span>{{ productPage }} / {{ productPages }}</span>
            <button type="button" :disabled="productPage >= productPages" @click="productPage += 1">
              Next
            </button>
          </nav>
        </aside>
        <form class="editor-form" @submit.prevent="saveProduct">
          <label
            >Category
            <select v-model="form.category_id" required>
              <option value="" disabled>Select</option>
              <option v-for="item in categories" :key="item.id" :value="item.id">
                {{ readableItemLabel(item) }} · {{ item.slug }}
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
          <label
            >Primary media
            <select v-model="form.primary_media_id">
              <option value="">No primary media</option>
              <option v-for="item in media" :key="item.id" :value="item.id">
                {{ item.type }} · {{ item.filename }}
              </option>
            </select></label
          >
          <TranslationFields
            v-model="form.translations"
            :locales="locales"
            :extra-fields="[
              { key: 'short_description', label: 'Short description', rows: 2 },
              { key: 'highlights_jsonb', label: 'Highlights · one item per line', rows: 5 },
            ]"
          />
          <div class="form-actions">
            <button type="submit">{{ selectedId ? 'Save changes' : 'Create product' }}</button
            ><button v-if="selectedId" type="button" class="danger" @click="archiveProduct">
              Archive
            </button>
          </div>
        </form>
      </div>
      <section v-if="selectedId" class="sub-editor">
        <h2>Translation review &amp; publication</h2>
        <div v-for="locale in locales" :key="locale.id" class="lifecycle-row">
          <p>
            <strong>{{ locale.native_name }}</strong>
            · translation {{ lifecycleStatus(translationStatuses, locale.id, 'missing') }} ·
            publication {{ lifecycleStatus(publications, locale.id, 'draft') }}
            · route
            {{
              routeStatus(locale.id)?.active && routeStatus(locale.id)?.indexable
                ? 'public'
                : 'inactive/noindex'
            }}
          </p>
          <div class="form-actions">
            <button
              v-if="
                ['draft', 'machine_translated'].includes(
                  lifecycleStatus(translationStatuses, locale.id, 'missing'),
                )
              "
              type="button"
              @click="reviewTranslation(locale.id)"
            >
              Mark human reviewed
            </button>
            <button
              v-if="lifecycleStatus(publications, locale.id, 'draft') === 'review'"
              type="button"
              @click="transitionPublication(locale.id, 'published')"
            >
              Publish
            </button>
            <button
              v-if="lifecycleStatus(publications, locale.id, 'draft') === 'published'"
              type="button"
              class="danger"
              @click="transitionPublication(locale.id, 'archived')"
            >
              Archive publication
            </button>
          </div>
        </div>
      </section>
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
        <p class="sub-editor__intro">
          Search by a readable name or slug, then select one or more linked records.
        </p>
        <div class="relation-picker-grid">
          <label>
            <span>Materials</span>
            <input
              v-model="relationSearch.material_ids"
              type="search"
              placeholder="Filter materials"
            />
            <select v-model="form.material_ids" multiple>
              <option
                v-for="item in filteredRelationOptions('material_ids', materials)"
                :key="item.id"
                :value="item.id"
              >
                {{ readableItemLabel(item) }} · {{ item.slug }}
              </option>
            </select>
          </label>
          <label>
            <span>Technologies</span>
            <input
              v-model="relationSearch.technology_ids"
              type="search"
              placeholder="Filter technologies"
            />
            <select v-model="form.technology_ids" multiple>
              <option
                v-for="item in filteredRelationOptions('technology_ids', technologies)"
                :key="item.id"
                :value="item.id"
              >
                {{ readableItemLabel(item) }} · {{ item.slug }}
              </option>
            </select>
          </label>
          <label>
            <span>Applications</span>
            <input
              v-model="relationSearch.application_ids"
              type="search"
              placeholder="Filter applications"
            />
            <select v-model="form.application_ids" multiple>
              <option
                v-for="item in filteredRelationOptions('application_ids', applications)"
                :key="item.id"
                :value="item.id"
              >
                {{ readableItemLabel(item) }} · {{ item.slug }}
              </option>
            </select>
          </label>
          <label>
            <span>Solutions</span>
            <input
              v-model="relationSearch.solution_ids"
              type="search"
              placeholder="Filter solutions"
            />
            <select v-model="form.solution_ids" multiple>
              <option
                v-for="item in filteredRelationOptions('solution_ids', solutions)"
                :key="item.id"
                :value="item.id"
              >
                {{ readableItemLabel(item) }} · {{ item.slug }}
              </option>
            </select>
          </label>
        </div>
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

<style scoped>
/* 产品浏览器：在一屏内完成搜索、筛选、定位与状态识别。 */
.product-browser {
  position: sticky;
  top: 1rem;
  align-self: start;
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--line, #dce6f0);
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #fff 100%);
  box-shadow: 0 18px 45px rgb(15 45 80 / 8%);
}

.product-browser__filters,
.product-browser__filters label,
.product-record-list__identity,
.relation-picker-grid label {
  display: grid;
}

.product-browser__filters {
  gap: 0.7rem;
}

.product-browser__filters > div {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.product-browser__filters label,
.relation-picker-grid label {
  gap: 0.38rem;
  color: #36506b;
  font-size: 0.76rem;
  font-weight: 750;
  letter-spacing: 0.03em;
}

.product-browser__filters input,
.product-browser__filters select,
.relation-picker-grid input,
.relation-picker-grid select {
  width: 100%;
  border: 1px solid #cbd9e7;
  border-radius: 10px;
  background: #fff;
  color: #10263e;
}

.product-browser__filters input,
.product-browser__filters select,
.relation-picker-grid input {
  min-height: 2.55rem;
  padding: 0.55rem 0.68rem;
}

.product-record-list {
  display: grid;
  gap: 0.48rem;
}

.product-record-list button {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) auto;
  gap: 0.7rem;
  align-items: center;
  width: 100%;
  padding: 0.58rem;
  border: 1px solid transparent;
  border-radius: 13px;
  background: transparent;
  color: #10263e;
  text-align: left;
}

.product-record-list button:hover,
.product-record-list button.is-selected {
  border-color: #77aee7;
  background: #eaf4ff;
}

.product-media-thumb {
  width: 52px;
  height: 52px;
  border: 1px solid #d5e2ee;
  border-radius: 11px;
  background: #eef4f9;
  object-fit: cover;
}

.product-media-thumb--empty {
  display: grid;
  place-items: center;
  color: #5a7188;
  font-size: 0.72rem;
  font-weight: 800;
}

.product-record-list__identity {
  min-width: 0;
  gap: 0.18rem;
}

.product-record-list__identity strong,
.product-record-list__identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-record-list__identity strong {
  font-size: 0.86rem;
}

.product-record-list__identity small {
  color: #6b7f93;
  font-size: 0.7rem;
}

.product-record-list__status {
  padding: 0.24rem 0.45rem;
  border-radius: 999px;
  background: #dff7e9;
  color: #176a42;
  font-size: 0.65rem;
  font-weight: 800;
  text-transform: uppercase;
}

.product-browser__pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  color: #526a82;
  font-size: 0.76rem;
}

.product-browser__pagination button {
  min-height: 2.2rem;
  padding: 0 0.7rem;
}

.product-browser__empty,
.sub-editor__intro {
  color: #667b90;
  font-size: 0.82rem;
}

/* 关系选择器：用可读名称检索，避免将 UUID 暴露给日常编辑人员。 */
.relation-picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.relation-picker-grid select {
  min-height: 10rem;
  padding: 0.45rem;
}

@media (max-width: 900px) {
  .product-browser {
    position: static;
  }

  .relation-picker-grid {
    grid-template-columns: 1fr;
  }
}
</style>
