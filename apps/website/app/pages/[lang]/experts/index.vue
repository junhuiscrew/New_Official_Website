<!-- 页面用途：服务端渲染已核验、已授权公开的真实人物列表与职责筛选。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCollectionDto, PublicPersonRole } from '~/types/public'
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

/** 将外部分页 query 约束为 Public API 允许的正整数。 */
function positiveInteger(value: unknown, fallback: number, maximum?: number): number {
  const candidate = Array.isArray(value) ? value[0] : value
  const parsed = typeof candidate === 'string' ? Number.parseInt(candidate, 10) : Number.NaN
  const safe = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
  return maximum ? Math.min(maximum, safe) : safe
}

/** 仅允许后端人物枚举进入筛选，未知输入按无筛选处理。 */
function personType(value: unknown): PublicPersonRole | '' {
  const candidate = Array.isArray(value) ? value[0] : value
  return candidate === 'author' || candidate === 'expert' || candidate === 'author_expert'
    ? candidate
    : ''
}

/** 将公开人物类型映射为本地化标签，避免模板动态访问未知翻译键。 */
function personTypeLabel(value: PublicPersonRole | undefined): string {
  if (value === 'author') return labels.value.authority.authorType
  if (value === 'expert') return labels.value.authority.expertType
  if (value === 'author_expert') return labels.value.authority.authorExpertType
  return ''
}

const requestedPage = computed(() => positiveInteger(route.query.page, 1))
const requestedPageSize = computed(() => positiveInteger(route.query.page_size, 24, 48))
const selectedType = computed(() => personType(route.query.type))
const requestKey = computed(
  () =>
    `authority:list:experts:${locale.value}:${selectedType.value}:${requestedPage.value}:${requestedPageSize.value}`,
)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCollectionDto>>(`/public/experts/${locale.value}`, {
    query: {
      type: selectedType.value || undefined,
      page: requestedPage.value,
      page_size: requestedPageSize.value,
    },
  }),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Experts not found' : 'Experts unavailable',
  })
}
const collection = computed(() => response.value!.data)

// Index SEO、hreflang 与 Schema 直接消费后端，不从人物卡片推导结构化数据。
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
      <p class="eyebrow">{{ labels.authority.expertsTitle }}</p>
      <h1>{{ labels.authority.expertsTitle }}</h1>
      <p>{{ labels.authority.expertsIntro }}</p>
    </header>
    <section class="public-container authority-index__content">
      <form class="authority-filter" method="get" :action="`/${locale}/experts/`">
        <label>
          <span>{{ labels.authority.personTypeFilter }}</span>
          <select name="type" :value="selectedType">
            <option value="">{{ labels.authority.allPersonTypes }}</option>
            <option value="author">{{ labels.authority.authorType }}</option>
            <option value="expert">{{ labels.authority.expertType }}</option>
            <option value="author_expert">{{ labels.authority.authorExpertType }}</option>
          </select>
        </label>
        <button type="submit">{{ labels.authority.applyFilter }}</button>
        <a v-if="selectedType" :href="`/${locale}/experts/`">
          {{ labels.authority.clearFilter }}
        </a>
      </form>
      <div v-if="collection.items.length" class="authority-grid">
        <article v-for="item in collection.items" :key="`${item.type}:${item.slug}`">
          <p v-if="item.role_type" class="eyebrow">
            {{ personTypeLabel(item.role_type) }}
          </p>
          <h2>
            <a :href="item.url">{{ item.name }}</a>
          </h2>
          <p v-if="item.summary">{{ item.summary }}</p>
        </article>
      </div>
      <EmptyState v-else :locale="locale" kind="generic" />
      <PaginationNav
        :locale="locale"
        :base-path="`/${locale}/experts/`"
        :page="collection.page"
        :pages="collection.pages"
        :page-size="collection.page_size"
        :query="{ type: selectedType }"
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

.authority-filter select,
.authority-filter button,
.authority-filter a {
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
}

.authority-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

.authority-grid article {
  padding: var(--space-6);
  border: var(--border-subtle);
  border-block-start: 3px solid var(--color-blue-600);
}

.authority-grid article > * + * {
  margin-block-start: var(--space-3);
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
