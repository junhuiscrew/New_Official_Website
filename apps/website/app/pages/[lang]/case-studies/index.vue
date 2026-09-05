<!-- 页面用途：服务端渲染仅含后端隐私白名单内容的已发布案例列表。 -->
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

/** 将不可信分页 query 约束为 Public API 允许的正整数。 */
function positiveInteger(value: unknown, fallback: number, maximum?: number): number {
  const candidate = Array.isArray(value) ? value[0] : value
  const parsed = typeof candidate === 'string' ? Number.parseInt(candidate, 10) : Number.NaN
  const safe = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
  return maximum ? Math.min(maximum, safe) : safe
}

const requestedPage = computed(() => positiveInteger(route.query.page, 1))
const requestedPageSize = computed(() => positiveInteger(route.query.page_size, 24, 48))
const requestKey = computed(
  () => `authority:list:cases:${locale.value}:${requestedPage.value}:${requestedPageSize.value}`,
)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCollectionDto>>(`/public/case-studies/${locale.value}`, {
    query: { page: requestedPage.value, page_size: requestedPageSize.value },
  }),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Case studies not found' : 'Case studies unavailable',
  })
}
const collection = computed(() => response.value!.data)

// Index SEO、hreflang 与 Schema 只序列化后端返回值。
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
      <p class="eyebrow">{{ labels.navigation.caseStudies }}</p>
      <h1>{{ labels.authority.casesTitle }}</h1>
      <p>{{ labels.authority.casesIntro }}</p>
    </header>
    <section class="public-container authority-index__content">
      <div v-if="collection.items.length" class="authority-grid authority-grid--cases">
        <CaseCard
          v-for="item in collection.items"
          :key="`${item.type}:${item.slug}`"
          :item="item"
          :locale="locale"
        />
      </div>
      <EmptyState v-else :locale="locale" kind="cases" />
      <PaginationNav
        :locale="locale"
        :base-path="`/${locale}/case-studies/`"
        :page="collection.page"
        :pages="collection.pages"
        :page-size="collection.page_size"
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

.authority-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}

@media (max-width: 48rem) {
  .authority-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
