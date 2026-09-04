<!-- 页面用途：公开 Company Profile SSR 与真实 Organization Schema。 -->
<script setup lang="ts">
import { serializeJsonLd } from '~/utils/jsonLd'
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
interface CompanyDto {
  company_name: string
  short_intro: string
  full_intro: string
  mission?: string
  advantages?: string[]
  schema: unknown
}
interface Envelope<T> {
  success: boolean
  data: T
  error: unknown
}
const { data: response, error } = await useAsyncData(`about:${lang}`, () =>
  api<Envelope<CompanyDto>>(`/public/company-profile/${lang}`),
)
if (error.value || !response.value?.data)
  throw createError({ statusCode: 404, statusMessage: 'Company profile not found' })
const page = computed(() => response.value!.data)
useHead(() => ({
  title: page.value.company_name,
  meta: [{ name: 'description', content: page.value.short_intro }],
  link: [{ rel: 'canonical', href: `https://junhuiscrewbarrel.com/${lang}/about/` }],
  script: [{ type: 'application/ld+json', innerHTML: serializeJsonLd(page.value.schema) }],
}))
</script>
<template>
  <main class="public-content-page">
    <article>
      <h1>{{ page.company_name }}</h1>
      <p>{{ page.short_intro }}</p>
      <p>{{ page.full_intro }}</p>
      <p v-if="page.mission">{{ page.mission }}</p>
      <ul>
        <li v-for="advantage in page.advantages || []" :key="advantage">{{ advantage }}</li>
      </ul>
    </article>
  </main>
</template>
