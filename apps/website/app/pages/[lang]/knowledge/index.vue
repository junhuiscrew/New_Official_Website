<!-- 页面用途：服务端渲染已发布 Knowledge 列表、分类筛选与稳定分页。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCollectionDto } from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const locale = computed<LocaleSlug>(() => normalizeLocale(route.params.lang))
const labels = computed(() => ui[locale.value])

/** 将外部 query 约束为 API 接受的正整数。 */
function positiveInteger(value: unknown, fallback: number, maximum?: number): number {
  const candidate = Array.isArray(value) ? value[0] : value
  const parsed = typeof candidate === 'string' ? Number.parseInt(candidate, 10) : Number.NaN
  const safe = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
  return maximum ? Math.min(maximum, safe) : safe
}

/** 只回显单个分类 slug，不把任意数组或超长值发给 Public API。 */
function singleQuery(value: unknown, maximum: number): string {
  const candidate = Array.isArray(value) ? value[0] : value
  return typeof candidate === 'string' ? candidate.trim().slice(0, maximum) : ''
}

const requestedPage = computed(() => positiveInteger(route.query.page, 1))
const requestedPageSize = computed(() => positiveInteger(route.query.page_size, 24, 48))
const selectedCategory = computed(() => singleQuery(route.query.category, 120))
const requestKey = computed(
  () =>
    `authority:list:knowledge:${locale.value}:${selectedCategory.value}:${requestedPage.value}:${requestedPageSize.value}`,
)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCollectionDto>>(`/public/knowledge/${locale.value}`, {
    query: {
      category: selectedCategory.value || undefined,
      page: requestedPage.value,
      page_size: requestedPageSize.value,
    },
  }),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Knowledge not found' : 'Knowledge unavailable',
  })
}
const collection = computed(() => response.value!.data)

// Index SEO、hreflang 与 Schema 均直接消费后端，不在 Vue 重建索引规则。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: collection.value.seo?.title,
  meta: collection.value.seo
    ? [
        ...(collection.value.seo.description
          ? [{ name: 'description', content: collection.value.seo.description }]
          : []),
        { name: 'robots', content: collection.value.seo.robots },
      ]
    : [],
  link: collection.value.seo
    ? [
        { rel: 'canonical', href: collection.value.seo.canonical },
        ...Object.entries(collection.value.seo.hreflang ?? {}).map(([hreflang, href]) => ({
          rel: 'alternate' as const,
          hreflang,
          href,
        })),
      ]
    : [],
  script: collection.value.schema
    ? [{ type: 'application/ld+json', innerHTML: serializeJsonLd(collection.value.schema) }]
    : [],
}))
</script>

<template>
  <div class="authority-index">
    <div v-if="collection.breadcrumb?.length" class="public-container authority-index__breadcrumb">
      <PublicBreadcrumb :items="collection.breadcrumb" />
    </div>
    <header class="public-container authority-index__header">
      <p class="eyebrow">{{ labels.navigation.knowledge }}</p>
      <h1>{{ labels.authority.knowledgeTitle }}</h1>
      <p>{{ labels.authority.knowledgeIntro }}</p>
    </header>
    <section class="public-container authority-index__content">
      <form class="authority-filter" method="get" :action="`/${locale}/knowledge/`">
        <label>
          <span>{{ labels.authority.categoryFilter }}</span>
          <input
            name="category"
            :value="selectedCategory"
            :placeholder="labels.authority.categoryPlaceholder"
            maxlength="120"
          />
        </label>
        <button type="submit">{{ labels.authority.applyFilter }}</button>
        <a v-if="selectedCategory" :href="`/${locale}/knowledge/`">
          {{ labels.authority.clearFilter }}
        </a>
      </form>
      <div v-if="collection.items.length" class="authority-grid">
        <ArticleCard
          v-for="item in collection.items"
          :key="`${item.type}:${item.slug}`"
          :item="item"
          :locale="locale"
        />
      </div>
      <EmptyState v-else :locale="locale" kind="knowledge" />
      <PaginationNav
        :locale="locale"
        :base-path="`/${locale}/knowledge/`"
        :page="collection.page"
        :pages="collection.pages"
        :page-size="collection.page_size"
        :query="{ category: selectedCategory }"
      />
    </section>
  </div>
</template>

<style scoped>
.authority-index__breadcrumb {
  padding-block: var(--space-4);
}

.authority-index__header,
.authority-index__content {
  display: grid;
  gap: var(--space-6);
}

.authority-index__header {
  padding-block: var(--space-12) var(--space-8);
}

.authority-index__header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}

.authority-index__content {
  padding-block-end: var(--space-16);
}

.authority-filter {
  padding: var(--space-5);
  display: flex;
  align-items: end;
  gap: var(--space-3);
  background: var(--color-neutral-100);
  border: var(--border-subtle);
}

.authority-filter label {
  flex: 1;
  display: grid;
  gap: var(--space-2);
  font-weight: 700;
}

.authority-filter input,
.authority-filter button,
.authority-filter a {
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
}

.authority-filter input {
  width: 100%;
  border: var(--border-strong);
}

.authority-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

@media (max-width: 64rem) {
  .authority-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 40rem) {
  .authority-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .authority-filter {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
