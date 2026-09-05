<!-- 页面用途：SSR 展示后端批准的制造能力、设备、媒体、关系、GEO 与询价入口。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCapabilityDetailDto, PublicEquipmentDto } from '~/types/public'
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
const requestKey = computed(() => `capability:${locale.value}:${slug.value}`)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCapabilityDetailDto>>(
    `/public/trust/capabilities/${locale.value}/${slug.value}`,
  ),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Capability not found' : 'Capability unavailable',
  })
}
const page = computed(() => response.value!.data)

/** 只把后端已批准的 Equipment public_specs_json 转成可读键值，不输出 raw JSON。 */
function equipmentSpecEntries(equipment: PublicEquipmentDto) {
  return Object.entries(equipment.translation.public_specs_json ?? {}).filter(
    ([key, value]) => Boolean(key.trim()) && value !== null && value !== '',
  )
}

// 页面 SEO、canonical、hreflang 与 Schema 只消费 Trust Public DTO。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title || page.value.translation.name,
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
  <div class="capability-detail">
    <div class="public-container capability-detail__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.navigation.capabilities"
      :title="page.translation.name"
      :summary="page.translation.summary || page.translation.name"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'manufacturing_capability', slug: page.slug })"
      :secondary-label="labels.navigation.capabilities"
      :secondary-href="`/${locale}/capabilities/`"
    >
      <template #heading
        ><h1>{{ page.translation.name }}</h1></template
      >
    </PageHero>

    <article class="public-container capability-detail__body">
      <PublicImage
        v-if="page.primary_media?.type === 'image'"
        :media="page.primary_media"
        :locale="locale"
        priority
      />
      <PublicVideo v-else-if="page.primary_media?.type === 'video'" :media="page.primary_media" />

      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section v-if="page.translation.description" class="capability-detail__description">
        <h2>{{ labels.catalog.overview }}</h2>
        <p>{{ page.translation.description }}</p>
      </section>

      <section v-if="page.translation.key_facts_json?.length" class="capability-detail__facts">
        <h2>{{ labels.sections.keyFacts }}</h2>
        <ul>
          <li v-for="fact in page.translation.key_facts_json" :key="fact">{{ fact }}</li>
        </ul>
      </section>

      <!-- Equipment 已由后端按 enabled + TranslationStatus=published 双重门禁过滤。 -->
      <section v-if="page.equipment.length" class="capability-detail__equipment">
        <h2>{{ labels.trust.equipment }}</h2>
        <div class="capability-detail__equipment-grid">
          <article v-for="equipment in page.equipment" :key="equipment.slug">
            <h3>{{ equipment.translation.name }}</h3>
            <p v-if="equipment.translation.summary">{{ equipment.translation.summary }}</p>
            <p v-if="equipment.translation.description">{{ equipment.translation.description }}</p>
            <dl>
              <div v-if="equipment.manufacturer">
                <dt>{{ labels.trust.manufacturer }}</dt>
                <dd>{{ equipment.manufacturer }}</dd>
              </div>
              <div v-if="equipment.model">
                <dt>{{ labels.trust.model }}</dt>
                <dd>{{ equipment.model }}</dd>
              </div>
              <div v-if="equipment.quantity !== null">
                <dt>{{ labels.trust.quantity }}</dt>
                <dd>{{ equipment.quantity }}</dd>
              </div>
              <div v-if="equipment.commissioning_year !== null">
                <dt>{{ labels.trust.commissioningYear }}</dt>
                <dd>{{ equipment.commissioning_year }}</dd>
              </div>
              <div v-if="equipment.precision_text">
                <dt>{{ labels.trust.precision }}</dt>
                <dd>{{ equipment.precision_text }}</dd>
              </div>
              <div v-if="equipment.capacity_text">
                <dt>{{ labels.trust.capacity }}</dt>
                <dd>{{ equipment.capacity_text }}</dd>
              </div>
            </dl>
            <section v-if="equipmentSpecEntries(equipment).length">
              <h4>{{ labels.trust.publicSpecifications }}</h4>
              <dl>
                <div v-for="[name, value] in equipmentSpecEntries(equipment)" :key="name">
                  <dt>{{ name }}</dt>
                  <dd>{{ value }}</dd>
                </div>
              </dl>
            </section>
          </article>
        </div>
      </section>

      <RelationLinks
        :locale="locale"
        :relations="page.relations"
        :groups="['technologies', 'products', 'cases']"
      />
    </article>
    <RfqCta :locale="locale" source-type="manufacturing_capability" :source-slug="page.slug" />
  </div>
</template>

<style scoped>
.capability-detail__breadcrumb {
  padding-block: var(--space-4);
}

.capability-detail__body {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: var(--space-10);
}

.capability-detail__description p {
  max-width: 54rem;
  margin-block-start: var(--space-4);
  color: var(--color-neutral-700);
  line-height: var(--line-height-relaxed);
  white-space: pre-line;
}

.capability-detail__facts ul {
  padding-inline-start: var(--space-5);
}

.capability-detail__equipment-grid {
  margin-block-start: var(--space-5);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}

.capability-detail__equipment-grid > article {
  padding: var(--space-6);
  display: grid;
  gap: var(--space-4);
  border: var(--border-subtle);
}

.capability-detail__equipment dl {
  margin: 0;
  display: grid;
  gap: var(--space-2);
}

.capability-detail__equipment dl > div {
  display: grid;
  grid-template-columns: minmax(7rem, 0.4fr) minmax(0, 1fr);
  gap: var(--space-3);
}

.capability-detail__equipment dt,
.capability-detail__equipment dd {
  margin: 0;
}

.capability-detail__equipment dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

@media (max-width: 48rem) {
  .capability-detail__equipment-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
