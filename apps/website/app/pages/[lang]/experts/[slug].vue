<!-- 页面用途：已核验真实 Author/Expert 的最小 SSR 公开资料页。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

interface ExpertDto {
  slug: string
  name: string
  job_title?: string
  short_bio?: string
  expertise: string[]
  role_type: string
  years_experience?: number
  linkedin_url?: string
  authored_knowledge: Array<{
    type: string
    slug: string
    name: string
    url: string
    summary: string
  }>
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
const { data: response, error } = await useAsyncData(`expert:${lang}:${slug}`, () =>
  api<Envelope<ExpertDto>>(`/public/experts/${lang}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Expert not found' })
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
      <h1>{{ page.name }}</h1>
      <p v-if="page.job_title">{{ page.job_title }}</p>
      <p>{{ page.short_bio }}</p>
      <p v-if="page.years_experience">Experience: {{ page.years_experience }} years</p>
      <ul v-if="page.expertise.length">
        <li v-for="item in page.expertise" :key="item">{{ item }}</li>
      </ul>
      <PublicGeoContent :geo="page.geo" />
      <PublicRelationLinks :relations="{ authored_knowledge: page.authored_knowledge }" />
    </article>
  </main>
</template>
