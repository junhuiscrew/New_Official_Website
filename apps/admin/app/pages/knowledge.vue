<!-- 页面用途：Knowledge Article、真实作者/审核人、关系、来源与 SEO/GEO 的最小真实 CRUD。 -->
<script setup lang="ts">
useHead({
  title: '知识文章',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template><AuthorityCrud title="知识文章" resource="knowledge" /></template>
