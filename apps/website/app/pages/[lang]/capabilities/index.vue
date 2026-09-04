<!-- 页面用途：公开制造能力目录占位 SSR，不提前制作最终首页视觉。 -->
<script setup lang="ts">
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const { data } = await useAsyncData(`trust-capabilities-${lang}`, () =>
  api<{ data: Array<{ slug: string; title: string; summary: string | null; url: string | null }> }>(
    `/public/trust/capabilities/${lang}`,
  ),
)
useHead({
  title: 'Manufacturing Capabilities',
  meta: [{ name: 'robots', content: 'index, follow' }],
})
</script>
<template>
  <main class="public-content-page">
    <h1>Manufacturing Capabilities</h1>
    <p v-if="!data?.data.length">No public capability records are currently configured.</p>
    <ul>
      <li v-for="item in data?.data || []" :key="item.slug">
        <NuxtLink v-if="item.url" :to="item.url">{{ item.title }}</NuxtLink
        ><strong v-else>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
      </li>
    </ul>
  </main>
</template>
