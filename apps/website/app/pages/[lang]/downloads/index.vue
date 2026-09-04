<!-- 页面用途：公开下载资源入口，禁止引用 private-rfq。 -->
<script setup lang="ts">
const route = useRoute()
const api = useApi()
const locale = String(route.params.lang)
const { data } = await useAsyncData(`public-downloads-${locale}`, () =>
  api(`/api/v1/public/downloads/${locale}`),
)
const downloads = computed(
  () =>
    (
      data.value as {
        data?: Array<{
          slug: string
          title: string
          summary?: string | null
          url: string
          version_label?: string | null
        }>
      } | null
    )?.data ?? [],
)
useHead({ title: 'Downloads', meta: [{ name: 'robots', content: 'index, follow' }] })
</script>
<template>
  <main class="public-content-page">
    <h1>Downloads</h1>
    <p v-if="downloads.length === 0">No public downloads are currently available.</p>
    <ul v-else>
      <li v-for="item in downloads" :key="item.slug">
        <a :href="item.url">{{ item.title }}</a>
        <span v-if="item.version_label"> · {{ item.version_label }}</span>
        <p v-if="item.summary">{{ item.summary }}</p>
      </li>
    </ul>
  </main>
</template>
