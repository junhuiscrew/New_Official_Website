<!-- 组件职责：以一份类型化配置服务四类 Catalog 的 SSR 列表与详情页面。 -->
<script setup lang="ts">
import { computed, watch } from 'vue'

import { normalizeLocale, rfqUrl } from '~/composables/useLocalePath'
import { ui } from '~/i18n/ui'
import type {
  CatalogRelationGroup,
  CatalogResource,
  LocaleSlug,
  PublicCatalogDetailDto,
  PublicCatalogTranslationDto,
  PublicCollectionDto,
  PublicContentType,
} from '~/types/public'
import { serializeJsonLd } from '~/utils/jsonLd'
import { publicRequestStatus, strictPositiveInteger } from '~/utils/publicRequest'

import EmptyState from './EmptyState.vue'
import GeoAnswer from './GeoAnswer.vue'
import PageHero from './PageHero.vue'
import PaginationNav from './PaginationNav.vue'
import PublicBreadcrumb from './PublicBreadcrumb.vue'
import RelationLinks from './RelationLinks.vue'
import RfqCta from './RfqCta.vue'

type CatalogLabelKey = keyof (typeof ui)['en']['catalog']
type CatalogField = Exclude<keyof PublicCatalogTranslationDto, 'name'>

interface CatalogSectionConfig {
  field: CatalogField
  label: CatalogLabelKey
}

interface CatalogPageConfig {
  sourceType: Extract<PublicContentType, 'material' | 'technology' | 'application' | 'solution'>
  title: CatalogLabelKey
  intro: CatalogLabelKey
  leadField: CatalogField
  sections: readonly CatalogSectionConfig[]
  relationGroups: CatalogRelationGroup[]
}

const catalogPageConfig = {
  materials: {
    sourceType: 'material',
    title: 'materialsTitle',
    intro: 'materialsIntro',
    leadField: 'definition',
    sections: [
      { field: 'processing_characteristics', label: 'processingCharacteristics' },
      { field: 'screw_impact', label: 'screwImpact' },
      { field: 'recommendations', label: 'recommendations' },
      { field: 'limitations', label: 'limitations' },
    ],
    relationGroups: ['products', 'technologies', 'solutions', 'cases', 'knowledge'],
  },
  technologies: {
    sourceType: 'technology',
    title: 'technologiesTitle',
    intro: 'technologiesIntro',
    leadField: 'definition',
    sections: [
      { field: 'process_description', label: 'processDescription' },
      { field: 'benefits', label: 'benefits' },
      { field: 'limitations', label: 'limitations' },
    ],
    relationGroups: ['products', 'materials', 'cases', 'knowledge'],
  },
  applications: {
    sourceType: 'application',
    title: 'applicationsTitle',
    intro: 'applicationsIntro',
    leadField: 'description',
    sections: [
      { field: 'technical_requirements', label: 'technicalRequirements' },
      { field: 'common_problems', label: 'commonProblems' },
    ],
    relationGroups: ['products', 'solutions', 'cases', 'knowledge'],
  },
  solutions: {
    sourceType: 'solution',
    title: 'solutionsTitle',
    intro: 'solutionsIntro',
    leadField: 'definition',
    sections: [
      { field: 'symptoms', label: 'symptoms' },
      { field: 'causes', label: 'causes' },
      { field: 'diagnosis', label: 'diagnosis' },
      { field: 'solution', label: 'recommendedApproach' },
      { field: 'limitations', label: 'limitations' },
    ],
    relationGroups: ['products', 'materials', 'applications', 'cases', 'knowledge'],
  },
} satisfies Record<CatalogResource, CatalogPageConfig>

const props = defineProps<{ resource: CatalogResource; mode: 'list' | 'detail' }>()
const route = useRoute()
const api = useApi()
const locale = computed<LocaleSlug>(() => normalizeLocale(route.params.lang))
const slug = computed(() => String(route.params.slug ?? ''))
const labels = computed(() => ui[locale.value])
const config = catalogPageConfig[props.resource]

interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

type CatalogPagePayload =
  | { mode: 'list'; data: PublicCollectionDto }
  | { mode: 'detail'; data: PublicCatalogDetailDto }

const requestedPage = computed(() => strictPositiveInteger(route.query.page, 1))
const requestedPageSize = computed(() => strictPositiveInteger(route.query.page_size, 24, 48))
// key 仅由真正影响 API 响应的响应式参数组成，避免 fragment 引发 SSR hydration 重复请求。
const requestKey = computed(() =>
  props.mode === 'list'
    ? `catalog:list:${props.resource}:${locale.value}:${requestedPage.value}:${requestedPageSize.value}`
    : `catalog:detail:${props.resource}:${locale.value}:${slug.value}`,
)
const { data: response, error } = await useAsyncData<CatalogPagePayload>(requestKey, async () => {
  if (props.mode === 'list') {
    const result = await api<Envelope<PublicCollectionDto>>(
      `/public/${props.resource}/${locale.value}`,
      {
        query: { page: requestedPage.value, page_size: requestedPageSize.value },
      },
    )
    return { mode: 'list', data: result.data }
  }
  const result = await api<Envelope<PublicCatalogDetailDto>>(
    `/public/${props.resource}/${locale.value}/${slug.value}`,
  )
  return { mode: 'detail', data: result.data }
})

if (error.value || !response.value) {
  const statusCode = publicRequestStatus(error.value)
  throw createError({
    statusCode,
    statusMessage: statusCode === 404 ? 'Catalog content not found' : 'Catalog content unavailable',
  })
}
// 同一列表组件的客户端页码变化失败时，不允许继续显示旧卡片和旧 metadata。
watch(error, (nextError) => {
  if (!nextError) return
  const statusCode = publicRequestStatus(nextError)
  showError(
    createError({
      statusCode,
      statusMessage:
        statusCode === 404 ? 'Catalog content not found' : 'Catalog content unavailable',
    }),
  )
})

