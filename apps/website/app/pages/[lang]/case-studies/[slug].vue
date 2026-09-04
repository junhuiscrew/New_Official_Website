<!-- 页面用途：客户隐私白名单保护的 Case Study 最小 SSR 页面。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

interface CaseDto {
  slug: string
  client_name?: string
  client_address?: string
  country_code?: string
  industry?: string
  machine_brand?: string
  machine_model?: string
  screw_diameter?: string
  filler_percentage?: string
  translation: {
    title: string
    summary?: string
    client_description?: string
    problem?: string
    analysis?: string
    solution?: string
    result?: string
    engineer_comment?: string
  }
  faqs: Array<{ question: string; answer: string }>
  relations: Record<
    string,
    Array<{ type: string; slug: string; name: string; url: string; summary: string }>
  >
  seo: { title: string; description?: string; canonical: string; robots: string }
  geo: Record<string, unknown> | null
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
const slug = String(route.params.slug)
const { data: response, error } = await useAsyncData(`case:${lang}:${slug}`, () =>
  api<Envelope<CaseDto>>(`/public/case-studies/${lang}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Case study not found' })
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
      <h1>{{ page.translation.title }}</h1>
      <p>{{ page.translation.summary }}</p>
      <p v-if="page.client_name">Customer: {{ page.client_name }}</p>
      <p v-if="page.client_address">Customer address: {{ page.client_address }}</p>
      <dl>
        <template
          v-for="(value, label) in {
            Country: page.country_code,
            Industry: page.industry,
            'Machine brand': page.machine_brand,
            'Machine model': page.machine_model,
            'Screw diameter': page.screw_diameter,
            'Filler percentage': page.filler_percentage,
          }"
          :key="label"
        >
          <template v-if="value"
            ><dt>{{ label }}</dt>
            <dd>{{ value }}</dd></template
          >
        </template>
      </dl>
      <p v-if="page.translation.client_description">
        {{ page.translation.client_description }}
      </p>
      <section>
        <h2>Problem</h2>
        <p>{{ page.translation.problem }}</p>
      </section>
      <section>
        <h2>Analysis</h2>
        <p>{{ page.translation.analysis }}</p>
      </section>
      <section>
        <h2>Solution</h2>
        <p>{{ page.translation.solution }}</p>
      </section>
      <section>
        <h2>Result</h2>
        <p>{{ page.translation.result }}</p>
      </section>
      <section v-if="page.translation.engineer_comment">
        <h2>Engineer comment</h2>
        <p>{{ page.translation.engineer_comment }}</p>
      </section>
      <PublicGeoContent :geo="page.geo" />
      <PublicRelationLinks :relations="page.relations" />
      <PublicFaqList :items="page.faqs" />
    </article>
  </main>
</template>
