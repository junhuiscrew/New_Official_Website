<!-- 页面用途：服务端渲染公开产品详情，组合媒体、清洁规格、型号、关系、GEO、FAQ 与 RFQ。 -->
<script setup lang="ts">
import { computed } from 'vue'

import MediaGallery from '~/components/MediaGallery.vue'
import PageHero from '~/components/PageHero.vue'
import PublicBreadcrumb from '~/components/PublicBreadcrumb.vue'
import PublicFaqList from '~/components/PublicFaqList.vue'
import PublicGeoContent from '~/components/PublicGeoContent.vue'
import PublicRelationLinks from '~/components/PublicRelationLinks.vue'
import RfqCta from '~/components/RfqCta.vue'
import SpecTable from '~/components/SpecTable.vue'
import TrustMetric from '~/components/TrustMetric.vue'
import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type { PublicProductDetailDto } from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const locale = normalizeLocale(route.params.lang)
const category = String(route.params.category)
const slug = String(route.params.slug)
const labels = computed(() => ui[locale])
const { data: response, error } = await useAsyncData(`product:${locale}:${category}:${slug}`, () =>
  api<Envelope<PublicProductDetailDto>>(`/public/products/${locale}/${category}/${slug}`),
)
if (error.value || !response.value?.data) {
  throw createError({ statusCode: 404, statusMessage: 'Product not found' })
}
const page = computed(() => response.value!.data)
const summary = computed(
  () => page.value.translation.short_description?.trim() || page.value.translation.name,
)
const descriptionParagraphs = computed(() =>
  (page.value.translation.description ?? '')
    .split(/\r?\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean),
)
const highlights = computed(() =>
  (page.value.translation.highlights ?? []).filter(
    (highlight): highlight is string => typeof highlight === 'string' && Boolean(highlight.trim()),
  ),
)
const galleryMedia = computed(() => {
  if (page.value.media.length) return page.value.media
  return page.value.primary_media ? [page.value.primary_media] : []
})
const coreRelations = computed(() => ({
  materials: page.value.relations.materials ?? [],
  technologies: page.value.relations.technologies ?? [],
  applications: page.value.relations.applications ?? [],
  solutions: page.value.relations.solutions ?? [],
}))
const capabilityRelations = computed(() => ({
  capabilities: page.value.relations.capabilities ?? [],
}))
const caseRelations = computed(() => ({
  cases: page.value.cases ?? page.value.relations.cases ?? [],
}))
const knowledgeRelations = computed(() => ({
  knowledge: page.value.knowledge ?? page.value.relations.knowledge ?? [],
}))

interface ProductTrustMetric {
  key: string
  label: string
  value: string
}

/** 将后端公开公司事实转为产品页可信度展示项，不在前端推导业务数据。 */
const trustMetrics = computed<ProductTrustMetric[]>(() => {
  const trust = page.value.trust_summary
  if (!trust) return []
  const metrics: Array<ProductTrustMetric | null> = [
    trust.founded_year !== undefined
      ? {
          key: 'founded-year',
          label: labels.value.home.foundedYear,
          value: String(trust.founded_year),
        }
      : null,
    trust.years_experience !== undefined
      ? {
          key: 'years-experience',
          label: labels.value.home.yearsExperience,
          value: String(trust.years_experience),
        }
      : null,
    trust.employee_count_range?.trim()
      ? {
          key: 'employees',
          label: labels.value.home.employees,
          value: trust.employee_count_range,
        }
      : null,
    trust.factory_area_sqm !== undefined
      ? {
          key: 'factory-area',
          label: labels.value.home.factoryArea,
          value: String(trust.factory_area_sqm),
        }
      : null,
    trust.annual_capacity_text?.trim()
      ? {
          key: 'annual-capacity',
          label: labels.value.home.annualCapacity,
          value: trust.annual_capacity_text,
        }
      : null,
    trust.export_markets?.length
      ? {
          key: 'export-markets',
          label: labels.value.home.exportMarkets,
          value: trust.export_markets.join(' · '),
        }
      : null,
  ]
  return metrics.filter((metric): metric is ProductTrustMetric => metric !== null)
})

