<!-- 页面用途：公开展会详情最小 SSR 页面。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const slug = String(route.params.slug)
interface Envelope<T> {
  success: boolean
  data: any
  error: unknown
}
const { data: response, error } = await useAsyncData(`exhibition:${lang}:${slug}`, () =>
  api<Envelope<any>>(`/public/trust/exhibitions/${lang}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Exhibition not found' })
const page = computed(() => response.value!.data)
useHead(() => ({
  title: page.value.seo?.title || page.value.translation.title,
  meta: [
    { name: 'description', content: page.value.seo?.description || page.value.translation.summary },
    {
      name: 'robots',
      content: page.value.seo?.robots_index === false ? 'noindex, follow' : 'index, follow',
    },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo?.canonical || page.value.url },
    ...(page.value.seo?.hreflang || []).map((item: { hreflang: string; url: string }) => ({
      rel: 'alternate',
      hreflang: item.hreflang,
      href: item.url,
    })),
  ],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>
<template>
  <main class="public-content-page">
    <article>
      <h1>{{ page.translation.title }}</h1>
      <p>{{ page.translation.summary }}</p>
      <p>{{ page.translation.description }}</p>
      <section v-if="page.geo">
        <h2>Event details</h2>
        <p>{{ page.geo.direct_answer }}</p>
        <ul>
          <li v-for="fact in page.geo.key_facts || []" :key="fact">{{ fact }}</li>
        </ul>
        <p v-for="evidence in page.geo.evidence || []" :key="evidence">{{ evidence }}</p>
      </section>
    </article>
  </main>
</template>
