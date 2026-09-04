<!-- 页面用途：制造能力最小公开 SSR 页面。 -->
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
const { data: response, error } = await useAsyncData(`capability:${lang}:${slug}`, () =>
  api<Envelope<any>>(`/public/trust/capabilities/${lang}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Capability not found' })
const page = computed(() => response.value!.data)
useHead(() => ({
  title: page.value.seo?.title || page.value.translation.name,
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
      <h1>{{ page.translation.name }}</h1>
      <p>{{ page.translation.summary }}</p>
      <p>{{ page.translation.description }}</p>
      <ul>
        <li v-for="fact in page.translation.key_facts_json || []" :key="fact">{{ fact }}</li>
      </ul>
      <section v-if="page.geo">
        <h2>Technical answer</h2>
        <p>{{ page.geo.direct_answer }}</p>
        <ul>
          <li v-for="fact in page.geo.key_facts || []" :key="fact">{{ fact }}</li>
        </ul>
        <p v-for="evidence in page.geo.evidence || []" :key="evidence">{{ evidence }}</p>
      </section>
    </article>
  </main>
</template>
