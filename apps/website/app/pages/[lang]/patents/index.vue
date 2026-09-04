<!-- 页面用途：公开专利索引入口；只展示真实已发布数据。 -->
<script setup lang="ts">
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const { data } = await useAsyncData(`trust-patents-${lang}`, () =>
  api<{ data: Array<{ slug: string; title: string; summary: string | null }> }>(
    `/public/trust/patents/${lang}`,
  ),
)
useHead({ title: 'Patents', meta: [{ name: 'robots', content: 'index, follow' }] })
</script>
<template>
  <main class="public-content-page">
    <h1>Patents</h1>
    <p v-if="!data?.data.length">No public patent records are currently configured.</p>
    <ul>
      <li v-for="item in data?.data || []" :key="item.slug">
        <strong>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
      </li>
    </ul>
  </main>
</template>
