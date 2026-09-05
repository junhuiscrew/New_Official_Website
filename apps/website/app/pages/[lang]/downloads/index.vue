<!-- 页面用途：SSR 展示后端已核验对象真实存在的 public-media 下载元数据。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale } from '~/composables/useLocalePath'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicDownloadDto, PublicPageMetadataDto } from '~/types/public'
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
const telemetry = useTelemetry()
const { data: response, error } = await useAsyncData(
  computed(() => `public-downloads:${locale.value}`),
  () => api<Envelope<PublicDownloadDto[]>>(`/public/downloads/${locale.value}`),
)
const { data: metadataResponse, error: metadataError } = await useAsyncData(
  computed(() => `page-metadata:downloads:${locale.value}`),
  () => api<Envelope<PublicPageMetadataDto>>(`/public/page-metadata/downloads/${locale.value}`),
)
if (error.value || metadataError.value || !metadataResponse.value?.data)
  throw createError({ statusCode: 500, statusMessage: 'Downloads unavailable' })
const metadata = computed(() => metadataResponse.value!.data)

/** 仅允许后端公开媒体代理 URL，客户端不接受任意对象存储或外站地址。 */
function safeDownloadUrl(url: string): string | null {
  return /^\/api\/v1\/public\/media\/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    url,
  )
    ? url
    : null
}

/** 将后端字节数转换为稳定、可读的文件大小。 */
function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return ''
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = units[0]
  for (let index = 0; index < units.length - 1 && value >= 1024; index += 1) {
    value /= 1024
    unit = units[index + 1]
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`
}

const downloads = computed(() =>
  (response.value?.data ?? []).filter((item) => safeDownloadUrl(item.url) !== null),
)

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
  <div class="downloads-page">
    <div class="public-container downloads-page__breadcrumb">
      <PublicBreadcrumb :items="metadata.breadcrumb" />
    </div>
    <header class="public-container downloads-page__header">
      <p class="eyebrow">{{ labels.navigation.about }}</p>
      <h1>{{ labels.trust.downloadsTitle }}</h1>
      <p>{{ labels.trust.downloadsIntro }}</p>
    </header>
    <section class="public-container downloads-page__content">
      <div v-if="downloads.length" class="downloads-page__list">
        <article v-for="item in downloads" :key="item.slug" class="download-record">
          <div>
            <p class="eyebrow">{{ item.resource_type }}</p>
            <h2>{{ item.title }}</h2>
            <p v-if="item.summary">{{ item.summary }}</p>
          </div>
          <dl>
            <div v-if="item.version_label">
              <dt>{{ labels.trust.version }}</dt>
              <dd>{{ item.version_label }}</dd>
            </div>
            <div v-if="item.published_date">
              <dt>{{ labels.content.published }}</dt>
              <dd>
                <time :datetime="item.published_date">{{ item.published_date }}</time>
              </dd>
            </div>
            <div>
              <dt>{{ labels.trust.fileType }}</dt>
              <dd>{{ item.mime_type }}</dd>
            </div>
            <div>
              <dt>{{ labels.trust.fileSize }}</dt>
              <dd>{{ formatFileSize(item.file_size_bytes) }}</dd>
            </div>
          </dl>
          <a
            class="download-record__action"
            :href="safeDownloadUrl(item.url)!"
            @click="
              telemetry.track('download_click', {
                locale,
                sourceType: 'download_resource',
                sourceSlug: item.slug,
                resourceType: item.resource_type,
              })
            "
          >
            {{ labels.cta.download }}
          </a>
        </article>
      </div>
      <EmptyState v-else :locale="locale" kind="downloads" />
    </section>
  </div>
</template>

<style scoped>
.downloads-page__header,
.downloads-page__content {
  display: grid;
  gap: var(--space-6);
}
.downloads-page__breadcrumb {
  padding-block: var(--space-4);
}
.downloads-page__header {
  padding-block: var(--space-12) var(--space-8);
}
.downloads-page__header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}
.downloads-page__content {
  padding-block-end: var(--space-16);
}
.downloads-page__list {
  display: grid;
  gap: var(--space-5);
}
.download-record {
  padding: var(--space-6);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(15rem, 0.55fr) auto;
  align-items: center;
  gap: var(--space-6);
  border: var(--border-subtle);
}
.download-record > div {
  display: grid;
  gap: var(--space-2);
}
.download-record dl {
  margin: 0;
  display: grid;
  gap: var(--space-2);
}
.download-record dl > div {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.download-record dt,
.download-record dd {
  margin: 0;
}
.download-record dt {
  color: var(--color-neutral-600);
}
.download-record__action {
  min-height: 2.75rem;
  padding: var(--space-3) var(--space-5);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-white);
  font-weight: 750;
  text-decoration: none;
  background: var(--color-blue-600);
  border-radius: var(--radius-sm);
}
@media (max-width: 48rem) {
  .download-record {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
  }
}
</style>
