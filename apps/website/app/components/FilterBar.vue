<!-- 组件职责：展示三项有业务含义的产品筛选，并把变更交给页面写回 URL。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, ProductFilterOptions, ProductFilters } from '~/types/public'

const props = defineProps<{
  locale: LocaleSlug
  modelValue: ProductFilters
  options: ProductFilterOptions
}>()
const emit = defineEmits<{
  'update:modelValue': [value: ProductFilters]
  change: [value: ProductFilters & { page: 1 }]
}>()
const labels = computed(() => ui[props.locale])

/** 更新单项公开 slug，并强制把分页恢复为第一页。 */
function updateFilter(field: keyof ProductFilters, event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  const next = { ...props.modelValue, [field]: value }
  emit('update:modelValue', next)
  emit('change', { ...next, page: 1 })
}

/** 清空三个筛选并恢复第一页。 */
function clearFilters(): void {
  const next: ProductFilters = { category: '', material: '', application: '' }
  emit('update:modelValue', next)
  emit('change', { ...next, page: 1 })
}
</script>

<template>
  <form class="filter-bar" aria-label="Product filters" @submit.prevent>
    <label>
      <span>{{ labels.products.category }}</span>
      <select
        name="category"
        :value="modelValue.category"
        @change="updateFilter('category', $event)"
      >
        <option value="">{{ labels.products.allCategories }}</option>
        <option v-for="option in options.categories" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label>
      <span>{{ labels.products.material }}</span>
      <select
        name="material"
        :value="modelValue.material"
        @change="updateFilter('material', $event)"
      >
        <option value="">{{ labels.products.allMaterials }}</option>
        <option v-for="option in options.materials" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label>
      <span>{{ labels.products.application }}</span>
      <select
        name="application"
        :value="modelValue.application"
        @change="updateFilter('application', $event)"
      >
        <option value="">{{ labels.products.allApplications }}</option>
        <option v-for="option in options.applications" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <button type="button" @click="clearFilters">{{ labels.products.clearFilters }}</button>
  </form>
</template>

<style scoped>
.filter-bar {
  padding: var(--space-5);
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  align-items: end;
  gap: var(--space-4);
  background: var(--color-neutral-100);
  border: var(--border-subtle);
}

.filter-bar label {
  min-width: 0;
  display: grid;
  gap: var(--space-2);
  color: var(--color-navy-900);
  font-size: var(--font-size-small);
  font-weight: 700;
}

.filter-bar select,
.filter-bar button {
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-3);
  font: inherit;
  border: var(--border-strong);
  border-radius: var(--radius-sm);
}

.filter-bar select {
  width: 100%;
  color: var(--color-neutral-950);
  background: var(--color-white);
}

.filter-bar button {
  color: var(--color-blue-700);
  font-weight: 750;
  background: var(--color-white);
}

@media (max-width: 56rem) {
  .filter-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 36rem) {
  .filter-bar {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
