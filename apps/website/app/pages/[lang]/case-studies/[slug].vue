<!-- 页面用途：客户隐私白名单保护的 Case Study 最小 SSR 页面。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

interface CaseDto {
  slug: string
  client_name?: string
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
      <PublicGeoContent :geo="page.geo" />
      <PublicFaqList :items="page.faqs" />
    </article>
  </main>
</template>
