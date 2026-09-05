<!-- 页面用途：提供不泄露内部诊断信息的本地化 404/500 恢复页。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { resolveRouteLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'

const { error } = defineProps<{
  error: {
    statusCode: number
  }
}>()

const route = useRoute()
const locale = computed(() => resolveRouteLocale(route.params.lang, route.path))
const labels = computed(() => ui[locale.value])
const isNotFound = computed(() => error.statusCode === 404)
const title = computed(() =>
  isNotFound.value ? labels.value.error.notFound : labels.value.error.serverError,
)

/** 清理 Nuxt 错误状态并返回当前语言首页。 */
async function returnHome(): Promise<void> {
  await clearError({ redirect: `/${locale.value}/` })
}

useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: title.value,
  meta: [{ name: 'robots', content: 'noindex,follow' }],
}))
</script>

<template>
  <main id="main-content" class="error-page">
    <div class="error-page__content">
      <p class="technical-number" aria-hidden="true">{{ isNotFound ? '404' : '500' }}</p>
      <h1>{{ title }}</h1>
      <p>{{ labels.error.recovery }}</p>
      <nav :aria-label="labels.error.recovery">
        <a :href="`/${locale}/products/`">{{ labels.navigation.products }}</a>
        <a :href="`/${locale}/knowledge/`">{{ labels.navigation.knowledge }}</a>
        <a :href="`/${locale}/search/`">{{ labels.navigation.search }}</a>
        <a :href="`/${locale}/request-a-quote/`">{{ labels.cta.requestQuote }}</a>
      </nav>
      <button type="button" @click="returnHome">{{ labels.common.backHome }}</button>
    </div>
  </main>
</template>

<style scoped>
.error-page {
  min-height: 100vh;
  padding: var(--space-8);
  display: grid;
  place-items: center;
  color: var(--color-neutral-800);
  background: var(--color-neutral-50);
}

.error-page__content {
  width: min(100%, 44rem);
  display: grid;
  gap: var(--space-5);
  text-align: center;
}

.error-page .technical-number {
  color: var(--color-blue-700);
  font-size: clamp(3rem, 12vw, 7rem);
  font-weight: 800;
  line-height: 1;
}

.error-page nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-5);
}

.error-page button {
  justify-self: center;
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-5);
  color: var(--color-white);
  font-weight: 700;
  background: var(--color-blue-700);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
</style>
