<!-- 组件职责：为 Sitemap 中的产品分类、材料、技术、应用和方案提供最小 SSR 页面。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'

const props = defineProps<{ resource: string; slugParam?: string }>()
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const slug = String(route.params[props.slugParam || 'slug'])
const { data: response, error } = await useAsyncData(
  `catalog:${props.resource}:${lang}:${slug}`,
  () =>
    api<{
      data: {
        translation: Record<string, string>
        seo: { title: string; description?: string; canonical: string; robots: string }
        geo: Record<string, unknown> | null
        breadcrumb: Array<{ name: string; url: string }>
        schema: unknown[]
        alternates?: Record<string, string>
      }
    }>(`/public/${props.resource}/${lang}/${slug}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Content not found' })
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
      <p v-for="(value, field) in page.translation" v-show="field !== 'name'" :key="field">
        {{ value }}
      </p>
      <PublicGeoContent :geo="page.geo" />
    </article>
  </main>
</template>
