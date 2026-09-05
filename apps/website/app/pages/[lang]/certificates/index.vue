<!-- 页面用途：聚合展示已发布 Certificate，不生成 Certificate 详情路由。 -->
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
  computed(() => `trust:certificates:${locale.value}`),
  () => api<Envelope<PublicTrustListItemDto[]>>(`/public/trust/certificates/${locale.value}`),
)
const { data: metadataResponse, error: metadataError } = await useAsyncData(
  computed(() => `page-metadata:certificates:${locale.value}`),
  () => api<Envelope<PublicPageMetadataDto>>(`/public/page-metadata/certificates/${locale.value}`),
)
if (error.value || metadataError.value || !metadataResponse.value?.data)
  throw createError({ statusCode: 500, statusMessage: 'Certificates unavailable' })
const items = computed(() => response.value?.data ?? [])
const metadata = computed(() => metadataResponse.value!.data)

// 聚合页 Head 只序列化后端页面元数据。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
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
  <div class="trust-aggregate">
    <div class="public-container trust-aggregate__breadcrumb">
      <PublicBreadcrumb :items="metadata.breadcrumb" />
    </div>
    <header class="public-container trust-aggregate__header">
      <p class="eyebrow">{{ labels.navigation.about }}</p>
      <h1>{{ labels.trust.certificatesTitle }}</h1>
      <p>{{ labels.trust.certificatesIntro }}</p>
    </header>
    <section class="public-container trust-aggregate__content">
      <div v-if="items.length" class="trust-aggregate__grid">
        <TrustRecordCard
          v-for="item in items"
          :key="item.slug"
          :locale="locale"
          :item="item"
          :details="item.details"
        />
      </div>
      <EmptyState v-else :locale="locale" kind="certificates" />
    </section>
  </div>
</template>

<style scoped>
.trust-aggregate__header,
.trust-aggregate__content {
  display: grid;
  gap: var(--space-6);
}
.trust-aggregate__breadcrumb {
  padding-block: var(--space-4);
}
.trust-aggregate__header {
  padding-block: var(--space-12) var(--space-8);
}
.trust-aggregate__header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}
.trust-aggregate__content {
  padding-block-end: var(--space-16);
}
.trust-aggregate__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}
@media (max-width: 48rem) {
  .trust-aggregate__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
