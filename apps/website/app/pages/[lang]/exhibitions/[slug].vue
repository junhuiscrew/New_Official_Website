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
  title: page.value.translation.title,
  meta: [{ name: 'description', content: page.value.translation.summary }],
  link: [{ rel: 'canonical', href: page.value.url }],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>
<template>
  <main class="public-content-page">
    <article>
      <h1>{{ page.translation.title }}</h1>
      <p>{{ page.translation.summary }}</p>
      <p>{{ page.translation.description }}</p>
    </article>
  </main>
</template>
