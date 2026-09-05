<!-- 页面用途：SSR 展示后端发布门禁批准的 Exhibition canonical 详情。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicExhibitionDetailDto } from '~/types/public'
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
const slug = computed(() => String(route.params.slug ?? ''))
const { data: response, error } = await useAsyncData(
  computed(() => `exhibition:${locale.value}:${slug.value}`),
  () =>
    api<Envelope<PublicExhibitionDetailDto>>(
      `/public/trust/exhibitions/${locale.value}/${slug.value}`,
    ),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Exhibition not found' : 'Exhibition unavailable',
  })
}
const page = computed(() => response.value!.data)

const detailLabels = computed<Record<string, string>>(() => ({
  event_name: labels.value.trust.exhibitionsTitle,
  country_code: labels.value.content.country,
  city: locale.value === 'zh-cn' ? '城市' : 'City',
  start_date: locale.value === 'zh-cn' ? '开始日期' : 'Start Date',
  end_date: locale.value === 'zh-cn' ? '结束日期' : 'End Date',
  booth_no: locale.value === 'zh-cn' ? '展位号' : 'Booth',
}))

/** 仅显示后端 Exhibition details 白名单中的非空事实。 */
const visibleDetails = computed(() =>
  Object.entries(page.value.details)
    .filter(([key, value]) => key in detailLabels.value && value !== null && value !== '')
    .map(([key, value]) => ({ key, label: detailLabels.value[key], value })),
)

// SEO/canonical/hreflang/Schema 只从 Exhibition Public DTO 序列化。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title || page.value.translation.title,
  meta: [
    ...(page.value.seo.description
      ? [{ name: 'description', content: page.value.seo.description }]
      : []),
    {
      name: 'robots',
      content: `${page.value.seo.robots_index ? 'index' : 'noindex'}, ${page.value.seo.robots_follow === false ? 'nofollow' : 'follow'}`,
    },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...page.value.seo.hreflang.map((item) => ({
      rel: 'alternate' as const,
      hreflang: item.hreflang,
      href: item.url,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <div class="exhibition-detail">
    <div class="public-container exhibition-detail__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.trust.exhibitionsTitle"
      :title="page.translation.title"
      :summary="page.translation.summary || page.translation.title"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'exhibition', slug: page.slug })"
      :secondary-label="labels.trust.exhibitionsTitle"
      :secondary-href="`/${locale}/exhibitions/`"
    >
      <template #heading
        ><h1>{{ page.translation.title }}</h1></template
      >
    </PageHero>

    <article class="public-container exhibition-detail__body">
      <PublicImage
        v-if="page.primary_media?.type === 'image'"
        :media="page.primary_media"
        :locale="locale"
        priority
      />
      <PublicVideo v-else-if="page.primary_media?.type === 'video'" :media="page.primary_media" />
      <GeoAnswer :locale="locale" :geo="page.geo" />
      <section v-if="visibleDetails.length">
        <h2>{{ labels.trust.eventDetails }}</h2>
        <dl>
          <div v-for="detail in visibleDetails" :key="detail.key">
            <dt>{{ detail.label }}</dt>
            <dd>{{ detail.value }}</dd>
          </div>
        </dl>
      </section>
      <section v-if="page.translation.description" class="exhibition-detail__description">
        <h2>{{ labels.catalog.overview }}</h2>
        <p>{{ page.translation.description }}</p>
      </section>
    </article>
    <RfqCta :locale="locale" source-type="exhibition" :source-slug="page.slug" />
  </div>
</template>

<style scoped>
.exhibition-detail__breadcrumb {
  padding-block: var(--space-4);
}
.exhibition-detail__body {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: var(--space-10);
}
.exhibition-detail dl {
  margin: var(--space-4) 0 0;
  display: grid;
  gap: var(--space-2);
}
.exhibition-detail dl > div {
  display: grid;
  grid-template-columns: minmax(8rem, 0.35fr) minmax(0, 1fr);
  gap: var(--space-3);
}
.exhibition-detail dt,
.exhibition-detail dd {
  margin: 0;
}
.exhibition-detail dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}
.exhibition-detail__description p {
  max-width: 54rem;
  margin-block-start: var(--space-4);
  color: var(--color-neutral-700);
  line-height: var(--line-height-relaxed);
  white-space: pre-line;
}
</style>
