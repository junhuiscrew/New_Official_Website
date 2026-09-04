<!-- 页面用途：带真实作者、来源和可见 GEO 事实的 Knowledge Article 最小 SSR 页面。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

interface KnowledgeDto {
  slug: string
  translation: { title: string; summary?: string; body_markdown: string }
  author: { name: string; job_title?: string; short_bio?: string }
  reviewer?: { name: string; job_title?: string } | null
  sources: Array<{ title: string; url: string; publisher?: string }>
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
const category = String(route.params.category)
const slug = String(route.params.slug)
const { data: response, error } = await useAsyncData(`knowledge:${lang}:${category}:${slug}`, () =>
  api<Envelope<KnowledgeDto>>(`/public/knowledge/${lang}/${category}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Knowledge article not found' })
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
      <p>
        By {{ page.author.name
        }}<span v-if="page.author.job_title"> — {{ page.author.job_title }}</span>
      </p>
      <p class="body-markdown">{{ page.translation.body_markdown }}</p>
      <PublicGeoContent :geo="page.geo" />
      <section v-if="page.sources.length">
        <h2>Sources</h2>
        <ol>
          <li v-for="source in page.sources" :key="source.url">
            <a :href="source.url" rel="noopener noreferrer">{{ source.title }}</a
            ><span v-if="source.publisher"> — {{ source.publisher }}</span>
          </li>
        </ol>
      </section>
      <PublicFaqList :items="page.faqs" />
    </article>
  </main>
</template>
