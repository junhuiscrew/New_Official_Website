<!-- 组件职责：兼容旧页面组件名，并转交统一 FAQAccordion 可见渲染。 -->
<script setup lang="ts">
import type { LocaleSlug, PublicFaqDto } from '~/types/public'

withDefaults(defineProps<{ items: PublicFaqDto[]; locale?: LocaleSlug }>(), { locale: 'en' })
</script>

<template>
  <FAQAccordion :locale="locale" :items="items" />
</template>
