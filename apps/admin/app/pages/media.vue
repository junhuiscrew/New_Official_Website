<!-- 页面用途：公开 Media Library 最小列表，私有 RFQ 文件不通过 media.read 暴露。 -->
<script setup lang="ts">
useHead({ title: 'Media Library', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const items = ref<Array<Record<string, unknown>>>([])
onMounted(async () => {
  items.value = await api.detail('/media')
})
</script>
<template>
  <main class="admin-shell">
    <h1>Media Library</h1>
    <ul>
      <li v-for="item in items" :key="String(item.id)">
        {{ item.type }} · {{ item.visibility }} · {{ item.file_extension }}
      </li>
    </ul>
  </main>
</template>
