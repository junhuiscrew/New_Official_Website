<!-- 组件职责：为首页可选区块提供一致、可访问的标题与简短说明。 -->
<script setup lang="ts">
defineProps<{
  title: string
  description?: string | null
}>()
</script>

<template>
  <header class="section-header">
    <h2>{{ title }}</h2>
    <p v-if="description">{{ description }}</p>
  </header>
</template>

<style scoped>
.section-header {
  display: grid;
  max-width: 46rem;
  gap: var(--space-3);
  margin-block-end: var(--space-8);
}

.section-header p {
  color: var(--color-neutral-600);
  font-size: 1.0625rem;
}
</style>
