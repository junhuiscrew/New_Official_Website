<!-- 页面用途：展会真实 CRUD 与统一发布入口。 -->
<script setup lang="ts">
useHead({
  title: '展会',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="展会" resource="exhibitions" /></template>
