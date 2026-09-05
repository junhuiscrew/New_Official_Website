<!-- 页面用途：SSR 展示仅含公开工程事实与逐项许可客户身份的 Case Study。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCaseDetailDto } from '~/types/public'
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
const requestKey = computed(() => `authority:case:${locale.value}:${slug.value}`)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCaseDetailDto>>(`/public/case-studies/${locale.value}/${slug.value}`),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Case study not found' : 'Case study unavailable',
  })
}
const page = computed(() => response.value!.data)
const engineeringFacts = computed(() => [
  { label: labels.value.content.country, value: page.value.country_code },
  { label: labels.value.content.industry, value: page.value.industry },
  { label: labels.value.content.machineBrand, value: page.value.machine_brand },
  { label: labels.value.content.machineModel, value: page.value.machine_model },
  { label: labels.value.content.screwDiameter, value: page.value.screw_diameter },
  { label: labels.value.content.fillerPercentage, value: page.value.filler_percentage },
])
const visibleEngineeringFacts = computed(() =>
  engineeringFacts.value.filter((fact) => Boolean(fact.value?.trim())),
)
const engineeringSections = computed(() => [
  { label: labels.value.content.problem, value: page.value.translation.problem },
  { label: labels.value.content.analysis, value: page.value.translation.analysis },
  { label: labels.value.content.solution, value: page.value.translation.solution },
  { label: labels.value.content.result, value: page.value.translation.result },
  { label: labels.value.content.engineerComment, value: page.value.translation.engineer_comment },
])
const visibleEngineeringSections = computed(() =>
  engineeringSections.value.filter((section) => Boolean(section.value?.trim())),
)

// Meta、canonical、hreflang 与 Schema 只使用已经过案例隐私门禁的后端 DTO。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title,
  meta: [
    ...(page.value.seo.description
      ? [{ name: 'description', content: page.value.seo.description }]
      : []),
    { name: 'robots', content: page.value.seo.robots },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...Object.entries(page.value.alternates ?? page.value.seo.hreflang ?? {}).map(
      ([hreflang, href]) => ({ rel: 'alternate' as const, hreflang, href }),
    ),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <div class="authority-detail">
    <div class="public-container authority-detail__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.navigation.caseStudies"
      :title="page.translation.title"
      :summary="page.translation.summary || page.translation.title"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'case_study', slug: page.slug })"
      :secondary-label="labels.navigation.caseStudies"
      :secondary-href="`/${locale}/case-studies/`"
      :media="page.media"
    >
      <template #heading
        ><h1>{{ page.translation.title }}</h1></template
      >
    </PageHero>
    <article class="public-container authority-detail__body">
      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section v-if="visibleEngineeringFacts.length" class="authority-detail__facts">
        <dl>
          <div v-for="fact in visibleEngineeringFacts" :key="fact.label">
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="page.customer_identity" class="authority-detail__customer">
        <h2>{{ labels.content.customer }}</h2>
        <PublicImage
          v-if="page.customer_identity.logo"
          :media="page.customer_identity.logo"
          :locale="locale"
        />
        <p v-if="page.customer_identity.name">{{ page.customer_identity.name }}</p>
        <p v-if="page.customer_identity.address">
          <strong>{{ labels.content.customerAddress }}:</strong>
          {{ page.customer_identity.address }}
        </p>
        <p v-if="page.translation.client_description">
          {{ page.translation.client_description }}
        </p>
      </section>

      <div v-if="visibleEngineeringSections.length" class="authority-detail__sections">
        <section v-for="section in visibleEngineeringSections" :key="section.label">
          <h2>{{ section.label }}</h2>
          <p>{{ section.value }}</p>
        </section>
      </div>

      <FAQAccordion :locale="locale" :items="page.faqs" />
      <!-- PublicRelationLinks 旧组件由更严格的 RelationLinks 白名单实现替代。 -->
      <RelationLinks
        :locale="locale"
        :relations="page.relations"
        :groups="[
          'products',
          'materials',
          'technologies',
          'applications',
          'solutions',
          'knowledge',
        ]"
      />
    </article>
    <RfqCta :locale="locale" source-type="case_study" :source-slug="page.slug" />
  </div>
</template>

<style scoped>
.authority-detail__breadcrumb {
  padding-block: var(--space-4);
}

.authority-detail__body {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: var(--space-10);
}

.authority-detail__facts dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.authority-detail__facts dl > div,
.authority-detail__customer,
.authority-detail__sections section {
  padding: var(--space-5);
  border: var(--border-subtle);
}

.authority-detail__facts dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.authority-detail__facts dd {
  margin: var(--space-2) 0 0;
  color: var(--color-navy-900);
  font-weight: 750;
}

.authority-detail__customer {
  display: grid;
  gap: var(--space-3);
}

.authority-detail__customer :deep(.public-image) {
  max-width: 16rem;
}

.authority-detail__sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}

.authority-detail__sections p {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-700);
  white-space: pre-line;
}

@media (max-width: 48rem) {
  .authority-detail__facts dl,
  .authority-detail__sections {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
