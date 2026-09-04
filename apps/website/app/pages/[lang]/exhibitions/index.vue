<!-- 页面用途：公开展会目录最小 SSR 页面。 -->
<script setup lang="ts">
const route = useRoute()
const api = useApi()
const lang = String(route.params.lang)
const { data } = await useAsyncData(`trust-exhibitions-${lang}`, () =>
  api<{ data: Array<{ slug: string; title: string; summary: string | null; url: string | null }> }>(
    `/public/trust/exhibitions/${lang}`,
  ),
)
useHead({ title: 'Exhibitions', meta: [{ name: 'robots', content: 'index, follow' }] })
</script>
<template>
  <main class="public-content-page">
    <h1>Exhibitions</h1>
    <p v-if="!data?.data.length">No public exhibition records are currently configured.</p>
    <ul>
      <li v-for="item in data?.data || []" :key="item.slug">
        <NuxtLink v-if="item.url" :to="item.url">{{ item.title }}</NuxtLink
        ><strong v-else>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
      </li>
    </ul>
  </main>
</template>
