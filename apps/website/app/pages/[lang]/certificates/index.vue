<!-- 页面用途：公开证书索引入口；只展示真实已发布数据。 -->
<script setup lang="ts">
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const { data } = await useAsyncData(`trust-certificates-${lang}`, () =>
  api<{ data: Array<{ slug: string; title: string; summary: string | null }> }>(
    `/public/trust/certificates/${lang}`,
  ),
)
useHead({ title: 'Certificates', meta: [{ name: 'robots', content: 'index, follow' }] })
</script>
<template>
  <main class="public-content-page">
    <h1>Certificates</h1>
    <p v-if="!data?.data.length">No public certificate records are currently configured.</p>
    <ul>
      <li v-for="item in data?.data || []" :key="item.slug">
        <strong>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
      </li>
    </ul>
  </main>
</template>
