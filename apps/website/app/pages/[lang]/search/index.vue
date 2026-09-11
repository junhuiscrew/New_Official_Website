<!-- 页面用途：服务端渲染八类公开内容搜索，并提供可取消、可清除的分页体验。 -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { normalizeLocale } from '~/composables/useLocalePath'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import { SITE_URL } from '~/site-config'
import type { PublicLinkDto, PublicSearchDto, PublicSearchType } from '~/types/public'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

interface SearchGroup {
  type: PublicSearchType
  title: string
  items: PublicLinkDto[]
}

const SEARCH_TYPES: PublicSearchType[] = [
  'product',
  'material',
  'technology',
  'application',
  'solution',
  'manufacturing_capability',
  'case_study',
  'knowledge_article',
]
const PAGE_SIZE = 12

const route = useRoute()
const api = useApi()
const locale = normalizeLocale(route.params.lang)
const labels = computed(() => ui[locale])
const query = computed(() =>
  String(route.query.q ?? '')
    .trim()
    .slice(0, 200),
)
const requestedPage = computed(() => {
  const parsed = Number.parseInt(String(route.query.page ?? '1'), 10)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1
})
const searchInput = ref(query.value)
const telemetry = useTelemetry()
const canonical = computed(() => {
  const base = `${SITE_URL}/${locale}/search/`
  return query.value ? `${base}?${new URLSearchParams({ q: query.value }).toString()}` : base
})

const emptySearch = (): Envelope<PublicSearchDto> => ({
  success: true,
  data: {
    query: query.value,
    items: [],
    groups: {
      product: [],
      material: [],
      technology: [],
      application: [],
      solution: [],
      manufacturing_capability: [],
      knowledge_article: [],
      case_study: [],
    },
    page: requestedPage.value,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  },
  error: null,
})

// 查询词进入 AsyncData key，确保 SSR HTML 与当前 URL 一致；短词不会请求后端。
const searchKey = computed(() => `search:${locale}:${query.value}:${requestedPage.value}`)
const {
  data: response,
  error,
  status,
} = await useAsyncData(
  searchKey,
  () =>
    query.value.length >= 2
      ? api<Envelope<PublicSearchDto>>(`/public/search/${locale}`, {
          query: { q: query.value, page: requestedPage.value, page_size: PAGE_SIZE },
        })
      : Promise.resolve(emptySearch()),
  { watch: [query, requestedPage], dedupe: 'cancel' },
)

watch(query, (value) => {
  searchInput.value = value
})

const allResults = computed(() => response.value?.data.items ?? [])
const totalResults = computed(() => response.value?.data.total ?? 0)
const totalPages = computed(() => response.value?.data.pages ?? 0)
const currentPage = computed(() => response.value?.data.page ?? requestedPage.value)
const visibleGroups = computed<SearchGroup[]>(() => {
  const titles: Record<PublicSearchType, string> = {
    product: labels.value.search.products,
    material: labels.value.search.materials,
    technology: labels.value.search.technologies,
    application: labels.value.search.applications,
    solution: labels.value.search.solutions,
    manufacturing_capability: labels.value.search.capabilities,
    knowledge_article: labels.value.search.knowledge,
    case_study: labels.value.search.cases,
  }
  return SEARCH_TYPES.map((type) => ({
    type,
    title: titles[type],
    items: allResults.value.filter((item) => item.type === type),
  })).filter((group) => group.items.length > 0)
})

/** 提交公开搜索；遥测只记录语言，不发送查询词。 */
async function submitSearch(): Promise<void> {
  const nextQuery = searchInput.value.trim().slice(0, 200)
  telemetry.track('search_submit', { locale })
  await navigateTo({
    path: `/${locale}/search/`,
    query: nextQuery ? { q: nextQuery } : {},
  })
}

/** 清空当前查询并回到未输入状态，不保留旧页码或旧结果。 */
async function clearSearch(): Promise<void> {
  searchInput.value = ''
  await navigateTo({ path: `/${locale}/search/` })
}

/** 创建始终保留查询词的分页目标。 */
function pageTarget(page: number) {
  return { path: `/${locale}/search/`, query: { q: query.value, page: String(page) } }
}

useHead(() => ({
  htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
  title: labels.value.search.title,
  meta: [{ name: 'robots', content: 'noindex,follow' }],
  link: [{ rel: 'canonical', href: canonical.value }],
}))
</script>

