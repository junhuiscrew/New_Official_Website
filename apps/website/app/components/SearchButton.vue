<!-- 组件职责：提供本地化搜索页导航入口，不在 Header 内启动客户端搜索应用。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug } from '~/types/public'

const props = defineProps<{ locale: LocaleSlug }>()
const label = computed(() => ui[props.locale].navigation.search)
</script>

<template>
  <a class="search-button" :href="`/${locale}/search/`" :aria-label="label">
    <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
    <span>{{ label }}</span>
  </a>
</template>

<style scoped>
.search-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: inherit;
  text-decoration: none;
}

svg {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}
</style>
