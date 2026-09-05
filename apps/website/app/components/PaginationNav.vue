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
const currentPage = computed(() =>
  Math.min(Math.max(1, Math.trunc(props.page)), Math.max(1, Math.trunc(props.pages))),
)
type PaginationItem = number | 'start-ellipsis' | 'end-ellipsis'

// 大型集合仅展示首尾页与当前页附近窗口，控制 SSR DOM 大小。
const visiblePages = computed<PaginationItem[]>(() => {
  const totalPages = Math.max(0, Math.trunc(props.pages))
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1)

  const selectedPages = new Set<number>([1, totalPages])
  const windowStart = Math.max(2, currentPage.value - 2)
  const windowEnd = Math.min(totalPages - 1, currentPage.value + 2)
  for (let page = windowStart; page <= windowEnd; page += 1) selectedPages.add(page)

  const sortedPages = [...selectedPages].sort((left, right) => left - right)
  const items: PaginationItem[] = []
  for (const page of sortedPages) {
    const previous = items.at(-1)
    if (typeof previous === 'number' && page - previous > 1)
      items.push(previous === 1 ? 'start-ellipsis' : 'end-ellipsis')
    items.push(page)
  }
  return items
})

/** 为每个可索引分页生成稳定 href，不依赖客户端点击处理。 */
function pageHref(page: number): string {
  const query = new URLSearchParams()
  for (const key of ['category', 'material', 'application'] as const) {
    const value = props.query?.[key]?.trim()
    if (value) query.set(key, value)
  }
  // 与后端 canonical 规则一致：第一页与默认分页大小不写入查询参数。
  if (page > 1) query.set('page', String(page))
  if (safePageSize.value !== 24) query.set('page_size', String(safePageSize.value))
  const queryString = query.toString()
  return queryString ? `${props.basePath}?${queryString}` : props.basePath
}
</script>

<template>
  <nav v-if="pages > 1" class="pagination" :aria-label="labels.pagination.label">
    <a v-if="page > 1" rel="prev" :href="pageHref(page - 1)">{{ labels.pagination.previous }}</a>
    <ol>
      <li v-for="item in visiblePages" :key="item">
        <a
          v-if="typeof item === 'number'"
          :href="pageHref(item)"
          :aria-current="item === currentPage ? 'page' : undefined"
          :aria-label="`${labels.pagination.page} ${item}`"
        >
          {{ item }}
        </a>
        <span v-else aria-hidden="true">…</span>
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