<template>
  <div class="search-page">
    <div class="public-container">
      <header class="search-page__header">
        <p class="eyebrow">{{ labels.navigation.search }}</p>
        <h1>{{ labels.search.title }}</h1>
      </header>

      <form class="search-page__form" role="search" @submit.prevent="submitSearch">
        <label for="public-search-query">{{ labels.search.label }}</label>
        <div>
          <input
            id="public-search-query"
            v-model="searchInput"
            name="q"
            type="search"
            minlength="2"
            maxlength="200"
            autocomplete="off"
            :placeholder="labels.search.placeholder"
          />
          <button type="submit">{{ labels.cta.search }}</button>
          <button
            v-if="searchInput || query"
            class="search-page__clear"
            type="button"
            @click="clearSearch"
          >
            {{ labels.search.clear }}
          </button>
        </div>
      </form>

      <p v-if="query && status !== 'pending'" class="search-page__summary">
        {{ labels.search.resultsFor }} “{{ query }}” · {{ totalResults }}
        {{ labels.search.resultCount }}
      </p>
      <p v-if="error" class="search-page__notice status-error" role="alert">
        {{ labels.error.loadingFailed }}
      </p>
      <p
        v-else-if="status === 'pending' && query.length >= 2"
        class="search-page__notice"
        role="status"
      >
        {{ labels.search.loading }}
      </p>
      <p v-else-if="query.length < 2" class="search-page__notice" role="status">
        {{ labels.search.prompt }}
      </p>

      <div v-else-if="visibleGroups.length" class="search-page__groups">
        <section v-for="group in visibleGroups" :key="group.type">
          <h2>{{ group.title }}</h2>
          <ul>
            <li v-for="item in group.items" :key="`${item.type}:${item.slug}`">
              <article>
                <span class="search-page__type">{{ group.title }}</span>
                <h3>
                  <a :href="item.url">{{ item.name }}</a>
                </h3>
                <p v-if="item.summary">{{ item.summary }}</p>
              </article>
            </li>
          </ul>
        </section>
      </div>

      <section v-else class="search-page__empty" role="status">
        <h2>{{ labels.empty.searchResults }}</h2>
        <p>{{ labels.error.recovery }}</p>
        <nav :aria-label="labels.error.recovery">
          <a :href="`/${locale}/products/`">{{ labels.navigation.products }}</a>
          <a :href="`/${locale}/knowledge/`">{{ labels.navigation.knowledge }}</a>
          <a :href="`/${locale}/request-a-quote/`">{{ labels.cta.requestQuote }}</a>
        </nav>
      </section>

      <nav
        v-if="totalPages > 1"
        class="search-page__pagination"
        :aria-label="labels.pagination.label"
      >
        <NuxtLink v-if="currentPage > 1" :to="pageTarget(currentPage - 1)">
          {{ labels.pagination.previous }}
        </NuxtLink>
        <span aria-current="page">
          {{ labels.pagination.page }} {{ currentPage }} / {{ totalPages }}
        </span>
        <NuxtLink v-if="currentPage < totalPages" :to="pageTarget(currentPage + 1)">
          {{ labels.pagination.next }}
        </NuxtLink>
      </nav>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  padding-block: var(--space-12) var(--space-20);
  background: var(--color-neutral-50);
}

.search-page__header,
.search-page__form,
.search-page__groups,
.search-page__empty {
  display: grid;
  gap: var(--space-4);
}

.search-page__form {
  max-width: 52rem;
  margin-block-start: var(--space-8);
}

.search-page__form > div {
  display: flex;
  gap: var(--space-3);
}

.search-page__form button,
.search-page__pagination a {
  padding: var(--space-3) var(--space-5);
  color: var(--color-white);
  font-weight: 700;
  text-decoration: none;
  background: var(--color-blue-700);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.search-page__form .search-page__clear {
  color: var(--color-navy-900);
  background: var(--color-white);
  border: var(--border-subtle);
}

.search-page__summary,
.search-page__notice {
  margin-block-start: var(--space-6);
}

.search-page__notice {
  padding: var(--space-4);
}

.search-page__groups {
  margin-block-start: var(--space-10);
  gap: var(--space-10);
}

.search-page__groups ul {
  margin-block-start: var(--space-5);
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  list-style: none;
}

.search-page__groups article {
  height: 100%;
  padding: var(--space-5);
  display: grid;
  gap: var(--space-3);
  background: var(--color-white);
  border-block-start: 3px solid var(--color-blue-600);
  box-shadow: var(--shadow-sm);
}

.search-page__type {
  color: var(--color-blue-700);
  font-size: var(--font-size-small);
  font-weight: 700;
}

.search-page__groups h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.search-page__empty {
  margin-block-start: var(--space-10);
  padding: var(--space-8);
  background: var(--color-white);
  border: var(--border-subtle);
}

.search-page__empty nav,
.search-page__pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-5);
}

.search-page__pagination {
  justify-content: center;
  margin-block-start: var(--space-10);
}

@media (max-width: 40rem) {
  .search-page__form > div {
    align-items: stretch;
    flex-direction: column;
  }

  .search-page__groups ul {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
