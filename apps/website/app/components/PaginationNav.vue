<!-- 组件职责：以可抓取的 canonical anchor 提供分页，并保留公开筛选参数。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, ProductFilters } from '~/types/public'

const props = defineProps<{
  locale: LocaleSlug
  basePath: string
  page: number
  pages: number
  pageSize: number
  query?: Partial<ProductFilters>
}>()
const labels = computed(() => ui[props.locale])
const safePageSize = computed(() => Math.min(48, Math.max(1, Math.trunc(props.pageSize))))
const visiblePages = computed(() =>
  Array.from({ length: Math.max(0, props.pages) }, (_, index) => index + 1),
)

/** 为每个可索引分页生成稳定 href，不依赖客户端点击处理。 */
function pageHref(page: number): string {
  const query = new URLSearchParams()
  for (const key of ['category', 'material', 'application'] as const) {
    const value = props.query?.[key]?.trim()
    if (value) query.set(key, value)
  }
  query.set('page', String(page))
  query.set('page_size', String(safePageSize.value))
  return `${props.basePath}?${query.toString()}`
}
</script>

<template>
  <nav v-if="pages > 1" class="pagination" aria-label="Pagination">
    <a v-if="page > 1" rel="prev" :href="pageHref(page - 1)">{{ labels.pagination.previous }}</a>
    <ol>
      <li v-for="pageNumber in visiblePages" :key="pageNumber">
        <a
          :href="pageHref(pageNumber)"
          :aria-current="pageNumber === page ? 'page' : undefined"
          :aria-label="`${labels.pagination.page} ${pageNumber}`"
        >
          {{ pageNumber }}
        </a>
      </li>
    </ol>
    <a v-if="page < pages" rel="next" :href="pageHref(page + 1)">{{ labels.pagination.next }}</a>
  </nav>
</template>

<style scoped>
.pagination,
.pagination ol {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.pagination ol {
  margin: 0;
  padding: 0;
  list-style: none;
}

.pagination a {
  min-width: 2.75rem;
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
  display: inline-grid;
  place-items: center;
  color: var(--color-blue-700);
  text-decoration: none;
  border: var(--border-subtle);
}

.pagination a[aria-current='page'] {
  color: var(--color-white);
  background: var(--color-blue-700);
  border-color: var(--color-blue-700);
}
</style>
