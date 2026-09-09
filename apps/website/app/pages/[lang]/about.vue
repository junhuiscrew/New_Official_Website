<!-- 页面用途：SSR 展示后端已发布 Company Public DTO 中真实存在的公司事实。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCompanyProfileDto } from '~/types/public'
import { telephoneHref } from '~/utils/contact'
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
const requestKey = computed(() => `about:${locale.value}`)
const { data: response, error } = await useAsyncData(requestKey, () =>
  api<Envelope<PublicCompanyProfileDto>>(`/public/company-profile/${locale.value}`),
)
if (error.value || !response.value?.data) {
  const statusCode = error.value?.statusCode === 404 ? 404 : 500
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Company profile not found' : 'Company profile unavailable',
  })
}
const page = computed(() => response.value!.data)

/** 将已填充 Company DTO 字段映射为本地化事实行，不在模板写任何业务数值。 */
const companyFacts = computed(() =>
  [
    { label: labels.value.home.foundedYear, value: page.value.founded_year },
    { label: labels.value.home.yearsExperience, value: page.value.years_experience },
    { label: labels.value.home.employees, value: page.value.employee_count_range },
    { label: labels.value.home.factoryArea, value: page.value.factory_area_sqm },
    { label: labels.value.home.annualCapacity, value: page.value.annual_capacity_text },
  ].filter((fact) => fact.value !== null && fact.value !== ''),
)
const hasContact = computed(() =>
  Boolean(page.value.phone || page.value.email || page.value.address),
)
// 非号码的演示联系方式保留为可见文字，避免生成不可用的 tel URL。
const phoneHref = computed(() => telephoneHref(page.value.phone))

// canonical、hreflang 与 Schema 全部来自 Company Public DTO。
useHead(() => ({
  htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
  title: page.value.seo.title || page.value.company_name,
  meta: [
    ...(page.value.seo.description
      ? [{ name: 'description', content: page.value.seo.description }]
      : []),
    {
      name: 'robots',
      content: `${page.value.seo.robots_index ? 'index' : 'noindex'}, ${page.value.seo.robots_follow ? 'follow' : 'nofollow'}`,
    },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...page.value.seo.hreflang.map((alternate) => ({
      rel: 'alternate' as const,
      hreflang: alternate.hreflang,
      href: alternate.url,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <div class="about-page">
    <div class="public-container about-page__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.navigation.about"
      :title="page.company_name"
      :summary="page.short_intro || page.full_intro || page.company_name"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale })"
      :secondary-label="labels.cta.exploreProducts"
      :secondary-href="`/${locale}/products/`"
    >
      <template #heading
        ><h1>{{ page.company_name }}</h1></template
      >
    </PageHero>

    <article class="public-container about-page__content">
      <section v-if="page.full_intro || page.mission" class="about-page__overview">
        <h2>{{ labels.trust.companyOverview }}</h2>
        <p v-if="page.full_intro">{{ page.full_intro }}</p>
        <p v-if="page.mission">{{ page.mission }}</p>
      </section>

      <section v-if="companyFacts.length || page.export_markets?.length" class="about-page__facts">
        <h2>{{ labels.trust.companyFacts }}</h2>
        <dl v-if="companyFacts.length">
          <div v-for="fact in companyFacts" :key="fact.label">
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>
        <div v-if="page.export_markets?.length">
          <h3>{{ labels.home.exportMarkets }}</h3>
          <ul>
            <li v-for="market in page.export_markets" :key="market">{{ market }}</li>
          </ul>
        </div>
      </section>

      <section v-if="page.advantages?.length" class="about-page__advantages">
        <h2>{{ labels.trust.advantages }}</h2>
        <ul>
          <li v-for="advantage in page.advantages" :key="advantage">{{ advantage }}</li>
        </ul>
      </section>

      <GeoAnswer :locale="locale" :geo="page.geo" />

      <section v-if="hasContact" class="about-page__contact">
        <h2>{{ labels.trust.contact }}</h2>
        <address>
          <a v-if="phoneHref" :href="phoneHref">{{ page.phone }}</a>
          <span v-else-if="page.phone">{{ page.phone }}</span>
          <a v-if="page.email" :href="`mailto:${page.email}`">{{ page.email }}</a>
          <span v-if="page.address">{{ page.address }}</span>
        </address>
      </section>
    </article>
    <RfqCta :locale="locale" />
  </div>
</template>

<style scoped>
.about-page__breadcrumb {
  padding-block: var(--space-4);
}

.about-page__content {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  gap: var(--space-10);
}

.about-page__overview,
.about-page__facts,
.about-page__advantages,
.about-page__contact {
  display: grid;
  gap: var(--space-4);
}

.about-page__overview p {
  max-width: 54rem;
  color: var(--color-neutral-700);
  line-height: var(--line-height-relaxed);
  white-space: pre-line;
}

.about-page__facts dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.about-page__facts dl > div {
  padding: var(--space-5);
  border: var(--border-subtle);
}

.about-page__facts dt {
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.about-page__facts dd {
  margin: var(--space-2) 0 0;
  color: var(--color-navy-900);
  font-weight: 750;
}

.about-page__facts ul,
.about-page__advantages ul {
  margin: 0;
  padding-inline-start: var(--space-5);
}

.about-page__contact address {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-style: normal;
}

@media (max-width: 48rem) {
  .about-page__facts dl {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