// SEO、canonical、hreflang 与 Schema 完全消费后端结果，前端不重建索引规则。
useHead(() => ({
  htmlAttrs: { lang: locale === 'zh-cn' ? 'zh-CN' : 'en' },
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
      ([hreflang, href]) => ({
        rel: 'alternate' as const,
        type: 'text/html',
        hreflang,
        href,
      }),
    ),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <article class="product-detail">
    <div class="public-container">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="labels.navigation.products"
      :title="page.translation.name"
      :summary="summary"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: 'product', slug: page.slug })"
      :secondary-label="labels.cta.viewProducts"
      :secondary-href="`/${locale}/products/`"
    >
      <template #heading
        ><h1>{{ page.translation.name }}</h1></template
      >
    </PageHero>

    <article class="product-detail__body public-container">
      <MediaGallery v-if="galleryMedia.length" :media="galleryMedia" :locale="locale" />

      <section v-if="page.specifications.length" class="product-detail__section">
        <h2>{{ labels.products.specifications }}</h2>
        <SpecTable :specifications="page.specifications" :locale="locale" />
      </section>

      <section v-if="page.models.length" class="product-detail__section">
        <h2>{{ labels.products.models }}</h2>
        <ul class="product-detail__models">
          <li v-for="model in page.models" :key="model.model_code">{{ model.model_code }}</li>
        </ul>
      </section>

      <section
        v-if="descriptionParagraphs.length || highlights.length"
        class="product-detail__section product-detail__description"
      >
        <h2>{{ labels.products.description }}</h2>
        <p v-for="paragraph in descriptionParagraphs" :key="paragraph">{{ paragraph }}</p>
        <ul v-if="highlights.length">
          <li v-for="highlight in highlights" :key="highlight">{{ highlight }}</li>
        </ul>
      </section>

      <PublicGeoContent :geo="page.geo" />
      <PublicRelationLinks :relations="coreRelations" :locale="locale" />
      <PublicRelationLinks
        :relations="capabilityRelations"
        :locale="locale"
        :heading="labels.navigation.capabilities"
      />
      <section v-if="page.trust_summary && trustMetrics.length" class="product-detail__section">
        <h2>{{ labels.sections.trust }}</h2>
        <dl class="product-detail__trust">
          <TrustMetric
            v-for="metric in trustMetrics"
            :key="metric.key"
            :label="metric.label"
            :value="metric.value"
          />
        </dl>
      </section>
      <PublicFaqList :items="page.faqs" />
      <PublicRelationLinks
        :relations="caseRelations"
        :locale="locale"
        :heading="labels.sections.caseStudies"
      />
      <PublicRelationLinks
        :relations="knowledgeRelations"
        :locale="locale"
        :heading="labels.sections.technicalKnowledge"
      />
    </article>

    <RfqCta :locale="locale" source-type="product" :source-slug="page.slug" />
  </article>
</template>

<style scoped>
.product-detail > .public-container:first-child {
  padding-block: var(--space-4);
}

.product-detail__body {
  padding-block: var(--space-12) var(--space-16);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 0.8fr);
  align-items: start;
  gap: var(--space-12);
}

.product-detail__section,
.product-detail__body > :deep(section) {
  min-width: 0;
}

.product-detail__section h2 {
  margin-block-end: var(--space-5);
}

.product-detail__models {
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  list-style: none;
}

.product-detail__trust {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}

.product-detail__models li {
  padding: var(--space-2) var(--space-4);
  font-family: var(--font-technical);
  background: var(--color-neutral-100);
  border: var(--border-subtle);
}

.product-detail__description {
  grid-column: 1 / -1;
  max-width: 54rem;
}

@media (max-width: 56rem) {
  .product-detail__body {
    grid-template-columns: minmax(0, 1fr);
  }

  .product-detail__description {
    grid-column: auto;
  }

  .product-detail__trust {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
