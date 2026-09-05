<!-- 页面用途：按 URL 查询参数服务端渲染全部公开产品，并提供三项轻量筛选。 -->
<script setup lang="ts">
import { computed } from 'vue'

import ProductListingView from '~/components/ProductListingView.vue'
import { normalizeLocale } from '~/composables/useLocalePath'
import type {
  ProductFilterOptions,
  ProductFilters,
  PublicCollectionDto,
  PublicLinkDto,
} from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const locale = normalizeLocale(route.params.lang)

/** 将未知 query 值归一化为单个公开 slug。 */
function queryText(value: unknown): string {
  const candidate = Array.isArray(value) ? value[0] : value
  return typeof candidate === 'string' ? candidate.trim() : ''
}

/** 严格解析公开分页参数，SSR 直达非法值时返回明确 400。 */
function positiveInteger(value: unknown, fallback: number, maximum?: number): number {
  const raw = queryText(value)
  if (!raw) return fallback
  if (!/^\d+$/.test(raw))
    throw createError({ statusCode: 400, statusMessage: 'Invalid pagination' })
  const parsed = Number(raw)
  if (parsed < 1 || (maximum !== undefined && parsed > maximum)) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid pagination' })
  }
  return parsed
}

/** 从 Nuxt/$fetch 错误中保留后端真实 HTTP 状态。 */
function requestStatus(value: unknown): number {
  if (!value || typeof value !== 'object') return 500
  const candidate = value as {
    statusCode?: number
    status?: number
    response?: { status?: number }
  }
  return candidate.statusCode ?? candidate.status ?? candidate.response?.status ?? 500
}

const filters = computed<ProductFilters>(() => ({
  category: queryText(route.query.category),
  material: queryText(route.query.material),
  application: queryText(route.query.application),
}))
const page = computed(() => positiveInteger(route.query.page, 1))
const pageSize = computed(() => positiveInteger(route.query.page_size, 24, 48))
const requestQuery = computed(() => ({
  page: page.value,
  page_size: pageSize.value,
  category: filters.value.category || undefined,
  material: filters.value.material || undefined,
  application: filters.value.application || undefined,
}))

/** 将公开链接集合转为 FilterBar 使用的 slug/name 选项。 */
function filterOptions(items: PublicLinkDto[]): Array<{ value: string; label: string }> {
  return items.map((item) => ({ value: item.slug, label: item.name }))
}

const { data: response, error } = await useAsyncData(
  `products:${locale}:${route.fullPath}`,
  async () => {
    const [products, categories, materials, applications] = await Promise.all([
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
    ])
    const options: ProductFilterOptions = {
      categories: filterOptions(categories.data.items),
      materials: filterOptions(materials.data.items),
      applications: filterOptions(applications.data.items),
    }
    return { collection: products.data, options }
  },
  { watch: [requestQuery] },
)
if (error.value || !response.value) {
  const statusCode = requestStatus(error.value)
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Products not found' : 'Products could not be loaded',
  })
}
const pageData = computed(() => response.value!)

// 列表页只序列化后端返回的 SEO DTO，不在 Vue 生成 Schema 或索引规则。
useHead(() => {
  const seo = pageData.value.collection.seo
  if (!seo) return { htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' } }
  return {
    htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
    title: seo.title,
    meta: [
      ...(seo.description ? [{ name: 'description', content: seo.description }] : []),
      { name: 'robots', content: seo.robots },
    ],
    link: [
      { rel: 'canonical', href: seo.canonical },
      ...Object.entries(seo.hreflang ?? {}).map(([hreflang, href]) => ({
        rel: 'alternate' as const,
        hreflang,
        href,
      })),
    ],
    script: pageData.value.collection.schema
      ? [
          {
            type: 'application/ld+json',
            innerHTML: serializeJsonLd(pageData.value.collection.schema),
          },
        ]
      : [],
  }
})

/** 把筛选变更写回 URL，并按契约将 page 重置为 1。 */
async function onFilterChange(next: ProductFilters & { page: 1 }): Promise<void> {
  await navigateTo({
    path: `/${locale}/products/`,
    query: {
      category: next.category || undefined,
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
    :options="pageData.options"
    :base-path="`/${locale}/products/`"
    :breadcrumb="pageData.collection.breadcrumb"
    @filter-change="onFilterChange"
  />
</template>
