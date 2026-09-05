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
  seo: {
    title?: string
    description?: string
    canonical: string
    robots_index: boolean
    robots_follow: boolean
    hreflang: Array<{ hreflang: string; url: string }>
  }
  geo?: { direct_answer?: string; key_facts?: string[]; evidence?: string[] }
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
  title: page.value.seo.title || page.value.company_name,
  meta: [
    { name: 'description', content: page.value.seo.description || page.value.short_intro },
    {
      name: 'robots',
      content: `${page.value.seo.robots_index ? 'index' : 'noindex'}, ${page.value.seo.robots_follow ? 'follow' : 'nofollow'}`,
    },
  ],
  link: [
    { rel: 'canonical', href: page.value.seo.canonical },
    ...page.value.seo.hreflang.map((alternate) => ({
      rel: 'alternate' as const,
      hreflang: alternate.hreflang,
      href: alternate.url,
    })),
  ],
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
      <!-- GEO 摘要必须与用户可见正文一致，不能成为 AI-only 隐藏内容。 -->
      <section v-if="page.geo?.direct_answer || page.geo?.key_facts?.length">
        <p v-if="page.geo?.direct_answer">{{ page.geo.direct_answer }}</p>
        <ul>
          <li v-for="fact in page.geo?.key_facts || []" :key="fact">{{ fact }}</li>
        </ul>
      </section>
    </article>
  </main>
</template>
