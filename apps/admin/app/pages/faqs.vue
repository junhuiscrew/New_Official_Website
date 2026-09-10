<!-- 页面用途：可关联到公开页面的双语 FAQ 最小真实 CRUD。 -->
<script setup lang="ts">
useHead({
  title: '常见问题',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template><AuthorityCrud title="常见问题" resource="faqs" /></template>