const collection = computed(() => (response.value?.mode === 'list' ? response.value.data : null))
const page = computed(() => (response.value?.mode === 'detail' ? response.value.data : null))
const listTitle = computed(() => labels.value.catalog[config.title])
const listIntro = computed(() => labels.value.catalog[config.intro])
const leadText = computed(() => {
  if (!page.value) return ''
  const value = page.value.translation[config.leadField]
  return value?.trim() || page.value.translation.name
})
const visibleSections = computed(() => {
  if (!page.value) return []
  return config.sections.flatMap((section) => {
    const value = page.value!.translation[section.field]?.trim()
    return value ? [{ ...section, value }] : []
  })
})

// SEO、canonical、hreflang 与 Schema 只序列化后端 DTO，前端不推导索引规则。
useHead(() => {
  if (page.value) {
    return {
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
    }
  }
  const seo = collection.value?.seo
  return {
    htmlAttrs: { lang: locale.value === 'zh-cn' ? 'zh-CN' : 'en' },
    title: seo?.title,
    meta: seo
      ? [
          ...(seo.description ? [{ name: 'description', content: seo.description }] : []),
          { name: 'robots', content: seo.robots },
        ]
      : [],
    link: seo
      ? [
          { rel: 'canonical', href: seo.canonical },
          ...Object.entries(seo.hreflang ?? {}).map(([hreflang, href]) => ({
            rel: 'alternate' as const,
            hreflang,
            href,
          })),
        ]
      : [],
    script: collection.value?.schema
      ? [
          {
            type: 'application/ld+json',
            innerHTML: serializeJsonLd(collection.value.schema),
          },
        ]
      : [],
  }
})
</script>

<template>
  <div v-if="collection" class="catalog-page catalog-page--list">
    <div v-if="collection.breadcrumb?.length" class="public-container catalog-page__breadcrumb">
      <PublicBreadcrumb :items="collection.breadcrumb" />
    </div>
    <header class="public-container catalog-page__list-header">
      <p class="eyebrow">{{ listTitle }}</p>
      <h1>{{ listTitle }}</h1>
      <p>{{ listIntro }}</p>
    </header>
    <section class="public-container catalog-page__results" :aria-label="listTitle">
      <div v-if="collection.items.length" class="catalog-page__grid">
        <article v-for="item in collection.items" :key="`${item.type}:${item.slug}`">
          <p class="eyebrow">{{ listTitle }}</p>
          <h2>
            <a :href="item.url">{{ item.name }}</a>
          </h2>
          <p v-if="item.summary">{{ item.summary }}</p>
        </article>
      </div>
      <EmptyState v-else :locale="locale" kind="generic" />
      <PaginationNav
        :locale="locale"
        :base-path="`/${locale}/${resource}/`"
        :page="collection.page"
        :pages="collection.pages"
        :page-size="collection.page_size"
      />
    </section>
  </div>

  <div v-else-if="page" class="catalog-page catalog-page--detail">
    <div class="public-container catalog-page__breadcrumb">
      <PublicBreadcrumb :items="page.breadcrumb" />
    </div>
    <PageHero
      :eyebrow="listTitle"
      :title="page.translation.name"
      :summary="leadText"
      :primary-label="labels.cta.requestQuote"
      :primary-href="rfqUrl({ locale, type: config.sourceType, slug: page.slug })"
      :secondary-label="labels.catalog.backToList"
      :secondary-href="`/${locale}/${resource}/`"
    />
    <article class="catalog-page__body public-container">
      <GeoAnswer :geo="page.geo" :locale="locale" />
      <div v-if="visibleSections.length" class="catalog-page__sections">
        <section v-for="section in visibleSections" :key="section.field">
          <h2>{{ labels.catalog[section.label] }}</h2>
          <p>{{ section.value }}</p>
        </section>
      </div>
      <RelationLinks :locale="locale" :relations="page.relations" :groups="config.relationGroups" />
    </article>
    <RfqCta :locale="locale" :source-type="config.sourceType" :source-slug="page.slug" />
  </div>
</template>

<style scoped>
.catalog-page__breadcrumb {
  padding-block: var(--space-4);
}

.catalog-page__list-header {
  padding-block: var(--space-12) var(--space-8);
  display: grid;
  gap: var(--space-3);
}

.catalog-page__list-header > p:last-child {
  max-width: 48rem;
  color: var(--color-neutral-600);
}

.catalog-page__results,
.catalog-page__body {
  padding-block-end: var(--space-16);
  display: grid;
  gap: var(--space-10);
}

.catalog-page__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6);
}

.catalog-page__grid article {
  padding: var(--space-6);
  border: var(--border-subtle);
  border-block-start: 3px solid var(--color-blue-600);
}

.catalog-page__grid h2 {
  margin-block-start: var(--space-3);
}

.catalog-page__grid h2 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.catalog-page__grid article > p:last-child {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-600);
}

.catalog-page__body {
  padding-block-start: var(--space-12);
}

.catalog-page__sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-8);
}

.catalog-page__sections section {
  margin: 0;
  padding-inline-start: var(--space-5);
  border-inline-start: 2px solid var(--color-neutral-300);
}

.catalog-page__sections p {
  margin-block-start: var(--space-3);
  color: var(--color-neutral-700);
  white-space: pre-line;
}

@media (max-width: 64rem) {
  .catalog-page__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 40rem) {
  .catalog-page__grid,
  .catalog-page__sections {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
