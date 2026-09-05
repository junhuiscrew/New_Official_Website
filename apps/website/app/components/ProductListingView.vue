<!-- 组件职责：组合产品筛选、公开卡片、空态和 canonical 分页，不持有 URL 状态。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type {
  LocaleSlug,
  ProductFilterOptions,
  ProductFilters,
  PublicCollectionDto,
} from '~/types/public'

import EmptyState from './EmptyState.vue'
import FilterBar from './FilterBar.vue'
import PaginationNav from './PaginationNav.vue'
import ProductCard from './ProductCard.vue'
import PublicBreadcrumb from './PublicBreadcrumb.vue'
import PublicGeoContent from './PublicGeoContent.vue'

const props = defineProps<{
  locale: LocaleSlug
  collection: PublicCollectionDto
  filters: ProductFilters
  options: ProductFilterOptions
  basePath: string
  paginationQuery?: Partial<ProductFilters>
  title?: string
  intro?: string | null
  breadcrumb?: Array<{ name: string; url: string }>
  geo?: {
    direct_answer?: string | null
    key_facts?: string[]
    evidence?: string[]
    related_questions?: string[]
    last_reviewed_at?: string | null
  } | null
}>()
const emit = defineEmits<{
  filterChange: [value: ProductFilters & { page: 1 }]
}>()
const labels = computed(() => ui[props.locale])
</script>

<template>
  <main id="main-content" class="product-listing public-content-page">
    <div v-if="breadcrumb?.length" class="public-container product-listing__breadcrumb">
      <PublicBreadcrumb :items="breadcrumb" />
    </div>
    <header class="product-listing__header public-container">
      <p class="eyebrow">{{ labels.navigation.products }}</p>
      <h1>{{ title ?? labels.products.title }}</h1>
      <p>{{ intro ?? labels.products.intro }}</p>
    </header>
    <div v-if="geo" class="public-container product-listing__geo">
      <PublicGeoContent :geo="geo" />
    </div>
    <section class="public-container product-listing__content" aria-label="Product results">
      <FilterBar
        :locale="locale"
        :model-value="filters"
        :options="options"
        @change="emit('filterChange', $event)"
      />
      <div v-if="collection.items.length" class="product-listing__grid">
        <ProductCard
          v-for="item in collection.items"
          :key="`${item.type}:${item.slug}`"
          :item="item"
          :locale="locale"
        />
      </div>
      <EmptyState v-else :locale="locale" kind="products" />
      <PaginationNav
        :locale="locale"
        :base-path="basePath"
        :page="collection.page"
        :pages="collection.pages"
        :page-size="collection.page_size"
        :query="paginationQuery ?? filters"
      />
    </section>
  </main>
</template>

<style scoped>
.product-listing__header {
  padding-block: var(--space-12) var(--space-8);
  display: grid;
  gap: var(--space-3);
}

.product-listing__breadcrumb {
  padding-block-start: var(--space-4);
}

.product-listing__geo {
  padding-block-end: var(--space-8);
}

.product-listing__header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}

.product-listing__content {
  padding-block-end: var(--space-16);
  display: grid;
  gap: var(--space-8);
}

.product-listing__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

@media (max-width: 64rem) {
  .product-listing__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 40rem) {
  .product-listing__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
