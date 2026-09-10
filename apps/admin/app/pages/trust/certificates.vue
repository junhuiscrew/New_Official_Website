<!-- 页面用途：证书真实 CRUD；禁止创建虚假证书。 -->
<script setup lang="ts">
useHead({
  title: '证书',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="证书" resource="certificates" /></template>
