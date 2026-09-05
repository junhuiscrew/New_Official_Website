<!-- 页面用途：SSR 展示 route-based Exhibition canonical 列表。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicPageMetadataDto, PublicTrustListItemDto } from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}
const route = useRoute()
const api = useApi()
const locale = computed<LocaleSlug>(() => normalizeLocale(route.params.lang))
const labels = computed(() => ui[locale.value])
const { data: response, error } = await useAsyncData(
  computed(() => `trust:exhibitions:${locale.value}`),
  () => api<Envelope<PublicTrustListItemDto[]>>(`/public/trust/exhibitions/${locale.value}`),
)
const { data: metadataResponse, error: metadataError } = await useAsyncData(
  computed(() => `page-metadata:exhibitions:${locale.value}`),
  () => api<Envelope<PublicPageMetadataDto>>(`/public/page-metadata/exhibitions/${locale.value}`),
)
if (error.value || metadataError.value || !metadataResponse.value?.data)
  throw createError({ statusCode: 500, statusMessage: 'Exhibitions unavailable' })
const items = computed(() => response.value?.data ?? [])
const metadata = computed(() => metadataResponse.value!.data)

// 聚合页 Head 只序列化后端页面元数据。
useHead(() => ({
  title: metadata.value.seo.title,
  meta: [
    { name: 'description', content: metadata.value.seo.description },
    { name: 'robots', content: metadata.value.seo.robots },
  ],
  link: [
    { rel: 'canonical', href: metadata.value.seo.canonical },
    ...Object.entries(metadata.value.seo.hreflang ?? {}).map(([hreflang, href]) => ({
      rel: 'alternate' as const,
      hreflang,
      href,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(metadata.value.schema) }],
}))
</script>

<template>
  <div class="exhibition-index">
    <div class="public-container exhibition-index__breadcrumb">
      <PublicBreadcrumb :items="metadata.breadcrumb" />
    </div>
    <header class="public-container exhibition-index__header">
      <p class="eyebrow">{{ labels.navigation.about }}</p>
      <h1>{{ labels.trust.exhibitionsTitle }}</h1>
      <p>{{ labels.trust.exhibitionsIntro }}</p>
    </header>
    <section class="public-container exhibition-index__content">
      <div v-if="items.length" class="exhibition-index__grid">
        <article v-for="item in items" :key="item.slug" class="exhibition-card">
          <h2>
            <a v-if="item.url" :href="item.url">{{ item.title }}</a>
          </h2>
          <p v-if="item.summary">{{ item.summary }}</p>
        </article>
      </div>
      <EmptyState v-else :locale="locale" />
    </section>
  </div>
</template>

<style scoped>
.exhibition-index__header,
.exhibition-index__content {
  display: grid;
  gap: var(--space-6);
}
.exhibition-index__breadcrumb {
  padding-block: var(--space-4);
}
.exhibition-index__header {
  padding-block: var(--space-12) var(--space-8);
}
.exhibition-index__header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}
.exhibition-index__content {
  padding-block-end: var(--space-16);
}
.exhibition-index__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}
.exhibition-card {
  padding: var(--space-6);
  border: var(--border-subtle);
  border-block-start: 3px solid var(--color-blue-600);
}
.exhibition-card p {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-600);
}
@media (max-width: 48rem) {
  .exhibition-index__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
