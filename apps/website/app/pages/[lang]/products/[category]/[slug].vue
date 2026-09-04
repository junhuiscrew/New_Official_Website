<!-- 页面用途：Product 的最小 SSR 语义页面，不包含最终产品详情视觉。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

interface ProductDto {
  slug: string
  translation: {
    name: string
    short_description?: string
    description?: string
    highlights?: unknown[]
  }
  models: Array<{ model_code: string }>
  specifications: Array<Record<string, unknown>>
  relations: Record<
    string,
    Array<{ type: string; slug: string; name: string; url: string; summary: string }>
  >
  faqs: Array<{ question: string; answer: string }>
  seo: { title: string; description?: string; canonical: string; robots: string }
  geo: {
    direct_answer?: string
    key_facts?: string[]
    evidence?: string[]
    related_questions?: string[]
    last_reviewed_at?: string
  } | null
  breadcrumb: Array<{ name: string; url: string }>
  schema: unknown[]
  alternates?: Record<string, string>
}
interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}

const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const category = String(route.params.category)
const slug = String(route.params.slug)
const { data: response, error } = await useAsyncData(`product:${lang}:${category}:${slug}`, () =>
  api<Envelope<ProductDto>>(`/public/products/${lang}/${category}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Product not found' })
const page = computed(() => response.value!.data)

useHead(() => ({
  title: page.value.seo.title,
  meta: [
    { name: 'description', content: page.value.seo.description },
    { name: 'robots', content: page.value.seo.robots },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...Object.entries(page.value.alternates || {}).map(([hreflang, href]) => ({
      rel: 'alternate' as const,
      type: 'text/html',
      hreflang,
      href,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>

<template>
  <main class="public-content-page">
    <PublicBreadcrumb :items="page.breadcrumb" />
    <article>
      <h1>{{ page.translation.name }}</h1>
      <p>{{ page.translation.short_description }}</p>
      <p>{{ page.translation.description }}</p>
      <pre v-if="page.translation.highlights?.length">{{ page.translation.highlights }}</pre>
      <PublicGeoContent :geo="page.geo" />
      <section v-if="page.models.length">
        <h2>Models</h2>
        <ul>
          <li v-for="model in page.models" :key="model.model_code">{{ model.model_code }}</li>
        </ul>
      </section>
      <section v-if="page.specifications.length">
        <h2>Specifications</h2>
        <pre>{{ page.specifications }}</pre>
      </section>
      <PublicRelationLinks :relations="page.relations" />
      <PublicFaqList :items="page.faqs" />
    </article>
  </main>
</template>
