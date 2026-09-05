<!-- 组件职责：把后端用于 FAQPage Schema 的同一问答数组完整呈现为可访问折叠内容。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicFaqDto } from '~/types/public'

const props = defineProps<{ locale: LocaleSlug; items: PublicFaqDto[] }>()
const labels = computed(() => ui[props.locale])
</script>

<template>
  <section
    v-if="items.length"
    class="faq-accordion"
    aria-labelledby="authority-faq-heading"
    data-schema-contract="same-items"
  >
    <h2 id="authority-faq-heading">{{ labels.content.faq }}</h2>
    <details v-for="item in items" :key="item.question">
      <summary>{{ item.question }}</summary>
      <p>{{ item.answer }}</p>
    </details>
  </section>
</template>

<style scoped>
.faq-accordion {
  display: grid;
  gap: var(--space-4);
}

.faq-accordion details {
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: var(--border-subtle);
}

.faq-accordion summary {
  color: var(--color-navy-900);
  font-weight: 750;
  cursor: pointer;
}

.faq-accordion details p {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-700);
}
</style>
