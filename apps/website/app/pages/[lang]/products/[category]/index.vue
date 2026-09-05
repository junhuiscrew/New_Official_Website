<!-- 页面用途：以 category 路径为主筛选，服务端渲染对应公开产品集合。 -->
<script setup lang="ts">
import { computed, watch } from 'vue'

import ProductListingView from '~/components/ProductListingView.vue'
import { normalizeLocale } from '~/composables/useLocalePath'
import type {
  ProductFilterOptions,
  ProductFilters,
  PublicCollectionDto,
  PublicBreadcrumbDto,
  GeoDto,
  PublicLinkDto,
  SeoDto,
} from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'
import { publicRequestStatus, strictPositiveInteger } from '~/utils/publicRequest'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

interface CategoryPageDto {
  translation: {
    name: string
    short_description?: string | null
    description?: string | null
  }
  seo: SeoDto
  geo: GeoDto | null
  breadcrumb: PublicBreadcrumbDto[]
  schema: unknown
  alternates?: Record<string, string>
}

const route = useRoute()
const api = useApi()
const locale = normalizeLocale(route.params.lang)

/** 将动态参数或查询参数规整为单个字符串。 */
function queryText(value: unknown): string {
  const candidate = Array.isArray(value) ? value[0] : value
  return typeof candidate === 'string' ? candidate.trim() : ''
}

const category = computed(() => queryText(route.params.category))
const filters = computed<ProductFilters>(() => ({
  category: category.value,
  material: queryText(route.query.material),
  application: queryText(route.query.application),
}))
const page = computed(() => strictPositiveInteger(route.query.page, 1))
const pageSize = computed(() => strictPositiveInteger(route.query.page_size, 24, 48))
const requestQuery = computed(() => ({
  page: page.value,
  page_size: pageSize.value,
  category: filters.value.category,
  material: filters.value.material || undefined,
  application: filters.value.application || undefined,
}))

/** 将公开 canonical 链接转换为筛选选项。 */
function filterOptions(items: PublicLinkDto[]): Array<{ value: string; label: string }> {
  return items.map((item) => ({ value: item.slug, label: item.name }))
}

const { data: response, error } = await useAsyncData(
  `products:category:${locale}:${route.fullPath}`,
  async () => {
    const [products, categories, materials, applications, categoryPage] = await Promise.all([
      api<Envelope<PublicCollectionDto>>(`/public/products/${locale}`, {
        query: requestQuery.value,
      }),
      api<Envelope<PublicCollectionDto<PublicLinkDto>>>(`/public/product-categories/${locale}`, {
        query: { page_size: 48 },
      }),
      api<Envelope<PublicCollectionDto<PublicLinkDto>>>(`/public/materials/${locale}`, {
        query: { page_size: 48 },
      }),
      api<Envelope<PublicCollectionDto<PublicLinkDto>>>(`/public/applications/${locale}`, {
        query: { page_size: 48 },
      }),
      api<Envelope<CategoryPageDto>>(`/public/product-categories/${locale}/${category.value}`),
    ])
    const options: ProductFilterOptions = {
      categories: filterOptions(categories.data.items),
      materials: filterOptions(materials.data.items),
      applications: filterOptions(applications.data.items),
    }
    return { collection: products.data, options, categoryPage: categoryPage.data }
  },
  { watch: [requestQuery] },
)
if (error.value || !response.value) {
  const statusCode = publicRequestStatus(error.value)
  throw createError({
    statusCode,
    statusMessage:
      statusCode === 404 ? 'Product category not found' : 'Products could not be loaded',
  })
}
// 分类内筛选 SPA 导航失败时清除旧正文/meta，保留后端 404 与 5xx。
watch(error, (nextError) => {
  if (!nextError) return
  const statusCode = publicRequestStatus(nextError)
  showError(
    createError({
      statusCode,
      statusMessage:
        statusCode === 404 ? 'Product category not found' : 'Products could not be loaded',
    }),
  )
})
const pageData = computed(() => response.value!)

// 分类页继续消费分类详情端点的 canonical、hreflang、robots 与 Schema。
useHead(() => {
  const categoryPage = pageData.value.categoryPage
  const listingSeo = pageData.value.collection.seo
  return {
    htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
    title: categoryPage.seo.title,
    meta: [
      ...(categoryPage.seo.description
        ? [{ name: 'description', content: categoryPage.seo.description }]
        : []),
      { name: 'robots', content: listingSeo?.robots ?? categoryPage.seo.robots },
    ],
    link: [
      { rel: 'canonical', href: listingSeo?.canonical ?? categoryPage.seo.canonical },
      ...Object.entries(
        listingSeo?.hreflang ?? categoryPage.alternates ?? categoryPage.seo.hreflang ?? {},
      ).map(([hreflang, href]) => ({ rel: 'alternate' as const, hreflang, href })),
    ],
    script: [
      {
        type: 'application/ld+json',
        innerHTML: serializeJsonLd(pageData.value.collection.schema),
      },
    ],
  }
})

/** 将筛选变更写入目标分类 URL；清空分类时回到全部产品页。 */
async function onFilterChange(next: ProductFilters & { page: 1 }): Promise<void> {
  const path = next.category
    ? `/${locale}/products/${encodeURIComponent(next.category)}/`
    : `/${locale}/products/`
  await navigateTo({
    path,
    query: {
      material: next.material || undefined,
      application: next.application || undefined,
      page: 1,
      page_size: pageSize.value,
    },
  })
}
</script>

<template>
  <ProductListingView
    :locale="locale"
    :collection="pageData.collection"
    :filters="filters"
    :pagination-query="{ material: filters.material, application: filters.application }"
    :options="pageData.options"
    :base-path="route.path"
    :title="pageData.categoryPage.translation.name"
    :intro="
      pageData.categoryPage.translation.short_description ??
      pageData.categoryPage.translation.description
    "
    :breadcrumb="pageData.collection.breadcrumb"
    :geo="pageData.categoryPage.geo"
    @filter-change="onFilterChange"
  />
</template>
