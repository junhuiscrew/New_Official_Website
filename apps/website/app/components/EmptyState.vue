<!-- 组件职责：为无公开数据的页面提供中性、本地化且不制造业务事实的恢复提示。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug } from '~/types/public'

const props = withDefaults(
  defineProps<{
    locale: LocaleSlug
    kind?: 'generic' | 'products' | 'knowledge' | 'cases' | 'certificates' | 'downloads'
  }>(),
  { kind: 'generic' },
)
const message = computed(() => ui[props.locale].empty[props.kind])
</script>

<template>
  <section class="empty-state" role="status">
    <p>{{ message }}</p>
  </section>
</template>

<style scoped>
.empty-state {
  padding: var(--space-12) var(--space-6);
  color: var(--color-neutral-600);
  text-align: center;
  background: var(--color-neutral-100);
  border: var(--border-subtle);
}
</style>
