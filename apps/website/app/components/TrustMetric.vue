<!-- 组件职责：原样呈现 Public DTO 提供的单项可信度标签和值，不推导或补造业务事实。 -->
<script setup lang="ts">
defineProps<{ label: string; value: string }>()
</script>

<template>
  <div class="trust-metric">
    <dt>{{ label }}</dt>
    <dd class="technical-number">{{ value }}</dd>
  </div>
</template>

<style scoped>
.trust-metric {
  min-width: 0;
  padding-inline-start: var(--space-4);
  border-inline-start: 3px solid var(--color-blue-600);
}

.trust-metric dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.trust-metric dd {
  margin: var(--space-1) 0 0;
  color: var(--color-navy-900);
  font-size: clamp(1.125rem, 2vw, 1.5rem);
  font-weight: 750;
}
</style>
